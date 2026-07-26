"""
day21_quality_profile_calibration.py

Day 21, Step 2: Runs ALL THREE quality profiles (strict/balanced/lenient)
against every self-collected image, and produces the client-facing table
your mentor's feedback specifically asked for: "at this threshold, what
percentage of real users would actually get through."

This is a materially different question from Day 7-9's per-check
calibration (which asked "does this ONE check separate good from bad").
Today asks "across the FULL composite score, how many genuine users pass
at each of the three client-facing settings" -- the actual number a client
would want before choosing a profile for their deployment.

Usage:
    python day21_quality_profile_calibration.py
"""
import cv2
import os
import sys
import csv

sys.path.insert(0, os.path.dirname(__file__))
from src.quality_score import compute_quality_score, QUALITY_PROFILES

DATA_DIR = os.path.join("data", "self_collected", "session_1")
OUTPUT_CSV = os.path.join("data", "day21_quality_profile_results.csv")

GENUINE_CATEGORIES = {"front", "left", "right"}


def collect_genuine_images():
    rows = []
    for category in GENUINE_CATEGORIES:
        folder = os.path.join(DATA_DIR, category)
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            if fname.lower().endswith((".jpg", ".png")):
                rows.append((category, os.path.join(folder, fname)))
    return rows


def main():
    images = collect_genuine_images()
    if not images:
        print(f"No genuine images found under {DATA_DIR}.")
        return

    all_results = []
    for category, path in images:
        frame = cv2.imread(path)
        if frame is None:
            continue

        row = {"category": category, "filename": os.path.basename(path)}
        for profile_name in QUALITY_PROFILES:
            result = compute_quality_score(frame, profile=profile_name)
            row[f"{profile_name}_score"] = result["overall_score"]
            row[f"{profile_name}_decision"] = result["decision"]
        all_results.append(row)

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
        writer.writeheader()
        writer.writerows(all_results)

    print(f"Wrote {len(all_results)} rows to {OUTPUT_CSV}\n")

    print("=" * 70)
    print("CLIENT-FACING SUMMARY: Genuine User Acceptance Rate by Profile")
    print("=" * 70)
    for profile_name, config in QUALITY_PROFILES.items():
        accepted = sum(1 for r in all_results if r[f"{profile_name}_decision"] == "accept")
        total = len(all_results)
        pct = accepted / total * 100
        print(f"\n{profile_name.upper()} (threshold={config['threshold']}%) -- {config['description']}")
        print(f"  {accepted}/{total} genuine images accepted ({pct:.1f}%)")

    print("\n" + "=" * 70)
    print("This table is exactly what to show a client when choosing a profile:")
    print("if BALANCED rejects too many real users in practice, that is the")
    print("concrete, numeric justification for switching to LENIENT for their")
    print("specific user base -- not a guess, a measured tradeoff.")
    print("\nNote the honest limitation: this is still only 18 genuine images from")
    print("one person. A real client rollout should repeat this exact calibration")
    print("against a larger, more diverse set of real users before finalizing.")


if __name__ == "__main__":
    main()
