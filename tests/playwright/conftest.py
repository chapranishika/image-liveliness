"""
tests/playwright/conftest.py

Launches tests/playwright/style_probe_app.py as a real Streamlit process
(once per theme, session-scoped) so the UI contrast/regression tests can
drive it with a real browser via Playwright. No camera, no ML models --
this fixture only needs Streamlit itself, so it starts in a couple of
seconds and needs nothing beyond what any other test in this suite
already requires.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_PROBE_APP = os.path.join(os.path.dirname(__file__), "style_probe_app.py")


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_up(url, timeout_s=30):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            time.sleep(0.5)
    return False


def _launch_probe(theme_mode):
    port = _find_free_port()
    env = os.environ.copy()
    env["STYLE_PROBE_THEME"] = theme_mode
    env["PYTHONPATH"] = _REPO_ROOT
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", _PROBE_APP,
            "--server.port", str(port),
            "--server.address", "127.0.0.1",
            "--server.headless", "true",
        ],
        cwd=_REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    if not _wait_until_up(url):
        proc.terminate()
        pytest.fail(f"style_probe_app ({theme_mode}) did not start within 30s")
    return proc, url


@pytest.fixture(scope="session")
def style_probe_url_light():
    proc, url = _launch_probe("light")
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


@pytest.fixture(scope="session")
def style_probe_url_dark():
    proc, url = _launch_probe("dark")
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
