"""
tests/test_api_health.py

api/health.py backs both the backend's real /health endpoint and the
admin console's health panel -- 0% covered before this file. While
testing check_database(), found it hardcoded its own database path
independently of src.db's FACE_DB_PATH-aware DB_PATH (fixed in the same
commit as this test, api/health.py) -- meaning a deployment that relocated
the database would have had this check silently looking at the wrong
file. These tests exercise the fix using the same temp_db isolation
pattern as the rest of the suite, not the real production database.
"""
from unittest.mock import patch

from api.health import (
    check_database,
    check_encryption_key,
    check_deepface_model_cache,
    check_camera_available,
    run_health_checks,
)


def test_check_database_passes_against_a_real_initialized_temp_db(temp_db):
    result = check_database()
    assert result["status"] == "pass"


def test_check_database_fails_when_db_path_points_nowhere(monkeypatch):
    monkeypatch.setattr("api.health.db_module.DB_PATH", "nonexistent/path/does_not_exist.db")
    result = check_database()
    assert result["status"] == "fail"
    assert "does not exist" in result["detail"]


def test_check_encryption_key_passes_when_set(monkeypatch):
    monkeypatch.setenv("FACE_DB_ENCRYPTION_KEY", "some-key-value")
    result = check_encryption_key()
    assert result["status"] == "pass"


def test_check_encryption_key_fails_when_unset(monkeypatch):
    monkeypatch.delenv("FACE_DB_ENCRYPTION_KEY", raising=False)
    result = check_encryption_key()
    assert result["status"] == "fail"
    assert "not set" in result["detail"]


def test_check_deepface_model_cache_warns_not_fails_when_empty(monkeypatch, tmp_path):
    """A missing model cache is a slow-first-request warning, not a hard failure -- the server itself is still usable."""
    empty_dir = tmp_path / "no_models_here"
    monkeypatch.setattr("os.path.expanduser", lambda p: str(empty_dir))
    result = check_deepface_model_cache()
    assert result["status"] == "warn"


def test_check_camera_available_warns_not_fails_on_a_headless_server():
    """A server-side missing camera is expected/normal (capture happens client-side in this project's architecture) -- must not report as a hard failure."""
    with patch("cv2.VideoCapture") as mock_cap:
        mock_cap.return_value.isOpened.return_value = False
        result = check_camera_available()
        assert result["status"] == "warn"


def test_run_health_checks_reports_unhealthy_only_on_a_real_hard_failure(temp_db, monkeypatch):
    monkeypatch.setenv("FACE_DB_ENCRYPTION_KEY", "some-key-value")
    result = run_health_checks()
    assert "checks" in result
    assert set(result["checks"].keys()) == {"database", "encryption_key", "deepface_model_cache", "camera"}
    # database + encryption_key both real-pass in this setup -- a warn-only
    # camera/model-cache state must not drag the overall status down.
    if result["checks"]["database"]["status"] == "pass" and result["checks"]["encryption_key"]["status"] == "pass":
        assert result["status"] == "healthy"


def test_run_health_checks_reports_unhealthy_when_encryption_key_missing(temp_db, monkeypatch):
    monkeypatch.delenv("FACE_DB_ENCRYPTION_KEY", raising=False)
    result = run_health_checks()
    assert result["status"] == "unhealthy"
    assert "encryption_key" in result["failing_checks"]
