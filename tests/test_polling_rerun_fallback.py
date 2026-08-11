"""
tests/test_polling_rerun_fallback.py

Unit test for _safe_polling_rerun() (app/streamlit_app.py). st.rerun(scope=
"fragment") raises StreamlitAPIException when the current execution is
itself a full-script rerun rather than a fragment rerun. The fallback must
swallow that exception without propagating it -- and must NOT chain a
second st.rerun() call, since that call sits inside col_cam and col_actions
renders after it in the script; a plain-rerun fallback would self-
perpetuate a full-rerun loop that never reaches col_actions. Doing nothing
is safe because the frame-capture component already drives its own
fragment-scoped reruns via its own component-value changes.

Plain function-level unit test, not a full Streamlit AppTest session -- this
is about the fallback behavior itself, not full app state. Importing
app.streamlit_app directly (Streamlit's "bare mode", used elsewhere in this
test suite's conftest-free imports) is enough to exercise it.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# app/streamlit_app.py calls st.stop() at import time if these are missing --
# set them before import, since a module-level import happens at pytest
# collection time, before conftest.py's autouse session fixture would
# otherwise have set them.
if not os.environ.get("FACE_DB_ENCRYPTION_KEY"):
    from cryptography.fernet import Fernet
    os.environ["FACE_DB_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
if not os.environ.get("FACE_API_KEY"):
    os.environ["FACE_API_KEY"] = "test_polling_rerun_fallback_key"

import streamlit as st
from app.streamlit_app import _safe_polling_rerun


def test_safe_polling_rerun_swallows_streamlit_api_exception_without_chaining(monkeypatch):
    calls = []

    def fake_rerun(*args, **kwargs):
        calls.append((args, kwargs))
        raise st.errors.StreamlitAPIException(
            'scope="fragment" cannot be used outside of a fragment rerun'
        )

    monkeypatch.setattr(st, "rerun", fake_rerun)

    _safe_polling_rerun()  # must not raise

    assert len(calls) == 1, f"expected exactly 1 call to st.rerun() (no chained fallback), got {len(calls)}"
    assert calls[0] == ((), {"scope": "fragment"}), f"call should be st.rerun(scope='fragment'), got {calls[0]}"


def test_safe_polling_rerun_calls_fragment_scope_on_happy_path(monkeypatch):
    calls = []
    monkeypatch.setattr(st, "rerun", lambda *a, **kw: calls.append((a, kw)))

    _safe_polling_rerun()

    assert calls == [((), {"scope": "fragment"})]
