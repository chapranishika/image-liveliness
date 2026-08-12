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
st.markdown('<div class="app-alert-box error">Custom error alert box</div>', unsafe_allow_html=True)
st.markdown('<div class="app-alert-box warning">Custom warning alert box</div>', unsafe_allow_html=True)
st.markdown('<div class="app-alert-box success">Custom success alert box</div>', unsafe_allow_html=True)

st.radio("nav", ["Verify Identity", "Guided Enrollment"], label_visibility="collapsed", key="nav_probe")

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
