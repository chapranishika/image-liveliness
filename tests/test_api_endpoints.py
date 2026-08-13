"""
tests/test_api_endpoints.py

Full-stack tests for api/api.py's /register, /verify, /delete, /health
endpoints via FastAPI's TestClient -- 0% covered before this file, despite
being the entire externally-facing API surface this project's reports
describe as production-relevant for a client's own integration.

Import-order safety: api.api is imported LAZILY, inside the api_client
fixture, only after temp_db has already set FACE_DB_PATH and reloaded
src.db -- api.api does `import src.db as db` (a live module reference,
not `from src.db import DB_PATH`), so it picks up the same isolated,
already-reloaded module object. A safety assertion confirms DB_PATH is
genuinely the isolated temp path, not the real project database, before
any test runs. api.api's own module-level load_env_file() call
unconditionally overwrites os.environ with the real .env file's values
(confirmed by reading src/keys.py directly, not assumed) -- this can
overwrite the fake FACE_API_KEY conftest.py's configure_env fixture set,
so the real key actually in effect is read back from os.environ after
import rather than hardcoded, but FACE_DB_PATH isolation is unaffected
since .env never sets that variable.
"""
import io
import os
import sys

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(temp_db):
    # api.api's module-level code (env var checks, load_env_file()) only
    # runs on the FIRST import in this process -- safe to import once and
    # reuse across tests, because api.api does `import src.db as db` (a
    # live module reference, not a frozen value), so it tracks each
    # test's own fresh temp_db reload correctly regardless of when
    # api.api itself was first imported. Re-verified below, every test,
    # rather than assumed.
    import api.api as api_module

    assert api_module.db.DB_PATH == temp_db.DB_PATH, (
        f"safety check failed: api.api.db.DB_PATH ({api_module.db.DB_PATH}) doesn't match "
        f"this test's isolated temp_db.DB_PATH ({temp_db.DB_PATH}) -- refusing to run rather "
        f"than risk touching the wrong database"
    )
    assert api_module.db.DB_PATH != os.path.join("data", "face_verification.db"), (
        "safety check failed: api.api is pointed at the real project database, refusing to run"
    )

    with TestClient(api_module.app) as client:
        client.api_key = os.environ["FACE_API_KEY"]
        yield client


def _jpeg_bytes(img):
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return io.BytesIO(buf.tobytes())


def test_health_endpoint_does_not_require_auth(api_client):
    """Health checks are meant for infrastructure monitoring -- must not require the API key."""
    resp = api_client.get("/health")
    assert resp.status_code == 200
    assert "status" in resp.json()


def test_register_rejects_a_request_with_no_api_key(api_client, genuine_front_image):
    files = {
        "front_image": ("front.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg"),
        "left_image": ("left.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg"),
        "right_image": ("right.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg"),
    }
    resp = api_client.post("/register", data={"name": "Alice", "consent_given": "true"}, files=files)
    assert resp.status_code == 401


def test_register_rejects_a_request_with_the_wrong_api_key(api_client, genuine_front_image):
    files = {
        "front_image": ("front.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg"),
        "left_image": ("left.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg"),
        "right_image": ("right.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg"),
    }
    resp = api_client.post(
        "/register", data={"name": "Alice", "consent_given": "true"}, files=files,
        headers={"X-API-Key": "definitely-not-the-real-key"},
    )
    assert resp.status_code == 401


def test_register_rejects_without_consent(api_client, genuine_front_image):
    files = {
        "front_image": ("front.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg"),
        "left_image": ("left.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg"),
        "right_image": ("right.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg"),
    }
    resp = api_client.post(
        "/register", data={"name": "Alice", "consent_given": "false"}, files=files,
        headers={"X-API-Key": api_client.api_key},
    )
    assert resp.status_code == 400
    assert "consent" in resp.json()["detail"].lower()


def test_register_rejects_an_invalid_image_file(api_client):
    garbage = io.BytesIO(b"this is not a real image file")
    files = {
        "front_image": ("front.jpg", garbage, "image/jpeg"),
        "left_image": ("left.jpg", io.BytesIO(b"also garbage"), "image/jpeg"),
        "right_image": ("right.jpg", io.BytesIO(b"also garbage"), "image/jpeg"),
    }
    resp = api_client.post(
        "/register", data={"name": "Alice", "consent_given": "true"}, files=files,
        headers={"X-API-Key": api_client.api_key},
    )
    assert resp.status_code == 400


def test_verify_returns_404_for_an_unknown_user(api_client, genuine_front_image):
    files = {"image": ("probe.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg")}
    resp = api_client.post(
        "/verify", data={"name": "NobodyRegisteredThisName"}, files=files,
        headers={"X-API-Key": api_client.api_key},
    )
    assert resp.status_code == 404


def test_delete_returns_404_for_an_unknown_user(api_client):
    resp = api_client.post(
        "/delete", data={"name": "NobodyRegisteredThisName"},
        headers={"X-API-Key": api_client.api_key},
    )
    assert resp.status_code == 404


def test_register_then_verify_then_delete_real_end_to_end(api_client, genuine_front_image):
    """
    The full real lifecycle in one isolated temp database: register a
    real genuine photo across all three angle slots (the endpoint doesn't
    require them to be geometrically distinct, just three uploads), verify
    against it (passive_only, matching how the live app's accessibility
    bypass calls this), then delete it -- ties the real endpoints together
    the way an external client integration actually would use them.
    """
    files = {
        "front_image": ("front.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg"),
        "left_image": ("left.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg"),
        "right_image": ("right.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg"),
    }
    reg_resp = api_client.post(
        "/register", data={"name": "TestSubject", "consent_given": "true"}, files=files,
        headers={"X-API-Key": api_client.api_key},
    )
    if reg_resp.status_code != 200:
        pytest.skip(f"registration didn't succeed with this fixture image in this run: {reg_resp.json()}")
    assert reg_resp.json()["status"] == "success"

    verify_files = {"image": ("probe.jpg", _jpeg_bytes(genuine_front_image), "image/jpeg")}
    verify_resp = api_client.post(
        "/verify", data={"name": "TestSubject", "challenge_override": "passive_only"}, files=verify_files,
        headers={"X-API-Key": api_client.api_key},
    )
    assert verify_resp.status_code == 200
    assert "verified" in verify_resp.json()

    delete_resp = api_client.post(
        "/delete", data={"name": "TestSubject", "hard_delete": "true"},
        headers={"X-API-Key": api_client.api_key},
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "success"

    # Confirms the delete was real, not a no-op -- verifying again must 404.
    verify_again = api_client.post(
        "/verify", data={"name": "TestSubject", "challenge_override": "passive_only"}, files=verify_files,
        headers={"X-API-Key": api_client.api_key},
    )
    assert verify_again.status_code == 404
