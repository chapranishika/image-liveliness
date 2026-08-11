"""
capture_screen_replay_samples.py

Phase 5, Part A SETUP: a focused capture tool for the real screen-replay
follow-up session flagged in docs/screen_replay_capture_checklist.md
(Phase 3) -- check_screen_surface_texture() (src/quality_checks.py,
TEXTURE_UNIFORMITY_MIN=0.90) was calibrated on only 2 real screen-replay
photos and needs more real samples across different devices/lighting/
distances to confirm the threshold holds.

Reuses the webcam-capture pattern established in capture_images.py, but
flattened to single-key toggles (no modal submenus) so it's easy to
operate solo while also holding a phone/screen with the other hand, and
labels files with the exact naming convention this phase asked for:

    screen_<device>_<lighting>_<distance>_NN.jpg

Controls (always shown on screen):
    D  - cycle device      (phone / laptop / monitor / tablet)
    L  - cycle lighting    (normal / dim / bright)
    X  - cycle distance    (close / normal / far)
    SPACE or C - capture a screen-replay sample with the current label
    G  - capture a genuine control photo (no screen, just your live face)
    Q / ESC - quit

Usage:
    python capture_screen_replay_samples.py
"""
import os
import sys
import time
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

MODEL_PATH = "blaze_face_short_range.tflite"
OUT_DIR = os.path.join("data", "self_collected", "session_2", "attacks")
CONTROL_DIR = os.path.join("data", "self_collected", "session_2", "genuine_control")

DEVICES = ["phone", "laptop", "monitor", "tablet"]
LIGHTINGS = ["normal", "dim", "bright"]
DISTANCES = ["close", "normal", "far"]


def ensure_model():
    if not os.path.exists(MODEL_PATH):
        print(f"[ERROR] {MODEL_PATH} not found in the project root -- capture_images.py normally "
              "downloads this automatically; run that once first, or copy the model file here.")
        sys.exit(1)


def next_filename(directory, prefix):
    idx = 1
    while True:
        fname = f"{prefix}_{idx:02d}.jpg"
        path = os.path.join(directory, fname)
        if not os.path.exists(path):
            return fname, path
        idx += 1


def main():
    ensure_model()
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(CONTROL_DIR, exist_ok=True)

    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.FaceDetectorOptions(base_options=base_options)
    detector = vision.FaceDetector.create_from_options(options)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open webcam.")
        sys.exit(1)

    device_i, lighting_i, distance_i = 0, 0, 1  # default: phone, normal, normal
    attack_count = 0
    control_count = len([f for f in os.listdir(CONTROL_DIR) if f.endswith(".jpg")])
    feedback_text, feedback_color, feedback_expiry = "", (0, 255, 0), 0.0

    print("=" * 60)
    print("Screen-replay sample capture -- Phase 5 Part A")
    print(f"Attack samples save to: {OUT_DIR}")
    print(f"Control samples save to: {CONTROL_DIR}")
    print("=" * 60)
    print("D=device  L=lighting  X=distance  SPACE/C=capture attack  G=capture control  Q=quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Failed to read frame.")
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        det = detector.detect(mp_image)
        num_faces = len(det.detections) if det.detections else 0

        disp = frame.copy()
        for d in (det.detections or []):
            bbox = d.bounding_box
            cv2.rectangle(disp, (bbox.origin_x, bbox.origin_y),
                          (bbox.origin_x + bbox.width, bbox.origin_y + bbox.height), (0, 255, 0), 2)

        y = 25
        label = f"screen_{DEVICES[device_i]}_{LIGHTINGS[lighting_i]}_{DISTANCES[distance_i]}"
        cv2.putText(disp, f"Current label: {label}", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        y += 28
        cv2.putText(disp, "D=device  L=lighting  X=distance  SPACE/C=capture  G=control  Q=quit",
                    (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        y += 22
        cv2.putText(disp, f"Faces detected: {num_faces}", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 255, 0) if num_faces == 1 else (0, 0, 255), 1)
        y += 22
        cv2.putText(disp, f"Attack samples saved: {attack_count}   Control samples saved: {control_count}",
                    (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        if time.time() < feedback_expiry:
            cv2.putText(disp, feedback_text, (15, disp.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, feedback_color, 2)

        cv2.imshow("Screen-Replay Sample Capture", disp)
        key = cv2.waitKey(1) & 0xFF

        if key in (ord("q"), 27):
            break
        elif key == ord("d"):
            device_i = (device_i + 1) % len(DEVICES)
        elif key == ord("l"):
            lighting_i = (lighting_i + 1) % len(LIGHTINGS)
        elif key == ord("x"):
            distance_i = (distance_i + 1) % len(DISTANCES)
        elif key in (ord(" "), ord("c")):
            if num_faces == 0:
                feedback_text, feedback_color = "[WARN] No face detected -- capture cancelled", (0, 0, 255)
            else:
                prefix = f"screen_{DEVICES[device_i]}_{LIGHTINGS[lighting_i]}_{DISTANCES[distance_i]}"
                fname, path = next_filename(OUT_DIR, prefix)
                cv2.imwrite(path, frame)
                attack_count += 1
                feedback_text, feedback_color = f"[SAVED] {fname}", (0, 255, 0)
                print(f"[SAVED] {path}")
            feedback_expiry = time.time() + 2.0
        elif key == ord("g"):
            if num_faces == 0:
                feedback_text, feedback_color = "[WARN] No face detected -- capture cancelled", (0, 0, 255)
            else:
                fname, path = next_filename(CONTROL_DIR, "genuine_control")
                cv2.imwrite(path, frame)
                control_count += 1
                feedback_text, feedback_color = f"[SAVED control] {fname}", (0, 255, 0)
                print(f"[SAVED control] {path}")
            feedback_expiry = time.time() + 2.0

    cap.release()
    cv2.destroyAllWindows()
    detector.close()
    print(f"\nDone. {attack_count} attack samples, {control_count} control samples saved this run.")
    print(f"Attack dir: {os.path.abspath(OUT_DIR)}")
    print(f"Control dir: {os.path.abspath(CONTROL_DIR)}")


if __name__ == "__main__":
    main()
