"""
api/security.py

Day 27: Basic API authentication and rate limiting -- addresses the gap
that /register and /verify were previously open endpoints, callable by
anyone who could reach the server.

This is a MINIMUM viable security layer appropriate for this project's
prototype scope, not a production-grade auth system. A real product would
use OAuth2/JWT with per-client scoped permissions and a proper API
gateway; a single shared API key checked on every request is the honest,
correctly-scoped starting point here -- worth stating explicitly rather
than implying more security than actually exists.

Usage (in api/api.py):
    from fastapi import FastAPI, Depends
    from api.security import verify_api_key, RateLimiter

    app = FastAPI()
    rate_limiter = RateLimiter(max_requests=30, window_seconds=60)

    @app.post("/verify")
    def verify_endpoint(request: Request, _=Depends(verify_api_key), _rl=Depends(rate_limiter)):
        ...
"""
import os
import time
from collections import defaultdict, deque
from fastapi import Header, HTTPException, Request

_API_KEY_ENV_VAR = "FACE_API_KEY"


def verify_api_key(x_api_key: str = Header(None)):
    """
    Checks the X-API-Key request header against the configured key.
    Raises 401 if missing or wrong. The key itself lives in an
    environment variable, same key-management discipline as Day 27's
    encryption key -- never hardcoded, never committed to Git.
    """
    expected_key = os.environ.get(_API_KEY_ENV_VAR)
    if not expected_key:
        raise HTTPException(status_code=500, detail="Server misconfigured: FACE_API_KEY not set")
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


class RateLimiter:
    """
    A simple in-memory sliding-window rate limiter: each caller (identified
    by their API key, so different clients get independent limits) may
    make at most max_requests within window_seconds.

    Honest limitation: this is in-memory, per-process state. It resets on
    server restart and does not share state across multiple server
    instances -- fine for this project's single-process local deployment,
    but a real multi-instance production deployment would need a shared
    store (Redis) instead, noted here rather than silently assumed away.
    """
    def __init__(self, max_requests=30, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests = defaultdict(deque)

    def __call__(self, request: Request, x_api_key: str = Header(None)):
        now = time.time()
        client_key = x_api_key or request.client.host
        history = self._requests[client_key]

        while history and now - history[0] > self.window_seconds:
            history.popleft()

        if len(history) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: max {self.max_requests} requests per {self.window_seconds}s"
            )

        history.append(now)
        return True
