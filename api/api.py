"""
api/api.py

Day 27-29: FastAPI endpoints coordinating face registration, verification,
soft/hard deletion, compliance logs, and system health checks.
All modifying endpoints are rate-limited and require X-API-Key authentication.
"""
import os
import cv2
import numpy as np
import sqlite3
from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Form
from typing import Optional

from api.security import verify_api_key, RateLimiter
from api.health import run_health_checks

# Ensure src path is available
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.keys import init_keys_in_env
init_keys_in_env()

import src.db as db
from src.pipeline import verify, run_quality_stage
from src.face_matching import get_embedding
from src.duplicate_check import check_for_duplicate
from src.quality_score import compute_quality_score

app = FastAPI(title="Secure Face Verification Framework API")

# Initialize database tables on startup
@app.on_event("startup")
def startup_event():
    db.init_db()

# Rate limiters
register_limiter = RateLimiter(max_requests=10, window_seconds=60)
verify_limiter = RateLimiter(max_requests=30, window_seconds=60)
delete_limiter = RateLimiter(max_requests=10, window_seconds=60)


def _decode_image_file(file: UploadFile) -> np.ndarray:
    """Decodes UploadFile bytes into a BGR OpenCV image."""
    try:
        contents = file.file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Image decoding failed.")
        return img
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")


@app.post("/register")
def register(
    request: Request,
    name: str = Form(...),
    consent_given: bool = Form(...),
    front_image: UploadFile = File(...),
    left_image: UploadFile = File(...),
    right_image: UploadFile = File(...),
    _=Depends(verify_api_key),
    _rl=Depends(register_limiter)
):
    """
    Day 28: Registration enforcers:
      - Validates and logs explicit biometric consent.
      - Conducts full quality scoring on the frontal image.
      - Runs duplicate detection check on the frontal template.
      - Stores templates encrypted at rest (Day 27).
    """
    if not consent_given:
        raise HTTPException(
            status_code=400,
            detail="Cannot register user without explicit biometric consent."
        )

    # Decode uploaded files
    front_frame = _decode_image_file(front_image)
    left_frame = _decode_image_file(left_image)
    right_frame = _decode_image_file(right_image)

    # 1. Frontal Quality check
    quality_res = compute_quality_score(front_frame)
    if quality_res["decision"] == "reject":
        raise HTTPException(
            status_code=400,
            detail=f"Frontal quality score {quality_res['overall_score']}% is below the profile threshold. Reason: {quality_res['reason']}"
        )

    # 2. Extract embeddings
    front_emb_res = get_embedding(front_frame)
    left_emb_res = get_embedding(left_frame)
    right_emb_res = get_embedding(right_frame)

    if (front_emb_res["status"] != "success" or 
        left_emb_res["status"] != "success" or 
        right_emb_res["status"] != "success"):
        raise HTTPException(
            status_code=400,
            detail="Could not extract face embeddings from one or more uploaded images."
        )

    front_emb = front_emb_res["embedding"]
    left_emb = left_emb_res["embedding"]
    right_emb = right_emb_res["embedding"]

    # 3. Duplicate check
    dup_res = check_for_duplicate(front_emb)
    if dup_res["is_duplicate"]:
        raise HTTPException(
            status_code=400,
            detail=f"Duplicate registration blocked: {dup_res['reason']}"
        )

    # 4. Insert user and templates
    try:
        user_id = db.insert_user(name, consent_given=True, actor="api")
        db.insert_template(user_id, "front", front_emb)
        db.insert_template(user_id, "left", left_emb)
        db.insert_template(user_id, "right", right_emb)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database write failed: {str(e)}")

    return {
        "status": "success",
        "message": f"Successfully registered user {name}.",
        "user_id": user_id,
        "name": name
    }


@app.post("/verify")
def verify_identity(
    request: Request,
    name: str = Form(...),
    image: UploadFile = File(...),
    challenge_override: Optional[str] = Form(None),
    profile: Optional[str] = Form(None),
    _=Depends(verify_api_key),
    _rl=Depends(verify_limiter)
):
    """
    Day 15/21: Verify a claimed identity by running the full 3-stage pipeline
    (Quality composite score, passive liveness check, and face matching).
    """
    # Look up user by name
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id, deleted_at FROM users WHERE name = ?", (name,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"User '{name}' not found.")
    user_id, deleted_at = row
    if deleted_at:
        raise HTTPException(status_code=400, detail=f"User '{name}' has been soft-deleted.")

    # Fetch templates
    stored_templates = db.get_templates_for_user(user_id, actor="api")
    if not stored_templates:
        raise HTTPException(status_code=400, detail=f"No templates stored for user '{name}'.")

    # Decode check frame
    frame = _decode_image_file(image)

    # Run verify (support challenge overrides for active challenges or bypass them for accessibility/static verification)
    run_active = True if (challenge_override and challenge_override != "passive_only") else False
    verify_res = verify(
        frame,
        stored_templates,
        run_active_challenge=run_active,
        preferred_challenge=challenge_override if run_active else None,
        profile=profile
    )

    # Parse and log verification decision
    decision = "accept" if verify_res["verified"] else "reject"
    match_score = 0.0
    quality_result = {}
    liveness_result = {}

    if verify_res["rejected_at_stage"] == "quality":
        quality_result = verify_res["detail"]
    else:
        # Quality passed
        if "quality_detail" in verify_res["detail"]:
            quality_result = verify_res["detail"]["quality_detail"]
        else:
            quality_result = {"status": "pass"}
        liveness_result = verify_res["detail"].get("liveness_detail", {})
        
        if verify_res["match_result"]:
            match_score = verify_res["match_result"]["best_score"]

    db.log_verification(
        user_id=user_id,
        quality_result=quality_result,
        liveness_result=liveness_result,
        match_score=match_score,
        decision=decision
    )

    return {
        "verified": verify_res["verified"],
        "rejected_at_stage": verify_res["rejected_at_stage"],
        "match_score": match_score,
        "detail": verify_res
    }


@app.post("/delete")
def delete_identity(
    request: Request,
    name: str = Form(...),
    hard_delete: bool = Form(False),
    _=Depends(verify_api_key),
    _rl=Depends(delete_limiter)
):
    """
    Day 28: GDPR/BIPA Right-to-Deletion handler.
    Supports soft deletion (excluding user from verification while keeping logs)
    and hard deletion (permanent removal from database).
    """
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE name = ?", (name,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"User '{name}' not found.")
    user_id = row[0]

    res = db.delete_user(user_id, hard_delete=hard_delete, actor="api")
    return {
        "status": "success",
        "message": f"Successfully {'hard' if hard_delete else 'soft'} deleted user '{name}'.",
        "details": res
    }


@app.get("/health")
def health():
    """Day 29: System dependency health monitoring."""
    return run_health_checks()
