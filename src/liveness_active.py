"""
src/liveness_active.py

Day 11: Active liveness detection — blink detection (Eye Aspect Ratio) and
head-turn detection (reusing the solvePnP pose logic from Day 8), combined
into a randomly-selected challenge-response check.

Reference: Soukupova & Cech (2016), "Real-Time Eye Blink Detection Using
Facial Landmarks" — EAR is measured as a pattern across a short window of
frames, not a single-frame snapshot, per the Approach & Design Document
Section 5.4 and the Phase 2 paper review.

This module assumes quality_checks_day8_9.py (Day 8) already exists in the
same src/ folder, since head-turn detection reuses its solvePnP pose logic
rather than duplicating it.
"""
import cv2
import numpy as np
import mediapipe as mp
import random
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from quality_checks_day8_9 import check_pose  # reuse Day 8's solvePnP pose logic

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ---- EAR landmark indices (6 points per eye, standard convention) ----
# Right eye: horizontal corners + 2 vertical pairs (upper/lower lid)
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
# Left eye: horizontal corners + 2 vertical pairs (upper/lower lid)
LEFT_EYE = [362, 385, 387, 263, 373, 380]

# ---- Placeholder thresholds — calibrate against your own blink data ----
EAR_BLINK_THRESHOLD = 0.25     # EAR below this = eye considered closed (calibrated Day 11)
BLINK_CONSEC_FRAMES_MIN = 2    # must stay below threshold for at least this many frames
HEAD_TURN_HOLD_FRAMES = 5      # frames the yaw must stay in the target zone to count


def _euclidean(p1, p2):
    return np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def compute_ear(landmarks, eye_indices, w=1.0, h=1.0):
    """
    Eye Aspect Ratio = (vertical distance 1 + vertical distance 2) / (2 * horizontal distance)
    Low EAR = eye closed/closing. High EAR = eye open.
    """
    pts = []
    for idx in eye_indices:
        lm = landmarks[idx]
        if hasattr(lm, 'x') and hasattr(lm, 'y'):
            pts.append((lm.x * w, lm.y * h))
        elif isinstance(lm, (tuple, list)):
            pts.append((lm[0], lm[1]))
        else:
            pts.append((lm.x, lm.y))
    horizontal = _euclidean(pts[0], pts[3])
    vertical_1 = _euclidean(pts[1], pts[5])
    vertical_2 = _euclidean(pts[2], pts[4])
    if horizontal == 0:
        return 0.0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def run_blink_challenge(camera_index=0, timeout_seconds=8):
    """
    Opens the webcam, tracks EAR across frames for up to timeout_seconds,
    and returns pass/fail based on whether a genuine blink pattern (a dip
    below threshold for several consecutive frames, then recovery) was seen.
    """
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        return {"check": "active_liveness_blink", "status": "error", "reason": "camera unavailable"}

    model_path = os.path.join(os.path.dirname(__file__), "..", "face_landmarker.task")
    if not os.path.exists(model_path):
        model_path = "face_landmarker.task"

    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        num_faces=1
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)

    ear_history = []
    below_threshold_streak = 0
    blink_detected = False
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        ret, frame = cap.read()
        if not ret:
            break
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        results = landmarker.detect(mp_image)

        display = frame.copy()
        cv2.putText(display, "Please blink twice", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        if results.face_landmarks:
            landmarks = results.face_landmarks[0]
            ear_right = compute_ear(landmarks, RIGHT_EYE, w, h)
            ear_left = compute_ear(landmarks, LEFT_EYE, w, h)
            avg_ear = (ear_right + ear_left) / 2.0
            ear_history.append(avg_ear)

            if avg_ear < EAR_BLINK_THRESHOLD:
                below_threshold_streak += 1
            else:
                if below_threshold_streak >= BLINK_CONSEC_FRAMES_MIN:
                    blink_detected = True
                below_threshold_streak = 0

            cv2.putText(display, f"EAR: {avg_ear:.3f}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        cv2.imshow("Active Liveness - Blink Challenge", display)
        if blink_detected or (cv2.waitKey(1) & 0xFF == ord("q")):
            break

    landmarker.close()
    cap.release()
    cv2.destroyAllWindows()

    return {
        "check": "active_liveness_blink",
        "status": "pass" if blink_detected else "fail",
        "reason": "" if blink_detected else "no blink pattern detected within timeout",
        "ear_samples": len(ear_history),
        "min_ear_observed": round(min(ear_history), 3) if ear_history else None,
    }


def run_head_turn_challenge(direction="left", camera_index=0, timeout_seconds=8):
    """
    Asks the user to turn their head in the given direction, reusing Day 8's
    solvePnP-based check_pose() to measure real yaw angle per frame, rather
    than re-implementing angle detection separately.
    direction: "left" or "right"
    """
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        return {"check": "active_liveness_head_turn", "status": "error", "reason": "camera unavailable"}

    hold_counter = 0
    turn_detected = False
    max_yaw_seen = 0.0
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        ret, frame = cap.read()
        if not ret:
            break

        pose_result = check_pose(frame)
        yaw = pose_result.get("yaw")

        display = frame.copy()
        cv2.putText(display, f"Please turn your head {direction}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        if yaw is not None:
            cv2.putText(display, f"yaw: {yaw:.1f} deg", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            max_yaw_seen = max(max_yaw_seen, abs(yaw)) if abs(yaw) > abs(max_yaw_seen) else max_yaw_seen

            in_target_zone = (
                (direction == "left" and yaw < -25.0) or
                (direction == "right" and yaw > 25.0)
            )
            # thresholds above use Day 8's recalibrated real values (Section 4.4
            # of the engineering log), not the original design-doc estimate
            if in_target_zone:
                hold_counter += 1
            else:
                hold_counter = 0

            if hold_counter >= HEAD_TURN_HOLD_FRAMES:
                turn_detected = True

        cv2.imshow("Active Liveness - Head Turn Challenge", display)
        if turn_detected or (cv2.waitKey(1) & 0xFF == ord("q")):
            break

    cap.release()
    cv2.destroyAllWindows()

    return {
        "check": "active_liveness_head_turn",
        "direction": direction,
        "status": "pass" if turn_detected else "fail",
        "reason": "" if turn_detected else "required turn angle not sustained within timeout",
        "max_yaw_observed": round(max_yaw_seen, 1),
    }


def run_random_active_challenge(camera_index=0):
    """
    Picks one challenge at random (blink, turn left, turn right) and runs it.
    This randomness is the actual security value of active liveness: a
    pre-recorded video of "blinking" doesn't help an attacker if the system
    asks for a head-turn instead, and vice versa.
    """
    challenge = random.choice(["blink", "turn_left", "turn_right"])
    if challenge == "blink":
        return run_blink_challenge(camera_index)
    elif challenge == "turn_left":
        return run_head_turn_challenge("left", camera_index)
    else:
        return run_head_turn_challenge("right", camera_index)
