"""
capture_rppg_window.py

Day 10: Captures a short (10-15 second) video where you hold still, saved
as a sequence of frames. This is NOT used today — rPPG processing itself
is built on Day 19 — but the capture step happens now, while you're
already thinking about liveness capture, so the raw material exists when
you need it later.

Why capture this separately from the head-turn active liveness clip:
motion corrupts the subtle skin-colour pulse signal rPPG depends on, so
this MUST be a dedicated "hold still" clip, not reused from active
liveness footage.

Usage:
    python capture_rppg_window.py --seconds 12 --session 1
"""
import cv2
import os
import argparse
import time

OUTPUT_DIR = os.path.join("data", "self_collected", "session_{}", "rppg_window")


def main(seconds, session):
    out_dir = OUTPUT_DIR.format(session)
    os.makedirs(out_dir, exist_ok=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam.")
        return

    fps_estimate = 20  # typical webcam default; actual rate will vary slightly
    total_frames_expected = seconds * fps_estimate

    print(f"Recording a {seconds}-second still window for rPPG use on Day 19.")
    print("Sit still, look at the camera, keep your face well and evenly lit.")
    print("Recording starts in 3 seconds...")
    time.sleep(3)

    frame_idx = 0
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        elapsed = time.time() - start_time
        filename = os.path.join(out_dir, f"rppg_frame_{frame_idx:04d}.jpg")
        cv2.imwrite(filename, frame)
        frame_idx += 1

        display = frame.copy()
        remaining = max(0, seconds - elapsed)
        cv2.putText(display, f"HOLD STILL - {remaining:.1f}s remaining",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow("rPPG Window Capture", display)

        if elapsed >= seconds:
            break
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Cancelled early.")
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"Captured {frame_idx} frames over {elapsed:.1f} seconds into {out_dir}/")
    print("These frames are the raw input for the rPPG pipeline built on Day 19")
    print("(ROI extraction -> bandpass filter -> FFT peak check).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=12, help="Recording duration, 10-15s recommended")
    parser.add_argument("--session", type=int, default=1)
    args = parser.parse_args()
    main(args.seconds, args.session)
