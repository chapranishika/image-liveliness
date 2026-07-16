"""
src/quality_checks_day8_9.py

Day 8: Pose validation (solvePnP), position/centering, single-vs-multi-face.
Day 9: Occlusion detection.

This implementation uses the modern MediaPipe Tasks API (FaceDetector and FaceLandmarker)
to prevent module import failures on newer versions of MediaPipe.
"""
import os
import urllib.request
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Model paths and download URLs
DETECTOR_MODEL_PATH = "blaze_face_short_range.tflite"
LANDMARKER_MODEL_PATH = "face_landmarker.task"
DETECTOR_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
LANDMARKER_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

def ensure_models_exist():
    if not os.path.exists(DETECTOR_MODEL_PATH):
        print(f"[INFO] Face detector model not found. Downloading from:\n{DETECTOR_URL}...")
        try:
            urllib.request.urlretrieve(DETECTOR_URL, DETECTOR_MODEL_PATH)
            print("[INFO] Detector model downloaded successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to download detector model: {e}")
            raise e
            
    if not os.path.exists(LANDMARKER_MODEL_PATH):
        print(f"[INFO] Face landmarker model not found. Downloading from:\n{LANDMARKER_URL}...")
        try:
            urllib.request.urlretrieve(LANDMARKER_URL, LANDMARKER_MODEL_PATH)
            print("[INFO] Landmarker model downloaded successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to download landmarker model: {e}")
            raise e

def get_detector(min_confidence=0.5):
    ensure_models_exist()
    base_options = python.BaseOptions(model_asset_path=DETECTOR_MODEL_PATH)
    options = vision.FaceDetectorOptions(
        base_options=base_options, 
        min_detection_confidence=min_confidence
    )
    return vision.FaceDetector.create_from_options(options)

def get_landmarker(min_confidence=0.5):
    ensure_models_exist()
    base_options = python.BaseOptions(model_asset_path=LANDMARKER_MODEL_PATH)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options, 
        min_face_detection_confidence=min_confidence
    )
    return vision.FaceLandmarker.create_from_options(options)

# ---- Landmark indices used throughout (confirmed via direct MediaPipe study) ----
NOSE_TIP = 1
CHIN = 152
RIGHT_EYE_OUTER = 33
LEFT_EYE_OUTER = 263

# ---- Generic 3D face model points (arbitrary units), matched to the four
# landmarks above, for solvePnP ----
MODEL_POINTS_3D = np.array([
    (0.0, 0.0, 0.0),          # Nose tip
    (0.0, 330.0, -65.0),      # Chin
    (-225.0, -170.0, -135.0), # Right eye outer corner
    (225.0, -170.0, -135.0),  # Left eye outer corner
], dtype=np.float64)

# ---- Placeholder thresholds — calibrate these against your own data ----
YAW_FRONTAL_MAX = 25.0       # beyond this, no longer "front-facing" for registration's primary template (calibrated Day 8)
YAW_PROFILE_MIN = 25.0       # profile capture window starts here (calibrated Day 8)
YAW_PROFILE_MAX = 65.0       # profile capture window ends here (calibrated Day 8)
PITCH_MAX = 35.0             # calibrated Day 8
ROLL_MAX = 20.0
MIN_FACE_AREA_RATIO = 0.03   # face bounding box area / image area, minimum (calibrated Day 8)
CENTER_TOLERANCE = 0.20      # face center must be within this fraction of image center
DETECTION_CONFIDENCE_MIN = 0.80  # below this, flag possible occlusion


def check_single_face(image, min_confidence=0.5):
    """
    Counts detected faces. Returns pass only when exactly one face is found.
    """
    h, w = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    
    detector = get_detector(min_confidence)
    results = detector.detect(mp_image)
    detector.close()
    
    count = len(results.detections) if results.detections else 0

    if count == 0:
        status, reason = "fail", "no face detected"
    elif count > 1:
        status, reason = "fail", f"{count} faces detected"
    else:
        status, reason = "pass", ""

    detection_score = None
    if count >= 1:
        detection_score = round(float(results.detections[0].categories[0].score), 3)

    return {
        "check": "single_face",
        "face_count": count,
        "detection_score": detection_score,
        "status": status,
        "reason": reason,
    }


def check_pose(image):
    """
    Uses solvePnP with the 4 landmarks (nose tip, chin, right/left eye outer
    corners) to compute real yaw/pitch/roll in degrees.
    """
    h, w = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    
    landmarker = get_landmarker()
    results = landmarker.detect(mp_image)
    landmarker.close()

    if not results.face_landmarks:
        return {"check": "pose", "status": "fail", "reason": "no face detected"}

    landmarks = results.face_landmarks[0]

    def px(idx):
        lm = landmarks[idx]
        return (lm.x * w, lm.y * h)

    image_points = np.array([
        px(NOSE_TIP),
        px(CHIN),
        px(RIGHT_EYE_OUTER),
        px(LEFT_EYE_OUTER),
    ], dtype=np.float64)

    focal_length = w
    center = (w / 2, h / 2)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype=np.float64)
    dist_coeffs = np.zeros((4, 1))  # assume no lens distortion

    rvec_init = np.zeros((3, 1), dtype=np.float64)
    tvec_init = np.array([[0.0], [0.0], [focal_length]], dtype=np.float64)

    success, rotation_vec, translation_vec = cv2.solvePnP(
        MODEL_POINTS_3D, image_points, camera_matrix, dist_coeffs,
        rvec=rvec_init, tvec=tvec_init, useExtrinsicGuess=True,
        flags=cv2.SOLVEPNP_ITERATIVE
    )
    if not success:
        return {"check": "pose", "status": "fail", "reason": "solvePnP failed to converge"}

    rotation_mat, _ = cv2.Rodrigues(rotation_vec)
    proj_matrix = np.hstack((rotation_mat, translation_vec))
    euler_angles = cv2.decomposeProjectionMatrix(proj_matrix)[6]
    pitch, yaw, roll = [float(a[0]) for a in euler_angles]

    abs_yaw = abs(yaw)
    if abs(pitch) > PITCH_MAX or abs(roll) > ROLL_MAX or abs_yaw > YAW_PROFILE_MAX:
        classification = "extreme"
        status = "fail"
    elif abs_yaw <= YAW_FRONTAL_MAX:
        classification = "frontal"
        status = "pass"
    elif YAW_PROFILE_MIN <= abs_yaw <= YAW_PROFILE_MAX:
        classification = "profile_right" if yaw > 0 else "profile_left"
        status = "pass"
    else:
        classification = "extreme"
        status = "fail"

    return {
        "check": "pose",
        "yaw": round(yaw, 1),
        "pitch": round(pitch, 1),
        "roll": round(roll, 1),
        "classification": classification,
        "status": status,
        "reason": "" if status == "pass" else "angle out of acceptable range",
    }


def check_position(image, min_confidence=0.5):
    """
    Checks the detected face's bounding box: is it reasonably centered,
    and does it occupy enough of the frame.
    """
    h, w = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    
    detector = get_detector(min_confidence)
    results = detector.detect(mp_image)
    detector.close()

    if not results.detections:
        return {"check": "position", "status": "fail", "reason": "no face detected"}

    bbox = results.detections[0].bounding_box
    face_center_x = (bbox.origin_x + bbox.width / 2) / w
    face_center_y = (bbox.origin_y + bbox.height / 2) / h
    face_area_ratio = (bbox.width * bbox.height) / (w * h)

    x_offset = abs(face_center_x - 0.5)
    y_offset = abs(face_center_y - 0.5)

    reasons = []
    if face_area_ratio < MIN_FACE_AREA_RATIO:
        reasons.append("face too small in frame (stand closer)")
    if x_offset > CENTER_TOLERANCE or y_offset > CENTER_TOLERANCE:
        reasons.append("face not centered")

    status = "pass" if not reasons else "fail"
    return {
        "check": "position",
        "face_area_ratio": round(face_area_ratio, 3),
        "x_offset": round(x_offset, 3),
        "y_offset": round(y_offset, 3),
        "status": status,
        "reason": "; ".join(reasons),
    }


def check_occlusion(image, min_confidence=0.5):
    """
    Approximate occlusion check. Flags possible occlusion if detection confidence is low,
    OR if local sharpness around key facial regions (eyes, nose, mouth) is
    unusually flat compared to the rest of the face.
    """
    h, w = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    
    detector = get_detector(min_confidence)
    det_results = detector.detect(mp_image)
    detector.close()

    if not det_results.detections:
        return {"check": "occlusion", "status": "fail", "reason": "no face detected"}

    detection_score = float(det_results.detections[0].categories[0].score)

    landmarker = get_landmarker(min_confidence)
    mesh_results = landmarker.detect(mp_image)
    landmarker.close()

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    region_points = {
        "left_eye": LEFT_EYE_OUTER,
        "right_eye": RIGHT_EYE_OUTER,
        "nose": NOSE_TIP,
        "mouth_area": CHIN,  # approximate mouth-region proxy using chin-adjacent patch
    }
    patch_variances = {}
    if mesh_results.face_landmarks:
        landmarks = mesh_results.face_landmarks[0]
        for name, idx in region_points.items():
            lm = landmarks[idx]
            cx, cy = int(lm.x * w), int(lm.y * h)
            half = 12
            y0, y1 = max(0, cy - half), min(h, cy + half)
            x0, x1 = max(0, cx - half), min(w, cx + half)
            patch = gray[y0:y1, x0:x1]
            if patch.size > 0:
                patch_variances[name] = float(patch.var())

    low_variance_regions = [name for name, v in patch_variances.items() if v < 25.0]

    reasons = []
    if detection_score < DETECTION_CONFIDENCE_MIN:
        reasons.append(f"low detection confidence ({detection_score:.2f})")
    if low_variance_regions:
        reasons.append(f"flat texture near: {', '.join(low_variance_regions)}")

    status = "pass" if not reasons else "fail"
    return {
        "check": "occlusion",
        "detection_score": round(detection_score, 3),
        "patch_variances": {k: round(v, 1) for k, v in patch_variances.items()},
        "status": status,
        "reason": "; ".join(reasons) if reasons else "",
    }
