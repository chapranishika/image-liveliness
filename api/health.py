"""
api/health.py

Day 29: Real health monitoring, replacing the Approach & Design Document's
originally planned /health endpoint (which just returned a static
{"status": "ok"}). A static response tells you the web server process is
running -- it tells you nothing about whether the actual dependencies
this system needs (camera, database, DeepFace models) are working.

Usage (in api/api.py):
    from api.health import run_health_checks

    @app.get("/health")
    def health_endpoint():
        return run_health_checks()
"""
import os
import time
import sqlite3


def check_database():
    db_path = os.path.join("data", "face_verification.db")
    if not os.path.exists(db_path):
        return {"status": "fail", "detail": "database file does not exist"}
    try:
        conn = sqlite3.connect(db_path, timeout=2)
        conn.execute("SELECT 1")
        conn.close()
        return {"status": "pass", "detail": ""}
    except Exception as e:
        return {"status": "fail", "detail": str(e)}


def check_encryption_key():
    key_present = bool(os.environ.get("FACE_DB_ENCRYPTION_KEY"))
    return {"status": "pass" if key_present else "fail",
            "detail": "" if key_present else "FACE_DB_ENCRYPTION_KEY not set"}


def check_deepface_model_cache():
    """
    DeepFace downloads model weights to a local cache on first use. If
    that cache is missing entirely (e.g. a fresh deployment with no
    internet access at startup), the FIRST real verification request
    would be the one that discovers this, with a slow, confusing failure.
    This check catches that ahead of time instead.
    """
    cache_dir = os.path.expanduser("~/.deepface/weights")
    if not os.path.isdir(cache_dir) or not os.listdir(cache_dir):
        return {"status": "warn", "detail": "DeepFace model cache appears empty -- first request will be slow while models download"}
    return {"status": "pass", "detail": ""}


def check_camera_available():
    """
    A basic camera availability check. Marked 'warn' rather than 'fail' on
    a server deployment, since a backend server process may legitimately
    have no camera attached at all -- capture typically happens client-side
    (Streamlit) in this project's architecture, not on the API server
    itself. Included for completeness in a local all-in-one deployment.
    """
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        available = cap.isOpened()
        cap.release()
        return {"status": "pass" if available else "warn",
                "detail": "" if available else "no camera detected on this host (expected on a headless server)"}
    except Exception as e:
        return {"status": "warn", "detail": str(e)}


def run_health_checks():
    checks = {
        "database": check_database(),
        "encryption_key": check_encryption_key(),
        "deepface_model_cache": check_deepface_model_cache(),
        "camera": check_camera_available(),
    }

    hard_failures = [name for name, result in checks.items() if result["status"] == "fail"]
    overall = "unhealthy" if hard_failures else "healthy"

    return {
        "status": overall,
        "timestamp": time.time(),
        "checks": checks,
        "failing_checks": hard_failures,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_health_checks(), indent=2))
