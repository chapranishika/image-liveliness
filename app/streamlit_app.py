"""
app/streamlit_app.py

A warm, simple, and clean consumer-grade user interface for secure face registration and verification.
Redesigned to resemble a polished client product (like Apple Face ID or modern banking setup) with plain English,
quiet badges, dynamic face-positioning guides, continuous camera streaming, and collapsable admin configurations.
"""
import os
import sys
import streamlit as st
import cv2
import numpy as np
import sqlite3
import pandas as pd
import threading
import time
from PIL import Image
import io
import av
import random
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

# WebRTC hiccup mitigation attempt (docs/scope_decision_worksheet.md): the
# documented 20-32s silent connection drop lines up almost exactly with
# aioice's own consent-freshness watchdog (CONSENT_INTERVAL=5s *
# CONSENT_FAILURES=6 ~= 30s, see venv/Lib/site-packages/aioice/ice.py) --
# after that many consecutive failed consent checks the ICE agent closes
# the connection outright rather than tolerating a transient stall. Raising
# the failure budget means a temporary stall (the observed behavior is a
# clean stop-then-resume, not a real network failure) is more likely to be
# ridden out on the SAME connection instead of forcing a slower full
# reconnect. Not guaranteed -- if the underlying stall is a genuine
# prolonged issue rather than a borderline-tolerance one, this just delays
# how long it takes to detect a real failure. aiortc/streamlit-webrtc
# expose no public config for this (confirmed: RTCConfiguration only
# carries iceServers), so this is the only lever available short of a
# different WebRTC library. Two-line, trivially revertible if it doesn't help.
try:
    import aioice.ice as _aioice_ice
    _aioice_ice.CONSENT_FAILURES = 20  # was 6
except Exception:
    pass

# Setup paths and ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.keys import load_env_file
load_env_file()

# Enforce strict key checks in UI
missing_vars = []
if not os.environ.get("FACE_DB_ENCRYPTION_KEY"):
    missing_vars.append("FACE_DB_ENCRYPTION_KEY")
if not os.environ.get("FACE_API_KEY"):
    missing_vars.append("FACE_API_KEY")

if missing_vars:
    import streamlit as st
    st.error("### 🔴 System Configuration Error")
    st.markdown(f"Required environment variable(s) not set: **{', '.join(missing_vars)}**")
    st.markdown("""
    Please configure these variables in a local `.env` file in the project root.
    
    1. Generate a database encryption key:
       ```bash
       python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
       ```
    2. Generate an API key:
       ```bash
       python -c "import secrets; print(secrets.token_urlsafe(32))"
       ```
    
    *Do not commit your `.env` file to git history.*
    """)
    st.stop()

import src.db as db
from src.pipeline import run_quality_stage, run_liveness_stage, get_embedding
from src.face_matching import cosine_similarity
from src.quality_score import compute_quality_score, QUALITY_PROFILES
from src.quality_checks_day8_9 import check_pose, check_single_face
from src.quality_checks import is_frame_corrupted
from src.liveness_passive import check_passive_liveness
from src.liveness_active import evaluate_blink_tick, evaluate_head_turn_tick
from src.rppg import extract_green_mean_from_frame, check_rppg_liveness_from_samples

# The theoretical tick rate is ~12.5/sec (the time.sleep(0.08) in the rerun
# trigger below), but real live testing measured actual ticks landing about
# 1 second apart -- MediaPipe detection + quality scoring + Streamlit's own
# rerun overhead dominate, not the sleep. Redundant per-tick detection calls
# (fixed via get_cached_landmarks() reuse, see liveness_active.py/rppg.py)
# closed part of that gap, but the real rate still isn't a fixed constant
# worth hardcoding. A hardcoded 12.5fps assumption previously meant the
# rPPG "enough samples" threshold (fps*5 ~= 62 samples) could take 60+ real
# seconds to reach while the timeout was only 8s -- rPPG would have failed
# almost every time regardless of a genuine live face. Fixed by tracking
# real wall-clock elapsed time instead: wait at least RPPG_MIN_WINDOW_S of
# real time, then compute the actual observed fps (samples / elapsed) and
# pass THAT to check_rppg_liveness_from_samples() -- correct regardless of
# how fast ticks actually land.
ACTIVE_CHALLENGE_TIMEOUT_S = 20.0
RPPG_MIN_WINDOW_S = 5.0
RPPG_TIMEOUT_S = 20.0

# Set database path from environment
db.DB_PATH = os.environ.get("FACE_DB_PATH", os.path.join("data", "face_verification.db"))
db.init_db()

# Page setup
from app.branding_config import COMPANY_NAME, LOGO_PATH, PRIMARY_COLOR
from app.styles import get_css_styles

# Initialize theme state
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "light"

st.set_page_config(
    page_title=f"{COMPANY_NAME} Authentication",
    page_icon="👤",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown(get_css_styles(st.session_state.theme_mode), unsafe_allow_html=True)

# Generate pleasant arpeggio confirmation beep sound dynamically
import base64
import math
import struct

def get_beep_wav_b64():
    sample_rate = 8000
    frequency = 660.0 # E5 tone
    duration = 0.18
    num_samples = int(sample_rate * duration)
    
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + num_samples, b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate, sample_rate, 1, 8,
        b"data", num_samples
    )
    
    data = bytearray()
    for i in range(num_samples):
        # Arpeggiate to A5 after 0.08s
        f = 880.0 if (i > sample_rate * 0.08) else frequency
        envelope = 1.0 - (i / num_samples)
        val = int(128 + 50 * math.sin(2.0 * math.pi * f * i / sample_rate) * envelope)
        data.append(val)
        
    wav_bytes = header + bytes(data)
    return base64.b64encode(wav_bytes).decode("ascii")

BEEP_DATA_URI = f"data:audio/wav;base64,{get_beep_wav_b64()}"

# ---------------------------------------------------------
# STREAMLIT WEBRTC FRAME GRABBER
# ---------------------------------------------------------
# Define thread-safe video frame grabber to keep processing out of recv() callback
class FrameGrabber:
    def __init__(self):
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.guide_state = "neutral"
        self.guide_arrow = "none"
        self.guide_pct = 0.0

    def video_frame_callback(self, frame):
        img = frame.to_ndarray(format="bgr24")
        with self.frame_lock:
            self.latest_frame = img.copy()
            state = self.guide_state
            arrow = self.guide_arrow
            pct = self.guide_pct

        annotated = img.copy()
        height, width, _ = annotated.shape
        center_x = width // 2
        center_y = height // 2
        
        # Guide oval proportions matching standard face bounds
        axes = (int(width * 0.22), int(height * 0.36))
        center = (center_x, center_y)
        
        # Map state to BGR color
        if state == "success":
            color = (129, 185, 16)      # Green
        elif state == "warning":
            color = (11, 148, 245)      # Amber
        else:
            color = (180, 160, 140)     # Neutral Gray
            
        # Draw head oval guide
        cv2.ellipse(annotated, center, axes, 0, 0, 360, color, thickness=3, lineType=cv2.LINE_AA)
        
        # Draw neck guidelines (connecting oval bottom to shoulders)
        left_start = (int(center_x - axes[0] * 0.5), int(center_y + axes[1] * 0.82))
        left_end = (int(center_x - axes[0] * 0.9), int(center_y + axes[1] * 1.15))
        right_start = (int(center_x + axes[0] * 0.5), int(center_y + axes[1] * 0.82))
        right_end = (int(center_x + axes[0] * 0.9), int(center_y + axes[1] * 1.15))
        
        cv2.line(annotated, left_start, left_end, color, thickness=3, lineType=cv2.LINE_AA)
        cv2.line(annotated, right_start, right_end, color, thickness=3, lineType=cv2.LINE_AA)
        
        # Draw turn arrows if prompt matches
        if arrow == "left":
            start_pt = (center_x + axes[0] + 55, center_y)
            end_pt = (center_x + axes[0] + 15, center_y)
            cv2.arrowedLine(annotated, start_pt, end_pt, color, thickness=4, tipLength=0.3, lineType=cv2.LINE_AA)
        elif arrow == "right":
            start_pt = (center_x - axes[0] - 55, center_y)
            end_pt = (center_x - axes[0] - 15, center_y)
            cv2.arrowedLine(annotated, start_pt, end_pt, color, thickness=4, tipLength=0.3, lineType=cv2.LINE_AA)
            
        # Draw green progress countdown arc if counting down
        if pct > 0.0:
            rad = axes[0] + 18
            cv2.ellipse(annotated, center, (rad, rad), 0, -90, int(-90 + 360 * pct), (129, 185, 16), thickness=4, lineType=cv2.LINE_AA)

        out_frame = av.VideoFrame.from_ndarray(annotated, format="bgr24")
        return out_frame

# Initialize single global FrameGrabber to share camera across verify/enroll
if "grabber" not in st.session_state:
    st.session_state.grabber = FrameGrabber()

# Alias for compatibility with any backend references
st.session_state.grabber_verify = st.session_state.grabber
st.session_state.grabber_enroll = st.session_state.grabber

# Initialize configuration parameters
if "selected_profile" not in st.session_state:
    st.session_state.selected_profile = "balanced"

selected_profile = st.session_state.selected_profile
os.environ["QUALITY_PROFILE"] = selected_profile

# Calibrated operational matching threshold. Set to 0.40 based on frontal-only calibration
# to guarantee an extremely low False Acceptance Rate (FAR = 0.34%) for high security, 
# while maintaining user convenience (FRR = 15.24%).
matching_threshold = 0.40
target_threshold = QUALITY_PROFILES[selected_profile]["threshold"]

# ---------------------------------------------------------
# TITLE BAR
# ---------------------------------------------------------
if LOGO_PATH:
    st.image(LOGO_PATH, width=150)
else:
    st.markdown(f"""
    <div class="header-bar">
        <div class="header-logo">{COMPANY_NAME[0] if COMPANY_NAME else "S"}</div>
        <div class="header-name">{COMPANY_NAME} Authentication Console</div>
        <div style="margin-left: auto;"><span class="status-badge success">✓ Camera ready</span></div>
    </div>
    """, unsafe_allow_html=True)

# Initialize navigation session state
if "active_view" not in st.session_state:
    st.session_state.active_view = "Verify Identity"

if "show_registration" not in st.session_state:
    st.session_state.show_registration = False

# ---------------------------------------------------------
# HELPERS: GENTLE USER-FRIENDLY ERRORS
# ---------------------------------------------------------
def explain_quality_failure(failed_reason, all_results=None):
    """
    Provides plain-English, actionable troubleshooting feedback on scan rejections.
    """
    st.markdown(f"""
    <div style="margin-top: 10px; margin-bottom: 12px;">
        <span class="status-badge danger">Scan didn't work</span>
        <p style="font-size: 0.9rem; color: #DC2626; margin-top: 8px; font-weight: 500;">
            Let's adjust a few details to get a better photo:
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    if all_results and "sub_scores" in all_results:
        sub = all_results["sub_scores"]
        corrections = []

        # Check lighting
        if "brightness" in sub and sub["brightness"]["score"] < 50:
            corrections.append("💡 **Lighting**: Please move to a brighter area or turn on more lights.")

        # Distance -- score_position()'s weighted sub-score is computed only
        # from face_area_ratio (how much of the frame the face fills); it
        # never factors in x/y offset, so a low position score always means
        # "too far away," never "off-center". check_position()'s own binary
        # reason can separately flag centering, but that never drives the
        # composite score, so it can't be surfaced as a live quality cause.
        if "position" in sub and sub["position"]["score"] < 50:
            corrections.append("📏 **Distance**: Move closer to the camera.")

        # Check pose/alignment
        if "pose" in sub and sub["pose"]["score"] < 50:
            corrections.append("📐 **Alignment**: Look straight at the camera and hold still.")

        # Check visibility
        if "occlusion" in sub and sub["occlusion"]["score"] < 50:
            corrections.append("🕶️ **Visibility**: Ensure your face is not covered by masks, hats, or dark glasses.")

        # Check blur
        if "blur" in sub and sub["blur"]["score"] < 50:
            corrections.append("🔍 **Sharpness**: Hold your device steady to get a clear picture.")

        # Check contrast (brief Phase 2 Section 3 registration check)
        if "contrast" in sub and sub["contrast"]["score"] < 50:
            corrections.append("🌗 **Contrast**: Avoid strong backlighting or glare; face a light source directly.")

        # Check resolution (brief Phase 2 Section 3 registration check) --
        # distinct from position/distance: this can fail even when the face
        # is well-framed, if the source frame itself is low-resolution.
        if "resolution" in sub and sub["resolution"]["score"] < 50:
            corrections.append("📷 **Image Detail**: Move closer so your face fills more of the frame.")

        if corrections:
            for item in corrections:
                st.info(item)
        else:
            st.info("Please make sure you are looking directly at the camera in good lighting.")

# Short-form corrective messages for the live guide overlay -- shorter than
# explain_quality_failure()'s post-capture card since these render inline
# under the camera feed while the user is actively repositioning.
LIVE_QUALITY_SHORT_MESSAGES = {
    "brightness": "Move to a brighter area",
    "blur": "Hold steady",
    "occlusion": "Remove anything covering your face",
    "pose": "Look straight at the camera",
    "position": "Move closer",
    "contrast": "Avoid backlighting or glare",
    "resolution": "Move closer",
}
GENERIC_QUALITY_FALLBACK_MESSAGE = "That didn't quite work — let's try again. Make sure your face is centered and fully visible."


def _live_quality_failure_reason(sub_scores):
    """
    Picks the worst-scoring (lowest) failing sub-score, using the same
    50-point threshold explain_quality_failure() uses, and returns its
    short-form corrective message for the live guide overlay.

    Note: score_position()'s weighted sub-score is computed only from
    face_area_ratio; it never factors in x/y offset, so a low position
    score always means "too far away," never "off-center" -- there is no
    separate "center your face" cause to distinguish here.
    """
    FAIL_THRESHOLD = 50
    failing = {k: v for k, v in sub_scores.items() if v.get("score", 100) < FAIL_THRESHOLD}
    if not failing:
        return GENERIC_QUALITY_FALLBACK_MESSAGE

    worst_key = min(failing, key=lambda k: failing[k]["score"])
    return LIVE_QUALITY_SHORT_MESSAGES.get(worst_key, GENERIC_QUALITY_FALLBACK_MESSAGE)


def verify_pose_and_quality(frame, profile_name, check_liveness=False):
    """
    Checks face presence, alignment, and quality for the single front-facing
    capture step used by both Verify Identity and Guided Enrollment.
    Translates raw technical thresholds/errors into specific, user-friendly
    live guidance instead of one generic reason.
    """
    face_check = check_single_face(frame)
    if face_check["status"] == "fail":
        return {"status": "fail", "reason": "We couldn't find a face. Make sure you are in a well-lit area and looking at the camera."}

    pose_res = check_pose(frame)
    if pose_res["status"] == "fail":
        if profile_name != "lenient":
            return {"status": "fail", "reason": "Please look directly at the camera."}
        else:
            pose_res = {"status": "pass", "yaw": 0.0, "classification": "frontal"}

    classification = pose_res.get("classification")
    if classification != "frontal" and profile_name != "lenient":
        return {"status": "fail", "reason": "Please look straight ahead at the camera."}

    quality_res = compute_quality_score(frame, profile=profile_name)

    if quality_res["decision"] == "reject" and profile_name == "lenient":
        # Fallback for headset users: if brightness, position, and pose are good, accept it!
        sub = quality_res.get("sub_scores", {})
        brightness_val = sub.get("brightness", {}).get("score", 100) >= 50
        position_val = sub.get("position", {}).get("score", 100) >= 50
        pose_val = sub.get("pose", {}).get("score", 100) >= 50
        if brightness_val and position_val and pose_val:
            quality_res["decision"] = "accept"
            quality_res["reason"] = ""

    if quality_res["decision"] == "reject":
        reason = _live_quality_failure_reason(quality_res.get("sub_scores", {}))
        return {"status": "fail", "reason": reason}

    liveness_res = {"status": "pass", "liveness_score": 0.99}
    if check_liveness:
        # Run passive liveness check on captured frame
        liveness_res = check_passive_liveness(frame)

        if liveness_res["status"] == "fail" and profile_name == "lenient":
            liveness_res["status"] = "pass"

        if liveness_res["status"] == "fail":
            return {"status": "fail", "reason": "Biometric check failed. Please ensure you are presenting a live face."}

    return {"status": "pass", "quality_result": quality_res, "liveness_result": liveness_res}

def _friendly_verification_reason(rejected_stage, detail):
    """
    Translates pipeline.py's raw internal stage-failure detail (e.g.
    "single_face check failed: no face detected", or a raw
    "score X below Y threshold Z" string) into the same friendly, specific
    phrasing the live guide overlay uses (_live_quality_failure_reason),
    for the final verification-outcome card a user sees after a rejected
    attempt. This is a different code path from that live pre-capture
    guide -- it covers the post-capture result card, which previously
    leaked pipeline.py's raw internal string straight into the headline.
    The raw string is preserved separately in verify_boot_logs for the
    Advanced Details expander; this only changes the main headline text.
    """
    if rejected_stage == "quality":
        all_results = detail.get("all_results") or {}
        sub_scores = all_results.get("sub_scores") or {}
        if not sub_scores:
            return "We couldn't find a face. Make sure you are in a well-lit area and looking at the camera."
        return _live_quality_failure_reason(sub_scores)
    elif rejected_stage == "liveness":
        return "Biometric check failed. Please present a live face."
    elif rejected_stage == "embedding":
        return "Could not map facial points cleanly. Hold still."
    elif rejected_stage == "matching":
        return "No matching biometric account found."
    return "That didn't quite work — let's try again."


def _get_sane_frame_or_retry(latest_img, max_retries=2, retry_delay=0.15):
    """
    Guards against a corrupted WebRTC frame (the documented intermittent
    connection hiccup, see docs/scope_decision_worksheet.md) reaching the
    verification pipeline. A frame arriving mid-hiccup can decode as
    macroblock-garbled but still "look like an image" -- no exception,
    just a false "no face detected" rejection on a genuinely good attempt.
    If the frame in hand is corrupted, waits briefly and grabs a fresh one
    from the live grabber instead of trusting it, up to max_retries times.
    Returns None if every attempt (the original frame plus max_retries
    fresh ones) is still corrupted.
    """
    frame = latest_img
    attempts = 0
    while frame is not None and is_frame_corrupted(frame) and attempts < max_retries:
        attempts += 1
        time.sleep(retry_delay)
        with st.session_state.grabber.frame_lock:
            if st.session_state.grabber.latest_frame is not None:
                frame = st.session_state.grabber.latest_frame.copy()
    if frame is None or is_frame_corrupted(frame):
        return None
    return frame


def run_verification_logic(latest_img, profile_name):
    latest_img = _get_sane_frame_or_retry(latest_img)
    if latest_img is None:
        # Retries exhausted -- this is a transient camera/connection
        # glitch, not a real rejection, so no verify_outcome is set (which
        # would render a hard "Verification Failed" card). The live
        # auto-capture loop naturally tries again on the next tick once
        # the connection recovers; the flash/beep already queued by the
        # caller still plays, so a manual-button click doesn't look inert.
        st.warning("We had trouble getting a clear frame from your camera. Please try again in a moment.")
        time.sleep(1.5)
        return

    st.session_state.verify_image = latest_img.copy()
    os.makedirs("scratch", exist_ok=True)
    cv2.imwrite("scratch/captured_verify_frame.jpg", latest_img)

    # 1. Fetch templates from DB and group by user (name and user_id)
    try:
        conn = sqlite3.connect(db.DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            SELECT t.user_id, u.name, t.angle_type, t.embedding
            FROM templates t
            JOIN users u ON t.user_id = u.user_id
            WHERE u.deleted_at IS NULL
        """)
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        st.session_state.verify_outcome = {
            "status": "fail",
            "stage": "matching",
            "reason": f"Database error: {str(e)}"
        }
        return

    if not rows:
        st.session_state.verify_outcome = {
            "status": "fail",
            "stage": "matching",
            "reason": "No registered accounts found."
        }
        st.session_state.verify_boot_logs = "No registered users in DB."
        return

    # Group templates by (user_id, name)
    grouped_templates = {}
    for user_id, name, angle_type, blob in rows:
        user_key = (user_id, name)
        if user_key not in grouped_templates:
            grouped_templates[user_key] = {}
        grouped_templates[user_key][angle_type] = db._blob_to_embedding(blob)

    # 2. Call the unified pipeline verify function
    from src.pipeline import verify
    verify_res = verify(
        latest_img,
        grouped_templates,
        run_active_challenge=False,
        match_threshold=matching_threshold,
        profile=profile_name
    )
    if verify_res["verified"]:
        best_user_id, best_match_name = verify_res["matched_user"]
        match_detail = verify_res["match_result"]
        best_score = match_detail["best_score"]
        best_angle = match_detail["best_match_angle"]
        qual_detail = verify_res["detail"]["quality_detail"]
        liveness_detail = verify_res["detail"]["liveness_detail"]
        
        # Log to DB
        db.log_verification(best_user_id, qual_detail, liveness_detail, best_score, "accept")
        
        st.session_state.verify_face_detected = True
        st.session_state.verify_outcome = {
            "status": "pass",
            "name": best_match_name,
            "score": best_score,
            "angle": best_angle,
            "quality_score": qual_detail["all_results"]["overall_score"],
            "liveness_score": liveness_detail.get("passive_result", {}).get("liveness_score", 0.99)
        }
        st.session_state.verify_boot_logs = f"Matched user {best_match_name} (Similarity: {best_score:.4f})"
    else:
        st.session_state.verify_face_detected = False
        rejected_stage = verify_res["rejected_at_stage"]
        
        if rejected_stage == "quality":
            qual_detail = verify_res["detail"]
            st.session_state.verify_outcome = {
                "status": "fail",
                "stage": "quality",
                "reason": _friendly_verification_reason("quality", qual_detail),
                "all_results": qual_detail.get("all_results")
            }
            st.session_state.verify_boot_logs = f"Quality check failed: {qual_detail['reason']}"
        elif rejected_stage == "liveness":
            liveness_detail = verify_res["detail"]
            st.session_state.verify_outcome = {
                "status": "fail",
                "stage": "liveness",
                "reason": _friendly_verification_reason("liveness", liveness_detail)
            }
            st.session_state.verify_boot_logs = "Liveness check failed."
        elif rejected_stage == "embedding":
            emb_detail = verify_res["detail"]
            st.session_state.verify_outcome = {
                "status": "fail",
                "stage": "embedding",
                "reason": _friendly_verification_reason("embedding", emb_detail)
            }
            st.session_state.verify_boot_logs = f"Embedding error: {emb_detail.get('reason') if isinstance(emb_detail, dict) else str(emb_detail)}"
        else:  # matching failure
            match_detail = verify_res["match_result"]
            best_score = match_detail.get("best_score", 0.0) if match_detail else 0.0
            best_match_name = None
            if verify_res.get("matched_user"):
                _, best_match_name = verify_res["matched_user"]

            # Log reject
            db.log_verification(None, verify_res["detail"]["quality_detail"], verify_res["detail"]["liveness_detail"], best_score, "reject")

            st.session_state.verify_outcome = {
                "status": "fail",
                "stage": "matching",
                "reason": _friendly_verification_reason("matching", match_detail),
                "score": best_score,
                "best_match": best_match_name
            }
            st.session_state.verify_boot_logs = f"Failed match. Best: {best_match_name} (Score: {best_score:.4f})"

# ---------------------------------------------------------
# SPLIT PAGE ARCHITECTURE: PERSISTENT CAMERA + TAB ACTIONS
# ---------------------------------------------------------
col_cam, col_actions = st.columns([1.1, 0.9])

# ---------------------------------------------------------
# CAMERA CARD -- scoped to an st.fragment so the ~12.5/sec polling tick
# only reruns/re-renders this card, not the entire page (header, sidebar,
# admin panels, etc). Perf investigation (scratch/perf_loop_log.txt) showed
# the real per-tick cost was dominated by Streamlit's full-script rerun,
# not by verify_pose_and_quality() itself (which measured 0-8ms). The 4
# "something happened" st.rerun() calls below (capture success / step
# advance) deliberately stay plain st.rerun() (full-app scope, the
# default) so col_actions still picks up the new state and shows the
# result -- only the routine "still polling, nothing changed" trigger at
# the bottom is scoped to the fragment.
# ---------------------------------------------------------
@st.fragment
def render_camera_card():
    st.markdown('<div class="consumer-title">Camera Feed</div>', unsafe_allow_html=True)
    st.markdown('<div class="consumer-sub">Align your face inside the dashed area below.</div>', unsafe_allow_html=True)

    ctx = webrtc_streamer(
        key="shared_webrtc_camera",
        mode=WebRtcMode.SENDRECV,
        video_frame_callback=st.session_state.grabber.video_frame_callback,
        media_stream_constraints={
            "video": {
                "width": {"ideal": 640},
                "height": {"ideal": 360},
                "aspectRatio": 1.7777777778
            },
            "audio": False
        },
        # Browser and Streamlit server are the same machine -- no NAT
        # traversal is ever needed, so skip STUN entirely rather than
        # letting aiortc fall back to its default public STUN server
        # (which can stall/retry on a restricted or slow network).
        rtc_configuration=RTCConfiguration({"iceServers": []}),
        async_processing=True
    )
    # Mirrored into session_state so code outside this fragment (the
    # col_actions column, and the second latest_img fetch just below the
    # fragment call) can read camera state without needing `ctx` itself,
    # which is now local to this fragment function.
    st.session_state.cam_playing = ctx.state.playing

    # Determine target state for dynamic guide styling
    instructions_text = "Align your face with the guide"
    overlay_class = ""
    guide_arrow_val = "none"

    # Determine active profile settings
    active_prof = st.session_state.get("selected_profile", "balanced")

    # Check success-flash status
    is_flashing = False
    if "flash_end_time" in st.session_state and st.session_state.flash_end_time is not None:
        if time.time() < st.session_state.flash_end_time:
            is_flashing = True
            overlay_class = "success"
            instructions_text = "Captured!"
        else:
            st.session_state.flash_end_time = None

    # Grab current frame from grabber thread safely
    latest_img = None
    if ctx.state.playing and not is_flashing:
        with st.session_state.grabber.frame_lock:
            if st.session_state.grabber.latest_frame is not None:
                latest_img = st.session_state.grabber.latest_frame.copy()

    # Determine check mode loop conditions
    would_poll_if_not_flashing = False
    if ctx.state.playing:
        if st.session_state.active_view == "Guided Enrollment":
            if st.session_state.get("enroll_step", 1) < 2:
                would_poll_if_not_flashing = True
        elif st.session_state.active_view == "Verify Identity":
            outcome = st.session_state.get("verify_outcome")
            if not outcome or outcome.get("status") != "pass":
                would_poll_if_not_flashing = True

    run_realtime_loop = would_poll_if_not_flashing and not is_flashing
    # Keep the auto-rerun trigger alive through a flash too -- otherwise
    # nothing ever re-checks whether flash_end_time has passed, and a
    # multi-step flow (Guided Enrollment) freezes on "Captured!" forever
    # after any step but the last, since nothing else schedules a rerun.
    keep_polling_alive = run_realtime_loop or (would_poll_if_not_flashing and is_flashing)

    if run_realtime_loop and latest_img is not None:
        verify_res = verify_pose_and_quality(latest_img, active_prof, check_liveness=False)

        if os.environ.get("DEBUG_CHALLENGE"):
            with open("scratch/debug_challenge.log", "a") as _f:
                _f.write(
                    f"{time.time():.3f} view={st.session_state.active_view} "
                    f"quality_status={verify_res['status']} quality_reason={verify_res.get('reason','')!r} "
                    f"countdown_start={st.session_state.get('countdown_start')} "
                    f"challenge_type={st.session_state.get('active_challenge_type')} "
                    f"challenge_passed={st.session_state.get('active_challenge_passed')} "
                    f"rppg_samples={len(st.session_state.get('rppg_samples') or [])} "
                    f"verify_outcome={st.session_state.get('verify_outcome')}\n"
                )

        # A live camera feed naturally flickers -- a single momentary blur
        # or yaw blip can make one frame in an otherwise-good hold report
        # "fail". Without tolerance, that one frame wipes an
        # almost-complete countdown and restarts it, which looks to the
        # user like verification simply hangs. Tolerate a couple of
        # consecutive misses before giving up on an in-progress countdown.
        FLICKER_TOLERANCE = 2
        if verify_res["status"] == "pass":
            st.session_state.countdown_fail_streak = 0
            treat_as_pass = True
        else:
            fail_streak = st.session_state.get("countdown_fail_streak", 0) + 1
            st.session_state.countdown_fail_streak = fail_streak
            treat_as_pass = (
                st.session_state.get("countdown_start") is not None
                and fail_streak <= FLICKER_TOLERANCE
            )

        if treat_as_pass:
            overlay_class = "success"
            if "countdown_start" not in st.session_state or st.session_state.countdown_start is None:
                st.session_state.countdown_start = time.time()

            elapsed = time.time() - st.session_state.countdown_start
            instructions_text = f"Hold still... {max(0.0, 1.5 - elapsed):.1f}s"

            if elapsed >= 1.5:
                # ---------------------------------------------------------
                # ACTIVE LIVENESS CHALLENGE (Layer 2) -- runs after the
                # quality hold, before the actual capture, in both flows.
                # State lives in session_state (shared across fragment
                # reruns, same pattern as countdown_start above), fed one
                # already-fetched WebRTC frame per tick via
                # evaluate_blink_tick()/evaluate_head_turn_tick()
                # (src/liveness_active.py) instead of the blocking
                # cv2.VideoCapture challenge functions, which can't read
                # from this app's browser-based camera feed at all.
                # ---------------------------------------------------------
                phase_active = (
                    st.session_state.get("active_challenge_type") is not None
                    or st.session_state.get("active_challenge_passed", False)
                )
                if not phase_active:
                    st.session_state.active_challenge_type = random.choice(["blink", "turn_left", "turn_right"])
                    st.session_state.active_challenge_history = [] if st.session_state.active_challenge_type == "blink" else 0
                    st.session_state.active_challenge_start = time.time()
                    st.session_state.active_challenge_passed = False
                    # Verify Identity also starts collecting an rPPG (Layer
                    # 3) sample buffer from this same moment, running
                    # concurrently rather than as a separate wait -- by the
                    # time the active challenge resolves, the buffer often
                    # already has enough samples.
                    if st.session_state.active_view == "Verify Identity":
                        st.session_state.rppg_samples = []
                        st.session_state.rppg_collect_start = time.time()

                def _fail_active_challenge(reason, stage="active_liveness", technical_reason=None):
                    st.session_state.countdown_start = None
                    st.session_state.active_challenge_type = None
                    st.session_state.active_challenge_history = None
                    st.session_state.active_challenge_passed = False
                    st.session_state.rppg_samples = None
                    st.session_state.rppg_collect_start = None
                    st.session_state.flash_end_time = None
                    if st.session_state.active_view == "Verify Identity":
                        # Route through the same persistent verify_outcome
                        # card (col_actions) and Advanced Details expander
                        # every other verification failure uses, instead of
                        # a transient st.error() that just flashes inside
                        # the camera card and vanishes on the next tick --
                        # this stage is specific (not the generic passive-
                        # liveness message) so it's distinguishable from a
                        # quality/matching failure.
                        st.session_state.verify_outcome = {
                            "status": "fail",
                            "stage": stage,
                            "reason": reason,
                        }
                        st.session_state.verify_boot_logs = technical_reason or reason
                        st.session_state.flash_end_time = time.time() + 0.6
                        # col_actions (the outcome card) renders outside this
                        # fragment, so it won't pick up the new verify_outcome
                        # on a fragment-scoped tick -- a full rerun is needed
                        # for the card to actually appear promptly, same as
                        # every other path that sets verify_outcome already
                        # does.
                        st.rerun()
                    else:
                        st.error(reason)
                        time.sleep(1.5)

                # Verify Identity collects rPPG samples on every tick through
                # this whole phase, whether the blink/turn challenge itself
                # has resolved yet or not -- it just needs a continuous
                # stream of frames, not any particular user action.
                if st.session_state.active_view == "Verify Identity":
                    green_mean = extract_green_mean_from_frame(latest_img)
                    if green_mean is not None:
                        st.session_state.rppg_samples.append(green_mean)

                if not st.session_state.active_challenge_passed:
                    challenge_type = st.session_state.active_challenge_type
                    challenge_elapsed = time.time() - st.session_state.active_challenge_start

                    if challenge_type == "blink":
                        new_hist, challenge_status = evaluate_blink_tick(latest_img, st.session_state.active_challenge_history)
                        instructions_text = "Please blink twice"
                    else:
                        direction = "left" if challenge_type == "turn_left" else "right"
                        new_hist, challenge_status = evaluate_head_turn_tick(latest_img, st.session_state.active_challenge_history, direction)
                        instructions_text = f"Please turn your head {direction}"
                        guide_arrow_val = direction
                    st.session_state.active_challenge_history = new_hist

                    if os.environ.get("DEBUG_CHALLENGE"):
                        with open("scratch/debug_challenge.log", "a") as _f:
                            _f.write(f"{time.time():.3f} view={st.session_state.active_view} type={challenge_type} elapsed={challenge_elapsed:.2f} status={challenge_status} hist={new_hist}\n")

                    if challenge_status == "pass":
                        st.session_state.active_challenge_passed = True
                        st.session_state.active_challenge_type = None
                        st.session_state.active_challenge_history = None
                        if os.environ.get("DEBUG_CHALLENGE"):
                            with open("scratch/debug_challenge.log", "a") as _f:
                                _f.write(f"{time.time():.3f} *** CHALLENGE PASSED ***\n")
                    elif challenge_elapsed >= ACTIVE_CHALLENGE_TIMEOUT_S:
                        if os.environ.get("DEBUG_CHALLENGE"):
                            with open("scratch/debug_challenge.log", "a") as _f:
                                _f.write(f"{time.time():.3f} *** CHALLENGE TIMED OUT ***\n")
                        _fail_active_challenge(
                            "We couldn't detect the requested motion in time. Please try again and follow the on-screen prompt.",
                            stage="active_liveness",
                            technical_reason=f"active_liveness check failed: '{challenge_type}' challenge timed out after {ACTIVE_CHALLENGE_TIMEOUT_S:.0f}s with no detected {challenge_type}",
                        )
                    # else: still pending -- keep polling, prompt text above already reflects it

                if st.session_state.active_challenge_passed:
                    # Active challenge passed. Verify Identity additionally
                    # gates on rPPG (Layer 3); Guided Enrollment proceeds
                    # straight to its existing capture step.
                    if st.session_state.active_view == "Verify Identity":
                        samples = st.session_state.rppg_samples
                        rppg_elapsed = time.time() - st.session_state.rppg_collect_start
                        # Real observed sampling rate, not an assumed
                        # constant -- see RPPG_MIN_WINDOW_S comment above.
                        real_fps = len(samples) / rppg_elapsed if rppg_elapsed > 0 else 0.0
                        if rppg_elapsed >= RPPG_MIN_WINDOW_S and real_fps > 0:
                            rppg_res = check_rppg_liveness_from_samples(samples, fps_estimate=real_fps)
                            if os.environ.get("DEBUG_CHALLENGE"):
                                with open("scratch/debug_challenge.log", "a") as _f:
                                    _f.write(f"{time.time():.3f} *** RPPG EVALUATED *** samples={len(samples)} elapsed={rppg_elapsed:.2f} real_fps={real_fps:.2f} result={rppg_res}\n")
                            st.session_state.rppg_samples = None
                            st.session_state.rppg_collect_start = None
                            if rppg_res["status"] != "pass":
                                _fail_active_challenge(
                                    "Biometric check failed. Please ensure you are presenting a live face.",
                                    stage="active_liveness",
                                    technical_reason=f"rppg check failed: {rppg_res.get('reason', 'no clear pulse signal')}",
                                )
                            else:
                                st.session_state.countdown_start = None
                                st.session_state.active_challenge_passed = False
                                st.session_state.flash_end_time = time.time() + 0.6
                                st.session_state.play_sound_trigger = True
                                try:
                                    run_verification_logic(latest_img, active_prof)
                                except Exception as e:
                                    import traceback
                                    traceback.print_exc()
                                    st.session_state.verify_outcome = {
                                        "status": "fail",
                                        "stage": "internal_error",
                                        "reason": str(e),
                                    }
                                if os.environ.get("DEBUG_CHALLENGE"):
                                    with open("scratch/debug_challenge.log", "a") as _f:
                                        _f.write(f"{time.time():.3f} *** run_verification_logic DONE *** verify_outcome={st.session_state.get('verify_outcome')}\n")
                                st.rerun()
                        elif rppg_elapsed >= RPPG_TIMEOUT_S:
                            _fail_active_challenge(
                                "Biometric check failed. Please ensure you are presenting a live face.",
                                stage="active_liveness",
                                technical_reason=f"rppg check failed: only {len(samples)} samples collected in {rppg_elapsed:.1f}s (needed >= {RPPG_MIN_WINDOW_S:.0f}s of real capture time)",
                            )
                        else:
                            instructions_text = "Almost there, hold still a moment longer..."
                    else:
                        # Run strict liveness & quality verification at capture execution moment
                        check_res = verify_pose_and_quality(latest_img, active_prof, check_liveness=True)
                        if check_res["status"] == "fail":
                            st.session_state.countdown_start = None
                            st.session_state.active_challenge_passed = False
                            st.session_state.flash_end_time = None
                            st.error(check_res["reason"])
                            time.sleep(1.5)
                        else:
                            st.session_state.countdown_start = None
                            st.session_state.active_challenge_passed = False
                            st.session_state.flash_end_time = time.time() + 0.6
                            st.session_state.play_sound_trigger = True
                            st.session_state.enroll_front = latest_img.copy()
                            st.session_state.enroll_step = 2
                            st.rerun()
        else:
            st.session_state.countdown_start = None
            st.session_state.countdown_fail_streak = 0
            st.session_state.active_challenge_type = None
            st.session_state.active_challenge_history = None
            st.session_state.active_challenge_passed = False
            st.session_state.rppg_samples = None
            st.session_state.rppg_collect_start = None
            reason = verify_res.get("reason", "")
            if "couldn't find a face" in reason.lower() or "we couldn't find a face" in reason.lower():
                overlay_class = ""
                instructions_text = "Align your face with the guide"
            else:
                overlay_class = "warning"
                instructions_text = reason

    # Update thread-safe grabber drawing parameters
    with st.session_state.grabber.frame_lock:
        st.session_state.grabber.guide_state = "success" if overlay_class == "success" else ("warning" if overlay_class == "warning" else "neutral")

        st.session_state.grabber.guide_arrow = guide_arrow_val

        pct_val = 0.0
        if overlay_class == "success" and not is_flashing:
            if "countdown_start" in st.session_state and st.session_state.countdown_start is not None:
                elapsed = time.time() - st.session_state.countdown_start
                pct_val = min(1.0, elapsed / 1.5)
        st.session_state.grabber.guide_pct = pct_val

    # Play quiet success beep if triggered
    if st.session_state.get("play_sound_trigger", False):
        st.session_state.play_sound_trigger = False
        st.markdown(f'<audio autoplay src="{BEEP_DATA_URI}" style="display:none;"></audio>', unsafe_allow_html=True)

    # Render instructions text with soft slide/fade transition container
    status_text = instructions_text if ctx.state.playing else "Camera offline. Please click the start button above to activate the scanner."
    st.markdown(f"""
    <div class="guidance-text-container" style="text-align: center; margin-top: 12px; font-size: 0.85rem; color: #64748B; font-weight: 500;">
        {status_text}
    </div>
    """, unsafe_allow_html=True)

    # 3. Quiet manual fallback capture button below camera stream
    if ctx.state.playing and not is_flashing:
        if st.button("Having trouble? Tap to capture manually", key="manual_fallback_capture_btn"):
            if latest_img is not None:
                if st.session_state.active_view == "Verify Identity":
                    st.session_state.play_sound_trigger = True
                    st.session_state.flash_end_time = time.time() + 0.6
                    run_verification_logic(latest_img, active_prof)
                    st.rerun()
                else:
                    check_res = verify_pose_and_quality(latest_img, active_prof, check_liveness=True)
                    if check_res["status"] == "fail":
                        st.error(check_res["reason"])
                    else:
                        st.session_state.play_sound_trigger = True
                        st.session_state.flash_end_time = time.time() + 0.6
                        st.session_state.enroll_front = latest_img.copy()
                        st.session_state.enroll_step = 2
                        st.rerun()
            else:
                st.error("Please wait until the camera feed is ready.")

    # ---------------------------------------------------------
    # ACTIVE RERUN TRIGGER LOOP -- scope="fragment" is the whole point of
    # this refactor: this fires ~12.5x/sec while polling, and previously
    # each tick re-executed and re-rendered the entire page. Now it only
    # re-executes this fragment.
    #
    # Pre-existing bug found via real testing (not introduced by the active
    # liveness/rPPG work, just never triggered by earlier synthetic-video
    # tests, which never got past the active-challenge gate): Streamlit
    # raises StreamlitAPIException if scope="fragment" is called while the
    # CURRENT execution is itself a full-script rerun rather than a
    # fragment rerun -- which happens here whenever a plain st.rerun() ran
    # just before this (e.g. after run_verification_logic() on a failed
    # verification, needed so col_actions outside the fragment updates),
    # and this same tick's fragment execution reaches this line again with
    # polling still wanting to continue. Falling back to a plain st.rerun()
    # in that case keeps polling alive either way -- confirmed necessary
    # via a real crash during live testing, not theoretical.
    # ---------------------------------------------------------
    if ctx.state.playing and keep_polling_alive:
        time.sleep(0.08)  # ~12.5 checks/second
        try:
            st.rerun(scope="fragment")
        except st.errors.StreamlitAPIException:
            st.rerun()


with col_cam:
    with st.container(border=True):
        render_camera_card()

# Fetch latest_img reference for compatibility with actions column blocks.
# Uses the session_state mirror set inside the fragment above, since `ctx`
# itself is local to that fragment function.
latest_img = None
if st.session_state.get("cam_playing", False):
    with st.session_state.grabber.frame_lock:
        if st.session_state.grabber.latest_frame is not None:
            latest_img = st.session_state.grabber.latest_frame.copy()
with col_actions:
    with st.container(border=True):
        # Custom high-end segmented tab selection with theme mode toggle side-by-side
        col_tab_item, col_theme_item = st.columns([0.65, 0.35])
        with col_tab_item:
            nav_options = ["Verify Identity", "Guided Enrollment"]
            selected_view = st.radio(
                "Navigation",
                options=nav_options,
                index=nav_options.index(st.session_state.active_view),
                label_visibility="collapsed",
                key="nav_view_radio",
            )
            st.session_state.active_view = selected_view
        with col_theme_item:
            theme_options = ["☀️ Light", "🌙 Dark"]
            current_theme_idx = 0 if st.session_state.theme_mode == "light" else 1
            selected_theme = st.selectbox(
                "Theme Mode Selection",
                options=theme_options,
                index=current_theme_idx,
                label_visibility="collapsed",
                key="theme_mode_select",
            )
            new_theme_mode = "light" if "Light" in selected_theme else "dark"
            if new_theme_mode != st.session_state.theme_mode:
                st.session_state.theme_mode = new_theme_mode
                st.rerun()
    
    # ---------------------------------------------------------
    # TAB: VERIFY IDENTITY
    # ---------------------------------------------------------
    if selected_view == "Verify Identity":
        st.markdown('<div class="consumer-title">Welcome</div>', unsafe_allow_html=True)
        st.markdown('<div class="consumer-sub">Scan your face to quickly verify your identity.</div>', unsafe_allow_html=True)
        
        # Beautiful informative auto-capture verification card element
        if "verify_outcome" not in st.session_state:
            st.markdown("""
            <div style="background: #EFF6FF; border-left: 4px solid #3B82F6; padding: 12px 16px; border-radius: 8px; font-size: 0.85rem; color: #1E40AF; margin-bottom:1.5rem; font-weight: 500; line-height: 1.4;">
                ℹ️ Look at the camera. The system will scan and verify your identity automatically once aligned.
            </div>
            """, unsafe_allow_html=True)
            
            # Simple button to manually trigger verification immediately if needed
            if st.button("Verify Manually", key="verify_action_btn"):
                if latest_img is None:
                    st.error("Please turn on the camera first.")
                else:
                    st.session_state.play_sound_trigger = True
                    st.session_state.flash_end_time = time.time() + 0.6
                    run_verification_logic(latest_img, selected_profile)
                    st.rerun()
        
        # Verification Outcome Presentation
        if "verify_outcome" in st.session_state:
            st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
            outcome = st.session_state.verify_outcome
            
            # Show verified photo thumbnail
            if "verify_image" in st.session_state and st.session_state.verify_image is not None:
                rgb_v = cv2.cvtColor(st.session_state.verify_image, cv2.COLOR_BGR2RGB)
                st.image(rgb_v, width=120)
                st.markdown("<div style='font-size:0.8rem; color:#64748B; margin-top:4px;'>Captured photo</div>", unsafe_allow_html=True)
                
            if outcome["status"] == "pass":
                st.markdown(f"""
                <div class="success-screen-card">
                    <div class="success-checkmark-circle">
                        <svg class="checkmark-svg" viewBox="0 0 52 52">
                            <circle class="checkmark-circle-path" cx="26" cy="26" r="25" fill="none"/>
                            <path class="checkmark-check-path" fill="none" d="M14.1 27.2 l7.1 7.2 16.7-16.8"/>
                        </svg>
                    </div>
                    <div class="success-screen-title">You're Verified!</div>
                    <div class="success-screen-sub">Welcome back, {outcome['name']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Add a reset button to allow re-verifying
                if st.button("Verify Again", key="reset_verify_outcome_btn"):
                    st.session_state.pop("verify_outcome", None)
                    st.session_state.pop("verify_image", None)
                    st.rerun()
            else:
                st.markdown(f"""
                <div style="margin-top:15px; margin-bottom: 10px;">
                    <span class="status-badge danger">✗ Verification Failed</span>
                </div>
                <div style="font-size:0.95rem; font-weight:500; color:#DC2626;">
                    {outcome['reason']}
                </div>
                """, unsafe_allow_html=True)
                
                # Check for troubleshooting
                if outcome["stage"] == "quality":
                    explain_quality_failure(outcome["reason"], outcome.get("all_results"))
                elif outcome["stage"] == "matching":
                    st.markdown("""
                    <div style="background: #FFFBEB; border-left: 4px solid #D97706; padding: 12px 16px; border-radius: 4px; margin-top: 15px; font-size: 0.85rem; color: #92400E;">
                        ⚠️ <strong>First time here?</strong> We couldn't find a matching biometric profile. If you have not registered your face yet, switch to the <strong>Guided Enrollment</strong> panel to create your account.
                    </div>
                    """, unsafe_allow_html=True)
                    
            # Advanced Tech Details collapsable expander
            with st.expander("🔬 Advanced details (Technical review)", expanded=False):
                st.write(f"Pipeline Stage: {outcome.get('stage', 'complete').upper()}")
                st.write(f"Quality Score: {outcome.get('quality_score', 'N/A')}% (Threshold: {target_threshold}%)")
                st.write(f"Liveness Confidence: {outcome.get('liveness_score', 'N/A')}")
                st.write(f"Match Similarity: {outcome.get('score', 'N/A')}")
                st.write(f"Match Angle: {outcome.get('angle', 'N/A')}")
                if "verify_boot_logs" in st.session_state:
                    st.code(st.session_state.verify_boot_logs)
        else:
            st.markdown("""
            <div class="clean-empty-state">
                <div class="clean-empty-text">Awaiting scan. Position your face in the guide — verification starts automatically.</div>
            </div>
            """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # TAB: GUIDED ENROLLMENT
    # ---------------------------------------------------------
    else:
        st.markdown('<div class="consumer-title">Register Biometrics</div>', unsafe_allow_html=True)
        st.markdown('<div class="consumer-sub">Look directly at the camera to capture your biometric profile.</div>', unsafe_allow_html=True)

        # Step state: 1 = capturing, 2 = captured, ready to register.
        # Enrollment stores only the front-facing template -- duplicate_check.py
        # already only ever compares front templates by design, and for a
        # frontal live query, best-of-three matching resolves via the front
        # template almost every time (frontal-frontal EER 3.19% vs cross-angle
        # EER 27.06%, see data/Evaluation_Report.md Sections 3-4), so left/right
        # templates were not meaningfully contributing to verification accuracy.
        if "enroll_step" not in st.session_state:
            st.session_state.enroll_step = 1
            st.session_state.enroll_front = None

        step = st.session_state.enroll_step

        reg_name = st.text_input("Full Name", key="enroll_name", placeholder="Enter your full name")
        consent = st.checkbox("I agree to store my encrypted facial signature for security logins.", key="enroll_consent")

        if step == 1:
            st.info("Align your face inside the outline to capture automatically.")
        else:
            st.markdown("<div style='background: #ECFDF5; border-left:4px solid #10B981; padding: 12px 16px; border-radius: 4px; margin-bottom:15px; font-size:0.85rem; color:#065F46;'>✓ Photo captured successfully. Click register below to complete.</div>", unsafe_allow_html=True)
            col_btns = st.columns(2)
            with col_btns[0]:
                if st.button("Retake Photo", key="reset_enroll_btn"):
                    st.session_state.enroll_step = 1
                    st.session_state.enroll_front = None
                    st.rerun()
            with col_btns[1]:
                if st.button("Register Face ID", key="save_enroll_btn"):
                    if not reg_name:
                        st.error("Please fill in your name.")
                    elif not consent:
                        st.error("You must agree to the storage consent checkbox.")
                    else:
                        with st.spinner("Encrypting secure biometric templates..."):
                            try:
                                emb_front = get_embedding(st.session_state.enroll_front)

                                if emb_front["status"] != "success":
                                    st.error("Frontal capture could not map landmarks.")
                                else:
                                    # Run duplicate check
                                    from src.duplicate_check import check_for_duplicate
                                    dup_res = check_for_duplicate(emb_front["embedding"])
                                    if dup_res["is_duplicate"]:
                                        st.error(f"Registration rejected: Face already registered as '{dup_res['matched_name']}' (User ID: {dup_res['matched_user_id']}) at similarity score {dup_res['score']:.4f}.")
                                    else:
                                        user_id = db.insert_user(reg_name, consent_given=consent, actor="consumer_ui")
                                        db.insert_template(user_id, "front", emb_front["embedding"])

                                        st.success(f"Successfully registered your profile, {reg_name}!")
                                        st.balloons()

                                        st.session_state.enroll_step = 1
                                        st.session_state.enroll_front = None
                                        st.rerun()
                            except Exception as e:
                                st.error(f"Save failed: {str(e)}")

        # Captured photo preview
        st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.9rem; font-weight:600; color:#0F172A; margin-bottom:12px;'>Your captured photo</div>", unsafe_allow_html=True)
        if st.session_state.enroll_front is not None:
            rgb_f = cv2.cvtColor(st.session_state.enroll_front, cv2.COLOR_BGR2RGB)
            st.image(rgb_f, width=160)
            st.markdown("<div style='font-size:0.75rem; color:#059669; font-weight:600;'>✓ Front photo</div>", unsafe_allow_html=True)
        else:
            st.markdown('<div class="clean-empty-state" style="padding:15px 5px;"><span class="clean-empty-text" style="font-size:0.75rem;">No photo captured yet</span></div>', unsafe_allow_html=True)


# ---------------------------------------------------------
# BOTTOM EXPANDER: REGULATORY COMPLIANCE & ADMIN AUDITS
# ---------------------------------------------------------
st.markdown("<hr style='margin: 30px 0;'>", unsafe_allow_html=True)
with st.expander("🛠️ System Management & Audits (Admin/Compliance Review)", expanded=False):
    st.markdown("### GDPR & BIPA Compliance Console")
    st.write("Review consent logs, template query audits, and execute biometric deletions.")
    
    show_admin = st.checkbox("📊 Load compliance data & diagnostics", value=False)
    if show_admin:
        col_delete, col_logs = st.columns([1, 1])

        with col_delete:
            # Security Quality Level Selection for Admins
            st.markdown("#### Security Compliance Settings")
            profile_options_desc = {
                "lenient": "Lenient (Fast, low-light optimized)",
                "balanced": "Balanced (Recommended standard)",
                "strict": "Strict (High-security checks)"
            }
            
            # Get active selection index
            default_idx = ["lenient", "balanced", "strict"].index(st.session_state.selected_profile)
            
            new_profile = st.selectbox(
                "System Quality Compliance Profile",
                options=["lenient", "balanced", "strict"],
                index=default_idx,
                format_func=lambda x: profile_options_desc[x],
                key="quality_profile_select",
            )
            
            if new_profile != st.session_state.selected_profile:
                st.session_state.selected_profile = new_profile
                st.rerun()

            st.markdown("---")
            
            st.markdown("#### Biometric Template Deletion (Right to be Forgotten)")
            # Load active users
            users = []
            try:
                conn = sqlite3.connect(db.DB_PATH)
                cur = conn.cursor()
                cur.execute("SELECT user_id, name, consent_given_at, deleted_at FROM users")
                users = [{"id": r[0], "name": r[1], "consent_at": r[2], "deleted_at": r[3]} for r in cur.fetchall()]
                conn.close()
            except Exception as e:
                st.error(f"Database error: {str(e)}")

            if not users:
                st.info("No registered users found.")
            else:
                df_users = pd.DataFrame(users)
                st.dataframe(df_users, use_container_width=True)

                selected_user_id = st.selectbox(
                    "Select User for biometric deletion",
                    options=[u["id"] for u in users],
                    format_func=lambda uid: next(u["name"] for u in users if u["id"] == uid)
                )

                delete_type = st.radio("Deletion Type", options=["Soft Delete", "Hard Delete (Permanent IRREVERSIBLE purge)"])
                
                if st.button("⚠️ Execute Biometric Deletion"):
                    username = next(u["name"] for u in users if u["id"] == selected_user_id)
                    with st.spinner(f"Processing deletion request..."):
                        try:
                            is_hard = (delete_type == "Hard Delete (Permanent IRREVERSIBLE purge)")
                            db.delete_user(selected_user_id, hard_delete=is_hard, actor="streamlit_admin")
                            st.success(f"Successfully deleted user '{username}'.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Deletion failed: {str(e)}")

        with col_logs:
            st.markdown("#### Dynamic Security Audit Trail")
            st.write("Logs representing biometric template reads/writes and verification transactions.")
            
            try:
                conn = sqlite3.connect(db.DB_PATH)
                df_access = pd.read_sql_query("SELECT * FROM access_log ORDER BY timestamp DESC LIMIT 15", conn)
                df_ver = pd.read_sql_query("SELECT * FROM verification_logs ORDER BY timestamp DESC LIMIT 15", conn)
                conn.close()
                
                st.markdown("##### Template Read/Write Access Log")
                st.dataframe(df_access, use_container_width=True)
                
                st.markdown("##### Verification Transactions Log")
                st.dataframe(df_ver, use_container_width=True)
            except Exception as e:
                st.error(f"Could not load audit logs: {str(e)}")

        st.markdown("---")
        st.markdown("#### System Diagnostics & Health Status")
        if "health_check_results" not in st.session_state:
            st.session_state.health_check_results = None
            
        if st.button("Run System Diagnostics & Health Checks", key="run_diagnostics_btn"):
            from api.health import check_database, check_encryption_key, check_deepface_model_cache, check_camera_available
            with st.spinner("Evaluating system component readiness..."):
                db_res = check_database()
                enc_res = check_encryption_key()
                mod_res = check_deepface_model_cache()
                cam_res = check_camera_available()
                
                st.session_state.health_check_results = {
                    "db_ok": (db_res["status"] == "pass"),
                    "db_msg": db_res["detail"] if db_res["detail"] else "Successfully connected to SQLite database.",
                    "enc_ok": (enc_res["status"] == "pass"),
                    "enc_msg": enc_res["detail"] if enc_res["detail"] else "Biometric encryption key loaded successfully.",
                    "mod_ok": (mod_res["status"] == "pass"),
                    "mod_msg": mod_res["detail"] if mod_res["detail"] else "All required face detection models are cached.",
                    "cam_ok": (cam_res["status"] in ["pass", "warn"]),
                    "cam_msg": cam_res["detail"] if cam_res["detail"] else "OS Camera Capture device is ready."
                }
                
        if st.session_state.health_check_results is not None:
            r = st.session_state.health_check_results
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                st.markdown(f"**SQLite Database**: {'✓ PASS' if r['db_ok'] else '✗ FAIL'} ({r['db_msg']})")
                st.markdown(f"**AES-128 Encryption**: {'✓ PASS' if r['enc_ok'] else '✗ FAIL'} ({r['enc_msg']})")
            with col_h2:
                st.markdown(f"**Models Cached**: {'✓ PASS' if r['mod_ok'] else '✗ FAIL'} ({r['mod_msg']})")
                st.markdown(f"**Camera Ready**: {'✓ PASS' if r['cam_ok'] else '✗ FAIL'} ({r['cam_msg']})")

# Note: the routine polling/rerun trigger now lives inside render_camera_card()
# above, scoped to that fragment (st.rerun(scope="fragment")) so the common
# "still polling, nothing changed" tick doesn't re-render this whole page.
