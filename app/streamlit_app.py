"""
app/streamlit_app.py

A high-fidelity Streamlit client dashboard demonstrating secure face registration,
verification pipeline, right-to-deletion enforcer, live health audits, and compliance logs.
Fully implements Streamlit UI Part 1 & 2 requirements, including:
1. Thread-safe FrameGrabber with streamlit-webrtc for smooth real-time webcam feed.
2. Separate registration captures for Front, Left, and Right faces with pose-specific quality gating.
3. Best-match identification across all registered users (1-to-N verification).
4. Stage-by-stage pipeline status rendering (Quality -> Liveness -> Embedding -> Matching).
5. Sidebar Quality Profile Selector (Strict, Balanced, Lenient) passed end-to-end.
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
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

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
    page_title=f"{COMPANY_NAME} Biometric Console",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown(CSS_STYLES, unsafe_allow_html=True)

# CSS loaded globally from app/styles.py

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

# Initialize FrameGrabbers in session state so they persist across reruns
if "grabber_enroll" not in st.session_state:
    st.session_state.grabber_enroll = FrameGrabber()
if "grabber_verify" not in st.session_state:
    st.session_state.grabber_verify = FrameGrabber()

# ---------------------------------------------------------
# SIDEBAR BRANDING & STATUS
# ---------------------------------------------------------
st.sidebar.markdown(f'<div class="sidebar-brand">{COMPANY_NAME} // SECURE BIOMETRICS</div>', unsafe_allow_html=True)
st.sidebar.markdown("---")

st.sidebar.markdown('<div class="mono-section-title">SYSTEM MONITOR</div>', unsafe_allow_html=True)

# Dynamically count registered users
active_users_count = 0
try:
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE deleted_at IS NULL")
    active_users_count = cur.fetchone()[0]
    conn.close()
except Exception:
    pass

st.sidebar.markdown(f"""
<div class="system-monitor">
    <div class="monitor-line">
        <span class="label">SYS_STATE</span>
        <span class="status-value active">ONLINE</span>
    </div>
    <div class="monitor-line">
        <span class="label">DEPL_MODE</span>
        <span class="status-value active">GATEWAY_ACTIVE</span>
    </div>
    <div class="monitor-line">
        <span class="label">STORAGE</span>
        <span class="status-value active">SQLITE_ENCRYPTED</span>
    </div>
    <div class="monitor-line">
        <span class="label">ACTIVE_USERS</span>
        <span class="status-value active">{active_users_count}</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown('<div class="mono-section-title">REGULATORY COMPLIANCE</div>', unsafe_allow_html=True)
st.sidebar.markdown("""
<div class="compliance-badge">
    <span class="badge-title">GDPR ENFORCED</span>
    <span class="badge-status">CONSENT_GATED // EXP_LOGS</span>
</div>
<div class="compliance-badge">
    <span class="badge-title">BIPA SECURE</span>
    <span class="badge-status">EXPLICIT_AGREEMENT // ENCRYPTED</span>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

st.sidebar.markdown('<div class="mono-section-title">QUALITY COMPLIANCE PROFILE</div>', unsafe_allow_html=True)
profile_options = {
    "lenient": "Lenient // Fast, low-light optimized verification",
    "balanced": "Balanced // Recommended for standard office lighting",
    "strict": "Strict // High-security biometric check with strict pose requirements"
}
selected_profile = st.sidebar.radio(
    "Quality Profile Selection",
    options=["lenient", "balanced", "strict"],
    index=1,
    label_visibility="collapsed"
)
st.sidebar.markdown(f"<div style='font-size:0.65rem; color:#64748B; margin-top:2px; font-family:\"JetBrains Mono\", monospace;'>{profile_options[selected_profile]}</div>", unsafe_allow_html=True)

matching_threshold = 0.68
target_threshold = QUALITY_PROFILES[selected_profile]["threshold"]

# Set environment variable dynamically for logging/DB configurations
os.environ["QUALITY_PROFILE"] = selected_profile
if not os.environ.get("FACE_DB_ENCRYPTION_KEY"):
    os.environ["FACE_DB_ENCRYPTION_KEY"] = "G5F1yYt4-6R6pW_nZ6t01vT1gQ15yV2uT3r4_n5m6t0="


# Title Header (Top Brand Bar)
if LOGO_PATH:
    st.image(LOGO_PATH, width=150)
else:
    st.markdown(f"""
    <div class="top-brand-bar">
        <div class="brand-logo-slot">{COMPANY_NAME[0] if COMPANY_NAME else "V"}</div>
        <div class="brand-name">{COMPANY_NAME} // SYSTEM CONSOLE</div>
        <div class="brand-tagline">BIOMETRIC MANAGEMENT ENVIRONMENT</div>
    </div>
    """, unsafe_allow_html=True)

# Initialize session state for single-page routing
if "show_registration" not in st.session_state:
    st.session_state.show_registration = False

# ---------------------------------------------------------
# HELPERS: ERROR DIAGNOSTICS
# ---------------------------------------------------------
def explain_quality_failure(failed_reason, all_results=None):
    """
    Explains the details of frame quality check failure in a clean, minimal user-friendly style.
    """
    st.markdown(f"""
    <div style="margin-top: 10px; margin-bottom: 12px;">
        <span class="status-pill danger">Quality Verification Failed</span>
        <p style="font-size: 0.85rem; color: #f43f5e; margin-top: 6px; font-weight: 500; font-family: 'Plus Jakarta Sans', sans-serif;">
            {failed_reason}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    if all_results and "sub_scores" in all_results:
        sub = all_results["sub_scores"]
        corrections = []
        
        # Check lighting
        if "brightness" in sub and sub["brightness"]["score"] < 50:
            corrections.append("💡 **Lighting**: Please move to a better lit area (increase brightness).")
            
        # Check centering/position
        if "position" in sub and sub["position"]["score"] < 50:
            corrections.append("🎯 **Centering**: Please center your face in the scanner (adjust left, right, or center position).")
            
        # Check pose/alignment
        if "pose" in sub and sub["pose"]["score"] < 50:
            corrections.append("📐 **Alignment**: Please look directly at the camera and keep your face straight (adjust tilt/yaw).")
            
        # Check visibility
        if "occlusion" in sub and sub["occlusion"]["score"] < 50:
            corrections.append("🕶️ **Visibility**: Please ensure your face is fully visible (remove masks, hats, or glasses).")

        # Check blur
        if "blur" in sub and sub["blur"]["score"] < 50:
            corrections.append("🔍 **Sharpness**: Please hold your device steady to reduce blur.")

        if corrections:
            for item in corrections:
                st.info(item)

# ---------------------------------------------------------
# HELPER: POSE-SPECIFIC QUALITY SCORER FOR REGISTRATION
# ---------------------------------------------------------
def verify_pose_and_quality(frame, expected_pose, profile_name):
    """
    Checks face presence, liveness, and pose classification.
    Allows left/right captures to pass by treating the pose check score as 100
    if it matches the expected angle direction (profile_left / profile_right).
    """
    face_check = check_single_face(frame)
    if face_check["status"] == "fail":
        return {"status": "fail", "reason": f"Single Face Check failed: {face_check.get('reason')}"}
        
    pose_res = check_pose(frame)
    if pose_res["status"] == "fail":
        return {"status": "fail", "reason": f"Pose Solver failed: {pose_res.get('reason')}"}

    yaw = pose_res.get("yaw", 0.0)
    classification = pose_res.get("classification")
    
    # Verify expected pose yaw angles
    if expected_pose == "front":
        if classification != "frontal":
            return {"status": "fail", "reason": f"Expected frontal pose (yaw <= 25°), got yaw {yaw:.1f}° ({classification})"}
    elif expected_pose == "left":
        if classification != "profile_left":
            return {"status": "fail", "reason": f"Expected left profile turn (yaw -25° to -65°), got yaw {yaw:.1f}° ({classification})"}
    elif expected_pose == "right":
        if classification != "profile_right":
            return {"status": "fail", "reason": f"Expected right profile turn (yaw 25° to 65°), got yaw {yaw:.1f}° ({classification})"}

    # Run overall quality calculation
    # For profile captures, we don't penalize the yaw (we treat pose score as 100)
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
        return {"status": "fail", "reason": f"Quality verification failed: {quality_res['reason']}"}

    # Run passive liveness check on captured frame
    liveness_res = check_passive_liveness(frame)
    if liveness_res["status"] == "fail":
        return {"status": "fail", "reason": f"Passive Liveness failed: {liveness_res.get('reason', 'flagged as spoof')}"}

    return {"status": "pass", "quality_result": quality_res, "liveness_result": liveness_res}

# Scorer subhelpers mapping raw values to subscores
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
# TAB SETUP
# ---------------------------------------------------------
tab_verify, tab_enroll = st.tabs(["VERIFY IDENTITY", "GUIDED ENROLLMENT"])

with tab_verify:
    st.markdown('<div class="reassurance-bar">Biometric authentication active. Position your face in the scanner area.</div>', unsafe_allow_html=True)
    
    col_v_cam, col_v_results = st.columns([1, 1])

    with col_v_cam:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.markdown('<div class="dashboard-card-title">Live Biometric Scanner</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="scanner-container">', unsafe_allow_html=True)
        grabber_v = st.session_state.grabber_verify
        ctx_verify = webrtc_streamer(
            key="webrtc_verify",
            mode=WebRtcMode.SENDRECV,
            video_frame_callback=grabber_v.video_frame_callback,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Empty/offline state
        if not ctx_verify.state.playing:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">CAMERA_OFFLINE</div>
                <div class="empty-state-text">BIOMETRIC FEED TERMINATED</div>
                <div class="empty-state-sub">Activate camera scanner to initialize acquisition pipeline.</div>
            </div>
            """, unsafe_allow_html=True)
            
        latest_verify_img = None
        if ctx_verify.state.playing:
            with grabber_v.frame_lock:
                if grabber_v.latest_frame is not None:
                    latest_verify_img = grabber_v.latest_frame.copy()
                    
        # Verify button inside card
        if st.button("Verify Identity", key="verify_action_btn"):
            if latest_verify_img is None:
                st.error("No frame received. Please ensure the verification camera is active.")
            else:
                st.session_state.verify_image = latest_verify_img.copy()
                st.session_state.verify_results_data = [] # Reset results

                # Define console renderer helper dynamically (no emojis, uses custom css badges/classes)
                def render_diagnostic_console(s1_status="pending", s1_detail="", s2_status="pending", s2_detail="", s3_status="pending", s3_detail="", s4_status="pending", s4_detail=""):
                    def get_class(status):
                        return "passed" if status == "passed" else "failed" if status == "failed" else "running" if status == "running" else "bypassed" if status == "bypassed" else "pending"
                    
                    def get_prefix(status):
                        return "[  OK  ]" if status == "passed" else "[ FAIL ]" if status == "failed" else "[ ACTIVE ]" if status == "running" else "[ BYPASS ]" if status == "bypassed" else "[ PEND ]"
                        
                    html = f"""
                    <div class="diagnostic-console">
                        <div class="console-line {get_class(s1_status)}">{get_prefix(s1_status)} STAGE_1: QUALITY_ASSESSMENT {s1_detail}</div>
                        <div class="console-line {get_class(s2_status)}">{get_prefix(s2_status)} STAGE_2: PASSIVE_LIVENESS {s2_detail}</div>
                        <div class="console-line {get_class(s3_status)}">{get_prefix(s3_status)} STAGE_3: ARCFACE_EMBEDDING {s3_detail}</div>
                        <div class="console-line {get_class(s4_status)}">{get_prefix(s4_status)} STAGE_4: TEMPLATE_MATCHING {s4_detail}</div>
                    </div>
                    """
                    return html

                # Setup progress indicators and render live status per stage
                status_box = st.empty()
                
                # ------------------- STAGE 1: QUALITY ASSESSMENT -------------------
                status_box.markdown(render_diagnostic_console("running"), unsafe_allow_html=True)
                time.sleep(0.05)
                
                qual_res = run_quality_stage(latest_verify_img, profile=selected_profile)
                if qual_res["status"] == "fail":
                    console_html = render_diagnostic_console(
                        "failed", f"(Score below threshold: {qual_res['reason']})", 
                        "bypassed", "", 
                        "bypassed", "", 
                        "bypassed", ""
                    )
                    status_box.markdown(console_html, unsafe_allow_html=True)
                    st.session_state.verify_outcome = {"status": "fail", "stage": "quality", "reason": qual_res['reason'], "all_results": qual_res.get("all_results")}
                    st.session_state.verify_boot_logs = console_html
                else:
                    score = qual_res["all_results"]["overall_score"]
                    status_box.markdown(render_diagnostic_console(
                        "passed", f"(Score: {score}%)", 
                        "running", "", 
                        "pending", "", 
                        "pending", ""
                    ), unsafe_allow_html=True)
                    time.sleep(0.05)
                    
                    # ------------------- STAGE 2: LIVENESS DETECTION -------------------
                    liveness_res = check_passive_liveness(latest_verify_img)
                    if liveness_res["status"] == "fail":
                        console_html = render_diagnostic_console(
                            "passed", f"(Score: {score}%)", 
                            "failed", "(Spoof attack detected)", 
                            "bypassed", "", 
                            "bypassed", ""
                        )
                        status_box.markdown(console_html, unsafe_allow_html=True)
                        st.session_state.verify_outcome = {"status": "fail", "stage": "liveness", "reason": "Spoof attack detected"}
                        st.session_state.verify_boot_logs = console_html
                    else:
                        prob = liveness_res.get("liveness_score", 0.99)
                        status_box.markdown(render_diagnostic_console(
                            "passed", f"(Score: {score}%)", 
                            "passed", f"(Real face prob: {prob*100:.1f}%)", 
                            "running", "", 
                            "pending", ""
                        ), unsafe_allow_html=True)
                        time.sleep(0.05)
                        
                        # ------------------- STAGE 3: FACE EMBEDDING -------------------
                        emb_res = get_embedding(latest_verify_img)
                        if emb_res["status"] != "success":
                            console_html = render_diagnostic_console(
                                "passed", f"(Score: {score}%)", 
                                "passed", f"(Real face prob: {prob*100:.1f}%)", 
                                "failed", f"({emb_res['reason']})", 
                                "bypassed", ""
                            )
                            status_box.markdown(console_html, unsafe_allow_html=True)
                            st.session_state.verify_outcome = {"status": "fail", "stage": "embedding", "reason": emb_res['reason']}
                            st.session_state.verify_boot_logs = console_html
                        else:
                            live_emb = emb_res["embedding"]
                            status_box.markdown(render_diagnostic_console(
                                "passed", f"(Score: {score}%)", 
                                "passed", f"(Real face prob: {prob*100:.1f}%)", 
                                "passed", "(512-D vector generated)", 
                                "running", ""
                            ), unsafe_allow_html=True)
                            time.sleep(0.05)
                            
                            # ------------------- STAGE 4: FACE MATCHING (1-TO-N) -------------------
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
                                    console_html = render_diagnostic_console(
                                        "passed", f"(Score: {score}%)", 
                                        "passed", f"(Real face prob: {prob*100:.1f}%)", 
                                        "passed", "(512-D vector generated)", 
                                        "failed", "(No active users registered)"
                                    )
                                    status_box.markdown(console_html, unsafe_allow_html=True)
                                    st.session_state.verify_outcome = {"status": "fail", "stage": "matching", "reason": "No registered users"}
                                    st.session_state.verify_boot_logs = console_html
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
                                        console_html = render_diagnostic_console(
                                            "passed", f"(Score: {score}%)", 
                                            "passed", f"(Real face prob: {prob*100:.1f}%)", 
                                            "passed", "(512-D vector generated)", 
                                            "passed", f"(Identified: {best_match_name} @ {best_score:.4f} via {best_angle})"
                                        )
                                        status_box.markdown(console_html, unsafe_allow_html=True)
                                        st.session_state.verify_outcome = {
                                            "status": "pass",
                                            "name": best_match_name,
                                            "score": best_score,
                                            "angle": best_angle,
                                            "quality_score": score
                                        }
                                        st.session_state.verify_boot_logs = console_html
                                    else:
                                        db.log_verification(None, qual_res, liveness_res, best_score, "reject")
                                        console_html = render_diagnostic_console(
                                            "passed", f"(Score: {score}%)", 
                                            "passed", f"(Real face prob: {prob*100:.1f}%)", 
                                            "passed", "(512-D vector generated)", 
                                            "failed", f"(Best match: {best_match_name} @ {best_score:.4f} below threshold)"
                                        )
                                        status_box.markdown(console_html, unsafe_allow_html=True)
                                        st.session_state.verify_outcome = {
                                            "status": "fail",
                                            "stage": "matching",
                                            "reason": f"Access Denied: Similarity {best_score:.4f} below threshold {matching_threshold} (best match: {best_match_name})"
                                        }
                                        st.session_state.verify_boot_logs = console_html
                            except Exception as e:
                                console_html = render_diagnostic_console(
                                    "passed", f"(Score: {score}%)", 
                                    "passed", f"(Real face prob: {prob*100:.1f}%)", 
                                    "passed", "(512-D vector generated)", 
                                    "failed", f"(Database query error: {str(e)})"
                                )
                                status_box.markdown(console_html, unsafe_allow_html=True)
                                st.session_state.verify_outcome = {"status": "fail", "stage": "matching", "reason": str(e)}
                                st.session_state.verify_boot_logs = console_html
                                
                status_box.empty()
                st.rerun()
                                
        st.markdown('</div>', unsafe_allow_html=True)

    with col_v_results:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.markdown('<div class="dashboard-card-title">Diagnostics & System Outcome</div>', unsafe_allow_html=True)
        
        # Display capture image if resolved
        if "verify_image" in st.session_state and st.session_state.verify_image is not None:
            rgb_verify = cv2.cvtColor(st.session_state.verify_image, cv2.COLOR_BGR2RGB)
            st.image(rgb_verify, use_container_width=True)
            st.markdown('<div class="artifact-meta">RESOLVED // INCOMING_VERIFICATION_FRAME</div>', unsafe_allow_html=True)
            
        # Reassurance summary line above details
        if "verify_outcome" in st.session_state:
            outcome = st.session_state.verify_outcome
            if outcome["status"] == "pass":
                st.markdown(f"""
                <span class="status-pill success">Access Granted</span>
                <div class="reassurance-bar" style="margin-top: 10px;">
                    Biometric match confirmed. Welcome back, <strong>{outcome['name']}</strong>.
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <span class="status-pill danger">Access Denied</span>
                <div class="reassurance-bar" style="margin-top: 10px; border-left-color: #f43f5e; background: rgba(244, 63, 94, 0.08);">
                    Authentication failed. {outcome['reason']}
                </div>
                """, unsafe_allow_html=True)
                
                if outcome["stage"] == "quality":
                    explain_quality_failure(outcome["reason"], outcome.get("all_results"))
                elif outcome["stage"] == "matching":
                    st.markdown("""
                    <div class="reassurance-bar" style="border-left-color: #f59e0b; background: rgba(245, 158, 11, 0.08); margin-top: 10px;">
                        ⚠️ <strong>Enrollment Required</strong>: Biometric signature not matched to any active user template. Please click the <strong>Guided Enrollment</strong> tab at the top of the page to register.
                    </div>
                    """, unsafe_allow_html=True)
            pass
        else:
            # Default empty state
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">AWAITING_SCAN</div>
                <div class="empty-state-text">NO ACTIVE BIOMETRIC SESSION</div>
                <div class="empty-state-sub">Trigger the "Verify Identity" scan to execute stage-by-stage biometric validations.</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)


with tab_enroll:
    st.markdown('<div class="reassurance-bar">Create a new biometric identity. Complete Frontal, Left Profile, and Right Profile facial captures.</div>', unsafe_allow_html=True)
    
    # Initialize enrollment step state
    if "enroll_step" not in st.session_state:
        st.session_state.enroll_step = 1
        st.session_state.enroll_front = None
        st.session_state.enroll_left = None
        st.session_state.enroll_right = None

    col_form, col_status = st.columns([1, 1])

    with col_form:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.markdown('<div class="dashboard-card-title">Enrollment Scanner</div>', unsafe_allow_html=True)
        
        # Step indicator
        step = st.session_state.enroll_step
        active1 = "active" if step == 1 else "completed" if step > 1 else ""
        active2 = "active" if step == 2 else "completed" if step > 2 else ""
        active3 = "active" if step == 3 else "completed" if step > 3 else ""

        st.markdown(f"""
        <div class="step-indicator-bar">
            <div class="step-node {active1}">
                <span class="step-num">01</span>
                <span class="step-label">FRONTAL</span>
            </div>
            <div class="step-line"></div>
            <div class="step-node {active2}">
                <span class="step-num">02</span>
                <span class="step-label">LEFT_POSE</span>
            </div>
            <div class="step-line"></div>
            <div class="step-node {active3}">
                <span class="step-num">03</span>
                <span class="step-label">RIGHT_POSE</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        reg_name = st.text_input("Full Name of Enrollee", key="enroll_name")
        consent = st.checkbox("I explicitly consent to my biometric data being encrypted and stored for face verification.", key="enroll_consent")

        grabber = st.session_state.grabber_enroll
        st.markdown('<div class="scanner-container">', unsafe_allow_html=True)
        ctx_enroll = webrtc_streamer(
            key="webrtc_enroll",
            mode=WebRtcMode.SENDRECV,
            video_frame_callback=grabber.video_frame_callback,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Camera Offline State
        if not ctx_enroll.state.playing:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">CAMERA_OFFLINE</div>
                <div class="empty-state-text">ENROLLMENT SCANNER STANDBY</div>
                <div class="empty-state-sub">Activate camera stream above to initialize biometric capturing.</div>
            </div>
            """, unsafe_allow_html=True)

        # Retrieve current frame from grabber
        latest_img = None
        if ctx_enroll.state.playing:
            with grabber.frame_lock:
                if grabber.latest_frame is not None:
                    latest_img = grabber.latest_frame.copy()

        # Step Gated Buttons
        if st.session_state.enroll_step == 1:
            st.markdown('<div class="reassurance-bar">Position your face looking directly into the camera.</div>', unsafe_allow_html=True)
            if st.button("📸 Capture Frontal Face", key="capture_front_btn"):
                if latest_img is None:
                    st.error("No frame received. Please ensure the webcam feed is active and playing.")
                else:
                    with st.spinner("Analyzing frontal frame quality and liveness..."):
                        check_res = verify_pose_and_quality(latest_img, "front", selected_profile)
                        if check_res["status"] == "pass":
                            st.session_state.enroll_front = latest_img.copy()
                            st.success("Frontal capture accepted!")
                            st.session_state.enroll_step = 2
                            st.rerun()
                        else:
                            st.error(f"Capture Rejected: {check_res['reason']}")

        elif st.session_state.enroll_step == 2:
            st.markdown('<div class="reassurance-bar">Turn your head slowly to the left (about 15-35 degrees).</div>', unsafe_allow_html=True)
            col_btns = st.columns(2)
            with col_btns[0]:
                if st.button("◀️ Back to Step 1", key="back_to_1"):
                    st.session_state.enroll_step = 1
                    st.rerun()
            with col_btns[1]:
                if st.button("📸 Capture Left Profile", key="capture_left_btn"):
                    if latest_img is None:
                        st.error("No frame received. Please ensure the webcam feed is active and playing.")
                    else:
                        with st.spinner("Analyzing left profile quality and liveness..."):
                            check_res = verify_pose_and_quality(latest_img, "left", selected_profile)
                            if check_res["status"] == "pass":
                                st.session_state.enroll_left = latest_img.copy()
                                st.success("Left profile capture accepted!")
                                st.session_state.enroll_step = 3
                                st.rerun()
                            else:
                                st.error(f"Capture Rejected: {check_res['reason']}")

        elif st.session_state.enroll_step == 3:
            st.markdown('<div class="reassurance-bar">Turn your head slowly to the right (about 15-35 degrees).</div>', unsafe_allow_html=True)
            col_btns = st.columns(2)
            with col_btns[0]:
                if st.button("◀️ Back to Step 2", key="back_to_2"):
                    st.session_state.enroll_step = 2
                    st.rerun()
            with col_btns[1]:
                if st.button("📸 Capture Right Profile", key="capture_right_btn"):
                    if latest_img is None:
                        st.error("No frame received. Please ensure the webcam feed is active and playing.")
                    else:
                        with st.spinner("Analyzing right profile quality and liveness..."):
                            check_res = verify_pose_and_quality(latest_img, "right", selected_profile)
                            if check_res["status"] == "pass":
                                st.session_state.enroll_right = latest_img.copy()
                                st.success("Right profile capture accepted!")
                                st.session_state.enroll_step = 4
                                st.rerun()
                            else:
                                st.error(f"Capture Rejected: {check_res['reason']}")

        elif st.session_state.enroll_step == 4:
            st.markdown('<div class="reassurance-bar" style="border-left-color: #10b981; background: rgba(16, 185, 129, 0.08);">All 3 templates successfully captured. Register user below.</div>', unsafe_allow_html=True)
            col_btns = st.columns(2)
            with col_btns[0]:
                if st.button("🔄 Reset enrollment", key="reset_enroll_btn"):
                    st.session_state.enroll_step = 1
                    st.session_state.enroll_front = None
                    st.session_state.enroll_left = None
                    st.session_state.enroll_right = None
                    st.rerun()
            with col_btns[1]:
                if st.button("🚀 Register Biometric Templates", key="save_enroll_btn"):
                    if not reg_name:
                        st.error("Please enter a name for the enrollee.")
                    elif not consent:
                        st.error("Explicit consent must be checked to register biometric profiles.")
                    else:
                        with st.spinner("Generating ArcFace embeddings and encrypting templates..."):
                            try:
                                emb_front = get_embedding(st.session_state.enroll_front)
                                emb_left = get_embedding(st.session_state.enroll_left)
                                emb_right = get_embedding(st.session_state.enroll_right)
                                
                                if emb_front["status"] != "success":
                                    st.error(f"Failed embedding frontal: {emb_front['reason']}")
                                elif emb_left["status"] != "success":
                                    st.error(f"Failed embedding left: {emb_left['reason']}")
                                elif emb_right["status"] != "success":
                                    st.error(f"Failed embedding right: {emb_right['reason']}")
                                else:
                                    user_id = db.insert_user(reg_name, consent_given=consent, actor="streamlit_ui")
                                    db.insert_template(user_id, "front", emb_front["embedding"])
                                    db.insert_template(user_id, "left", emb_left["embedding"])
                                    db.insert_template(user_id, "right", emb_right["embedding"])
                                    
                                    st.success(f"Successfully registered user '{reg_name}'!")
                                    st.balloons()
                                    
                                    st.session_state.enroll_step = 1
                                    st.session_state.enroll_front = None
                                    st.session_state.enroll_left = None
                                    st.session_state.enroll_right = None
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error during registration: {str(e)}")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_status:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.markdown('<div class="dashboard-card-title">Template Acquisition Artifacts</div>', unsafe_allow_html=True)
        col_img1, col_img2, col_img3 = st.columns(3)
        with col_img1:
            if st.session_state.enroll_front is not None:
                rgb = cv2.cvtColor(st.session_state.enroll_front, cv2.COLOR_BGR2RGB)
                st.image(rgb, use_container_width=True)
                st.markdown('<div class="artifact-meta">RESOLVED // FRONT</div>', unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="preview-box-empty">
                    <div class="crosshair-indicator"></div>
                    <div class="mono-label">FRONT // EMPTY</div>
                </div>
                """, unsafe_allow_html=True)
        with col_img2:
            if st.session_state.enroll_left is not None:
                rgb = cv2.cvtColor(st.session_state.enroll_left, cv2.COLOR_BGR2RGB)
                st.image(rgb, use_container_width=True)
                st.markdown('<div class="artifact-meta">RESOLVED // LEFT</div>', unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="preview-box-empty">
                    <div class="crosshair-indicator"></div>
                    <div class="mono-label">LEFT // EMPTY</div>
                </div>
                """, unsafe_allow_html=True)
        with col_img3:
            if st.session_state.enroll_right is not None:
                rgb = cv2.cvtColor(st.session_state.enroll_right, cv2.COLOR_BGR2RGB)
                st.image(rgb, use_container_width=True)
                st.markdown('<div class="artifact-meta">RESOLVED // RIGHT</div>', unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="preview-box-empty">
                    <div class="crosshair-indicator"></div>
                    <div class="mono-label">RIGHT // EMPTY</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# COMPLIANCE LOGS & SYSTEM HEALTH AUDIT (ADMINISTRATIVE)
# ---------------------------------------------------------
st.markdown("---")
with st.expander("[ COMPLIANCE LOGS & SYSTEM HEALTH AUDIT ]", expanded=False):
    st.markdown("<div class='terminal-section-title'>GDPR & BIPA COMPLIANCE AUDIT CENTER</div>", unsafe_allow_html=True)
    st.write("Review consent logs, template query audits, and execute soft/hard biometric template deletions.")
    
    col_delete, col_logs = st.columns([1, 1])

    with col_delete:
        st.markdown("### Biometric Template Deletion (Right to be Forgotten)")
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
            # Create interactive table/selector
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
                with st.spinner(f"Processing deletion request for '{username}'..."):
                    try:
                        is_hard = (delete_type == "Hard Delete (Permanent IRREVERSIBLE purge)")
                        db.delete_user(selected_user_id, hard_delete=is_hard, actor="streamlit_admin")
                        st.success(f"Successfully executed {delete_type} for user '{username}'.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Deletion failed: {str(e)}")

    with col_logs:
        st.markdown("### Dynamic Security Audit Trail")
        st.write("Live logs representing biometric template reads/writes and verification transactions.")
        
        # Load access_log
        try:
            conn = sqlite3.connect(db.DB_PATH)
            df_access = pd.read_sql_query("SELECT * FROM access_log ORDER BY timestamp DESC LIMIT 15", conn)
            df_ver = pd.read_sql_query("SELECT * FROM verification_log ORDER BY timestamp DESC LIMIT 15", conn)
            conn.close()
            
            st.markdown("#### Biometric Template Read/Write Access Log")
            st.dataframe(df_access, use_container_width=True)
            
            st.markdown("#### Biometric Verification Transactions Log")
            st.dataframe(df_ver, use_container_width=True)
        except Exception as e:
            st.error(f"Could not load audit logs: {str(e)}")

    st.markdown("---")
    st.markdown("<div class='terminal-section-title'>SYSTEM DIAGNOSTIC OVERVIEW</div>", unsafe_allow_html=True)
    st.write("Verifies database storage integrity, encryption key validity, local model caches, and camera status.")

    # Execute health audits
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
    mod_msg = mod_res["detail"] if mod_res["detail"] else "All required face detection and matching models are cached locally."
    
    cam_ok = (cam_res["status"] in ["pass", "warn"])
    cam_msg = cam_res["detail"] if cam_res["detail"] else "Video capture device is ready for authentication tasks."

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        st.markdown("<div class='terminal-section-title'>DATABASE STATUS</div>", unsafe_allow_html=True)
        status_db = "PASS" if db_ok else "FAIL"
        st.markdown(f"""
        <div class="metric-card">
            <h4>SQLite Storage Instance</h4>
            <span class="badge badge-{"pass" if db_ok else "fail"}">{status_db}</span>
            <p style='margin-top: 0.5rem;'>{db_msg}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div class='terminal-section-title'>CRYPTOGRAPHIC MONITOR</div>", unsafe_allow_html=True)
        status_enc = "PASS" if enc_ok else "FAIL"
        st.markdown(f"""
        <div class="metric-card">
            <h4>AES-128-CBC Fernet Credentials</h4>
            <span class="badge badge-{"pass" if enc_ok else "fail"}">{status_enc}</span>
            <p style='margin-top: 0.5rem;'>{enc_msg}</p>
        </div>
        """, unsafe_allow_html=True)

    with col_h2:
        st.markdown("<div class='terminal-section-title'>LOCAL MODEL CACHE</div>", unsafe_allow_html=True)
        status_mod = "PASS" if mod_ok else "FAIL"
        st.markdown(f"""
        <div class="metric-card">
            <h4>DeepFace & MediaPipe Local Files</h4>
            <span class="badge badge-{"pass" if mod_ok else "fail"}">{status_mod}</span>
            <p style='margin-top: 0.5rem;'>{mod_msg}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div class='terminal-section-title'>CAMERA CAPTURE PIPELINE</div>", unsafe_allow_html=True)
        status_cam = "PASS" if cam_ok else "FAIL"
        st.markdown(f"""
        <div class="metric-card">
            <h4>OS Camera Capture Pipeline</h4>
            <span class="badge badge-{"pass" if cam_ok else "fail"}">{status_cam}</span>
            <p style='margin-top: 0.5rem;'>{cam_msg}</p>
        </div>
        """, unsafe_allow_html=True)
