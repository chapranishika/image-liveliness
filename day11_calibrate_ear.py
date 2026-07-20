"""
day11_calibrate_ear.py

Before trusting the EAR_BLINK_THRESHOLD placeholder value in liveness_active.py,
this script measures your OWN eyes-open vs eyes-closed EAR values, live,
so the threshold is chosen from real numbers, not the textbook default.

This matters because the Real-time Eye Blink Detection paper (Soukupova &
Cech, 2016) and its replications note that eye shape varies enough between
people that a single universal EAR threshold does not generalize perfectly
— exactly the same "don't guess, measure" discipline as Days 7 and 8.

Usage:
    python day11_calibrate_ear.py
    Follow on-screen instructions: keep eyes OPEN normally for 5 seconds,
    then CLOSE your eyes for 3 seconds, then open again.
"""
import cv2
import mediapipe as mp
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from src.liveness_active import compute_ear, RIGHT_EYE, LEFT_EYE

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam.")
        return

    model_path = "face_landmarker.task"
    if not os.path.exists(model_path):
        model_path = os.path.join(os.path.dirname(__file__), "face_landmarker.task")

    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        num_faces=1
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)

    open_ears = []
    closed_ears = []
    phase_duration = 5  # seconds for "open" phase
    closed_duration = 3  # seconds for "closed" phase

    print("Phase 1: keep your eyes OPEN normally for 5 seconds...")

    phase = "open"
    phase_start = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        results = landmarker.detect(mp_image)

        elapsed_phase = time.time() - phase_start
        display = frame.copy()

        if results.face_landmarks:
            landmarks = results.face_landmarks[0]
            ear = (compute_ear(landmarks, RIGHT_EYE, w, h) +
                   compute_ear(landmarks, LEFT_EYE, w, h)) / 2.0

            if phase == "open":
                open_ears.append(ear)
                label = f"OPEN phase - {phase_duration - elapsed_phase:.1f}s left - EAR={ear:.3f}"
            elif phase == "closed":
                closed_ears.append(ear)
                label = f"CLOSED phase - {closed_duration - elapsed_phase:.1f}s left - EAR={ear:.3f}"
            else:
                label = "Done"

            cv2.putText(display, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 255, 0), 2)

        cv2.imshow("EAR Calibration", display)

        if phase == "open" and elapsed_phase >= phase_duration:
            phase = "closed"
            phase_start = time.time()
            print("Phase 2: CLOSE your eyes now for 3 seconds...")
        elif phase == "closed" and elapsed_phase >= closed_duration:
            break

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    landmarker.close()
    cap.release()
    cv2.destroyAllWindows()

    if not open_ears or not closed_ears:
        print("Not enough data captured. Try again with better lighting/face visibility.")
        return

    print("\n" + "=" * 50)
    print("CALIBRATION RESULTS")
    print("=" * 50)
    print(f"Eyes OPEN   -> min={min(open_ears):.3f}  mean={sum(open_ears)/len(open_ears):.3f}  max={max(open_ears):.3f}")
    print(f"Eyes CLOSED -> min={min(closed_ears):.3f}  mean={sum(closed_ears)/len(closed_ears):.3f}  max={max(closed_ears):.3f}")
    midpoint = (min(open_ears) + max(closed_ears)) / 2
    print(f"\nSuggested EAR_BLINK_THRESHOLD (midpoint of the gap): {midpoint:.3f}")
    print("Update EAR_BLINK_THRESHOLD in liveness_active.py with this value")
    print("(or your own judgment call within the gap), and log the reasoning in OneNote.")


if __name__ == "__main__":
    main()
