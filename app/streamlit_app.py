"""
app/streamlit_app.py

A high-fidelity Streamlit client dashboard demonstrating secure face registration,
verification pipeline, right-to-deletion enforcer, live health audits, and compliance logs.
"""
import os
import sys
import streamlit as st
import cv2
import numpy as np
import requests
import sqlite3
import pandas as pd
from PIL import Image
import io

# Ensure src path is available
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import src.db as db

# Page setup
st.set_page_config(
    page_title="Biometric Face Verification Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark-mode premium look
st.markdown("""
<style>
    /* Theme color variables and core styling */
    .stApp {
        background-color: #0E1117;
        color: #E2E8F0;
    }
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-bottom: 0.2rem;
        background: linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #94A3B8;
        margin-bottom: 2rem;
    }
    /* styled card container */
    .metric-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
    }
    .badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        font-size: 0.75rem;
        font-weight: 600;
        border-radius: 9999px;
        text-transform: uppercase;
    }
    .badge-pass { background-color: #059669; color: #ECFDF5; }
    .badge-warn { background-color: #D97706; color: #FEF3C7; }
    .badge-fail { background-color: #DC2626; color: #FEF2F2; }
</style>
""", unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.markdown("### 🛠️ System Configuration")
api_url = st.sidebar.text_input("API Gateway URL", value="http://localhost:8000")
api_key = st.sidebar.text_input("X-API-Key Header", value="dev_shared_secret_api_key", type="password")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Active Quality Profile")
profile_selection = st.sidebar.selectbox(
    "Select Target Threshold Profile",
    options=["lenient", "balanced", "strict"],
    index=1,
    help="Changes the server's threshold preset. Lenient (50%), Balanced (70%), Strict (85%)."
)

# Set environment variable dynamically so the local server picks it up
os.environ["QUALITY_PROFILE"] = profile_selection
os.environ["FACE_API_KEY"] = api_key
os.environ["FACE_DB_ENCRYPTION_KEY"] = os.environ.get("FACE_DB_ENCRYPTION_KEY", "b'G5F1yYt4-6R6pW_nZ6t01vT1gQ15yV2uT3r4_n5m6t0='")

# Title Header
st.markdown('<div class="main-header">Biometric Face Verification Center</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Modular Face Liveness and Registration Gating Engine</div>', unsafe_allow_html=True)

# Tabs
tab_enroll, tab_verify, tab_audit, tab_health = st.tabs([
    "👤 Guided Enrollment",
    "🔍 Identity Verification",
    "🛡️ Compliance & Logs",
    "🏥 Server Health Audit"
])


# ---------------------------------------------------------
# TAB 1: GUIDED ENROLLMENT
# ---------------------------------------------------------
with tab_enroll:
    st.header("Guided Biometric Registration")
    st.write("Enrolls a new user with three distinct templates (front, left profile, right profile) for best-of-three matching.")
    
    # Initialize enrollment session states
    if "enroll_step" not in st.session_state:
        st.session_state.enroll_step = 1
        st.session_state.enroll_front = None
        st.session_state.enroll_left = None
        st.session_state.enroll_right = None

    col_form, col_status = st.columns([1, 1])

    with col_form:
        reg_name = st.text_input("Full Name of Enrollee", key="enroll_name")
        consent = st.checkbox("I explicitly consent to my biometric data being encrypted and stored for face verification.", key="enroll_consent")

        if st.session_state.enroll_step == 1:
            st.info("📸 **Step 1: Frontal Capture** — Face the camera directly. Ensure good lighting.")
            cam_front = st.camera_input("Capture Frontal Face", key="cam_front")
            if cam_front:
                st.session_state.enroll_front = cam_front.getvalue()
                if st.button("Proceed to Left Profile"):
                    st.session_state.enroll_step = 2
                    st.experimental_rerun()

        elif st.session_state.enroll_step == 2:
            st.info("📸 **Step 2: Left Profile Capture** — Turn your head slightly to the left (15-35 degrees).")
            cam_left = st.camera_input("Capture Left Profile Face", key="cam_left")
            if cam_left:
                st.session_state.enroll_left = cam_left.getvalue()
                col_btn = st.columns(2)
                with col_btn[0]:
                    if st.button("Back"):
                        st.session_state.enroll_step = 1
                        st.experimental_rerun()
                with col_btn[1]:
                    if st.button("Proceed to Right Profile"):
                        st.session_state.enroll_step = 3
                        st.experimental_rerun()

        elif st.session_state.enroll_step == 3:
            st.info("📸 **Step 3: Right Profile Capture** — Turn your head slightly to the right (15-35 degrees).")
            cam_right = st.camera_input("Capture Right Profile Face", key="cam_right")
            if cam_right:
                st.session_state.enroll_right = cam_right.getvalue()
                col_btn = st.columns(2)
                with col_btn[0]:
                    if st.button("Back"):
                        st.session_state.enroll_step = 2
                        st.experimental_rerun()
                with col_btn[1]:
                    if st.button("Review & Submit"):
                        st.session_state.enroll_step = 4
                        st.experimental_rerun()

        elif st.session_state.enroll_step == 4:
            st.success("🎉 All captures completed! Please review and submit.")
            
            # Reset Button
            if st.button("Reset Enrollment Process"):
                st.session_state.enroll_step = 1
                st.session_state.enroll_front = None
                st.session_state.enroll_left = None
                st.session_state.enroll_right = None
                st.experimental_rerun()

            # Submit API Call
            if st.button("🚀 Register & Save Encrypted Templates"):
                if not reg_name:
                    st.error("Please enter a name.")
                elif not consent:
                    st.error("Biometric consent must be checked.")
                else:
                    with st.spinner("Submitting templates to secure registration API..."):
                        try:
                            headers = {"X-API-Key": api_key}
                            data = {"name": reg_name, "consent_given": str(consent).lower()}
                            files = {
                                "front_image": ("front.jpg", st.session_state.enroll_front, "image/jpeg"),
                                "left_image": ("left.jpg", st.session_state.enroll_left, "image/jpeg"),
                                "right_image": ("right.jpg", st.session_state.enroll_right, "image/jpeg")
                            }
                            resp = requests.post(f"{api_url}/register", headers=headers, data=data, files=files)
                            
                            if resp.status_code == 200:
                                st.success(f"Successfully enrolled '{reg_name}'! User ID: {resp.json().get('user_id')}")
                                st.balloons()
                                # Reset
                                st.session_state.enroll_step = 1
                                st.session_state.enroll_front = None
                                st.session_state.enroll_left = None
                                st.session_state.enroll_right = None
                            else:
                                st.error(f"Registration Failed: {resp.json().get('detail', 'Unknown error')}")
                        except Exception as e:
                            st.error(f"Could not connect to API server: {str(e)}")

    with col_status:
        st.markdown("### Captured Preview Matrix")
        col_img1, col_img2, col_img3 = st.columns(3)
        with col_img1:
            st.markdown("**Front Face**")
            if st.session_state.enroll_front:
                st.image(st.session_state.enroll_front, use_column_width=True)
            else:
                st.text("Pending capture...")
        with col_img2:
            st.markdown("**Left Profile**")
            if st.session_state.enroll_left:
                st.image(st.session_state.enroll_left, use_column_width=True)
            else:
                st.text("Pending capture...")
        with col_img3:
            st.markdown("**Right Profile**")
            if st.session_state.enroll_right:
                st.image(st.session_state.enroll_right, use_column_width=True)
            else:
                st.text("Pending capture...")


# ---------------------------------------------------------
# TAB 2: IDENTITY VERIFICATION
# ---------------------------------------------------------
with tab_verify:
    st.header("Biometric Identity Verification")
    st.write("Verifies a user's identity by running the full 3-stage validation process (Quality composite score, passive liveness, and face matching).")
    
    # Query database to get all active registered users
    users_list = []
    try:
        conn = sqlite3.connect(db.DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM users WHERE deleted_at IS NULL")
        users_list = [row[0] for row in cur.fetchall()]
        conn.close()
    except Exception as e:
        st.warning("Could not load users list from local database. Make sure SQLite file exists.")

    if not users_list:
        st.warning("No users registered. Please enroll a user first.")
    else:
        col_v_form, col_v_results = st.columns([1, 1])

        with col_v_form:
            claimed_identity = st.selectbox("Select Your Claimed Identity", options=users_list)
            v_image = st.camera_input("Align Face for Verification", key="verify_cam")
            
            if v_image:
                if st.button("🔑 Verify Identity"):
                    with st.spinner("Executing secure 3-stage validation pipeline..."):
                        try:
                            headers = {"X-API-Key": api_key}
                            data = {"name": claimed_identity}
                            files = {"image": ("verify.jpg", v_image.getvalue(), "image/jpeg")}
                            
                            resp = requests.post(f"{api_url}/verify", headers=headers, data=data, files=files)
                            
                            if resp.status_code == 200:
                                st.session_state.verify_response = resp.json()
                            else:
                                st.error(f"Verification Request Failed: {resp.json().get('detail', 'Unknown error')}")
                        except Exception as e:
                            st.error(f"API Connection Error: {str(e)}")

        with col_v_results:
            st.markdown("### Verification Result Details")
            if "verify_response" in st.session_state:
                res = st.session_state.verify_response
                verified = res.get("verified", False)
                rejected_stage = res.get("rejected_at_stage")
                match_score = res.get("match_score", 0.0)
                detail = res.get("detail", {})

                # Overall banner
                if verified:
                    st.success(f"✅ **Identity Verified Successfully!** (Best Cosine Similarity: `{match_score:.4f}`)")
                else:
                    st.error(f"❌ **Access Denied.** Rejected at stage: `{rejected_stage}`")

                # Detailed parameters display
                st.markdown("---")
                st.markdown("#### 📐 Stage 1: Quality Assessment")
                
                # Retrieve quality detail nested dictionary
                qual_detail = {}
                if rejected_stage == "quality":
                    qual_detail = detail.get("detail", {}).get("all_results", {})
                else:
                    qual_detail = detail.get("quality_detail", {}).get("all_results", {})
                
                if qual_detail:
                    st.write(f"**Composite Score:** `{qual_detail.get('overall_score', 0)}%` (threshold: `{qual_detail.get('threshold', 70)}%` preset `{qual_detail.get('profile', 'balanced')}`)")
                    
                    sub_scores = qual_detail.get("sub_scores", {})
                    for metric, s_dict in sub_scores.items():
                        raw = s_dict.get("raw_value")
                        score = s_dict.get("score", 0.0)
                        
                        raw_formatted = f"{raw:.2f}" if isinstance(raw, float) else str(raw)
                        st.progress(int(score)/100.0)
                        st.write(f"└ **{metric.capitalize()}** Sub-score: `{score}/100` (Raw Value: `{raw_formatted}`)")
                else:
                    st.write("Quality check was skipped.")

                st.markdown("---")
                st.markdown("#### 🧬 Stage 2: Passive Liveness")
                liveness_detail = detail.get("liveness_detail", {})
                if liveness_detail:
                    passive_res = liveness_detail.get("passive_result", {})
                    if passive_res:
                        is_real = passive_res.get("is_real")
                        score = passive_res.get("antispoof_score", 0.0)
                        st.write(f"**Passive Texture Check (MiniFASNet):** `{'PASS' if is_real else 'FAIL'}` (Score: `{score:.4f}`)")
                else:
                    st.write("Liveness checks skipped or not run.")

                st.markdown("---")
                st.markdown("#### 👤 Stage 3: Face Matching")
                match_res = detail.get("match_result", {})
                if match_res:
                    st.write(f"**Best Match Match Angle:** `{match_res.get('best_match_angle')}`")
                    st.write(f"**Verification Match Score:** `{match_score:.4f}`")
                    st.write("**All Template Scores:**")
                    for angle, score in match_res.get("all_scores", {}).items():
                        st.write(f"└ `{angle}` similarity: `{score:.4f}`")
                else:
                    st.write("Face matching skipped because quality/liveness failed.")


# ---------------------------------------------------------
# TAB 3: COMPLIANCE & AUDIT LOGS
# ---------------------------------------------------------
with tab_audit:
    st.header("Compliance Controls & System Audit Logs")
    st.write("Provides controls to exercise GDPR/BIPA biometric deletion rights, and displays compliance access logs.")
    
    col_del, col_logs = st.columns([1, 2])

    with col_del:
        st.markdown("### Deletion Right Enforcer")
        del_user_name = st.selectbox("Select User to Remove", options=[""] + users_list, key="del_name")
        hard_delete = st.checkbox("Hard Delete (Irreversible template purge)", value=False)
        
        if del_user_name:
            if st.button("⚠️ Delete Biometric Identity"):
                with st.spinner("Exercising GDPR right-to-deletion..."):
                    try:
                        headers = {"X-API-Key": api_key}
                        data = {"name": del_user_name, "hard_delete": str(hard_delete).lower()}
                        resp = requests.post(f"{api_url}/delete", headers=headers, data=data)
                        if resp.status_code == 200:
                            st.success(resp.json().get("message"))
                            st.experimental_rerun()
                        else:
                            st.error(f"Deletion Failed: {resp.json().get('detail')}")
                    except Exception as e:
                        st.error(f"Could not connect to API: {str(e)}")

    with col_logs:
        st.markdown("### Compliance Logs")
        
        # Load Logs from database
        try:
            conn = sqlite3.connect(db.DB_PATH)
            
            st.markdown("#### Access Audit Trail (`access_log`)")
            df_access = pd.read_sql_query("SELECT * FROM access_log ORDER BY timestamp DESC LIMIT 20", conn)
            st.dataframe(df_access, use_container_width=True)

            st.markdown("#### Verification History (`verification_logs`)")
            df_ver = pd.read_sql_query("SELECT * FROM verification_logs ORDER BY timestamp DESC LIMIT 20", conn)
            st.dataframe(df_ver, use_container_width=True)

            conn.close()
        except Exception as e:
            st.warning("Could not read audit logs database.")


# ---------------------------------------------------------
# TAB 4: SERVER HEALTH AUDIT
# ---------------------------------------------------------
with tab_health:
    st.header("Real-Time System Health Checks")
    st.write("Proactively audits server dependencies, credentials, model cache setups, and hardware availability.")

    if st.button("🔄 Poll Health Gateway Status"):
        st.experimental_rerun()

    try:
        resp = requests.get(f"{api_url}/health")
        if resp.status_code == 200:
            health_data = resp.json()
            status = health_data.get("status", "unknown")
            timestamp = health_data.get("timestamp", 0)
            checks = health_data.get("checks", {})

            # Overall banner
            if status == "healthy":
                st.success("🟢 **Server Status: HEALTHY** (All core dependencies online)")
            else:
                st.error("🔴 **Server Status: UNHEALTHY** (Dependencies failed)")

            # Metric Cards grid
            col_h1, col_h2, col_h3, col_h4 = st.columns(4)
            
            with col_h1:
                db_status = checks.get("database", {}).get("status", "fail")
                db_detail = checks.get("database", {}).get("detail", "")
                badge_class = "badge-pass" if db_status == "pass" else "badge-fail"
                st.markdown(f"""
                <div class="metric-card">
                    <h4>SQLite Database</h4>
                    <span class="badge {badge_class}">{db_status}</span>
                    <p style="font-size: 0.8rem; color: #94A3B8; margin-top: 0.5rem;">{db_detail or 'Connection online'}</p>
                </div>
                """, unsafe_allow_html=True)

            with col_h2:
                enc_status = checks.get("encryption_key", {}).get("status", "fail")
                enc_detail = checks.get("encryption_key", {}).get("detail", "")
                badge_class = "badge-pass" if enc_status == "pass" else "badge-fail"
                st.markdown(f"""
                <div class="metric-card">
                    <h4>Encryption Key</h4>
                    <span class="badge {badge_class}">{enc_status}</span>
                    <p style="font-size: 0.8rem; color: #94A3B8; margin-top: 0.5rem;">{enc_detail or 'Env key loaded'}</p>
                </div>
                """, unsafe_allow_html=True)

            with col_h3:
                cache_status = checks.get("deepface_model_cache", {}).get("status", "warn")
                cache_detail = checks.get("deepface_model_cache", {}).get("detail", "")
                badge_class = "badge-pass" if cache_status == "pass" else "badge-warn"
                st.markdown(f"""
                <div class="metric-card">
                    <h4>DeepFace Cache</h4>
                    <span class="badge {badge_class}">{cache_status}</span>
                    <p style="font-size: 0.8rem; color: #94A3B8; margin-top: 0.5rem;">{cache_detail or 'Cache verified'}</p>
                </div>
                """, unsafe_allow_html=True)

            with col_h4:
                cam_status = checks.get("camera", {}).get("status", "warn")
                cam_detail = checks.get("camera", {}).get("detail", "")
                badge_class = "badge-pass" if cam_status == "pass" else "badge-warn"
                st.markdown(f"""
                <div class="metric-card">
                    <h4>Host Camera</h4>
                    <span class="badge {badge_class}">{cam_status}</span>
                    <p style="font-size: 0.8rem; color: #94A3B8; margin-top: 0.5rem;">{cam_detail or 'Camera online'}</p>
                </div>
                """, unsafe_allow_html=True)

        else:
            st.error(f"Health Check Failed: {resp.status_code}")
    except Exception as e:
        st.error(f"Could not connect to health gateway at {api_url}: {str(e)}")
