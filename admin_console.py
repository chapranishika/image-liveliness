"""
admin_console.py

Standalone admin/compliance console -- GDPR & BIPA "right to be forgotten"
deletion, the audit trail (access log + verification log), and system
health checks. Deliberately a SEPARATE Streamlit process from the
consumer-facing app (app/streamlit_app.py), on its own port, not linked
to or reachable from the main app's UI at all -- these are sensitive,
PII-touching operations (deleting a user's biometric data, reading who
accessed what and when) that don't belong sitting behind a collapsed
expander in the same interface every end user sees, which is where this
used to live before this project's live UI/UX pass.

Run separately from the consumer app:
    streamlit run admin_console.py --server.port 8502

This process has NO authentication of its own -- it relies entirely on
network-level access control (only bind/expose this port to a trusted
operator, e.g. localhost only, or a private network/VPN, never a public
port). Do not deploy this reachable from the public internet without
adding a real access-control layer in front of it.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import streamlit as st

from app.styles import get_css_styles
from app.branding_config import COMPANY_NAME
from src import db
from src.keys import load_env_file

load_env_file()

st.set_page_config(page_title=f"{COMPANY_NAME} Admin Console", layout="wide")

if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "light"
st.markdown(get_css_styles(st.session_state.theme_mode), unsafe_allow_html=True)

st.markdown(f"""
<div class="header-bar">
    <div class="header-logo">{COMPANY_NAME[0] if COMPANY_NAME else "A"}</div>
    <div class="header-name">{COMPANY_NAME} Admin & Compliance Console</div>
</div>
""", unsafe_allow_html=True)

st.markdown(
    "**Restricted tool.** This process is separate from the consumer-facing "
    "app and has no login of its own -- access to it must be controlled at "
    "the network level (see this file's module docstring)."
)

col_delete, col_logs = st.columns(2)

# ---------------------------------------------------------------------
# Biometric template deletion (GDPR / BIPA "right to be forgotten")
# ---------------------------------------------------------------------
with col_delete:
    st.markdown("### Biometric Template Deletion (Right to be Forgotten)")

    users = []
    try:
        conn = sqlite3.connect(db.DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT user_id, name, consent_given_at, deleted_at FROM users ORDER BY user_id")
        users = [{"id": r[0], "name": r[1], "consent_at": r[2], "deleted_at": r[3]} for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        st.error(f"Database error: {str(e)}")

    if not users:
        st.info("No registered users found.")
    else:
        st.dataframe(pd.DataFrame(users), use_container_width=True)

        selected_user_id = st.selectbox(
            "Select user for biometric deletion",
            options=[u["id"] for u in users],
            format_func=lambda uid: next(u["name"] for u in users if u["id"] == uid),
        )

        delete_type = st.radio(
            "Deletion type",
            options=["Soft delete", "Hard delete (permanent, irreversible)"],
        )

        if st.button("⚠️ Execute Biometric Deletion"):
            username = next(u["name"] for u in users if u["id"] == selected_user_id)
            with st.spinner("Processing deletion request..."):
                try:
                    is_hard = delete_type.startswith("Hard")
                    db.delete_user(selected_user_id, hard_delete=is_hard, actor="admin_console")
                    st.success(f"Successfully deleted user '{username}'.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Deletion failed: {str(e)}")

# ---------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------
with col_logs:
    st.markdown("### Audit Trail")
    st.write("Access log (registrations, deletions, template reads) and verification transaction log.")

    try:
        conn = sqlite3.connect(db.DB_PATH)
        df_access = pd.read_sql_query("SELECT * FROM access_log ORDER BY timestamp DESC LIMIT 20", conn)
        df_ver = pd.read_sql_query("SELECT * FROM verification_logs ORDER BY timestamp DESC LIMIT 20", conn)
        conn.close()

        st.markdown("#### Access Log")
        st.dataframe(df_access, use_container_width=True)

        st.markdown("#### Verification Transactions Log")
        st.dataframe(df_ver, use_container_width=True)
    except Exception as e:
        st.error(f"Could not load audit logs: {str(e)}")

st.markdown("<hr style='margin: 30px 0;'>", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# System health checks
# ---------------------------------------------------------------------
st.markdown("### System Health Checks")

from api.health import check_database, check_encryption_key, check_deepface_model_cache, check_camera_available

db_res = check_database()
enc_res = check_encryption_key()
mod_res = check_deepface_model_cache()
cam_res = check_camera_available()

col_h1, col_h2 = st.columns(2)
with col_h1:
    status = "✓ PASS" if db_res["status"] == "pass" else "✗ FAIL"
    st.markdown(f"**SQLite Database**: {status} ({db_res.get('detail') or 'Successfully connected.'})")
    status = "✓ PASS" if enc_res["status"] == "pass" else "✗ FAIL"
    st.markdown(f"**Encryption Key**: {status} ({enc_res.get('detail') or 'Biometric encryption key loaded successfully.'})")
with col_h2:
    status = "✓ PASS" if mod_res["status"] == "pass" else "✗ FAIL"
    st.markdown(f"**Models Cached**: {status} ({mod_res.get('detail') or 'All required face detection models are cached.'})")
    status = "✓ PASS" if cam_res["status"] in ("pass", "warn") else "✗ FAIL"
    st.markdown(f"**Camera Device**: {status} ({cam_res.get('detail') or 'OS camera capture device is ready.'})")
