"""
day21_spoof_detection_calibration.py

Day 21, Step 4: Calibrates the passive liveness decision boundary using
real antispoof_score values from DeepFace/MiniFASNet, following the same
APCER/BPCER/ACER metrics established in the Approach & Design Document
(Section 11) and the Days 6-9 Engineering Log, rather than trusting
MiniFASNet's internal default cutoff blindly.

Genuine scores: antispoof_score from real self-collected front/left/right
images (should score high / is_real=True).
Attack scores: antispoof_score from staged attack images (should score
low / is_real=False).

Usage:
    python day21_spoof_detection_calibration.py
"""
import cv2
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from src.liveness_passive import check_passive_liveness

DATA_DIR = os.path.join("data", "self_collected", "session_1")
GENUINE_CATEGORIES = ["front", "left", "right"]
ATTACK_CATEGORY = "attacks"


def collect_scores(categories):
    scores = []
    for category in categories:
        folder = os.path.join(DATA_DIR, category)
        if not os.path.isdir(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if not fname.lower().endswith((".jpg", ".png")):
                continue
            frame = cv2.imread(os.path.join(folder, fname))
            if frame is None:
                continue
            result = check_passive_liveness(frame)
            if result.get("antispoof_score") is not None:
                scores.append((fname, result["antispoof_score"], result["is_real"]))
    return scores


def compute_apcer_bpcer(genuine_scores, attack_scores, threshold):
    """
    APCER: proportion of ATTACK images wrongly accepted (score >= threshold).
    BPCER: proportion of GENUINE images wrongly rejected (score < threshold).
    """
    if not attack_scores:
        apcer = None
    else:
        wrongly_accepted = sum(1 for s in attack_scores if s >= threshold)
        apcer = wrongly_accepted / len(attack_scores)

    if not genuine_scores:
        bpcer = None
    else:
        wrongly_rejected = sum(1 for s in genuine_scores if s < threshold)
        bpcer = wrongly_rejected / len(genuine_scores)

    return apcer, bpcer


def main():
    print("Scoring genuine images (front/left/right)...")
    genuine = collect_scores(GENUINE_CATEGORIES)
    print("Scoring attack images...")
    attacks = collect_scores([ATTACK_CATEGORY])

    genuine_scores = [s for _, s, _ in genuine]
    attack_scores = [s for _, s, _ in attacks]

    print(f"\nGenuine antispoof_scores ({len(genuine_scores)} images): "
          f"min={min(genuine_scores):.4f} mean={np.mean(genuine_scores):.4f} max={max(genuine_scores):.4f}"
          if genuine_scores else "\nNo genuine scores collected.")
    print(f"Attack antispoof_scores ({len(attack_scores)} images): "
          f"min={min(attack_scores):.4f} mean={np.mean(attack_scores):.4f} max={max(attack_scores):.4f}"
          if attack_scores else "No attack scores collected.")

    if not genuine_scores or not attack_scores:
        print("\nInsufficient data to calibrate -- need both genuine and attack scores.")
        return

    print("\n" + "=" * 70)
    print("APCER / BPCER / ACER across candidate thresholds")
    print("=" * 70)
    print(f"{'Threshold':<12}{'APCER (attacks missed)':<26}{'BPCER (genuine rejected)':<26}{'ACER'}")

    best_threshold = None
    best_acer = float("inf")
    for threshold in np.arange(0.1, 1.0, 0.05):
        apcer, bpcer = compute_apcer_bpcer(genuine_scores, attack_scores, threshold)
        acer = (apcer + bpcer) / 2
        print(f"{threshold:<12.2f}{apcer:<26.3f}{bpcer:<26.3f}{acer:.3f}")
        if acer < best_acer:
            best_acer = acer
            best_threshold = threshold

    print(f"\nBest threshold by minimum ACER: {best_threshold:.2f} (ACER={best_acer:.3f})")
    print("\nHonest note: this project's Day 10 test already showed 100% accuracy")
    print("(26/26) at MiniFASNet's own default internal cutoff, so this calibration")
    print("is a confirmatory exercise on a small sample, not a correction of a broken")
    print("system. A larger, more diverse attack sample (varied lighting, more attack")
    print("subtypes, ideally CelebA-Spoof) would give a materially more trustworthy")
    print("ACER number than 8 attack images alone can provide.")


if __name__ == "__main__":
    main()
