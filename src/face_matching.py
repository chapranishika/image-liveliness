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
    Uses MediaPipe Tasks API face detector to crop the face region first,
    eliminating background noise and resolving the different-person bias.
    """
    import mediapipe as mp
    from src.quality_checks_day8_9 import get_detector

    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))

    # get_detector() returns a cached, shared instance (reused across every
    # caller at this confidence level) -- closing it here would break every
    # later call in the same process, since the cache would keep handing
    # back the now-closed detector. min_confidence matches the live quality
    # checklist's threshold so a frame that clears live detection doesn't
    # then fail this crop step and silently fall back to embedding the
    # whole uncropped frame.
    detector = get_detector(min_confidence=0.3)
    results = detector.detect(mp_image)

    face_frame = frame
    if results.detections:
        bbox = results.detections[0].bounding_box
        x = max(0, int(bbox.origin_x))
        y = max(0, int(bbox.origin_y))
        box_w = int(bbox.width)
        box_h = int(bbox.height)

        # Add 15% padding margin around the face
        margin_x = int(box_w * 0.15)
        margin_y = int(box_h * 0.15)

        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(w, x + box_w + margin_x)
        y2 = min(h, y + box_h + margin_y)

        face_frame = frame[y1:y2, x1:x2]

    from deepface import DeepFace

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
    cv2.imwrite(tmp_path, face_frame)

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
