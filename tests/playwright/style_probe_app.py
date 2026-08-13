"""
tests/playwright/style_probe_app.py

Permanent test fixture rendering every UI element type that had a real,
found-in-production contrast/color bug this project's live testing turned
up: alert boxes (all four kinds), the nav radio pill, a checkbox, a
primary button, a bullet list, and a selectbox. Uses the REAL
app.styles.get_css_styles() and app.branding_config, not a
reimplementation, so this fixture tracks the actual app and a real
regression here means a real regression there.

Launched by tests/playwright/conftest.py as a standalone Streamlit
process; not meant to be run by hand (though `streamlit run` on it works
fine for a quick manual look).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import streamlit as st
from app.styles import get_css_styles

theme_mode = os.environ.get("STYLE_PROBE_THEME", "light")
st.markdown(get_css_styles(theme_mode), unsafe_allow_html=True)

st.markdown('<div class="consumer-title">Style Probe</div>', unsafe_allow_html=True)

st.info("Info alert message")
st.error("Error alert message")
st.warning("Warning alert message")
st.success("Success alert message")

# This app's own custom alert-style boxes (app-alert-box class in
# styles.py) -- a separate CSS path from the native st.info/error/
# warning/success above, used for things like the "Look at the camera"
# and "Photo captured successfully" boxes. Covered separately since a fix
# to one path doesn't guarantee the other stayed correct.
st.markdown('<div class="app-alert-box info">Custom info alert box</div>', unsafe_allow_html=True)
# role="alert" -- matches _render_action_error_banner()'s real markup
# (app/streamlit_app.py) exactly, so a regression there is caught here.
st.markdown('<div class="app-alert-box error" role="alert">Custom error alert box</div>', unsafe_allow_html=True)
st.markdown('<div class="app-alert-box warning">Custom warning alert box</div>', unsafe_allow_html=True)
# role="status" aria-live="polite" -- matches the real "Photo captured
# successfully" markup in app/streamlit_app.py's Guided Enrollment step 2.
st.markdown('<div class="app-alert-box success" role="status" aria-live="polite">Custom success alert box</div>', unsafe_allow_html=True)

# The two real terminal-outcome cards from Verify Identity
# (app/streamlit_app.py) -- rendered here with the exact same markup/ARIA
# so a regression in either is caught without needing to drive the full
# live verification flow through Playwright.
st.markdown(
    """
    <div class="success-screen-card" role="status" aria-live="polite">
        <div class="success-screen-title">You're Verified!</div>
        <div class="success-screen-sub">Welcome back, Probe User</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div role="alert" aria-live="assertive">
    <div style="margin-top:15px; margin-bottom: 10px;">
        <span class="status-badge danger">Verification Failed</span>
    </div>
    <div>Probe failure reason</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.radio("nav", ["Verify Identity", "Guided Enrollment"], label_visibility="collapsed", key="nav_probe")

st.markdown(
    '<span class="status-badge success">Success badge</span> '
    '<span class="status-badge danger">Danger badge</span>',
    unsafe_allow_html=True,
)

st.checkbox("I agree to the consent checkbox", value=True, key="consent_probe")

st.button("Register Face ID", key="button_probe")

st.markdown(
    "**Before you start:**\n"
    "- Good, even lighting\n"
    "- Only you in frame\n"
    "- Look directly at the camera"
)

st.selectbox(
    "Quality profile",
    options=["lenient", "balanced", "strict"],
    index=1,
    format_func=lambda x: {"lenient": "Lenient", "balanced": "Balanced", "strict": "Strict"}[x],
    key="profile_probe",
)
