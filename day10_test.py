"""
day10_test.py

Runs the passive liveness check against every self-collected image —
both genuine good-pose images (front/left/right, expected to pass) and
staged attack images (expected to fail) — and writes results to CSV.

This is the same "measure against real data, don't just trust the design"
discipline used in Days 7-9: DeepFace's anti-spoofing model is pretrained
and not something we built ourselves, so today's job is to verify it
actually behaves as expected on OUR camera and OUR staged attacks, not
just trust published accuracy numbers.

Usage:
    python day10_test.py
"""
import os
import csv
import cv2
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.liveness_passive import check_passive_liveness

DATA_DIR = os.path.join("data", "self_collected", "session_1")
OUTPUT_CSV = os.path.join("data", "day10_passive_liveness_results.csv")

EXPECTED_REAL = {"front", "left", "right"}
EXPECTED_SPOOF = {"attacks"}


def collect_images():
    rows = []
    for category in os.listdir(DATA_DIR):
        cat_path = os.path.join(DATA_DIR, category)
        if not os.path.isdir(cat_path):
            continue
        for fname in os.listdir(cat_path):
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                rows.append((category, os.path.join(cat_path, fname)))
    return rows


def main():
    images = collect_images()
    if not images:
        print(f"No images found under {DATA_DIR}.")
        return

    results = []
    correct = 0
    total_scored = 0

    for category, path in images:
        img = cv2.imread(path)
        if img is None:
            print(f"[WARN] Could not read {path}, skipping.")
            continue

        result = check_passive_liveness(img)
        expected = "real" if category in EXPECTED_REAL else ("spoof" if category in EXPECTED_SPOOF else "n/a")

        actual = "real" if result["is_real"] else ("spoof" if result["is_real"] is False else "error")
        is_correct = None
        if expected in ("real", "spoof") and actual in ("real", "spoof"):
            is_correct = (expected == actual)
            total_scored += 1
            if is_correct:
                correct += 1

        results.append({
            "category": category,
            "filename": os.path.basename(path),
            "expected": expected,
            "is_real": result["is_real"],
            "antispoof_score": result["antispoof_score"],
            "status": result["status"],
            "reason": result["reason"],
            "correct": is_correct,
        })
        print(f"{category:<10} {os.path.basename(path):<28} "
              f"expected={expected:<6} is_real={result['is_real']!s:<6} "
              f"score={result['antispoof_score']!s:<8} status={result['status']}")

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"\nWrote {len(results)} rows to {OUTPUT_CSV}")
    if total_scored:
        accuracy = correct / total_scored * 100
        print(f"Passive liveness accuracy on self-collected images: {correct}/{total_scored} ({accuracy:.1f}%)")
    print("\nLook specifically at which attack subtypes fooled the model, if any —")
    print("that becomes real evidence for your attack-testing matrix (Day 18/19),")
    print("not just a pass/fail number. Log the breakdown in OneNote.")


if __name__ == "__main__":
    main()
