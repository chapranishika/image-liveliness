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
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

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
from src.quality_score import compute_quality_score, QUALITY_PROFILES, WEIGHTS
from src.quality_checks_day8_9 import check_pose, check_single_face
from src.liveness_passive import check_passive_liveness

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
            
        return av.VideoFrame.from_ndarray(annotated, format="bgr24")

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

matching_threshold = 0.50
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
            
        # Check centering/position
        if "position" in sub and sub["position"]["score"] < 50:
            corrections.append("🎯 **Centering**: Position your face directly in the middle of the camera guide.")
            
        # Check pose/alignment
        if "pose" in sub and sub["pose"]["score"] < 50:
            corrections.append("📐 **Alignment**: Look straight at the camera and hold still.")
            
        # Check visibility
        if "occlusion" in sub and sub["occlusion"]["score"] < 50:
            corrections.append("🕶️ **Visibility**: Ensure your face is not covered by masks, hats, or dark glasses.")

        # Check blur
        if "blur" in sub and sub["blur"]["score"] < 50:
            corrections.append("🔍 **Sharpness**: Hold your device steady to get a clear picture.")

        if corrections:
            for item in corrections:
                st.info(item)
        else:
            st.info("Please make sure you are looking directly at the camera in good lighting.")

def verify_pose_and_quality(frame, expected_pose, profile_name, check_liveness=False):
    """
    Checks face presence, alignment, and quality.
    Translates all raw technical thresholds/errors into user-friendly instructions.
    """
    face_check = check_single_face(frame)
    if face_check["status"] == "fail":
        return {"status": "fail", "reason": "We couldn't find a face. Make sure you are in a well-lit area and looking at the camera."}
        
    pose_res = check_pose(frame)
    if pose_res["status"] == "fail":
        if profile_name != "lenient":
            if expected_pose == "left":
                return {"status": "fail", "reason": "Please turn your head a little further to the left."}
            elif expected_pose == "right":
                return {"status": "fail", "reason": "Please turn your head a little further to the right."}
            return {"status": "fail", "reason": "Please look directly at the camera."}
        else:
            pose_res = {"status": "pass", "yaw": 0.0, "classification": "profile_left" if expected_pose == "left" else ("profile_right" if expected_pose == "right" else "frontal")}

    yaw = pose_res.get("yaw", 0.0)
    classification = pose_res.get("classification")
    
    # Verify expected pose yaw angles
    if expected_pose == "front":
        if classification != "frontal" and profile_name != "lenient":
            return {"status": "fail", "reason": "Please look straight ahead at the camera."}
    elif expected_pose == "left":
        if classification != "profile_left" and profile_name != "lenient":
            return {"status": "fail", "reason": "Please turn your head a little further to the left."}
    elif expected_pose == "right":
        if classification != "profile_right" and profile_name != "lenient":
            return {"status": "fail", "reason": "Please turn your head a little further to the right."}

    # Run overall quality calculation
    if expected_pose in ["left", "right"]:
        sub_results = {
            "brightness": score_brightness_for_profile(frame),
            "blur": score_blur_for_profile(frame),
            "position": score_position_for_profile(frame),
            "occlusion": score_occlusion_for_profile(frame),
            "pose": {"name": "pose", "raw_value": yaw, "score": 100.0}
        }
        overall = sum(sub_results[k]["score"] * WEIGHTS[k] for k in WEIGHTS)
        overall = round(overall, 1)
        thresh = QUALITY_PROFILES[profile_name]["threshold"]
        decision = "accept" if overall >= thresh else "reject"
        quality_res = {
            "overall_score": overall,
            "decision": decision,
            "profile": profile_name,
            "threshold": thresh,
            "reason": "" if decision == "accept" else f"Quality score {overall}% below threshold {thresh}%",
            "sub_scores": sub_results
        }
    else:
        quality_res = compute_quality_score(frame, profile=profile_name)

    if quality_res["decision"] == "reject":
        # Fallback for headset users: if brightness, position, and pose are good, accept it!
        sub = quality_res.get("sub_scores", {})
        brightness_val = sub.get("brightness", {}).get("score", 100) >= 50
        position_val = sub.get("position", {}).get("score", 100) >= 50
        pose_val = sub.get("pose", {}).get("score", 100) >= 50
        if brightness_val and position_val and pose_val:
            quality_res["decision"] = "accept"
            quality_res["reason"] = ""

    if quality_res["decision"] == "reject":
        return {"status": "fail", "reason": "That didn't quite work — let's try again. Make sure your face is centered and fully visible."}

    liveness_res = {"status": "pass", "liveness_score": 0.99}
    if check_liveness:
        # Run passive liveness check on captured frame
        liveness_res = check_passive_liveness(frame)
        if liveness_res["status"] == "fail" and profile_name == "lenient":
            liveness_res["status"] = "pass"
            
        if liveness_res["status"] == "fail":
            return {"status": "fail", "reason": "Biometric check failed. Please ensure you are presenting a live face."}

    return {"status": "pass", "quality_result": quality_res, "liveness_result": liveness_res}

# Profile capture helper shortcuts
def score_brightness_for_profile(frame):
    from src.quality_score import score_brightness
    return score_brightness(frame)

def score_blur_for_profile(frame):
    from src.quality_score import score_blur
    return score_blur(frame)

def score_position_for_profile(frame):
    from src.quality_score import score_position
    return score_position(frame)

def score_occlusion_for_profile(frame):
    from src.quality_score import score_occlusion
    return score_occlusion(frame)

def run_verification_logic(latest_img, profile_name):
    st.session_state.verify_image = latest_img.copy()
    
    # Check quality & face presence
    qual_res = run_quality_stage(latest_img, profile=profile_name)
    
    # Headset bypass override check: if quality failed, allow fallback if vital signals are solid
    if qual_res["status"] == "fail" and "all_results" in qual_res:
        all_res = qual_res["all_results"]
        sub = all_res.get("sub_scores", {})
        brightness_val = sub.get("brightness", {}).get("score", 100) >= 50
        position_val = sub.get("position", {}).get("score", 100) >= 50
        pose_val = sub.get("pose", {}).get("score", 100) >= 50
        if brightness_val and position_val and pose_val:
            qual_res["status"] = "pass"
            
    if qual_res["status"] == "fail":
        st.session_state.verify_face_detected = False
        st.session_state.verify_outcome = {
            "status": "fail",
            "stage": "quality",
            "reason": qual_res["reason"],
            "all_results": qual_res.get("all_results")
        }
        st.session_state.verify_boot_logs = f"Quality check failed: {qual_res['reason']}"
    else:
        st.session_state.verify_face_detected = True
        score = qual_res["all_results"]["overall_score"]
        
        # Check liveness
        liveness_res = check_passive_liveness(latest_img)
        if liveness_res["status"] == "fail" and profile_name == "lenient":
            liveness_res["status"] = "pass"
            
        if liveness_res["status"] == "fail":
            st.session_state.verify_outcome = {
                "status": "fail",
                "stage": "liveness",
                "reason": "Biometric check failed. Please present a live face."
            }
            st.session_state.verify_boot_logs = "Liveness check failed."
        else:
            prob = liveness_res.get("liveness_score", 0.99)
            
            # Generate embedding
            emb_res = get_embedding(latest_img)
            if emb_res["status"] != "success":
                st.session_state.verify_outcome = {
                    "status": "fail",
                    "stage": "embedding",
                    "reason": "Could not map facial points cleanly. Hold still."
                }
                st.session_state.verify_boot_logs = f"Embedding error: {emb_res['reason']}"
            else:
                live_emb = emb_res["embedding"]
                
                # Matching 1-to-N
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
                    
                    if not rows:
                        st.session_state.verify_outcome = {
                            "status": "fail",
                            "stage": "matching",
                            "reason": "No registered accounts found."
                        }
                        st.session_state.verify_boot_logs = "No registered users in DB."
                    else:
                        best_match_name = None
                        best_score = -1.0
                        best_angle = None
                        best_user_id = None
                        
                        for user_id, name, angle_type, blob in rows:
                            stored_emb = db._blob_to_embedding(blob)
                            sim = cosine_similarity(live_emb, stored_emb)
                            if sim > best_score:
                                best_score = sim
                                best_match_name = name
                                best_angle = angle_type
                                best_user_id = user_id
                                
                        if best_score >= matching_threshold:
                            db.log_verification(best_user_id, qual_res, liveness_res, best_score, "accept")
                            st.session_state.verify_outcome = {
                                "status": "pass",
                                "name": best_match_name,
                                "score": best_score,
                                "angle": best_angle,
                                "quality_score": score,
                                "liveness_score": prob
                            }
                            st.session_state.verify_boot_logs = f"Matched user {best_match_name} (Similarity: {best_score:.4f})"
                        else:
                            db.log_verification(None, qual_res, liveness_res, best_score, "reject")
                            st.session_state.verify_outcome = {
                                "status": "fail",
                                "stage": "matching",
                                "reason": "No matching biometric account found.",
                                "score": best_score,
                                "best_match": best_match_name
                            }
                            st.session_state.verify_boot_logs = f"Failed match. Best: {best_match_name} (Score: {best_score:.4f})"
                except Exception as e:
                    st.session_state.verify_outcome = {
                        "status": "fail",
                        "stage": "matching",
                        "reason": f"Database error: {str(e)}"
                    }

# ---------------------------------------------------------
# SPLIT PAGE ARCHITECTURE: PERSISTENT CAMERA + TAB ACTIONS
# ---------------------------------------------------------
col_cam, col_actions = st.columns([1.1, 0.9])

with col_cam:
    with st.container(border=True):
        st.markdown('<div class="consumer-title">Camera Feed</div>', unsafe_allow_html=True)
        st.markdown('<div class="consumer-sub">Align your face inside the dashed area below.</div>', unsafe_allow_html=True)
        
        # 1. Continuous single-camera streamer (lightweight constraints for zero lag)
        ctx = webrtc_streamer(
            key="shared_webrtc_camera",
            mode=WebRtcMode.SENDRECV,
            video_frame_callback=st.session_state.grabber.video_frame_callback,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True
        )
        
        # Determine target state for dynamic guide styling
        instructions_text = "Align your face with the guide"
        overlay_class = ""
        
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
        run_realtime_loop = False
        if ctx.state.playing and not is_flashing:
            if st.session_state.active_view == "Guided Enrollment":
                if st.session_state.get("enroll_step", 1) < 4:
                    run_realtime_loop = True
            elif st.session_state.active_view == "Verify Identity":
                outcome = st.session_state.get("verify_outcome")
                if not outcome or outcome.get("status") != "pass":
                    run_realtime_loop = True
                    
        if run_realtime_loop and latest_img is not None:
            # Match current step pose target
            if st.session_state.active_view == "Verify Identity":
                expected_pose = "front"
            else:
                step = st.session_state.get("enroll_step", 1)
                expected_pose = "front" if step == 1 else ("left" if step == 2 else "right")
                
            verify_res = verify_pose_and_quality(latest_img, expected_pose, active_prof, check_liveness=False)
            
            if verify_res["status"] == "pass":
                overlay_class = "success"
                if "countdown_start" not in st.session_state or st.session_state.countdown_start is None:
                    st.session_state.countdown_start = time.time()
                    
                elapsed = time.time() - st.session_state.countdown_start
                instructions_text = f"Hold still... {max(0.0, 1.5 - elapsed):.1f}s"
                
                if elapsed >= 1.5:
                    if st.session_state.active_view == "Verify Identity":
                        st.session_state.countdown_start = None
                        st.session_state.flash_end_time = time.time() + 0.6
                        st.session_state.play_sound_trigger = True
                        run_verification_logic(latest_img, active_prof)
                        st.rerun()
                    else:
                        step = st.session_state.get("enroll_step", 1)
                        # Run strict liveness & quality verification at capture execution moment
                        check_res = verify_pose_and_quality(latest_img, expected_pose, active_prof, check_liveness=True)
                        if check_res["status"] == "fail":
                            st.session_state.countdown_start = None
                            st.session_state.flash_end_time = None
                            st.error(check_res["reason"])
                            time.sleep(1.5)
                        else:
                            st.session_state.countdown_start = None
                            st.session_state.flash_end_time = time.time() + 0.6
                            st.session_state.play_sound_trigger = True
                            if step == 1:
                                st.session_state.enroll_front = latest_img.copy()
                                st.session_state.enroll_step = 2
                            elif step == 2:
                                st.session_state.enroll_left = latest_img.copy()
                                st.session_state.enroll_step = 3
                            elif step == 3:
                                st.session_state.enroll_right = latest_img.copy()
                                st.session_state.enroll_step = 4
                            st.rerun()
            else:
                st.session_state.countdown_start = None
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
            
            arrow_state = "none"
            if st.session_state.active_view == "Guided Enrollment" and not is_flashing:
                step = st.session_state.get("enroll_step", 1)
                if step == 2:
                    arrow_state = "left"
                elif step == 3:
                    arrow_state = "right"
            st.session_state.grabber.guide_arrow = arrow_state
            
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
                        step = st.session_state.get("enroll_step", 1)
                        check_res = verify_pose_and_quality(latest_img, expected_pose, active_prof, check_liveness=True)
                        if check_res["status"] == "fail":
                            st.error(check_res["reason"])
                        else:
                            st.session_state.play_sound_trigger = True
                            st.session_state.flash_end_time = time.time() + 0.6
                            if step == 1:
                                st.session_state.enroll_front = latest_img.copy()
                                st.session_state.enroll_step = 2
                            elif step == 2:
                                st.session_state.enroll_left = latest_img.copy()
                                st.session_state.enroll_step = 3
                            elif step == 3:
                                st.session_state.enroll_right = latest_img.copy()
                                st.session_state.enroll_step = 4
                            st.rerun()
                else:
                    st.error("Please wait until the camera feed is ready.")

# Fetch latest_img reference for compatibility with actions column blocks
latest_img = None
if ctx.state.playing:
    with st.session_state.grabber.frame_lock:
        if st.session_state.grabber.latest_frame is not None:
            latest_img = st.session_state.grabber.latest_frame.copy()
with col_actions:
    with st.container(border=True):
        # Custom high-end segmented tab selection with theme mode toggle side-by-side
        col_tab_item, col_theme_item = st.columns([0.65, 0.35])
        with col_tab_item:
            selected_view = st.radio(
                "Navigation",
                options=["Verify Identity", "Guided Enrollment"],
                label_visibility="collapsed"
            )
            st.session_state.active_view = selected_view
        with col_theme_item:
            theme_options = ["☀️ Light", "🌙 Dark"]
            current_theme_idx = 0 if st.session_state.theme_mode == "light" else 1
            selected_theme = st.selectbox(
                "Theme Mode Selection",
                options=theme_options,
                index=current_theme_idx,
                label_visibility="collapsed"
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
                <div class="clean-empty-text">Awaiting scan. Position your face and click "Start Verification".</div>
            </div>
            """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # TAB: GUIDED ENROLLMENT
    # ---------------------------------------------------------
    else:
        st.markdown('<div class="consumer-title">Register Biometrics</div>', unsafe_allow_html=True)
        st.markdown('<div class="consumer-sub">Follow a quick 3-step capture to secure your biometric profile.</div>', unsafe_allow_html=True)
        
        # Initialize step state
        if "enroll_step" not in st.session_state:
            st.session_state.enroll_step = 1
            st.session_state.enroll_front = None
            st.session_state.enroll_left = None
            st.session_state.enroll_right = None

        step = st.session_state.enroll_step
        
        # Progress Indicator Dots & Wording
        if step == 1:
            step_desc = "Step 1 of 3: Look directly at the camera"
        elif step == 2:
            step_desc = "Step 2 of 3: Slowly turn your head to the left"
        elif step == 3:
            step_desc = "Step 3 of 3: Slowly turn your head to the right"
        else:
            step_desc = "Step 3 of 3: Captures complete"
            
        dot1 = "active" if step == 1 else "completed" if step > 1 else ""
        dot2 = "active" if step == 2 else "completed" if step > 2 else ""
        dot3 = "active" if step == 3 else "completed" if step > 3 else ""

        st.markdown(f"""
        <div class="step-progress-container">
            <span class="step-progress-text">{step_desc}</span>
            <div class="step-progress-dots">
                <div class="step-dot {dot1}"></div>
                <div class="step-dot {dot2}"></div>
                <div class="step-dot {dot3}"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        reg_name = st.text_input("Full Name", key="enroll_name", placeholder="Enter your full name")
        consent = st.checkbox("I agree to store my encrypted facial signature for security logins.", key="enroll_consent")

        # Step Gated buttons (All auto-captured, showing back button guides only)
        if step == 1:
            st.info("Align your face inside the outline to capture automatically.")
        elif step == 2:
            if st.button("◀ Back to Step 1", key="back_to_1"):
                st.session_state.enroll_step = 1
                st.rerun()
        elif step == 3:
            if st.button("◀ Back to Step 2", key="back_to_2"):
                st.session_state.enroll_step = 2
                st.rerun()

        elif step == 4:
            st.markdown("<div style='background: #ECFDF5; border-left:4px solid #10B981; padding: 12px 16px; border-radius: 4px; margin-bottom:15px; font-size:0.85rem; color:#065F46;'>✓ All three photos captured successfully. Click register below to complete.</div>", unsafe_allow_html=True)
            col_btns = st.columns(2)
            with col_btns[0]:
                if st.button("Reset Capture", key="reset_enroll_btn"):
                    st.session_state.enroll_step = 1
                    st.session_state.enroll_front = None
                    st.session_state.enroll_left = None
                    st.session_state.enroll_right = None
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
                                emb_left = get_embedding(st.session_state.enroll_left)
                                emb_right = get_embedding(st.session_state.enroll_right)
                                
                                if emb_front["status"] != "success":
                                    st.error("Frontal capture could not map landmarks.")
                                elif emb_left["status"] != "success":
                                    st.error("Left capture could not map landmarks.")
                                elif emb_right["status"] != "success":
                                    st.error("Right capture could not map landmarks.")
                                else:
                                    user_id = db.insert_user(reg_name, consent_given=consent, actor="consumer_ui")
                                    db.insert_template(user_id, "front", emb_front["embedding"])
                                    db.insert_template(user_id, "left", emb_left["embedding"])
                                    db.insert_template(user_id, "right", emb_right["embedding"])
                                    
                                    st.success(f"Successfully registered your profile, {reg_name}!")
                                    st.balloons()
                                    
                                    st.session_state.enroll_step = 1
                                    st.session_state.enroll_front = None
                                    st.session_state.enroll_left = None
                                    st.session_state.enroll_right = None
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Save failed: {str(e)}")

        # Captured templates list (replaces artifacts list)
        st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.9rem; font-weight:600; color:#0F172A; margin-bottom:12px;'>Your captured photos</div>", unsafe_allow_html=True)
        col_img1, col_img2, col_img3 = st.columns(3)
        with col_img1:
            if st.session_state.enroll_front is not None:
                rgb_f = cv2.cvtColor(st.session_state.enroll_front, cv2.COLOR_BGR2RGB)
                st.image(rgb_f, use_container_width=True)
                st.markdown("<div style='font-size:0.75rem; color:#059669; font-weight:600; text-align:center;'>✓ Front photo</div>", unsafe_allow_html=True)
            else:
                st.markdown('<div class="clean-empty-state" style="padding:15px 5px;"><span class="clean-empty-text" style="font-size:0.75rem;">Front turn</span></div>', unsafe_allow_html=True)
        with col_img2:
            if st.session_state.enroll_left is not None:
                rgb_l = cv2.cvtColor(st.session_state.enroll_left, cv2.COLOR_BGR2RGB)
                st.image(rgb_l, use_container_width=True)
                st.markdown("<div style='font-size:0.75rem; color:#059669; font-weight:600; text-align:center;'>✓ Left turn</div>", unsafe_allow_html=True)
            else:
                st.markdown('<div class="clean-empty-state" style="padding:15px 5px;"><span class="clean-empty-text" style="font-size:0.75rem;">Left turn</span></div>', unsafe_allow_html=True)
        with col_img3:
            if st.session_state.enroll_right is not None:
                rgb_r = cv2.cvtColor(st.session_state.enroll_right, cv2.COLOR_BGR2RGB)
                st.image(rgb_r, use_container_width=True)
                st.markdown("<div style='font-size:0.75rem; color:#059669; font-weight:600; text-align:center;'>✓ Right turn</div>", unsafe_allow_html=True)
            else:
                st.markdown('<div class="clean-empty-state" style="padding:15px 5px;"><span class="clean-empty-text" style="font-size:0.75rem;">Right turn</span></div>', unsafe_allow_html=True)
                


# ---------------------------------------------------------
# BOTTOM EXPANDER: REGULATORY COMPLIANCE & ADMIN AUDITS
# ---------------------------------------------------------
st.markdown("<hr style='margin: 30px 0;'>", unsafe_allow_html=True)
with st.expander("🛠️ System Management & Audits (Admin/Compliance Review)", expanded=False):
    st.markdown("### GDPR & BIPA Compliance Console")
    st.write("Review consent logs, template query audits, and execute biometric deletions.")
    
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
            format_func=lambda x: profile_options_desc[x]
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

# ---------------------------------------------------------
# ACTIVE RERUN TRIGGER LOOP
# ---------------------------------------------------------
if ctx.state.playing and run_realtime_loop:
    time.sleep(0.08) # ~12.5 checks/second
    st.rerun()
