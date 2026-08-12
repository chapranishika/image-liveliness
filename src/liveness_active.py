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
from quality_checks_day8_9 import check_pose, get_landmarker, get_cached_landmarks  # reuse Day 8's solvePnP pose logic + cached landmarker

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

# HEAD_TURN_FLICKER_TOLERANCE: single-frame yaw estimation from solvePnP is
# noisy -- more so with glasses, which can perturb landmark detection -- so
# a sustained, correct head turn can still produce an occasional borderline
# reading. Resetting the hold counter to zero on any single out-of-zone
# reading would make the challenge feel like it hangs even while the turn
# is held correctly (the same failure mode FLICKER_TOLERANCE=2 already
# guards against for the quality-hold countdown in app/streamlit_app.py).
# Tolerates up to this many consecutive out-of-zone/no-face readings
# without losing hold progress.
HEAD_TURN_FLICKER_TOLERANCE = 2

# LOOP_SIGNATURE_* -- heuristic replay/loop detector for the live active-
# challenge frame sequence (see check_frame_loop_signature() below).
# Deliberately conservative: a near-EXACT match requirement and a multi-
# match count, specifically to avoid false-flagging a genuine, briefly
# very still live user. NOT calibrated against a real staged replay
# attack in this pass (no physical screen/camera setup available here) --
# same disclosed-limitation pattern already used elsewhere in this
# project (e.g. TEXTURE_UNIFORMITY_MIN's calibration comment in
# quality_checks.py) rather than an unstated assumption of effectiveness.
LOOP_SIGNATURE_MIN_LAG_SECONDS = 1.2  # frames closer together in time than this are naturally near-identical even for a real, still person
LOOP_SIGNATURE_DIFF_THRESHOLD = 1.5   # mean abs diff on a 0-255 grayscale 32x32 thumbnail -- tighter than typical sensor/compression noise between two genuinely separate real camera frames
LOOP_SIGNATURE_MIN_MATCHES = 4        # this many near-duplicate matches in one attempt before flagging as a possible loop/replay

# BLINK_TICK_CONSEC_FRAMES_MIN (tick path only): BLINK_CONSEC_FRAMES_MIN=2
# was calibrated for the blocking version, which reads frames from
# cv2.VideoCapture at ~20-30fps -- 2 consecutive frames there is
# ~67-100ms, comfortably inside a real blink's ~150-400ms closed window.
# The live app's tick path is fed by the frame-capture component's
# periodic snapshots (~350ms apart, see app/frame_capture_component's
# CAPTURE_INTERVAL_MS), so requiring 2 consecutive captures below threshold
# would demand ~700ms of continuously-closed eyes -- longer than most real
# blinks. One captured below-threshold frame at this cadence is already
# good evidence of a genuine blink (a mis-detection blip is unlikely to
# land exactly at the same instant a real capture fires), so
# evaluate_blink_tick() uses this instead of BLINK_CONSEC_FRAMES_MIN.
BLINK_TICK_CONSEC_FRAMES_MIN = 1


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


def evaluate_blink_tick(frame, history):
    """
    Single-frame, tick-compatible counterpart to run_blink_challenge() --
    the live app's fragment reruns feed one already-captured WebRTC frame
    per tick rather than owning a blocking cv2.VideoCapture loop, so this
    takes one frame plus the running history and returns the updated
    history plus a status, instead of looping internally.

    Reuses the same EAR pipeline (compute_ear, RIGHT_EYE/LEFT_EYE,
    EAR_BLINK_THRESHOLD, get_landmarker) as the blocking version, but the
    consecutive-frames-below-threshold requirement is BLINK_TICK_CONSEC_FRAMES_MIN,
    not BLINK_CONSEC_FRAMES_MIN -- see that constant's comment for why the
    much slower tick cadence here needs a different value.

    history: list of past avg_ear float samples (pass [] on the first tick
    of a new challenge attempt).

    Returns (new_history, status) where status is "pending" or "pass".
    """
    h, w = frame.shape[:2]
    # get_cached_landmarks() reuses the same detection result check_pose()
    # (called earlier in the same tick, via verify_pose_and_quality())
    # already computed for this exact frame object -- avoids paying for a
    # second full MediaPipe landmark-detection pass on identical input.
    results = get_cached_landmarks(frame, 0.5)

    if not results.face_landmarks:
        return history, "pending"

    landmarks = results.face_landmarks[0]
    ear_right = compute_ear(landmarks, RIGHT_EYE, w, h)
    ear_left = compute_ear(landmarks, LEFT_EYE, w, h)
    avg_ear = (ear_right + ear_left) / 2.0
    new_history = history + [avg_ear]

    # Same dip-then-recover detection as run_blink_challenge(): count
    # consecutive samples below threshold, and declare a blink the moment
    # EAR recovers above threshold after enough consecutive low samples.
    below_streak = 0
    for val in reversed(new_history):
        if val < EAR_BLINK_THRESHOLD:
            below_streak += 1
        else:
            break
    if below_streak == 0 and len(new_history) >= 2:
        prior_streak = 0
        for val in new_history[-2::-1]:
            if val < EAR_BLINK_THRESHOLD:
                prior_streak += 1
            else:
                break
        if prior_streak >= BLINK_TICK_CONSEC_FRAMES_MIN:
            return new_history, "pass"

    return new_history, "pending"


def evaluate_head_turn_tick(frame, history, direction="left"):
    """
    Single-frame, tick-compatible counterpart to run_head_turn_challenge().
    Reuses check_pose()'s solvePnP yaw (Day 8) and the same HEAD_TURN_HOLD_FRAMES
    threshold logic as the blocking version, plus HEAD_TURN_FLICKER_TOLERANCE
    (see that constant's comment).

    history: (hold_streak, miss_streak) tuple. hold_streak counts consecutive
    in-target-zone ticks, tolerating up to HEAD_TURN_FLICKER_TOLERANCE
    out-of-zone/no-face readings in a row without resetting; miss_streak
    tracks how many of those tolerated misses have accumulated since the
    last in-zone tick. Pass (0, 0) on the first tick of a new challenge
    attempt.

    Returns (new_history, status) where status is "pending" or "pass".
    """
    hold_streak, miss_streak = history
    pose_result = check_pose(frame)
    yaw = pose_result.get("yaw")

    # check_pose()'s yaw sign comes from solvePnP against the webcam's raw
    # (non-mirrored) frame: a person's physical right turn moves their face
    # toward what the un-mirrored image renders as its left side. "left"/
    # "right" below refer to the user's actual physical turn direction, not
    # raw image-left/image-right.
    in_target_zone = yaw is not None and (
        (direction == "left" and yaw > 25.0) or
        (direction == "right" and yaw < -25.0)
    )

    if in_target_zone:
        hold_streak += 1
        miss_streak = 0
    else:
        miss_streak += 1
        if miss_streak > HEAD_TURN_FLICKER_TOLERANCE:
            # Tolerance exceeded -- this looks like a genuine interruption
            # (looked away, walked off, real occlusion), not just sensor
            # noise. Reset for real.
            hold_streak = 0
            miss_streak = 0

    new_history = (hold_streak, miss_streak)
    if hold_streak >= HEAD_TURN_HOLD_FRAMES:
        return new_history, "pass"
    return new_history, "pending"


def check_frame_loop_signature(frame, frame_buffer):
    """
    Heuristic replay/loop detector for the active-challenge frame
    sequence. A looped video clip repeats its exact visual content
    (including the exact motion trajectory) every time it cycles; a real,
    live person's natural micro-movement, breathing, and blink timing
    essentially never reproduces the same frame content again, even a few
    seconds apart. Downsamples each frame small and compares the current
    one against everything already buffered more than
    LOOP_SIGNATURE_MIN_LAG_SECONDS old (wall-clock, not tick count -- stays
    correct regardless of buffer trimming) -- short-lag closeness is expected
    even from a genuinely still live person and is deliberately not
    counted, only repeats further apart than that.

    See the LOOP_SIGNATURE_* constants' comment for the calibration
    caveat: this has not been tested against a real staged replay attack,
    and is tuned conservatively (tight match threshold, multi-match
    requirement) specifically to avoid false-flagging a genuine live user.

    frame_buffer: list of (thumbnail: np.ndarray, timestamp: float) tuples
    from earlier ticks in this same challenge attempt. Pass [] on the
    first tick of a new attempt.

    Returns (new_buffer, is_suspicious, match_count).
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    thumb = cv2.resize(gray, (32, 32)).astype(np.float32)

    now = time.time()
    match_count = 0
    for past_thumb, past_ts in frame_buffer:
        if now - past_ts < LOOP_SIGNATURE_MIN_LAG_SECONDS:
            continue
        diff = float(np.abs(thumb - past_thumb).mean())
        if diff < LOOP_SIGNATURE_DIFF_THRESHOLD:
            match_count += 1

    new_buffer = frame_buffer + [(thumb, now)]
    # Cap buffer size to bound memory/CPU cost across a long attempt --
    # safe to trim freely now that matching is timestamp-based, not
    # dependent on buffer length or position within it.
    if len(new_buffer) > 200:
        new_buffer = new_buffer[-200:]

    is_suspicious = match_count >= LOOP_SIGNATURE_MIN_MATCHES
    return new_buffer, is_suspicious, match_count


def run_random_active_challenge(camera_index=0, preferred_challenge=None):
    """
    Picks one challenge at random (blink, turn left, turn right) and runs it,
    or respects the preferred_challenge if provided (for accessibility compliance,
    e.g., for users with head movement or blinking limitations).
    """
    if preferred_challenge in ["blink", "turn_left", "turn_right"]:
        challenge = preferred_challenge
    else:
        challenge = random.choice(["blink", "turn_left", "turn_right"])

    if challenge == "blink":
        return run_blink_challenge(camera_index)
    elif challenge == "turn_left":
        return run_head_turn_challenge("left", camera_index)
    else:
        return run_head_turn_challenge("right", camera_index)
