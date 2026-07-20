"""
src/liveness_passive.py

Day 10: Passive liveness detection using DeepFace's built-in anti-spoofing
(which internally runs MiniFASNet — see Approach & Design Document Section 5.2
and the Phase 2 repository study for why these are the same model, not two
separate options).

Important, confirmed directly from DeepFace's own source (modules/recognition.py
and extract_faces): when anti_spoofing=True and a spoof is detected, DeepFace
raises a hard ValueError rather than returning a graceful is_real=False result.
This module exists specifically to catch that exception and convert it into a
normal, structured result your pipeline can act on — never letting it crash
a request.

Usage:
    import cv2
    from src.liveness_passive import check_passive_liveness

    img = cv2.imread("data/self_collected/session_1/front/front_001.jpg")
    result = check_passive_liveness(img)
    print(result)
"""
import cv2
import numpy as np
import tempfile
import os

# DeepFace is imported lazily inside the function that needs it, so that
# importing this module (e.g. for testing other functions) doesn't force
# a slow TensorFlow/DeepFace load every time.


def check_passive_liveness(image, detector_backend="skip"):
    """
    Runs DeepFace's anti-spoofing check on a single image.

    DeepFace's extract_faces() only accepts a file path or a numpy array in
    certain call patterns depending on version; to be safe and explicit, we
    write the frame to a temporary file, since this is the most reliable way
    to guarantee consistent behavior across DeepFace versions.

    Returns a dict:
        {
            "check": "passive_liveness",
            "is_real": bool or None,
            "antispoof_score": float or None,
            "status": "pass" | "fail" | "error",
            "reason": str,
        }
    """
    from deepface import DeepFace

    # Write to a temp file — avoids inconsistent behavior across DeepFace
    # versions when passing raw arrays directly with anti_spoofing=True.
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
    cv2.imwrite(tmp_path, image)

    try:
        faces = DeepFace.extract_faces(
            img_path=tmp_path,
            detector_backend=detector_backend,
            anti_spoofing=True,
            enforce_detection=True,
        )

        if not faces:
            return {
                "check": "passive_liveness",
                "is_real": None,
                "antispoof_score": None,
                "status": "fail",
                "reason": "no face detected",
            }

        face = faces[0]
        is_real = face.get("is_real")
        antispoof_score = face.get("antispoof_score")

        status = "pass" if is_real else "fail"
        reason = "" if is_real else "flagged as spoof by passive liveness model"

        return {
            "check": "passive_liveness",
            "is_real": is_real,
            "antispoof_score": round(float(antispoof_score), 4) if antispoof_score is not None else None,
            "status": status,
            "reason": reason,
        }

    except ValueError as e:
        # This is the EXPECTED behavior documented in the Approach & Design
        # Document (Section 5.2 / Phase 2 findings): DeepFace raises a hard
        # exception on detecting a spoof rather than returning gracefully.
        # We catch it here and convert it into the same structured format
        # every other check in this pipeline uses, so the rest of the system
        # never has to know DeepFace behaves this way internally.
        return {
            "check": "passive_liveness",
            "is_real": False,
            "antispoof_score": None,
            "status": "fail",
            "reason": f"spoof detected (DeepFace raised exception: {str(e)})",
        }

    except Exception as e:
        # Any other unexpected error (e.g. face detection failure under
        # enforce_detection=True) — surfaced clearly rather than silently
        # swallowed, but still returned as structured data, not a crash.
        return {
            "check": "passive_liveness",
            "is_real": None,
            "antispoof_score": None,
            "status": "error",
            "reason": str(e),
        }

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
