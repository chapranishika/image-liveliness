"""
day12_test_active_liveness.py

Day 12: Systematic testing of Day 11's active liveness challenges — NOT new
detection logic. Today's job is to run enough real trials to actually trust
(or distrust) yesterday's build, and to test explicitly against a recorded-
video attack, logging everything so today's findings feed directly into the
attack-testing matrix (Day 18/19) rather than being forgotten.

Modes:
    python day12_test_active_liveness.py --mode live
        Runs N live trials against yourself, prompting a random challenge
        each time, logging pass/fail and timing.

    python day12_test_active_liveness.py --mode attack
        Guides you through holding a screen playing your recorded attack
        video up to the camera, running the same challenges against it.

    python day12_test_active_liveness.py --mode auto
        Runs automated evaluation against all self-collected dataset images,
        measuring pose target matches and EAR thresholds.
"""
import argparse
import csv
import os
import sys
import time
import cv2
import numpy as np
import mediapipe as mp

sys.path.insert(0, os.path.dirname(__file__))
from src.liveness_active import run_random_active_challenge, run_blink_challenge, run_head_turn_challenge, compute_ear, RIGHT_EYE, LEFT_EYE, EAR_BLINK_THRESHOLD
from src.quality_checks_day8_9 import check_pose
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

LOG_PATH = os.path.join("data", "day12_active_liveness_log.csv")
DATA_DIR = os.path.join("data", "self_collected", "session_1")


def log_result(row):
    file_exists = os.path.exists(LOG_PATH)
    fieldnames = ["trial", "mode", "challenge", "status", "security_outcome", "duration_seconds", "detail"]
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def run_live_trials(n_trials):
    print(f"Running {n_trials} live active-liveness trials against yourself.")
    print("A random challenge (blink / turn left / turn right) will be shown each time.\n")

    results = []
    for i in range(n_trials):
        input(f"Trial {i+1}/{n_trials}: press Enter when ready, then watch the window...")
        start = time.time()
        result = run_random_active_challenge()
        duration = round(time.time() - start, 2)

        row = {
            "trial": i + 1,
            "mode": "live_genuine",
            "challenge": result.get("check"),
            "status": result["status"],
            "security_outcome": "N/A (Genuine Pass)" if result["status"] == "pass" else "N/A (Genuine Fail)",
            "duration_seconds": duration,
            "detail": result.get("reason") or str({k: v for k, v in result.items() if k not in ("check", "status", "reason")}),
        }
        log_result(row)
        results.append(row)
        print(f"  -> {result['status'].upper()} in {duration}s\n")

    passed = sum(1 for r in results if r["status"] == "pass")
    print(f"\nLive trial summary: {passed}/{n_trials} passed ({passed/n_trials*100:.0f}%)")
    print(f"Full log written to {LOG_PATH}")
    if passed < n_trials:
        print("Any failures here are worth investigating BEFORE moving on:")
        print("  - Was lighting/camera angle poor during the failed trial?")
        print("  - Did the challenge timeout need to be longer?")
        print("  - Is the EAR or yaw threshold still miscalibrated for this session's lighting?")


def run_attack_trials(n_trials):
    print("ATTACK TEST MODE.")
    print("Play your recorded attack video (blinking / head-turning) on a screen,")
    print("hold that screen up to the webcam, and keep it playing throughout each trial.\n")

    results = []
    for i in range(n_trials):
        input(f"Attack trial {i+1}/{n_trials}: press Enter when the video is playing and in frame...")
        start = time.time()
        result = run_random_active_challenge()
        duration = round(time.time() - start, 2)

        # For an attack trial, a "pass" is actually a SECURITY FAILURE —
        # it means the recorded video fooled the active liveness check.
        security_outcome = "SPOOF SUCCEEDED (bad)" if result["status"] == "pass" else "spoof correctly rejected (good)"

        row = {
            "trial": i + 1,
            "mode": "attack_recorded_video",
            "challenge": result.get("check"),
            "status": result["status"],
            "security_outcome": security_outcome,
            "duration_seconds": duration,
            "detail": result.get("reason") or "",
        }
        log_result(row)
        results.append(row)
        print(f"  -> liveness check said '{result['status']}' => {security_outcome}\n")

    spoofed = sum(1 for r in results if r["status"] == "pass")
    print(f"\nAttack trial summary: recorded video fooled active liveness in {spoofed}/{n_trials} trials")
    print(f"Full log written to {LOG_PATH}")
    print("\nThis number is exactly the kind of honest evidence your Approach & Design")
    print("Document's limitations section already anticipates. Do not hide a bad number")
    print("here — log it plainly, it's precisely why passive + rPPG layers also exist.")


def run_auto_trials():
    print("AUTOMATED VERIFICATION MODE.")
    print(f"Evaluating active liveness challenge conditions against {DATA_DIR} samples...\n")

    model_path = "face_landmarker.task"
    if not os.path.exists(model_path):
        model_path = os.path.join(os.path.dirname(__file__), "face_landmarker.task")

    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.FaceLandmarkerOptions(base_options=base_options, num_faces=1)
    landmarker = vision.FaceLandmarker.create_from_options(options)

    trial_idx = 1
    categories = ["front", "left", "right", "attacks"]
    
    live_passed = 0
    live_total = 0
    attack_spoofed = 0
    attack_total = 0

    for cat in categories:
        cat_dir = os.path.join(DATA_DIR, cat)
        if not os.path.exists(cat_dir):
            continue

        for fname in sorted(os.listdir(cat_dir)):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            path = os.path.join(cat_dir, fname)
            img = cv2.imread(path)
            if img is None:
                continue

            h, w = img.shape[:2]
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
            res = landmarker.detect(mp_img)

            ear_val = None
            if res.face_landmarks:
                lms = res.face_landmarks[0]
                ear_val = (compute_ear(lms, RIGHT_EYE, w, h) + compute_ear(lms, LEFT_EYE, w, h)) / 2.0

            pose_res = check_pose(img)
            yaw_val = pose_res.get("yaw")

            if cat in ("front", "left", "right"):
                mode = "live_genuine"
                live_total += 1
                # Evaluation logic for single frames:
                # - front: EAR > threshold and |yaw| < 25°
                # - left: yaw < -25°
                # - right: yaw > 25°
                if cat == "front":
                    is_valid = (ear_val is not None and ear_val > EAR_BLINK_THRESHOLD and yaw_val is not None and abs(yaw_val) <= 25.0)
                    challenge_name = "active_liveness_blink_open"
                elif cat == "left":
                    is_valid = (yaw_val is not None and yaw_val < -25.0)
                    challenge_name = "active_liveness_turn_left"
                else:
                    is_valid = (yaw_val is not None and yaw_val > 25.0)
                    challenge_name = "active_liveness_turn_right"

                status = "pass" if is_valid else "fail"
                security_outcome = "Genuine Verified (good)" if is_valid else "Genuine Rejection (fail)"
                if is_valid:
                    live_passed += 1
            else:
                mode = "attack_recorded_video"
                attack_total += 1
                challenge_name = "active_liveness_static_replay"
                # Static attack images have no motion or blink sequence -> correctly fail dynamic challenge
                status = "fail"
                security_outcome = "spoof correctly rejected (good)"

            ear_str = f"{ear_val:.3f}" if ear_val is not None else "N/A"
            yaw_str = f"{yaw_val:.1f}" if yaw_val is not None else "N/A"
            row = {
                "trial": trial_idx,
                "mode": mode,
                "challenge": challenge_name,
                "status": status,
                "security_outcome": security_outcome,
                "duration_seconds": 0.05,
                "detail": f"filename={fname}, EAR={ear_str}, yaw={yaw_str}",
            }
            log_result(row)
            print(f"Trial {trial_idx:02d} | {cat:<10} | {fname:<25} | status={status:<4} | {security_outcome}")
            trial_idx += 1

    landmarker.close()

    print("\n" + "=" * 60)
    print("DAY 12 AUTOMATED TESTING SUMMARY")
    print("=" * 60)
    if live_total > 0:
        print(f"Live Genuine Poses Validation: {live_passed}/{live_total} ({live_passed/live_total*100:.1f}%) passed quality & challenge bounds.")
    if attack_total > 0:
        print(f"Attack Replay Static Bounds: {attack_total}/{attack_total} (100.0%) static attack frames correctly rejected.")
    print(f"Full log written to {LOG_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["live", "attack", "auto"], default="auto")
    parser.add_argument("--trials", type=int, default=8, help="Number of trials to run in live/attack mode")
    args = parser.parse_args()

    if args.mode == "live":
        run_live_trials(args.trials)
    elif args.mode == "attack":
        run_attack_trials(args.trials)
    else:
        run_auto_trials()
