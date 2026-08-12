"""
tests/test_active_liveness_gate.py

Regression test for the security gate found and fixed in this project: two
buttons ("Having trouble? Tap to capture manually" and "Verify Manually")
could each trigger a verification/enrollment decision without the active
liveness (blink/head-turn) challenge ever having passed. The fix added a
structural safety net -- the gate now lives INSIDE run_verification_logic()
and _capture_enrollment_photo(), the only two functions that can actually
finalize a decision, rather than relying on every call site to remember to
check first.

This test exists so that gap cannot quietly reopen: if the gate is ever
removed or weakened, these tests fail loudly instead of the bug only
surfacing again via a live user noticing a checklist mismatch, the way it
was actually found.

Same "bare mode" import pattern as test_polling_rerun_fallback.py.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if not os.environ.get("FACE_DB_ENCRYPTION_KEY"):
    from cryptography.fernet import Fernet
    os.environ["FACE_DB_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
if not os.environ.get("FACE_API_KEY"):
    os.environ["FACE_API_KEY"] = "test_active_liveness_gate_key"

import numpy as np
import streamlit as st
import app.streamlit_app as app_module

_DUMMY_FRAME = np.zeros((10, 10, 3), dtype="uint8")


def _reset_session_state():
    st.session_state.clear()


def test_run_verification_logic_blocks_when_challenge_not_passed(monkeypatch):
    _reset_session_state()
    st.session_state.active_challenge_passed = False

    called = []
    monkeypatch.setattr(app_module, "_get_sane_frame_or_retry", lambda img: called.append(img) or img)

    app_module.run_verification_logic(_DUMMY_FRAME, "balanced")

    assert called == [], "run_verification_logic must not proceed past the gate when the challenge hasn't passed"
    outcome = st.session_state.get("verify_outcome")
    assert outcome is not None
    assert outcome["status"] == "fail"
    assert outcome["stage"] == "active_liveness"


def test_run_verification_logic_blocks_when_flag_never_set(monkeypatch):
    # active_challenge_passed never set at all -- must default to blocked,
    # not silently proceed. This is exactly the shape of the bypass bug:
    # a caller that never set/checked the flag must still be refused.
    _reset_session_state()

    called = []
    monkeypatch.setattr(app_module, "_get_sane_frame_or_retry", lambda img: called.append(img) or img)

    app_module.run_verification_logic(_DUMMY_FRAME, "balanced")

    assert called == []
    assert st.session_state.get("verify_outcome", {}).get("stage") == "active_liveness"


def test_run_verification_logic_proceeds_once_challenge_passed(monkeypatch):
    _reset_session_state()
    st.session_state.active_challenge_passed = True

    called = []
    monkeypatch.setattr(app_module, "_get_sane_frame_or_retry", lambda img: called.append(img) or None)

    app_module.run_verification_logic(_DUMMY_FRAME, "balanced")

    assert len(called) == 1, "run_verification_logic should proceed past the gate once the challenge has passed"


def test_capture_enrollment_photo_blocks_when_challenge_not_passed(monkeypatch):
    _reset_session_state()
    st.session_state.active_challenge_passed = False

    called = []
    monkeypatch.setattr(
        app_module, "verify_pose_and_quality",
        lambda *a, **kw: called.append((a, kw)) or {"status": "fail", "reason": "should not be reached"},
    )

    result = app_module._capture_enrollment_photo(_DUMMY_FRAME, "balanced", liveness_blocking=True)

    assert called == [], "_capture_enrollment_photo must not proceed past the gate when the challenge hasn't passed"
    assert result["status"] == "fail"
    assert "blink" in result["reason"].lower() or "head-turn" in result["reason"].lower()


def test_capture_enrollment_photo_blocks_when_flag_never_set(monkeypatch):
    _reset_session_state()

    called = []
    monkeypatch.setattr(
        app_module, "verify_pose_and_quality",
        lambda *a, **kw: called.append((a, kw)) or {"status": "fail", "reason": "should not be reached"},
    )

    result = app_module._capture_enrollment_photo(_DUMMY_FRAME, "balanced", liveness_blocking=True)

    assert called == []
    assert result["status"] == "fail"


def test_capture_enrollment_photo_proceeds_once_challenge_passed(monkeypatch):
    _reset_session_state()
    st.session_state.active_challenge_passed = True

    called = []
    monkeypatch.setattr(
        app_module, "verify_pose_and_quality",
        lambda *a, **kw: called.append((a, kw)) or {"status": "pass", "liveness_result": {"status": "pass"}},
    )

    result = app_module._capture_enrollment_photo(_DUMMY_FRAME, "balanced", liveness_blocking=True)

    assert len(called) == 1, "_capture_enrollment_photo should proceed past the gate once the challenge has passed"
    assert result["status"] == "pass"
