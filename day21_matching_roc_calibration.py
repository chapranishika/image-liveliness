"""
day21_matching_roc_calibration.py

Day 21, Step 3: Replaces the placeholder match_threshold=0.68 (set back on
Day 15 with an explicit "pending Day 20/21 calibration" comment) with a
real, measured threshold derived from actual genuine and impostor
similarity scores, using scikit-learn's ROC curve tools.

Genuine pairs: two different images of the SAME person -> should score high.
Impostor pairs: images of DIFFERENT people -> should score low.
The Equal Error Rate (EER) is the threshold where the rate of wrongly
rejecting genuine users equals the rate of wrongly accepting impostors --
the standard, defensible way to pick a similarity threshold, per the
project's own Research Reference Table (Yu et al. TPAMI survey).

This script uses self-collected images as a minimum viable calibration set.
For the full calibration the Approach & Design Document specifies (LFW +
CFP pairs), swap DATA_DIR / pairing logic below for those datasets once
sampled -- the ROC/EER math itself does not change.

Usage:
    python day21_matching_roc_calibration.py
"""
import cv2
import os
import sys
import itertools
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc

sys.path.insert(0, os.path.dirname(__file__))
from src.face_matching import get_embedding, cosine_similarity

DATA_DIR = os.path.join("data", "self_collected", "session_1")
GENUINE_CATEGORIES = ["front", "left", "right"]


def load_embeddings():
    """Returns {category: [(filename, embedding), ...]}"""
    embeddings = {}
    for category in GENUINE_CATEGORIES:
        folder = os.path.join(DATA_DIR, category)
        if not os.path.isdir(folder):
            continue
        items = []
        for fname in sorted(os.listdir(folder)):
            if not fname.lower().endswith((".jpg", ".png")):
                continue
            frame = cv2.imread(os.path.join(folder, fname))
            result = get_embedding(frame)
            if result["status"] == "success":
                items.append((fname, result["embedding"]))
        embeddings[category] = items
    return embeddings


def build_genuine_pairs(embeddings):
    """
    All pairs of images within the SAME identity, across categories --
    e.g. front vs left, front vs right, left vs right -- since these all
    represent the same real person and should score highly, testing
    exactly the cross-angle matching the multi-angle design depends on.
    """
    all_items = [item for cat_items in embeddings.values() for item in cat_items]
    scores = []
    for (name_a, emb_a), (name_b, emb_b) in itertools.combinations(all_items, 2):
        scores.append(cosine_similarity(emb_a, emb_b))
    return scores


def build_impostor_pairs_from_cfp_placeholder():
    """
    IMPORTANT HONEST NOTE: with only ONE self-collected identity available,
    there are no genuine "different person" pairs to build impostor scores
    from -- every self-collected image is the SAME person. This function
    is a clearly-labeled placeholder returning a synthetic impostor
    distribution for demonstration purposes ONLY, so the ROC/EER code path
    can be shown working end to end.

    THIS MUST BE REPLACED with real impostor pairs from CFP (different
    identities) or a second real registered person before this threshold
    is treated as production-ready -- do not deploy a threshold calibrated
    against synthetic impostor data.
    """
    print("[WARNING] No second real identity available -- using a SYNTHETIC")
    print("impostor score distribution as a clearly-labeled placeholder.")
    print("Replace with real CFP cross-identity pairs before trusting this")
    print("threshold in production. See Approach & Design Document, Part 0.2.\n")
    rng = np.random.default_rng(seed=42)
    # A synthetic distribution centered well below typical genuine scores,
    # loosely modeled on published ArcFace impostor-score literature --
    # explicitly NOT real measured data.
    return list(np.clip(rng.normal(loc=0.15, scale=0.12, size=40), -1.0, 1.0))


def main():
    print("Loading and embedding all self-collected genuine images...")
    embeddings = load_embeddings()
    total_images = sum(len(v) for v in embeddings.values())
    print(f"Loaded {total_images} images across {list(embeddings.keys())}\n")

    genuine_scores = build_genuine_pairs(embeddings)
    impostor_scores = build_impostor_pairs_from_cfp_placeholder()

    print(f"Genuine pairs: {len(genuine_scores)} (real, measured)")
    print(f"Impostor pairs: {len(impostor_scores)} (SYNTHETIC placeholder, see warning above)\n")

    y_true = [1] * len(genuine_scores) + [0] * len(impostor_scores)
    y_scores = genuine_scores + impostor_scores

    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    fnr = 1 - tpr
    roc_auc = auc(fpr, tpr)

    eer_idx = np.nanargmin(np.abs(fnr - fpr))
    eer_threshold = thresholds[eer_idx]
    eer_value = (fpr[eer_idx] + fnr[eer_idx]) / 2

    print(f"AUC: {roc_auc:.4f}")
    print(f"EER: {eer_value:.4f} at threshold {eer_threshold:.4f}")
    print(f"\nRECALIBRATED match_threshold suggestion: {eer_threshold:.4f}")
    print("(compare against the Day 15 placeholder of 0.68 -- update")
    print("face_matching.py's default threshold once real impostor data")
    print("replaces the synthetic placeholder above)")

    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, label=f"ROC curve (AUC = {roc_auc:.3f})")
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Random guess")
    plt.scatter(fpr[eer_idx], tpr[eer_idx], color="red", zorder=5, label=f"EER point ({eer_value:.3f})")
    plt.xlabel("False Positive Rate (impostor accepted)")
    plt.ylabel("True Positive Rate (genuine accepted)")
    plt.title("Face Matching ROC Curve (Day 21 Calibration)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join("data", "day21_matching_roc_curve.png"), dpi=150)
    print("\nROC curve saved to data/day21_matching_roc_curve.png")


if __name__ == "__main__":
    main()
