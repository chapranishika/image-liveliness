"""
capture_images.py
Opens your webcam and lets you save labeled frames on keypress, organized
into the data/self_collected/ folder structure from the Approach & Design
Document.

Controls (while the webcam window is focused):
    f   -> save frame into data/self_collected/front/
    l   -> save frame into data/self_collected/left/
    r   -> save frame into data/self_collected/right/
    b   -> save frame into data/self_collected/bad_quality/
    a   -> save frame into data/self_collected/attacks/
    q   -> quit

Each save is auto-numbered and stamped with today's session date, e.g.
    front/front_session1_2026-07-16_001.jpg

Usage:
    python capture_images.py --session 1
"""
import cv2
import os
import argparse
from datetime import date

CATEGORY_KEYS = {
    ord("f"): "front",
    ord("l"): "left",
    ord("r"): "right",
    ord("b"): "bad_quality",
    ord("a"): "attacks",
}

BASE_DIR = os.path.join("data", "self_collected")


def next_index(folder, prefix):
    existing = [f for f in os.listdir(folder) if f.startswith(prefix)]
    return len(existing) + 1


def main(session):
    today = date.today().isoformat()
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam. Check camera permissions/connection.")
        return

    print("Capture running. Keys: f=front  l=left  r=right  b=bad_quality  a=attacks  q=quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame from webcam.")
            break

        display = frame.copy()
        cv2.putText(display, "f=front l=left r=right b=bad a=attack q=quit",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
        cv2.imshow("Self-Collection Capture", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key in CATEGORY_KEYS:
            category = CATEGORY_KEYS[key]
            folder = os.path.join(BASE_DIR, category)
            os.makedirs(folder, exist_ok=True)
            prefix = f"{category}_session{session}_{today}"
            idx = next_index(folder, prefix)
            filename = os.path.join(folder, f"{prefix}_{idx:03d}.jpg")
            cv2.imwrite(filename, frame)
            print(f"[SAVED] {filename}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=int, default=1, help="Session number (increment each new day/lighting session)")
    args = parser.parse_args()
    main(args.session)
