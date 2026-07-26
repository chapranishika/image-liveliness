"""
day19_attack_testing_matrix.py

Day 19: Runs the full quality-and-liveness pipeline (Day 14) against every
staged attack category captured back on Day 6: photograph, screen replay,
video replay, frozen frame, and multiple face. Produces one clear results
table showing which layer actually caught each attack type, exactly the
attack-scenario matrix described in the Approach & Design Document
(Section 9).

Usage:
    python day19_attack_testing_matrix.py
"""
import cv2
import os
import sys
import csv

sys.path.insert(0, os.path.dirname(__file__))
from src.pipeline import run_quality_and_liveness_stage

ATTACKS_DIR = os.path.join("data", "self_collected", "session_1", "attacks")
OUTPUT_CSV = os.path.join("data", "day19_attack_matrix_results.csv")

CATEGORY_MAP = {
    "printed": "Photograph Attack",
    "screen": "Screen Replay Attack",
    "video": "Video Replay Attack",
    "frozen": "Frozen Frame Attack",
    "multiple": "Multiple Face Attack",
}


def classify_filename(fname):
    for prefix, label in CATEGORY_MAP.items():
        if fname.lower().startswith(prefix):
            return label
    return "Unclassified"


def main():
    if not os.path.isdir(ATTACKS_DIR):
        print(f"Attacks folder not found: {ATTACKS_DIR}")
        return

    files = sorted(f for f in os.listdir(ATTACKS_DIR) if f.lower().endswith((".jpg", ".png")))
    if not files:
        print("No attack images found. Capture them first (see capture_images.py, key 'a').")
        return

    results = []
    for fname in files:
        path = os.path.join(ATTACKS_DIR, fname)
        frame = cv2.imread(path)
        if frame is None:
            print(f"[WARN] Could not read {fname}, skipping.")
            continue

        attack_type = classify_filename(fname)
        # Active liveness is deliberately OFF here: these are static images,
        # and active liveness needs a live multi-frame session, not a single
        # saved frame -- this matrix specifically measures what QUALITY and
        # PASSIVE liveness alone catch, which is the honest, correct scope
        # for a batch test against saved images.
        stage_result = run_quality_and_liveness_stage(frame, run_active_challenge=False)

        caught_at = "NOT CAUGHT"
        reason = ""
        if stage_result["overall_status"] == "reject":
            caught_at = stage_result["rejected_at_stage"]
            detail = stage_result["detail"]
            reason = detail.get("failed_check") or detail.get("reason", "")

        results.append({
            "filename": fname,
            "attack_type": attack_type,
            "expected": "rejected",
            "actual": "rejected" if caught_at != "NOT CAUGHT" else "PASSED (security concern)",
            "caught_at_stage": caught_at,
            "reason": reason,
        })
        print(f"{attack_type:<24} {fname:<28} caught_at={caught_at:<10} reason={reason}")

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"\nWrote {len(results)} rows to {OUTPUT_CSV}")

    print("\n" + "=" * 60)
    print("SUMMARY BY ATTACK TYPE")
    print("=" * 60)
    types = sorted(set(r["attack_type"] for r in results))
    for t in types:
        rows = [r for r in results if r["attack_type"] == t]
        caught = sum(1 for r in rows if r["caught_at_stage"] != "NOT CAUGHT")
        print(f"{t}: {caught}/{len(rows)} correctly rejected")

    not_caught = [r for r in results if r["caught_at_stage"] == "NOT CAUGHT"]
    if not_caught:
        print(f"\n{len(not_caught)} attack image(s) were NOT caught by quality or passive liveness alone:")
        for r in not_caught:
            print(f"  - {r['filename']} ({r['attack_type']})")
        print("This is exactly the honest gap active liveness and rPPG exist to close --")
        print("log this finding plainly rather than treating it as a failure.")


if __name__ == "__main__":
    main()
