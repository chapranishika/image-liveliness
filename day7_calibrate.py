"""
day7_calibrate.py

Runs the brightness and blur checks from src/quality_checks.py against every
image in data/self_collected/, and writes the raw measured values to a CSV.

This is the actual point of Day 7: don't guess thresholds, look at what your
own camera produces for genuinely good vs genuinely bad images, then pick
thresholds that separate them, and write the reasoning into OneNote.

Usage:
    python day7_calibrate.py
"""
import os
import csv
import cv2
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.quality_checks import check_brightness, check_blur

DATA_DIR = os.path.join("data", "self_collected")
OUTPUT_CSV = os.path.join("data", "day7_quality_results.csv")

# Categories where we EXPECT a pass, vs where we deliberately captured bad
# examples and EXPECT at least one of the checks to fail.
EXPECTED_GOOD = {"front", "left", "right"}
EXPECTED_BAD = {"bad_quality"}


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

        brightness = check_brightness(img)
        blur = check_blur(img)

        expected = "good" if category in EXPECTED_GOOD else ("bad" if category in EXPECTED_BAD else "n/a")

        results.append({
            "category": category,
            "filename": os.path.basename(path),
            "expected": expected,
            "brightness_value": brightness["value"],
            "brightness_status": brightness["status"],
            "blur_value": blur["value"],
            "blur_status": blur["status"],
        })

    # Write CSV
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"Wrote {len(results)} rows to {OUTPUT_CSV}\n")

    # Print a quick per-category summary to help pick thresholds
    print(f"{'Category':<14}{'Count':<7}{'Brightness min/mean/max':<28}{'Blur min/mean/max'}")
    categories = sorted(set(r["category"] for r in results))
    for cat in categories:
        rows = [r for r in results if r["category"] == cat]
        b_vals = [r["brightness_value"] for r in rows]
        blur_vals = [r["blur_value"] for r in rows]
        b_summary = f"{min(b_vals):.1f} / {sum(b_vals)/len(b_vals):.1f} / {max(b_vals):.1f}"
        blur_summary = f"{min(blur_vals):.1f} / {sum(blur_vals)/len(blur_vals):.1f} / {max(blur_vals):.1f}"
        print(f"{cat:<14}{len(rows):<7}{b_summary:<28}{blur_summary}")

    print("\nLook at where 'front/left/right' values land vs 'bad_quality' values.")
    print("Pick BRIGHTNESS_MIN/MAX and BLUR_MIN in src/quality_checks.py so they")
    print("separate the two groups, then write the chosen numbers and why into")
    print("OneNote's Daily Log for today, and into the Excel tracker's Notes column.")


if __name__ == "__main__":
    main()
