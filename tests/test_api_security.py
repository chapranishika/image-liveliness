"""
tests/test_api_security.py

api/security.py's verify_api_key() and RateLimiter are the exact security
features every report this session has repeated as a "What Works Today"
claim ("The backend requires a security key and limits request rates.")
-- never actually verified by a test before this file. Both are pure,
standalone functions with no src.db/FastAPI-app import-order risk, so
they're called directly rather than through a full FastAPI TestClient.
"""
import os
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from api.security import verify_api_key, RateLimiter


def test_verify_api_key_accepts_the_correct_key(monkeypatch):
    monkeypatch.setenv("FACE_API_KEY", "the-real-key")
    assert verify_api_key(x_api_key="the-real-key") is True


def test_verify_api_key_rejects_a_wrong_key(monkeypatch):
    monkeypatch.setenv("FACE_API_KEY", "the-real-key")
    with pytest.raises(HTTPException) as excinfo:
        verify_api_key(x_api_key="a-guessed-key")
    assert excinfo.value.status_code == 401


def test_verify_api_key_rejects_a_missing_key(monkeypatch):
    monkeypatch.setenv("FACE_API_KEY", "the-real-key")
    with pytest.raises(HTTPException) as excinfo:
        verify_api_key(x_api_key=None)
    assert excinfo.value.status_code == 401


def test_verify_api_key_fails_closed_if_server_has_no_key_configured(monkeypatch):
    """
    A misconfigured server (FACE_API_KEY unset) must reject every request,
    not silently accept them -- the fail-closed direction matters for a
    security gate.
    """
    monkeypatch.delenv("FACE_API_KEY", raising=False)
    with pytest.raises(HTTPException) as excinfo:
        verify_api_key(x_api_key="anything")
    assert excinfo.value.status_code == 500


def _mock_request(host="1.2.3.4"):
    req = Mock()
    req.client.host = host
    return req


def test_rate_limiter_allows_requests_under_the_limit():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    req = _mock_request()
    for _ in range(3):
        assert limiter(req, x_api_key="client-a") is True


def test_rate_limiter_blocks_the_request_over_the_limit():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    req = _mock_request()
    for _ in range(3):
        limiter(req, x_api_key="client-a")
    with pytest.raises(HTTPException) as excinfo:
        limiter(req, x_api_key="client-a")
    assert excinfo.value.status_code == 429


def test_rate_limiter_tracks_clients_independently_by_api_key():
    """Different callers must not share a limit budget -- one client hitting the limit must not block another."""
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    req = _mock_request()
    limiter(req, x_api_key="client-a")
    limiter(req, x_api_key="client-a")
    with pytest.raises(HTTPException):
        limiter(req, x_api_key="client-a")

    # client-b, same host, different key -- must have its own fresh budget.
    assert limiter(req, x_api_key="client-b") is True


def test_rate_limiter_falls_back_to_client_host_when_no_api_key_given():
    """
    __call__'s client_key = x_api_key or request.client.host -- exercises
    the fallback path directly (relevant since verify_api_key would
    already reject a keyless request in the real dependency chain, but
    RateLimiter itself has no such guarantee about call order).
    """
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    req_a = _mock_request(host="1.1.1.1")
    req_b = _mock_request(host="2.2.2.2")
    assert limiter(req_a, x_api_key=None) is True
    # Different host, no key -- independent budget.
    assert limiter(req_b, x_api_key=None) is True
    with pytest.raises(HTTPException):
        limiter(req_a, x_api_key=None)


def test_rate_limiter_window_expires_old_requests():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    req = _mock_request()
    limiter(req, x_api_key="client-a")
    with pytest.raises(HTTPException):
        limiter(req, x_api_key="client-a")

    # Simulate the window having passed by directly manipulating the
    # internal history -- avoids a real 60s sleep in a unit test.
    history = limiter._requests["client-a"]
    for i in range(len(history)):
        history[i] -= 61
    assert limiter(req, x_api_key="client-a") is True
