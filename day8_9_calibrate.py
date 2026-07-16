"""
day8_9_calibrate.py

Runs pose, position, single-face, and occlusion checks against every image
in data/self_collected/, prints the raw values so you can judge whether
your thresholds in quality_checks_day8_9.py actually separate good from bad
examples, same philosophy as day7_calibrate.py.

Usage:
    python day8_9_calibrate.py
"""
import os
import csv
import cv2
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.quality_checks_day8_9 import check_pose, check_position, check_single_face, check_occlusion

DATA_DIR = os.path.join("data", "self_collected")
OUTPUT_CSV = os.path.join("data", "day8_9_quality_results.csv")


def collect_images():
    rows = []
    for session_name in os.listdir(DATA_DIR):
        session_path = os.path.join(DATA_DIR, session_name)
        if not os.path.isdir(session_path) or not session_name.startswith("session_"):
            continue
        for category in os.listdir(session_path):
            cat_path = os.path.join(session_path, category)
            if not os.path.isdir(cat_path):
                continue
            for fname in os.listdir(cat_path):
                if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    rows.append((category, os.path.join(cat_path, fname)))
    return rows


def main():
    images = collect_images()
    if not images:
        print(f"No images found under {DATA_DIR}. Run capture_images.py first.")
        return

    results = []
    for category, path in images:
        img = cv2.imread(path)
        if img is None:
            print(f"[WARN] Could not read {path}, skipping.")
            continue

        single_face = check_single_face(img)
        pose = check_pose(img)
        position = check_position(img)
        occlusion = check_occlusion(img)

        results.append({
            "category": category,
            "filename": os.path.basename(path),
            "face_count": single_face.get("face_count"),
            "single_face_status": single_face.get("status"),
            "yaw": pose.get("yaw"),
            "pitch": pose.get("pitch"),
            "roll": pose.get("roll"),
            "pose_classification": pose.get("classification"),
            "pose_status": pose.get("status"),
            "face_area_ratio": position.get("face_area_ratio"),
            "x_offset": position.get("x_offset"),
            "y_offset": position.get("y_offset"),
            "position_status": position.get("status"),
            "detection_score": occlusion.get("detection_score"),
            "occlusion_status": occlusion.get("status"),
            "occlusion_reason": occlusion.get("reason"),
        })
        print(f"{category:<12} {os.path.basename(path):<35} "
              f"yaw={pose.get('yaw')!s:<7} class={pose.get('classification')!s:<14} "
              f"pos={position.get('status')!s:<5} occl={occlusion.get('status')!s}")

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"\nWrote {len(results)} rows to {OUTPUT_CSV}")
    print("\nWhat to look for:")
    print("- front/ images should classify as 'frontal' and pass pose")
    print("- left/ images should classify as 'profile_left' with yaw roughly -15 to -35")
    print("- right/ images should classify as 'profile_right' with yaw roughly 15 to 35")
    print("- your deliberately extreme-angle bad_quality shots should classify as 'extreme' and fail")
    print("- your deliberately occluded bad_quality shots should fail the occlusion check")
    print("If they don't sort this way, adjust the threshold constants at the top of")
    print("quality_checks_day8_9.py and rerun, then log the final numbers and why in OneNote.")


if __name__ == "__main__":
    main()
