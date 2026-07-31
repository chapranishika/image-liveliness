"""
src/registration.py

Day 16: The full registration pipeline — implementing, for the first time
with real captured data, the multi-angle design committed to in the
Approach & Design Document (Part 0.1). Captures a strict front-facing
primary template, then reuses the active liveness head-turn challenge to
capture left and right profile templates as a side effect of the same
user action, requiring no extra steps.

Usage:
    from src.registration import register_new_user
    result = register_new_user("Alice")
"""
import cv2
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))
from quality_checks import check_brightness, check_blur
from quality_checks_day8_9 import check_single_face, check_pose, check_position, check_occlusion
from liveness_active import compute_ear, RIGHT_EYE, LEFT_EYE
from face_matching import get_embedding
from db import init_db, insert_user, insert_template


# Same recalibrated yaw window established in Day 8's engineering log and
# reused throughout Day 11's active liveness — one source of truth, not a
# separate number invented for registration.
YAW_PROFILE_MIN = 25.0
YAW_PROFILE_MAX = 65.0
HOLD_FRAMES_REQUIRED = 5


def capture_front_template(camera_index=0, timeout_seconds=15):
    """
    Captures a single frame and runs it through the FULL quality gate
    (Chapter 9's run_quality_stage logic, inlined here rather than
    reusing pipeline.py directly, since registration's front capture has
    a slightly different flow: it retries live rather than rejecting once
    and stopping). This is the STRICT primary template — it must pass
    every check exactly as section 3.3 of the project brief requires.
    """
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        return {"status": "error", "reason": "camera unavailable"}

    start = time.time()
    last_reason = ""
    while time.time() - start < timeout_seconds:
        ret, frame = cap.read()
        if not ret:
            continue

        checks = [check_single_face(frame), check_brightness(frame), check_blur(frame),
                  check_pose(frame), check_position(frame), check_occlusion(frame)]
        failed = next((c for c in checks if c["status"] == "fail"), None)

        display = frame.copy()
        if failed:
            last_reason = f"{failed['check']}: {failed.get('reason', '')}"
            cv2.putText(display, f"Adjust: {last_reason}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imshow("Registration - Front Capture", display)
            cv2.waitKey(1)
            continue

        cv2.putText(display, "Good - capturing front template", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("Registration - Front Capture", display)
        cv2.waitKey(500)
        cap.release()
        cv2.destroyAllWindows()
        return {"status": "success", "frame": frame}

    cap.release()
    cv2.destroyAllWindows()
    return {"status": "fail", "reason": f"timed out, last issue: {last_reason}"}


def capture_profile_templates(camera_index=0, timeout_seconds=15):
    """
    Runs the SAME head-turn action used for active liveness (Day 11), but
    captures the frame at the moment yaw enters the 25-65 degree window
    for BOTH sides in one continuous session, rather than treating this
    as a pass/fail liveness challenge. This is the literal implementation
    of "one user action, two outcomes" described in Part 0.1 — the person
    only turns their head once each way; the difference from Day 11 is
    what the captured frame is used FOR, not what the user experiences.
    """
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        return {"status": "error", "reason": "camera unavailable"}

    captured = {"left": None, "right": None}
    hold_counters = {"left": 0, "right": 0}
    start = time.time()

    while time.time() - start < timeout_seconds and (captured["left"] is None or captured["right"] is None):
        ret, frame = cap.read()
        if not ret:
            continue

        pose = check_pose(frame)
        yaw = pose.get("yaw")

        display = frame.copy()
        remaining = [a for a in ("left", "right") if captured[a] is None]
        cv2.putText(display, f"Please turn head to capture: {', '.join(remaining)}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        if yaw is not None:
            cv2.putText(display, f"yaw: {yaw:.1f}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            if yaw < -YAW_PROFILE_MIN and yaw > -YAW_PROFILE_MAX and captured["left"] is None:
                hold_counters["left"] += 1
                if hold_counters["left"] >= HOLD_FRAMES_REQUIRED:
                    captured["left"] = frame.copy()
            elif yaw > YAW_PROFILE_MIN and yaw < YAW_PROFILE_MAX and captured["right"] is None:
                hold_counters["right"] += 1
                if hold_counters["right"] >= HOLD_FRAMES_REQUIRED:
                    captured["right"] = frame.copy()

        cv2.imshow("Registration - Profile Capture", display)
        cv2.waitKey(1)

    cap.release()
    cv2.destroyAllWindows()

    if captured["left"] is None or captured["right"] is None:
        missing = [a for a in ("left", "right") if captured[a] is None]
        return {"status": "fail", "reason": f"could not capture: {', '.join(missing)}", "captured": captured}

    return {"status": "success", "captured": captured}


def register_new_user(name, camera_index=0):
    """
    The complete Day 16 registration flow: front capture (strict gate) ->
    profile capture (reusing the head-turn action) -> embed all three ->
    duplicate check (Day 17-18, called here as a stub until built) -> store.
    """
    init_db()

    front_result = capture_front_template(camera_index)
    if front_result["status"] != "success":
        return {"status": "rejected", "stage": "front_capture", "reason": front_result.get("reason")}

    profile_result = capture_profile_templates(camera_index)
    if profile_result["status"] != "success":
        return {"status": "rejected", "stage": "profile_capture", "reason": profile_result.get("reason")}

    front_embed = get_embedding(front_result["frame"])
    left_embed = get_embedding(profile_result["captured"]["left"])
    right_embed = get_embedding(profile_result["captured"]["right"])

    for label, embed_result in [("front", front_embed), ("left", left_embed), ("right", right_embed)]:
        if embed_result["status"] != "success":
            return {"status": "rejected", "stage": f"{label}_embedding", "reason": embed_result["reason"]}

    # Duplicate check (Day 17-18): compares the new front embedding against
    # every existing registered user's front template before allowing
    # storage. Wired in here now that duplicate_check.py exists.
    from duplicate_check import check_for_duplicate
    dup_result = check_for_duplicate(front_embed["embedding"])
    if dup_result["is_duplicate"]:
        return {"status": "rejected", "stage": "duplicate_check", "reason": dup_result["reason"]}

    user_id = insert_user(name, consent_given=True)
    insert_template(user_id, "front", front_embed["embedding"])
    insert_template(user_id, "left", left_embed["embedding"])
    insert_template(user_id, "right", right_embed["embedding"])

    return {"status": "registered", "user_id": user_id, "name": name}
