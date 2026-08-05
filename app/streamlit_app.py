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
from streamlit_webrtc import webrtc_streamer, WebRtcMode

# Setup paths and ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
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
from app.styles import CSS_STYLES

st.set_page_config(
    page_title=f"{COMPANY_NAME} Authentication",
    page_icon="👤",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown(CSS_STYLES, unsafe_allow_html=True)

# ---------------------------------------------------------
# STREAMLIT WEBRTC FRAME GRABBER
# ---------------------------------------------------------
# Define thread-safe video frame grabber to keep processing out of recv() callback
class FrameGrabber:
    def __init__(self):
        self.frame_lock = threading.Lock()
        self.latest_frame = None

    def video_frame_callback(self, frame):
        img = frame.to_ndarray(format="bgr24")
        with self.frame_lock:
            self.latest_frame = img
        return frame

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

matching_threshold = 0.68
target_threshold = QUALITY_PROFILES[selected_profile]["threshold"]

if not os.environ.get("FACE_DB_ENCRYPTION_KEY"):
    os.environ["FACE_DB_ENCRYPTION_KEY"] = "G5F1yYt4-6R6pW_nZ6t01vT1gQ15yV2uT3r4_n5m6t0="

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

def verify_pose_and_quality(frame, expected_pose, profile_name):
    """
    Checks face presence, alignment, and quality.
    Translates all raw technical thresholds/errors into user-friendly instructions.
    """
    face_check = check_single_face(frame)
    if face_check["status"] == "fail":
        return {"status": "fail", "reason": "We couldn't find a face. Make sure you are in a well-lit area and looking at the camera."}
        
    pose_res = check_pose(frame)
    if pose_res["status"] == "fail":
        if expected_pose == "left":
            return {"status": "fail", "reason": "Please turn your head a little further to the left."}
        elif expected_pose == "right":
            return {"status": "fail", "reason": "Please turn your head a little further to the right."}
        return {"status": "fail", "reason": "Please look directly at the camera."}

    yaw = pose_res.get("yaw", 0.0)
    classification = pose_res.get("classification")
    
    # Verify expected pose yaw angles
    if expected_pose == "front":
        if classification != "frontal":
            return {"status": "fail", "reason": "Please look straight ahead at the camera."}
    elif expected_pose == "left":
        if classification != "profile_left":
            return {"status": "fail", "reason": "Please turn your head a little further to the left."}
    elif expected_pose == "right":
        if classification != "profile_right":
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

    # Run passive liveness check on captured frame
    liveness_res = check_passive_liveness(frame)
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

# ---------------------------------------------------------
# SPLIT PAGE ARCHITECTURE: PERSISTENT CAMERA + TAB ACTIONS
# ---------------------------------------------------------
col_cam, col_actions = st.columns([1.1, 0.9])

with col_cam:
    st.markdown('<div class="consumer-card">', unsafe_allow_html=True)
    st.markdown('<div class="consumer-title">Camera Feed</div>', unsafe_allow_html=True)
    st.markdown('<div class="consumer-sub">Align your face inside the dashed area below.</div>', unsafe_allow_html=True)
    
    # 1. Continuous single-camera streamer (lightweight constraints for zero lag)
    st.markdown('<div class="camera-wrapper">', unsafe_allow_html=True)
    ctx = webrtc_streamer(
        key="shared_webrtc_camera",
        mode=WebRtcMode.SENDRECV,
        video_frame_callback=st.session_state.grabber.video_frame_callback,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True
    )
    st.markdown('</div>', unsafe_allow_html=True) # Close camera-wrapper
    
    # Determine target state for dynamic guide styling
    instructions_text = "Align your face with the guide"
    overlay_class = ""
    arrow_html = ""
    
    if st.session_state.active_view == "Verify Identity":
        if st.session_state.get("verify_face_detected", False):
            overlay_class = "detected"
    else:
        # Guided Enrollment details
        step = st.session_state.get("enroll_step", 1)
        if step == 1:
            instructions_text = "Look straight ahead at the camera"
            if st.session_state.get("enroll_face_detected_front", False):
                overlay_class = "detected"
        elif step == 2:
            instructions_text = "Slowly turn your head left until you feel a slight stretch, then hold still"
            arrow_html = '<div class="face-arrow face-arrow-left">←</div>'
            if st.session_state.get("enroll_face_detected_left", False):
                overlay_class = "detected"
        elif step == 3:
            instructions_text = "Slowly turn your head right until you feel a slight stretch, then hold still"
            arrow_html = '<div class="face-arrow face-arrow-right">→</div>'
            if st.session_state.get("enroll_face_detected_right", False):
                overlay_class = "detected"
                
    # 2. Render centered face guide overlay unconditionally in the parent DOM (always active)
    st.markdown(f"""
    <div class="face-guide-overlay {overlay_class}">
        <div class="face-oval {overlay_class}">
            {arrow_html}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Render instructions text unconditionally to prevent layout shifts
    status_text = instructions_text if ctx.state.playing else "Camera offline. Please click the start button above to activate the scanner."
    st.markdown(f"""
    <div style="text-align: center; margin-top: 12px; font-size: 0.85rem; color: #64748B; font-weight: 500;">
        {status_text}
    </div>
    """, unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True) # Close consumer-card

# Grab current frame from grabber thread safely
latest_img = None
if ctx.state.playing:
    with st.session_state.grabber.frame_lock:
        if st.session_state.grabber.latest_frame is not None:
            latest_img = st.session_state.grabber.latest_frame.copy()

with col_actions:
    st.markdown('<div class="consumer-card">', unsafe_allow_html=True)
    
    # Custom high-end segmented tab selection
    st.markdown('<div style="margin-bottom: 1.5rem;">', unsafe_allow_html=True)
    selected_view = st.radio(
        "Navigation",
        options=["Verify Identity", "Guided Enrollment"],
        label_visibility="collapsed"
    )
    st.session_state.active_view = selected_view
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ---------------------------------------------------------
    # TAB: VERIFY IDENTITY
    # ---------------------------------------------------------
    if selected_view == "Verify Identity":
        st.markdown('<div class="consumer-title">Welcome</div>', unsafe_allow_html=True)
        st.markdown('<div class="consumer-sub">Scan your face to quickly verify your identity.</div>', unsafe_allow_html=True)
        
        # Verify action triggers
        if st.button("Start Verification", key="verify_action_btn"):
            if latest_img is None:
                st.error("Please turn on the camera to begin verification.")
            else:
                st.session_state.verify_image = latest_img.copy()
                
                # Check quality & face presence
                qual_res = run_quality_stage(latest_img, profile=selected_profile)
                
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
                <div style="margin-top:15px; margin-bottom: 10px;">
                    <span class="status-badge success">✓ Access Granted</span>
                </div>
                <div style="font-size:1rem; font-weight:600; color:#059669;">
                    Identity verified. Welcome back, {outcome['name']}!
                </div>
                """, unsafe_allow_html=True)
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

        # Step Gated buttons
        if step == 1:
            if st.button("Capture Front Photo", key="capture_front_btn"):
                if latest_img is None:
                    st.error("Please turn on the camera first.")
                else:
                    check_res = verify_pose_and_quality(latest_img, "front", selected_profile)
                    if check_res["status"] == "pass":
                        st.session_state.enroll_front = latest_img.copy()
                        st.session_state.enroll_face_detected_front = True
                        st.session_state.enroll_step = 2
                        st.success("Front photo captured successfully!")
                        st.rerun()
                    else:
                        st.session_state.enroll_face_detected_front = False
                        st.error(check_res["reason"])

        elif step == 2:
            col_btns = st.columns(2)
            with col_btns[0]:
                if st.button("◀ Back", key="back_to_1"):
                    st.session_state.enroll_step = 1
                    st.rerun()
            with col_btns[1]:
                if st.button("Capture Left Photo", key="capture_left_btn"):
                    if latest_img is None:
                        st.error("Please turn on the camera first.")
                    else:
                        check_res = verify_pose_and_quality(latest_img, "left", selected_profile)
                        if check_res["status"] == "pass":
                            st.session_state.enroll_left = latest_img.copy()
                            st.session_state.enroll_face_detected_left = True
                            st.session_state.enroll_step = 3
                            st.success("Left profile captured successfully!")
                            st.rerun()
                        else:
                            st.session_state.enroll_face_detected_left = False
                            st.error(check_res["reason"])

        elif step == 3:
            col_btns = st.columns(2)
            with col_btns[0]:
                if st.button("◀ Back", key="back_to_2"):
                    st.session_state.enroll_step = 2
                    st.rerun()
            with col_btns[1]:
                if st.button("Capture Right Photo", key="capture_right_btn"):
                    if latest_img is None:
                        st.error("Please turn on the camera first.")
                    else:
                        check_res = verify_pose_and_quality(latest_img, "right", selected_profile)
                        if check_res["status"] == "pass":
                            st.session_state.enroll_right = latest_img.copy()
                            st.session_state.enroll_face_detected_right = True
                            st.session_state.enroll_step = 4
                            st.success("Right profile captured successfully!")
                            st.rerun()
                        else:
                            st.session_state.enroll_face_detected_right = False
                            st.error(check_res["reason"])

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
                
    st.markdown('</div>', unsafe_allow_html=True) # Close consumer-card

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
    st.markdown("#### System Health Checks")

    from api.health import check_database, check_encryption_key, check_deepface_model_cache, check_camera_available
    
    db_res = check_database()
    enc_res = check_encryption_key()
    mod_res = check_deepface_model_cache()
    cam_res = check_camera_available()
    
    db_ok = (db_res["status"] == "pass")
    db_msg = db_res["detail"] if db_res["detail"] else "Successfully connected to SQLite database."
    
    enc_ok = (enc_res["status"] == "pass")
    enc_msg = enc_res["detail"] if enc_res["detail"] else "Biometric encryption key loaded successfully."
    
    mod_ok = (mod_res["status"] == "pass")
    mod_msg = mod_res["detail"] if mod_res["detail"] else "All required face detection models are cached."
    
    cam_ok = (cam_res["status"] in ["pass", "warn"])
    cam_msg = cam_res["detail"] if cam_res["detail"] else "OS Camera Capture device is ready."

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        st.markdown(f"**SQLite Database**: {'✓ PASS' if db_ok else '✗ FAIL'} ({db_msg})")
        st.markdown(f"**AES-128 Encryption**: {'✓ PASS' if enc_ok else '✗ FAIL'} ({enc_msg})")
    with col_h2:
        st.markdown(f"**Models Cached**: {'✓ PASS' if mod_ok else '✗ FAIL'} ({mod_msg})")
        st.markdown(f"**Camera Ready**: {'✓ PASS' if cam_ok else '✗ FAIL'} ({cam_msg})")
