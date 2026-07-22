"""
src/face_matching.py

Day 15: Face embedding generation and similarity comparison using DeepFace
with the ArcFace backend. This is the "Face Embedding" and "Face Matching"
boxes from Diagram 1, the final stage after quality and liveness have
already passed.
"""
import numpy as np
import tempfile
import os
import cv2


def get_embedding(frame, model_name="ArcFace", detector_backend="skip"):
    """
    Converts a face frame into a 512-dimensional ArcFace embedding.
    detector_backend="skip" is used deliberately, same reasoning as Day 10's
    passive liveness check: by the time a frame reaches this function, it
    has already passed face detection during the quality stage, so a second
    detection pass here would be redundant.
    """
    from deepface import DeepFace

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
    cv2.imwrite(tmp_path, frame)

    try:
        result = DeepFace.represent(
            img_path=tmp_path,
            model_name=model_name,
            detector_backend=detector_backend,
            enforce_detection=False,
        )
        embedding = np.array(result[0]["embedding"])
        return {"status": "success", "embedding": embedding, "reason": ""}
    except Exception as e:
        return {"status": "error", "embedding": None, "reason": str(e)}
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def cosine_similarity(embedding_a, embedding_b):
    """
    Standard cosine similarity: 1.0 means identical direction (same person,
    ideally), 0.0 means unrelated, negative values mean opposite. This is
    the comparison DeepFace itself uses internally for ArcFace.
    """
    a = embedding_a / np.linalg.norm(embedding_a)
    b = embedding_b / np.linalg.norm(embedding_b)
    return float(np.dot(a, b))


def match_against_templates(live_embedding, stored_templates, threshold=0.68):
    """
    Compares one live embedding against a dict of stored templates, e.g.
        {"front": embedding_front, "left": embedding_left, "right": embedding_right}
    and returns the BEST match, not just the first one — this is the exact
    "best-of-three" logic the multi-angle registration design (Approach &
    Design Document, Part 0.1) depends on.

    threshold=0.68 is a PLACEHOLDER pending Day 20's real ROC/EER
    calibration against LFW and CFP pairs — do not treat this as final.
    """
    if not stored_templates:
        return {"status": "reject", "best_match_angle": None, "best_score": None,
                "reason": "no stored templates for this identity"}

    scores = {angle: cosine_similarity(live_embedding, emb) for angle, emb in stored_templates.items()}
    best_angle = max(scores, key=scores.get)
    best_score = scores[best_angle]

    status = "accept" if best_score >= threshold else "reject"
    return {
        "status": status,
        "best_match_angle": best_angle,
        "best_score": round(best_score, 4),
        "all_scores": {k: round(v, 4) for k, v in scores.items()},
        "reason": "" if status == "accept" else f"best score {best_score:.4f} below threshold {threshold}",
    }
