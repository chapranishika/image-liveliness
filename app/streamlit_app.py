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
import threading
import time
from PIL import Image
import io
import random
import streamlit.components.v1 as components

# Camera capture uses a lightweight custom component (plain getUserMedia +
# periodic canvas capture) rather than a full WebRTC peer connection --
# simpler connection lifecycle, no ICE/STUN/TURN negotiation to manage.
# See app/frame_capture_component/index.html for the implementation.
_FRAME_CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frame_capture_component")
_frame_capture = components.declare_component("frame_capture", path=_FRAME_CAPTURE_DIR)

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
from src.quality_checks import check_screen_surface_texture
from src.liveness_passive import check_passive_liveness
from src.liveness_active import evaluate_blink_tick, evaluate_head_turn_tick, check_frame_loop_signature
from src.rppg import extract_green_mean_from_frame, check_rppg_liveness_from_samples

# Actual tick rate varies with system load rather than sitting at a fixed
# 12.5/sec, so the rPPG sample-count threshold is derived from real
# wall-clock elapsed time (samples / elapsed) instead of an assumed
# constant fps -- keeps the "enough samples" check correct regardless of
# how fast ticks land.
ACTIVE_CHALLENGE_TIMEOUT_S = 20.0
RPPG_MIN_WINDOW_S = 5.0
RPPG_TIMEOUT_S = 20.0
# A challenge timeout re-rolls a fresh gesture in place (same attempt, no
# fail screen) up to this many rounds before actually failing.
MAX_CHALLENGE_ROUNDS = 3

ACTIVE_CHALLENGE_TYPES = ["blink", "turn_left", "turn_right"]

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
        # JS-side capture timestamp (ms) of latest_frame, set alongside it
        # whenever a genuinely new frame is decoded. The frame-capture
        # component only pushes a new frame_b64 every ~700ms, but this
        # fragment can rerun far faster (up to 12.5/sec) and re-decodes the
        # same still-cached component value each of those ticks -- so
        # latest_frame gets a fresh ndarray object every tick even when the
        # underlying image hasn't changed. latest_frame_ts lets callers that
        # care about genuinely distinct samples (rPPG) detect and skip those
        # repeats instead of treating ~9 duplicate frames as 9 real samples.
        self.latest_frame_ts = None
        # guide_state/guide_arrow/guide_pct drive the overlay guide (oval,
        # turn arrows, progress ring), passed as args into the frame-capture
        # component (_frame_capture(...) call in render_camera_card()),
        # which draws it client-side as an SVG on top of the local camera
        # preview -- see app/frame_capture_component/index.html's
        # drawOverlay().
        self.guide_state = "neutral"
        self.guide_arrow = "none"
        self.guide_pct = 0.0

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
    _col_prereq, _col_before = st.columns(2)
    with _col_prereq:
        st.markdown(
            "**System prerequisites:**\n"
            "- **RAM:** at least 4 GB free\n"
            "- **CPU:** 4 logical cores recommended\n"
            "- **Camera:** any 720p-capable webcam (a built-in laptop camera is sufficient)\n"
            "- **Internet:** none required during use, everything runs locally\n"
        )
    with _col_before:
        st.markdown(
            "**Before you start:**\n"
            "- Good, even lighting (avoid strong light directly behind you)\n"
            "- Only you in frame\n"
            "- Face fully visible, no mask, hand, or hair covering it\n"
            "- Look directly at the camera\n"
            "- Any laptop or desktop with a working webcam works, no special hardware needed"
        )

# Initialize navigation session state
if "active_view" not in st.session_state:
    st.session_state.active_view = "Verify Identity"

# Live "checks passing" checklist state (camera card) -- live_checklist is
# rebuilt fresh every tick from cache-cheap checks; the other two track the
# two checks that only resolve at specific moments (motion challenge/rPPG
# mid-hold, antispoof only at the final capture instant), not every tick.
st.session_state.setdefault("live_checklist", {})
st.session_state.setdefault("antispoof_last_status", "pending")
st.session_state.setdefault("rppg_last_status", "pending")
# Separate from active_challenge_passed (which gets reset to False the
# instant a capture succeeds, so the next attempt starts clean) -- without
# this, the checklist dot flips back to "pending" on the very tick it
# should be showing "pass", since that reset and the checklist render both
# happen in the same tick right after a genuine pass. Purely a display
# concern; the reset above still gates the real capture/verify decision.
st.session_state.setdefault("motion_challenge_display_status", "pending")
# True once ctx.state.playing has been True at least once this session --
# distinguishes "camera never started" (genuine, user must click Start) from
# "camera dropped mid-session" (the documented 20-32s WebRTC/aioice hiccup,
# docs/scope_decision_worksheet.md -- self-recovers, user shouldn't be told
# to click anything). Never reset back to False once set.
st.session_state.setdefault("cam_ever_started", False)
st.session_state.setdefault("hiccup_just_reset", False)

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
    "occlusion": "Remove anything covering your face (mask, hand, hair, etc.)",
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


def verify_pose_and_quality(frame, profile_name, check_liveness=False, liveness_blocking=True):
    """
    Checks face presence, alignment, and quality for the single front-facing
    capture step used by both Verify Identity and Guided Enrollment.
    Translates raw technical thresholds/errors into specific, user-friendly
    live guidance instead of one generic reason.
    """
    face_check = check_single_face(frame)
    if face_check["status"] == "fail":
        if "faces detected" in face_check.get("reason", ""):
            return {"status": "fail", "reason": "More than one face is in view. Please make sure only you are in frame."}
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

        # Screen-surface texture check, run alongside passive liveness --
        # same signal wired into src/pipeline.py's run_liveness_stage() for
        # the Verify Identity path (see that function's comment for the
        # Phase 3 screen-replay motivation); mirrored here so Guided
        # Enrollment's own capture decision, which calls
        # check_passive_liveness() directly rather than going through
        # pipeline.py, gets the same protection instead of being a silent
        # gap. Folded into liveness_res's own status/reason (not a separate
        # dict) since this function's callers only read a single
        # liveness_result.status field, unlike pipeline.py's richer detail
        # structure.
        screen_surface_res = check_screen_surface_texture(frame)
        liveness_res["screen_surface_result"] = screen_surface_res
        if liveness_res["status"] == "fail" and profile_name == "lenient":
            liveness_res["status"] = "pass"
        # Screen-surface texture check underperforms on the available real
        # calibration data (near-zero catch rate, some false positives), so
        # it's recorded for visibility but no longer blocks on its own --
        # see src/pipeline.py's run_liveness_stage() for the calibration
        # notes.

        if liveness_res["status"] == "fail" and liveness_blocking:
            return {"status": "fail", "reason": "We couldn't confirm a live person. Please don't use a photo, video, or screen — look directly at your own camera.", "liveness_result": liveness_res}

    return {"status": "pass", "quality_result": quality_res, "liveness_result": liveness_res}


def _combined_antispoof_status(liveness_detail):
    """
    The checklist's "antispoof" row reflects BOTH passive liveness
    (MiniFASNet) and the screen-surface texture check (Phase 3) -- either
    one failing counts as a fail here, since both are independent signals
    contributing to the same disclosed antispoof checklist item rather than
    the screen-surface check silently replacing or hiding behind passive
    liveness's own result.
    """
    passive_status = liveness_detail.get("passive_result", {}).get("status", "pending")
    screen_status = liveness_detail.get("screen_surface_result", {}).get("status", "pending")
    if passive_status == "fail" or screen_status == "fail":
        return "fail"
    return passive_status


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
            # No face (or more than one) was found before quality scoring
            # even ran -- compute_quality_score() already carries a specific
            # friendly reason for that case (distinguishing "no face" from
            # "more than one face"); fall back to the generic message only
            # if that's somehow missing.
            return all_results.get("reason") or "We couldn't find a face. Make sure you are in a well-lit area and looking at the camera."
        return _live_quality_failure_reason(sub_scores)
    elif rejected_stage == "liveness":
        return "We couldn't confirm a live person. Please don't use a photo, video, or screen — look directly at your own camera."
    elif rejected_stage == "embedding":
        return "Could not map facial points cleanly. Hold still."
    elif rejected_stage == "matching":
        return "No matching biometric account found."
    return "That didn't quite work — let's try again."


def _get_sane_frame_or_retry(latest_img, max_retries=2, retry_delay=0.15):
    """
    Retries a couple times on a genuinely missing frame (frame is None)
    before giving up, since that's a real, transient case with a snapshot-
    based capture pipeline.
    """
    frame = latest_img
    attempts = 0
    while frame is None and attempts < max_retries:
        attempts += 1
        time.sleep(retry_delay)
        with st.session_state.grabber.frame_lock:
            if st.session_state.grabber.latest_frame is not None:
                frame = st.session_state.grabber.latest_frame.copy()
    return frame


def _set_action_error(msg):
    """
    Records a button-click error (camera not ready, missing name, duplicate
    face, save failed, etc.) for the single, always-in-the-same-place
    banner at the top of the Verify Identity / Guided Enrollment panel --
    caller must follow this with st.rerun() so the banner (rendered earlier
    in script order, at the top of the panel) actually picks it up on the
    fresh top-to-bottom pass, rather than only on the next unrelated rerun.
    """
    st.session_state.action_error = msg


def _clear_action_error():
    st.session_state.action_error = None


def _render_action_error_banner():
    err = st.session_state.get("action_error")
    if err:
        st.markdown(
            f'<div class="app-alert-box error">✗ {err}</div>',
            unsafe_allow_html=True,
        )


def _capture_enrollment_photo(latest_img, profile_name, liveness_blocking):
    """
    Single, self-gated entry point for finalizing a Guided Enrollment
    capture -- used by both the automatic flow and the manual fallback
    button, same structural-safety-net reasoning as run_verification_logic()
    above: requires active_challenge_passed internally rather than trusting
    every caller to have checked first.

    Returns the same shape verify_pose_and_quality() does (a "pending"/
    "fail" dict, or the pass dict) so existing call-site status handling
    doesn't need to change -- a blocked gate is reported as "fail" with an
    actionable reason, not a new status value callers would need to learn.
    """
    if not st.session_state.get("active_challenge_passed", False):
        return {"status": "fail", "reason": "Please complete the blink or head-turn prompt above before capturing."}
    check_res = verify_pose_and_quality(latest_img, profile_name, check_liveness=True, liveness_blocking=liveness_blocking)
    st.session_state.antispoof_last_status = check_res.get("liveness_result", {}).get("status", "pending")
    return check_res


def run_verification_logic(latest_img, profile_name):
    # Structural safety net (Breach 1B): every current caller already
    # checks active_challenge_passed before calling this, but that relies
    # on each caller remembering to -- exactly the pattern that let two
    # buttons bypass the active-liveness challenge earlier in this
    # project. Checking it again here, inside the one function that can
    # actually trigger a verification decision, means a bypass of this
    # specific kind cannot happen again even from a future caller that
    # forgets to check first.
    if not st.session_state.get("active_challenge_passed", False):
        st.session_state.verify_face_detected = False
        st.session_state.verify_outcome = {
            "status": "fail",
            "stage": "active_liveness",
            "reason": "Please complete the blink or head-turn prompt above before verifying.",
        }
        return

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
        st.session_state.antispoof_last_status = _combined_antispoof_status(liveness_detail)

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
            st.session_state.antispoof_last_status = _combined_antispoof_status(liveness_detail)
            st.session_state.verify_outcome = {
                "status": "fail",
                "stage": "liveness",
                "reason": _friendly_verification_reason("liveness", liveness_detail)
            }
            st.session_state.verify_boot_logs = "Liveness check failed."
        elif rejected_stage == "embedding":
            emb_detail = verify_res["detail"]
            # Liveness already passed to reach this stage, so the nested
            # shape matches the success-path case (detail.liveness_detail),
            # not the rejected_stage=="liveness" case above.
            st.session_state.antispoof_last_status = _combined_antispoof_status(verify_res["detail"].get("liveness_detail", {}))
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

            # Liveness already passed to reach the matching stage, same
            # nested shape as the success/embedding cases above.
            st.session_state.antispoof_last_status = _combined_antispoof_status(verify_res["detail"].get("liveness_detail", {}))

            st.session_state.verify_outcome = {
                "status": "fail",
                "stage": "matching",
                "reason": _friendly_verification_reason("matching", match_detail),
                "score": best_score,
                "best_match": best_match_name
            }
            st.session_state.verify_boot_logs = f"Failed match. Best: {best_match_name} (Score: {best_score:.4f})"


def _safe_polling_rerun():
    """
    Swallows StreamlitAPIException when scope="fragment" is invalid for the
    current execution context. That happens when a full-script rerun is
    already in progress for a reason outside this fragment (a widget click
    in col_actions, a verification result, etc.) -- the right move is to
    let that run finish normally rather than chain another rerun, since
    col_actions is defined later in the script than this fragment and a
    chained rerun would starve it of ever completing. Polling resumes on
    the frame-capture component's own next value-change tick regardless.
    """
    try:
        st.rerun(scope="fragment")
    except st.errors.StreamlitAPIException:
        pass


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
    if os.environ.get("DEBUG_PERF"):
        _perf_tick_start = time.time()
        _perf_prev_start = st.session_state.get("_debug_perf_last_tick_start")
        _delta_str = f"{(_perf_tick_start - _perf_prev_start) * 1000:.1f}" if _perf_prev_start is not None else ""
        with open("scratch/perf_loop_log.txt", "a") as _f:
            _f.write(f"{_perf_tick_start:.6f} iter_delta_ms={_delta_str}\n")
        st.session_state._debug_perf_last_tick_start = _perf_tick_start

    st.markdown('<div class="consumer-title">Camera Feed</div>', unsafe_allow_html=True)
    st.markdown('<div class="consumer-sub">Align your face inside the dashed area below.</div>', unsafe_allow_html=True)

    # "Playing" is defined as "did a fresh frame arrive recently" -- covers
    # both a never-started and a stalled frame source with one mechanism,
    # since either case shows up the same way: frame age exceeding
    # FRAME_STALE_MS.
    _component_value = _frame_capture(
        guide_state=st.session_state.grabber.guide_state,
        guide_arrow=st.session_state.grabber.guide_arrow,
        guide_pct=st.session_state.grabber.guide_pct,
        key="frame_capture",
    )

    FRAME_STALE_MS = 3000  # ~4x the component's own 700ms capture interval
    _frame_decoded_ok = False
    if isinstance(_component_value, dict) and "frame_b64" in _component_value:
        _frame_ts = _component_value.get("ts")
        _frame_age_ms = (time.time() * 1000 - _frame_ts) if _frame_ts else None
        try:
            _img_bytes = base64.b64decode(_component_value["frame_b64"])
            _arr = np.frombuffer(_img_bytes, dtype=np.uint8)
            _decoded = cv2.imdecode(_arr, cv2.IMREAD_COLOR)
        except Exception:
            _decoded = None
        if _decoded is not None:
            with st.session_state.grabber.frame_lock:
                st.session_state.grabber.latest_frame = _decoded
                st.session_state.grabber.latest_frame_ts = _frame_ts
            _frame_decoded_ok = _frame_age_ms is not None and _frame_age_ms < FRAME_STALE_MS

    class _SimpleState:
        def __init__(self, playing):
            self.playing = playing

    class _SimpleCtx:
        def __init__(self, playing):
            self.state = _SimpleState(playing)

    ctx = _SimpleCtx(_frame_decoded_ok)

    # Mirrored into session_state so code outside this fragment (the
    # col_actions column, and the second latest_img fetch just below the
    # fragment call) can read camera state without needing `ctx` itself,
    # which is now local to this fragment function.
    st.session_state.cam_playing = ctx.state.playing
    if ctx.state.playing:
        st.session_state.cam_ever_started = True
    elif st.session_state.get("active_challenge_type") is not None or st.session_state.get("rppg_collect_start") is not None:
        # The connection just dropped mid-attempt -- almost certainly the
        # documented 20-32s WebRTC/aioice consent-check hiccup (docs/
        # scope_decision_worksheet.md), which self-recovers on its own.
        # active_challenge_start and rppg_collect_start are wall-clock
        # (time.time()) based, so once ticks resume after a gap this long,
        # challenge_elapsed/rppg_elapsed would already be past
        # ACTIVE_CHALLENGE_TIMEOUT_S/RPPG_TIMEOUT_S and read as a genuine
        # liveness failure -- false, and caused by the environment, not the
        # user. Chose to reset cleanly here (option b) over tracking
        # cumulative not-playing time to subtract from elapsed (option a):
        # simpler, and more honest about what actually happened than a
        # silent time adjustment the user would never see either way.
        st.session_state.countdown_start = None
        st.session_state.active_challenge_type = None
        st.session_state.active_challenge_history = None
        st.session_state.active_challenge_passed = False
        st.session_state.active_challenge_round = None
        st.session_state.rppg_samples = None
        st.session_state.rppg_collect_start = None
        st.session_state.rppg_last_status = "pending"
        st.session_state.antispoof_last_status = "pending"
        st.session_state.flash_end_time = None
        st.session_state.hiccup_just_reset = True

    if os.environ.get("DEBUG_WEBRTC"):
        _prev_playing = st.session_state.get("_debug_webrtc_last_playing")
        if _prev_playing != ctx.state.playing:
            with open("scratch/debug_webrtc.log", "a") as _f:
                _f.write(f"{time.time():.3f} TRANSITION {_prev_playing} -> {ctx.state.playing}\n")
        else:
            with open("scratch/debug_webrtc.log", "a") as _f:
                _f.write(f"{time.time():.3f} tick playing={ctx.state.playing}\n")
        st.session_state._debug_webrtc_last_playing = ctx.state.playing

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

    # Note: the old separate "frozen frame while technically still playing"
    # detection (a mean-pixel-fingerprint check) is gone -- it's now
    # redundant. ctx.state.playing itself already means "a fresh frame
    # decoded within FRAME_STALE_MS" under the new capture mechanism above,
    # so a stalled frame source now shows up as ctx.state.playing == False
    # directly, and falls through to the exact same connection-drop reset
    # logic below rather than needing a second, parallel detection path.

    # Live "checks passing" checklist -- built unconditionally every tick
    # the camera is playing (not gated on run_realtime_loop below), so it
    # reflects live state even while the user is still positioning, before
    # the quality hold has started counting down. check_single_face() and
    # compute_quality_score() both go through get_cached_detections()/
    # get_cached_landmarks() (quality_checks_day8_9.py), which cache
    # MediaPipe's result per frame object -- verify_pose_and_quality() below
    # already triggers the same underlying detection for this exact frame,
    # so this adds no new model inference, just reads/re-derives from the
    # same cached result.
    checklist = {}
    face_res = check_single_face(latest_img) if latest_img is not None else None
    checklist["one_face"] = "pass" if (face_res and face_res["status"] == "pass") else (
        "fail" if face_res else "pending")
    if face_res and face_res["status"] == "pass":
        qres = compute_quality_score(latest_img, profile=active_prof)
        for key, tick_label in [
            ("brightness", "brightness"), ("blur", "sharpness"), ("pose", "head_angle"),
            ("position", "distance"), ("occlusion", "not_covered"),
            ("contrast", "contrast"), ("resolution", "resolution"),
        ]:
            sub = qres.get("sub_scores", {}).get(key)
            checklist[tick_label] = "pass" if (sub and sub["score"] >= 50) else (
                "fail" if sub else "pending")
    else:
        for tick_label in ["brightness", "sharpness", "head_angle", "distance",
                            "not_covered", "contrast", "resolution"]:
            checklist[tick_label] = "pending"
    st.session_state.live_checklist = checklist

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

        _existing_countdown_start = st.session_state.get("countdown_start")
        _in_challenge_phase = (
            _existing_countdown_start is not None
            and (time.time() - _existing_countdown_start) >= 1.5
        )

        if _in_challenge_phase:
            # Once past the initial 1.5s hold, the challenge/rPPG logic runs
            # on every tick regardless of the outer frontal-pose quality
            # check -- a deliberate head-turn challenge is expected to fail
            # that check for as long as the turn is held, so gating on it
            # would starve evaluate_head_turn_tick() of the ticks it needs.
            # The challenge tick evaluators and the rPPG timeout are the
            # correct gates for this phase instead.
            overlay_class = "success" if treat_as_pass else "warning"
            elapsed = time.time() - st.session_state.countdown_start
            if True:  # always true here; kept for indentation consistency with the block below
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
                    st.session_state.active_challenge_type = random.choice(ACTIVE_CHALLENGE_TYPES)
                    st.session_state.active_challenge_history = [] if st.session_state.active_challenge_type == "blink" else (0, 0)
                    st.session_state.active_challenge_start = time.time()
                    st.session_state.active_challenge_passed = False
                    st.session_state.enroll_frontal_wait_start = None
                    if "active_challenge_round" not in st.session_state or st.session_state.active_challenge_round is None:
                        st.session_state.active_challenge_round = 1
                    # A fresh attempt starts -- clear out any stale pass/fail
                    # tick left over from a previous attempt so the checklist
                    # doesn't show a leftover result for a check that hasn't
                    # run yet this time.
                    st.session_state.rppg_last_status = "pending"
                    st.session_state.antispoof_last_status = "pending"
                    # Replay-signature evidence (loop detector + screen-
                    # surface texture) also starts fresh per attempt --
                    # accumulated across the whole challenge window, checked
                    # at the moment the gesture itself would otherwise pass.
                    st.session_state.challenge_frame_loop_buffer = []
                    st.session_state.challenge_screen_surface_fail_count = 0
                    st.session_state.challenge_screen_surface_sample_count = 0
                    # Passive liveness (MiniFASNet, the same trained
                    # anti-spoof model used at final capture) sampled a few
                    # times during the challenge too -- added after live
                    # testing found a physically-tilted photo/phone defeats
                    # the loop/screen-surface checks above (no repeated
                    # frame content to catch, since the attacker is
                    # continuously moving it by hand), but a trained
                    # spoof-classifier has a real chance of reading texture/
                    # reflection cues those simpler checks can't see.
                    # Throttled to roughly once/second (not every tick like
                    # the cheap checks above) via the timestamp below -- a
                    # real model inference, measured at ~125-550ms per call,
                    # not a few-millisecond heuristic. This is a genuine,
                    # disclosed trade-off: a brief once-per-second hitch in
                    # the live feed during the challenge window, in exchange
                    # for a real trained classifier's opinion rather than
                    # only frame-diff heuristics.
                    st.session_state.challenge_passive_liveness_fail_count = 0
                    st.session_state.challenge_passive_liveness_sample_count = 0
                    st.session_state.challenge_passive_liveness_last_sample_ts = None
                    st.session_state.enroll_antispoof_retry_count = 0
                    # Verify Identity also starts collecting an rPPG (Layer
                    # 3) sample buffer from this same moment, running
                    # concurrently rather than as a separate wait -- by the
                    # time the active challenge resolves, the buffer often
                    # already has enough samples.
                    if st.session_state.active_view == "Verify Identity":
                        st.session_state.rppg_samples = []
                        st.session_state.rppg_collect_start = time.time()
                        st.session_state.rppg_last_sampled_ts = None

                def _fail_active_challenge(reason, stage="active_liveness", technical_reason=None):
                    st.session_state.countdown_start = None
                    st.session_state.active_challenge_type = None
                    st.session_state.active_challenge_history = None
                    st.session_state.active_challenge_passed = False
                    st.session_state.active_challenge_round = None
                    st.session_state.rppg_samples = None
                    st.session_state.rppg_collect_start = None
                    st.session_state.rppg_last_status = "pending"
                    st.session_state.antispoof_last_status = "pending"
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
                #
                # Only sample when latest_frame_ts has actually advanced --
                # this fragment can rerun faster than a genuinely new camera
                # frame arrives, and appending the same frame's green-channel
                # value multiple times in a row would turn the signal into a
                # staircase instead of a genuine physiological waveform,
                # corrupting the bandpass/FFT pulse extraction in
                # check_rppg_liveness_from_samples(). Deduping keeps
                # real_fps an accurate description of the true sample rate.
                if st.session_state.active_view == "Verify Identity":
                    _cur_frame_ts = st.session_state.grabber.latest_frame_ts
                    if _cur_frame_ts is not None and _cur_frame_ts != st.session_state.get("rppg_last_sampled_ts"):
                        green_mean = extract_green_mean_from_frame(latest_img)
                        if green_mean is not None:
                            st.session_state.rppg_samples.append(green_mean)
                        st.session_state.rppg_last_sampled_ts = _cur_frame_ts

                # Replay-signature evidence (Breach 1A: a canned/looped
                # recording could otherwise satisfy the geometric blink/turn
                # check on its own). Accumulated every tick across the whole
                # challenge window, not just at the pass instant, so there's
                # a real evidence base by the time the gesture would
                # otherwise pass -- see check_frame_loop_signature()'s
                # docstring for the false-positive-avoidance reasoning.
                if not st.session_state.active_challenge_passed:
                    st.session_state.challenge_frame_loop_buffer, _loop_suspicious, _loop_match_count = check_frame_loop_signature(
                        latest_img, st.session_state.challenge_frame_loop_buffer
                    )
                    _ss_res = check_screen_surface_texture(latest_img)
                    st.session_state.challenge_screen_surface_sample_count += 1
                    if _ss_res["status"] == "fail":
                        st.session_state.challenge_screen_surface_fail_count += 1

                    _pl_last_ts = st.session_state.challenge_passive_liveness_last_sample_ts
                    if _pl_last_ts is None or (time.time() - _pl_last_ts) >= 1.0:
                        st.session_state.challenge_passive_liveness_last_sample_ts = time.time()
                        _pl_res = check_passive_liveness(latest_img)
                        st.session_state.challenge_passive_liveness_sample_count += 1
                        if _pl_res["status"] == "fail":
                            st.session_state.challenge_passive_liveness_fail_count += 1

                if not st.session_state.active_challenge_passed:
                    challenge_type = st.session_state.active_challenge_type
                    challenge_elapsed = time.time() - st.session_state.active_challenge_start
                    challenge_remaining = max(0, round(ACTIVE_CHALLENGE_TIMEOUT_S - challenge_elapsed))

                    if challenge_type == "blink":
                        new_hist, challenge_status = evaluate_blink_tick(latest_img, st.session_state.active_challenge_history)
                        instructions_text = f"Please blink twice ({challenge_remaining}s left)"
                    else:
                        direction = "left" if challenge_type == "turn_left" else "right"
                        new_hist, challenge_status = evaluate_head_turn_tick(latest_img, st.session_state.active_challenge_history, direction)
                        # Direct user feedback: naming left/right alone left
                        # room for doubt about which way to actually turn --
                        # pointing at the arrow itself is unambiguous
                        # regardless of how the word "left"/"right" reads.
                        instructions_text = f"Turn slightly {direction}, toward the arrow — hold for 5s ({challenge_remaining}s left)"
                        guide_arrow_val = direction
                    st.session_state.active_challenge_history = new_hist

                    if os.environ.get("DEBUG_CHALLENGE"):
                        with open("scratch/debug_challenge.log", "a") as _f:
                            _f.write(f"{time.time():.3f} view={st.session_state.active_view} type={challenge_type} elapsed={challenge_elapsed:.2f} status={challenge_status} hist={new_hist}\n")

                    if challenge_status == "pass":
                        # Gesture geometry passed -- also require the
                        # accumulated replay-signature evidence from this
                        # same attempt to not indicate a loop/screen replay
                        # before accepting it as a genuine pass. A suspected
                        # replay is treated exactly like a timed-out round
                        # (retry the same gesture, only hard-fail once
                        # MAX_CHALLENGE_ROUNDS is exhausted) rather than an
                        # immediate hard rejection -- these signals are not
                        # independently validated against a real staged
                        # attack (see check_frame_loop_signature()'s
                        # docstring), so a false positive should cost a
                        # genuine user one retry, not the whole attempt.
                        _ss_samples = st.session_state.challenge_screen_surface_sample_count
                        _ss_fails = st.session_state.challenge_screen_surface_fail_count
                        # NOT a replay_suspected input (see below) -- still
                        # measured and logged for visibility, just no longer
                        # trusted to gate anything.
                        _pl_samples = st.session_state.challenge_passive_liveness_sample_count
                        _pl_fails = st.session_state.challenge_passive_liveness_fail_count
                        # Lower sample-count floor than screen-surface's old
                        # one (2, not 5) since passive liveness only gets
                        # one sample per second, not every tick -- a short-
                        # lived challenge attempt might only collect 2-3
                        # samples total, and a trained spoof classifier
                        # failing even a couple of real samples is stronger
                        # evidence than a cheap heuristic needs to reach the
                        # same confidence.
                        _pl_majority_fail = _pl_samples >= 2 and (_pl_fails / _pl_samples) > 0.5
                        # screen_surface_texture deliberately dropped from
                        # this decision: tested against the real attack/
                        # genuine images in data/self_collected/session_2/
                        # (scratch/calibrate_replay_checks_on_real_images.py)
                        # and measured 0/4 attacks caught, 3/9 genuine
                        # images false-flagged -- pure false-positive risk
                        # with zero measured benefit on real data, not a
                        # borderline judgment call. passive_liveness on the
                        # same real images measured 4/4 attacks caught
                        # (encouraging) but 2/9 genuine false-flagged (a
                        # real single-frame noise rate, which is exactly why
                        # this stays a majority-vote over multiple samples
                        # rather than a single-frame gate, and a suspected
                        # replay still only costs a retry, not a hard fail).
                        _replay_suspected = _loop_suspicious or _pl_majority_fail

                        if os.environ.get("DEBUG_CHALLENGE"):
                            with open("scratch/debug_challenge.log", "a") as _f:
                                _f.write(f"{time.time():.3f} challenge geometry passed -- loop_suspicious={_loop_suspicious} loop_matches={_loop_match_count} ss_fail_ratio={_ss_fails}/{_ss_samples} pl_fail_ratio={_pl_fails}/{_pl_samples} replay_suspected={_replay_suspected}\n")

                        if _replay_suspected:
                            if st.session_state.active_challenge_round < MAX_CHALLENGE_ROUNDS:
                                st.session_state.active_challenge_round += 1
                                st.session_state.active_challenge_history = [] if challenge_type == "blink" else (0, 0)
                                st.session_state.active_challenge_start = time.time()
                                st.session_state.challenge_frame_loop_buffer = []
                                st.session_state.challenge_screen_surface_fail_count = 0
                                st.session_state.challenge_screen_surface_sample_count = 0
                                st.session_state.challenge_passive_liveness_fail_count = 0
                                st.session_state.challenge_passive_liveness_sample_count = 0
                                st.session_state.challenge_passive_liveness_last_sample_ts = None
                            else:
                                _fail_active_challenge(
                                    "We couldn't confirm a live camera feed. Please make sure you're using your own live camera, not a photo, video, or screen, and try again.",
                                    stage="active_liveness",
                                    technical_reason=f"active_liveness check failed: replay signal suspected (loop_matches={_loop_match_count}, screen_surface_fail_ratio={_ss_fails}/{_ss_samples}, passive_liveness_fail_ratio={_pl_fails}/{_pl_samples}), {MAX_CHALLENGE_ROUNDS} rounds attempted",
                                )
                        else:
                            st.session_state.active_challenge_passed = True
                            st.session_state.active_challenge_type = None
                            st.session_state.active_challenge_history = None
                            if os.environ.get("DEBUG_CHALLENGE"):
                                with open("scratch/debug_challenge.log", "a") as _f:
                                    _f.write(f"{time.time():.3f} *** CHALLENGE PASSED ***\n")
                    elif challenge_elapsed >= ACTIVE_CHALLENGE_TIMEOUT_S:
                        if os.environ.get("DEBUG_CHALLENGE"):
                            with open("scratch/debug_challenge.log", "a") as _f:
                                _f.write(f"{time.time():.3f} *** CHALLENGE TIMED OUT (round {st.session_state.active_challenge_round}) ***\n")
                        if st.session_state.active_challenge_round < MAX_CHALLENGE_ROUNDS:
                            # Give the SAME gesture another window in place
                            # instead of hard-failing the whole attempt -- see
                            # MAX_CHALLENGE_ROUNDS comment. Deliberately does
                            # NOT re-randomize challenge_type here: live
                            # testing showed switching gestures on retry
                            # (asked for a turn, then blink, then a turn
                            # again) reads as "the app can't make up its
                            # mind" and defeats the point of picking one
                            # random gesture per attempt. One gesture is
                            # chosen once per attempt; only the detection
                            # window for that same gesture is extended.
                            st.session_state.active_challenge_round += 1
                            st.session_state.active_challenge_history = [] if challenge_type == "blink" else (0, 0)
                            st.session_state.active_challenge_start = time.time()
                        else:
                            _fail_active_challenge(
                                "We couldn't detect the requested motion in time. Please try again and follow the on-screen prompt.",
                                stage="active_liveness",
                                technical_reason=f"active_liveness check failed: '{challenge_type}' challenge timed out after {ACTIVE_CHALLENGE_TIMEOUT_S:.0f}s with no detected {challenge_type}, {MAX_CHALLENGE_ROUNDS} rounds attempted",
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
                        _rppg_ready = rppg_elapsed >= RPPG_MIN_WINDOW_S and real_fps > 0
                        _rppg_gave_up = (not _rppg_ready) and rppg_elapsed >= RPPG_TIMEOUT_S
                        if _rppg_ready or _rppg_gave_up:
                            # rPPG pulse extraction from a webcam is
                            # inherently noisy (compression, lighting, short
                            # window). Still measured and recorded
                            # (rppg_last_status feeds the checklist dot
                            # honestly), but a fail/insufficient-signal
                            # result no longer blocks verification on its
                            # own -- face match + the active gesture +
                            # passive anti-spoof scan carry the actual
                            # liveness/identity decision.
                            if _rppg_ready:
                                rppg_res = check_rppg_liveness_from_samples(samples, fps_estimate=real_fps)
                            else:
                                rppg_res = {"status": "fail", "reason": f"only {len(samples)} samples in {rppg_elapsed:.1f}s"}
                            if os.environ.get("DEBUG_CHALLENGE"):
                                with open("scratch/debug_challenge.log", "a") as _f:
                                    _f.write(f"{time.time():.3f} *** RPPG EVALUATED (non-blocking) *** samples={len(samples)} elapsed={rppg_elapsed:.2f} real_fps={real_fps:.2f} result={rppg_res}\n")
                            st.session_state.rppg_last_status = rppg_res["status"]
                            st.session_state.rppg_samples = None
                            st.session_state.rppg_collect_start = None
                            st.session_state.motion_challenge_display_status = "pass"
                            st.session_state.flash_end_time = time.time() + 0.6
                            st.session_state.play_sound_trigger = True
                            # Regression found via live testing: run_verification_logic()
                            # checks active_challenge_passed internally (the Breach 1B
                            # structural gate) -- it must still be True when called, so
                            # the reset that prepares clean state for the NEXT attempt
                            # has to happen AFTER this call, not before. Resetting first
                            # (the order this block used before that gate existed) made
                            # every real Verify Identity attempt fail its own gate.
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
                            st.session_state.countdown_start = None
                            st.session_state.active_challenge_passed = False
                            st.session_state.active_challenge_round = None
                            if os.environ.get("DEBUG_CHALLENGE"):
                                with open("scratch/debug_challenge.log", "a") as _f:
                                    _f.write(f"{time.time():.3f} *** run_verification_logic DONE *** verify_outcome={st.session_state.get('verify_outcome')}\n")
                            st.rerun()
                        else:
                            instructions_text = "Almost there, hold still a moment longer..."
                    else:
                        # Real bug found via yaw logging: a head-turn
                        # challenge passes at the exact instant the person
                        # is still turned 25+ degrees -- that's literally
                        # what satisfied it -- but capturing immediately on
                        # that same frame runs the strict check below,
                        # which requires a frontal pose and would reject
                        # almost every turn-based pass on the spot. Blink
                        # never hits this since the person stays frontal
                        # throughout. Verify Identity doesn't either, since
                        # rPPG collection (RPPG_MIN_WINDOW_S, several
                        # seconds) already provides a natural buffer to
                        # return to frontal before capture; Guided
                        # Enrollment has no such buffer, so add one
                        # explicitly here: wait for a frontal pose (bounded
                        # by a timeout, so a person who walks away still
                        # gets a real failure eventually) before running
                        # the capture-time check at all.
                        if "enroll_frontal_wait_start" not in st.session_state or st.session_state.enroll_frontal_wait_start is None:
                            st.session_state.enroll_frontal_wait_start = time.time()
                        _pose_check = check_pose(latest_img)
                        _frontal_wait_elapsed = time.time() - st.session_state.enroll_frontal_wait_start
                        ENROLL_FRONTAL_WAIT_TIMEOUT_S = 8.0
                        if _pose_check.get("classification") != "frontal" and _frontal_wait_elapsed < ENROLL_FRONTAL_WAIT_TIMEOUT_S:
                            instructions_text = "Great! Now look back at the camera"
                            check_res = {"status": "pending"}
                        else:
                            st.session_state.enroll_frontal_wait_start = None
                            check_res = _capture_enrollment_photo(latest_img, active_prof, liveness_blocking=True)
                        if check_res["status"] == "pending":
                            pass
                        elif check_res["status"] == "fail":
                            # A single antispoof reading is noisy enough
                            # (see check_passive_liveness()'s calibration
                            # notes) that treating it exactly like a real
                            # quality failure -- wiping out an already-
                            # completed blink/turn challenge and forcing a
                            # full redo -- was frustrating enough in real
                            # testing that this check was made non-blocking
                            # entirely for a while. Restored as a real gate,
                            # but a bounded number of quick recapture
                            # attempts are given first (same frontal pose,
                            # same passed gesture, just a fresh frame) before
                            # treating it as a genuine rejection -- a real
                            # spoof will keep failing across retries; a
                            # single noisy live reading usually won't.
                            _is_antispoof_fail = check_res.get("liveness_result", {}).get("status") == "fail"
                            _antispoof_retries = st.session_state.get("enroll_antispoof_retry_count", 0)
                            ENROLL_ANTISPOOF_MAX_RETRIES = 2
                            if _is_antispoof_fail and _antispoof_retries < ENROLL_ANTISPOOF_MAX_RETRIES:
                                st.session_state.enroll_antispoof_retry_count = _antispoof_retries + 1
                                instructions_text = "One moment, refining the capture..."
                            else:
                                st.session_state.countdown_start = None
                                st.session_state.active_challenge_passed = False
                                st.session_state.motion_challenge_display_status = "pending"
                                st.session_state.active_challenge_round = None
                                st.session_state.flash_end_time = None
                                st.session_state.enroll_antispoof_retry_count = 0
                                st.error(check_res["reason"])
                                time.sleep(1.5)
                        else:
                            st.session_state.enroll_antispoof_retry_count = 0
                            st.session_state.countdown_start = None
                            st.session_state.active_challenge_passed = False
                            st.session_state.motion_challenge_display_status = "pass"
                            st.session_state.active_challenge_round = None
                            st.session_state.flash_end_time = time.time() + 0.6
                            st.session_state.play_sound_trigger = True
                            st.session_state.enroll_front = latest_img.copy()
                            st.session_state.enroll_step = 2
                            st.rerun()
        elif treat_as_pass:
            # Still in the initial hold-still countdown (not yet past 1.5s),
            # and this tick's quality genuinely passed (or was tolerated).
            overlay_class = "success"
            if _existing_countdown_start is None:
                st.session_state.countdown_start = time.time()
            elapsed = time.time() - st.session_state.countdown_start
            instructions_text = f"Hold still... {max(0.0, 1.5 - elapsed):.1f}s"
        else:
            # Still in the initial hold-still countdown, and quality failed
            # beyond FLICKER_TOLERANCE -- this is the only case that should
            # reset the countdown, since we're not yet past it (once past,
            # _in_challenge_phase above is the only gate that matters).
            st.session_state.countdown_start = None
            st.session_state.countdown_fail_streak = 0
            st.session_state.active_challenge_type = None
            st.session_state.active_challenge_history = None
            st.session_state.active_challenge_passed = False
            st.session_state.motion_challenge_display_status = "pending"
            st.session_state.active_challenge_round = None
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
    if ctx.state.playing:
        status_text = instructions_text
        st.session_state.hiccup_just_reset = False
    elif st.session_state.get("cam_ever_started"):
        # A camera that was playing and is now not is almost always the
        # documented 20-32s WebRTC/aioice consent-check hiccup (docs/
        # scope_decision_worksheet.md), not a real disconnect the user needs
        # to act on -- telling them to click Start here is actively wrong,
        # since it implies a problem they caused and need to fix.
        if st.session_state.get("hiccup_just_reset"):
            status_text = "Connection hiccup -- let's try that again. Reconnecting... this can briefly take up to 30 seconds."
        else:
            status_text = "Reconnecting... this can briefly take up to 30 seconds."
    else:
        status_text = "Camera offline. Please click the start button above to activate the scanner."
    st.markdown(f"""
    <div class="guidance-text-container" style="text-align: center; margin-top: 12px; font-size: 0.85rem; color: #64748B; font-weight: 500;">
        {status_text}
    </div>
    """, unsafe_allow_html=True)

    # Live "checks passing" checklist -- read-only display layer built from
    # st.session_state.live_checklist (Step 3, rebuilt every tick from
    # cache-cheap checks) plus the two phase items that only resolve at
    # specific moments (motion challenge mid-hold, antispoof only at the
    # final capture instant). Purely additive: does not replace or alter
    # the actual accept/reject decision logic above.
    if ctx.state.playing:
        _checklist = st.session_state.get("live_checklist", {})
        _motion_status = (
            "pass" if (st.session_state.get("active_challenge_passed") or st.session_state.get("motion_challenge_display_status") == "pass")
            else ("in_progress" if st.session_state.get("active_challenge_type") else "pending")
        )
        _rppg_status = st.session_state.get("rppg_last_status", "pending")
        if _rppg_status == "pending" and st.session_state.get("rppg_collect_start") is not None:
            _rppg_status = "in_progress"
        _antispoof_status = st.session_state.get("antispoof_last_status", "pending")

        CHECKLIST_LABELS = [
            ("one_face", "One face detected"),
            ("head_angle", "Head angle"),
            ("brightness", "Brightness"),
            ("sharpness", "Sharpness"),
            ("contrast", "Contrast"),
            ("distance", "Distance / framing"),
            ("not_covered", "Face not covered"),
            ("resolution", "Resolution"),
            ("motion_challenge", "Blink / head-turn"),
            ("rppg", "Heartbeat pattern (Verify only)"),
            ("antispoof", "Skin-texture / anti-spoof scan"),
        ]
        _status_by_key = dict(_checklist)
        _status_by_key["motion_challenge"] = _motion_status
        _status_by_key["rppg"] = _rppg_status
        _status_by_key["antispoof"] = _antispoof_status

        _rows_html = ""
        for key, label in CHECKLIST_LABELS:
            if key == "rppg" and st.session_state.active_view == "Guided Enrollment":
                continue
            status = _status_by_key.get(key, "pending")
            _rows_html += f'<div class="checklist-item"><span class="checklist-dot {status}"></span>{label}</div>'

        st.markdown(f'<div class="checklist-grid">{_rows_html}</div>', unsafe_allow_html=True)

    # 3. Quiet manual fallback capture button below camera stream
    if ctx.state.playing and not is_flashing:
        if st.button("Having trouble? Tap to capture manually", key="manual_fallback_capture_btn"):
            if latest_img is None:
                st.error("Please wait until the camera feed is ready.")
            elif not st.session_state.get("active_challenge_passed", False):
                # This button is for forcing a capture when auto-capture is
                # struggling (e.g. lighting), not a way to skip the blink/
                # head-turn liveness challenge -- that check still has to
                # pass first, the same as the automatic flow requires.
                st.error("Please complete the blink or head-turn prompt above before capturing.")
            else:
                if st.session_state.active_view == "Verify Identity":
                    st.session_state.play_sound_trigger = True
                    st.session_state.flash_end_time = time.time() + 0.6
                    run_verification_logic(latest_img, active_prof)
                    st.rerun()
                else:
                    check_res = _capture_enrollment_photo(latest_img, active_prof, liveness_blocking=True)
                    if check_res["status"] == "fail":
                        st.error(check_res["reason"])
                    else:
                        st.session_state.play_sound_trigger = True
                        st.session_state.flash_end_time = time.time() + 0.6
                        st.session_state.enroll_front = latest_img.copy()
                        st.session_state.enroll_step = 2
                        st.rerun()

    # ---------------------------------------------------------
    # ACTIVE RERUN TRIGGER LOOP -- fires ~12.5x/sec while polling, scoped to
    # this fragment only (not a full-page rerun).
    #
    # Streamlit raises StreamlitAPIException if scope="fragment" is called
    # while the current execution is itself a full-script rerun rather than
    # a fragment rerun -- which happens here whenever a plain st.rerun() ran
    # just before this (e.g. after run_verification_logic() on a failed
    # verification, needed so col_actions outside the fragment updates).
    # _safe_polling_rerun() handles that case.
    # ---------------------------------------------------------
    if ctx.state.playing and keep_polling_alive:
        time.sleep(0.08)  # ~12.5 checks/second
        if os.environ.get("DEBUG_PERF"):
            _perf_tick_end = time.time()
            with open("scratch/perf_loop_log.txt", "a") as _f:
                _f.write(f"{_perf_tick_end:.6f} script_exec_ms={(_perf_tick_end - _perf_tick_start) * 1000:.1f}\n")
        _safe_polling_rerun()
    elif not ctx.state.playing and st.session_state.get("cam_ever_started"):
        # Once ctx.state.playing goes False, nothing else causes this
        # fragment to run again on its own -- keep polling on a slower
        # cadence (no need to stream at 0.08s when there's nothing to
        # stream) so a real recovery is picked up promptly without
        # requiring the user to interact with something.
        time.sleep(0.8)
        _safe_polling_rerun()


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
            if selected_view != st.session_state.active_view:
                _clear_action_error()
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
        _render_action_error_banner()
        st.markdown('<div class="consumer-sub">Scan your face to quickly verify your identity.</div>', unsafe_allow_html=True)
        st.markdown('<div class="consumer-sub">Typically takes 5-10 seconds. If a gesture needs to be retried, it can take up to about a minute.</div>', unsafe_allow_html=True)

        # Verification Outcome Presentation -- shown immediately after the
        # prerequisites/checklist, above the info box and manual-verify
        # button below, so a pass/fail result is the first thing seen
        # rather than buried under a divider further down the panel.
        if "verify_outcome" in st.session_state:
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
                    _clear_action_error()
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
                    <div class="app-alert-box warning" style="margin-top: 15px;">
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

        # Beautiful informative auto-capture verification card element
        if "verify_outcome" not in st.session_state:
            st.markdown("""
            <div class="app-alert-box info">
                ℹ️ Look at the camera. The system will scan and verify your identity automatically once aligned.
            </div>
            """, unsafe_allow_html=True)

            # Simple button to manually trigger verification immediately if needed
            if st.button("Verify Manually", key="verify_action_btn"):
                _clear_action_error()
                if latest_img is None:
                    _set_action_error("Please turn on the camera first.")
                    st.rerun()
                elif not st.session_state.get("active_challenge_passed", False):
                    # Same gate the automatic flow requires -- this button
                    # forces verification to run right now instead of
                    # waiting for the next auto-capture tick, it is not a
                    # way to skip the blink/head-turn liveness challenge.
                    _set_action_error("Please complete the blink or head-turn prompt above before verifying.")
                    st.rerun()
                else:
                    st.session_state.play_sound_trigger = True
                    st.session_state.flash_end_time = time.time() + 0.6
                    run_verification_logic(latest_img, selected_profile)
                    st.rerun()

            st.markdown('<div class="clean-empty-state" style="padding:10px 0 0 0;"><span class="clean-empty-text" style="font-size:0.8rem;">Awaiting scan. Position your face in the guide, verification starts automatically.</span></div>', unsafe_allow_html=True)

    # ---------------------------------------------------------
    # TAB: GUIDED ENROLLMENT
    # ---------------------------------------------------------
    else:
        st.markdown('<div class="consumer-title">Register Biometrics</div>', unsafe_allow_html=True)
        _render_action_error_banner()
        st.markdown('<div class="consumer-sub">Look directly at the camera to capture your biometric profile.</div>', unsafe_allow_html=True)
        st.markdown('<div class="consumer-sub">Typically takes 5-10 seconds. If a gesture needs to be retried, it can take up to about a minute.</div>', unsafe_allow_html=True)

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
            st.markdown('<div class="app-alert-box success">✓ Photo captured successfully. Click register below to complete.</div>', unsafe_allow_html=True)
            col_btns = st.columns(2)
            with col_btns[0]:
                if st.button("Retake Photo", key="reset_enroll_btn"):
                    _clear_action_error()
                    st.session_state.enroll_step = 1
                    st.session_state.enroll_front = None
                    st.rerun()
            with col_btns[1]:
                if st.button("Register Face ID", key="save_enroll_btn"):
                    _clear_action_error()
                    if not reg_name:
                        _set_action_error("Please fill in your name.")
                        st.rerun()
                    elif not consent:
                        _set_action_error("You must agree to the storage consent checkbox.")
                        st.rerun()
                    else:
                        with st.spinner("Encrypting secure biometric templates..."):
                            try:
                                emb_front = get_embedding(st.session_state.enroll_front)

                                if emb_front["status"] != "success":
                                    _set_action_error("Frontal capture could not map landmarks.")
                                    st.rerun()
                                else:
                                    # Run duplicate check
                                    from src.duplicate_check import check_for_duplicate
                                    dup_res = check_for_duplicate(emb_front["embedding"])
                                    if dup_res["is_duplicate"]:
                                        _set_action_error(f"Registration rejected: Face already registered as '{dup_res['matched_name']}' (User ID: {dup_res['matched_user_id']}) at similarity score {dup_res['score']:.4f}.")
                                        st.rerun()
                                    else:
                                        user_id = db.insert_user(reg_name, consent_given=consent, actor="consumer_ui")
                                        db.insert_template(user_id, "front", emb_front["embedding"])

                                        st.success(f"Successfully registered your profile, {reg_name}!")
                                        st.balloons()

                                        st.session_state.enroll_step = 1
                                        st.session_state.enroll_front = None
                                        st.rerun()
                            except Exception as e:
                                _set_action_error(f"Save failed: {str(e)}")
                                st.rerun()

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
# ADMIN: QUALITY PROFILE -- client-side deployment configuration,
# deliberately not exposed to the end user during registration/verification.
# ---------------------------------------------------------
st.markdown("<hr style='margin: 30px 0;'>", unsafe_allow_html=True)
with st.expander("Admin settings", expanded=False):
    profile_options_desc = {
        "lenient": "Lenient (Fast, low-light optimized)",
        "balanced": "Balanced (Recommended standard)",
        "strict": "Strict (High-security checks)"
    }
    default_idx = ["lenient", "balanced", "strict"].index(st.session_state.selected_profile)
    new_profile = st.selectbox(
        "Quality profile",
        options=["lenient", "balanced", "strict"],
        index=default_idx,
        format_func=lambda x: profile_options_desc[x],
        key="quality_profile_select",
    )
    if new_profile != st.session_state.selected_profile:
        st.session_state.selected_profile = new_profile
        st.rerun()

    st.markdown("---")
    st.markdown("#### System requirements")
    st.markdown(
        "- **RAM:** at least 4 GB free (8 GB if also running the API backend for an external integration)\n"
        "- **CPU:** 4 logical cores recommended for comfortable headroom during a live session\n"
        "- **Camera:** any 720p-capable webcam (a built-in laptop camera is sufficient)\n"
        "- **Internet:** none required during use, everything runs locally; a connection is only needed once, for initial setup\n"
    )

# Note: the routine polling/rerun trigger now lives inside render_camera_card()
# above, scoped to that fragment (st.rerun(scope="fragment")) so the common
# "still polling, nothing changed" tick doesn't re-render this whole page.
