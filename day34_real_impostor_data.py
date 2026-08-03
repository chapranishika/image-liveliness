"""
day34_real_impostor_data.py

Phase A: Real Impostor Data (Day 34)
Parses the CFP dataset to extract real genuine and real impostor score distributions
using the ArcFace matching pipeline. Caches embeddings to optimize performance.
"""
import os
import sys
import cv2
import itertools
import numpy as np
import kagglehub

sys.path.insert(0, os.path.dirname(__file__))
from src.face_matching import get_embedding, cosine_similarity

def _infer_identity(filepath):
    """
    Deliberately the ONLY function in the codebase that encodes folder layout assumptions.
    Derives the unique identity ID from a given file path in the CFP dataset.
    """
    normalized = os.path.normpath(filepath)
    parts = normalized.split(os.sep)
    for category in ["frontal", "profile"]:
        if category in parts:
            idx = parts.index(category)
            if idx > 0:
                return parts[idx - 1]
    # Fallback to directory base names
    return os.path.basename(os.path.dirname(os.path.dirname(filepath)))

def get_cfp_images_dir():
    """Returns the cached path to CFP Images directory via kagglehub."""
    cache_path = kagglehub.dataset_download("chinafax/cfpw-dataset")
    return os.path.join(cache_path, "cfp-dataset", "Data", "Images")

def load_cfp_identities(cfp_data_dir, max_identities=50):
    """
    Loads frontal and profile file paths for up to max_identities identities.
    Returns:
        dict: {identity_id: {"frontal": [paths], "profile": [paths]}}
    """
    if not os.path.isdir(cfp_data_dir):
        raise ValueError(f"CFP Images folder '{cfp_data_dir}' not found.")

    identities = {}
    # Scan sorted list of directory names to be deterministic
    subdirs = sorted([d for d in os.listdir(cfp_data_dir) if os.path.isdir(os.path.join(cfp_data_dir, d))])
    
    count = 0
    for subdir in subdirs:
        if count >= max_identities:
            break
        id_path = os.path.join(cfp_data_dir, subdir)
        
        frontal_dir = os.path.join(id_path, "frontal")
        profile_dir = os.path.join(id_path, "profile")
        
        if os.path.isdir(frontal_dir) and os.path.isdir(profile_dir):
            frontals = sorted([
                os.path.join(frontal_dir, f) for f in os.listdir(frontal_dir)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ])
            profiles = sorted([
                os.path.join(profile_dir, f) for f in os.listdir(profile_dir)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ])
            
            if frontals and profiles:
                # Infer identity once to verify folder assumption
                inferred_id = _infer_identity(frontals[0])
                identities[inferred_id] = {
                    "frontal": frontals,
                    "profile": profiles
                }
                count += 1
                
    return identities

def build_real_impostor_pairs(identities_dict, max_pairs=200):
    """
    Computes real cross-identity impostor scores.
    Compares the first frontal image of different identities.
    Caches embeddings to run in O(N) rather than O(N^2) embedding extractions.
    """
    print(f"[day34] Generating real impostor pairs (max_pairs={max_pairs})...")
    # Pre-extract first frontal embedding for each identity
    id_embeddings = {}
    for ident_id, data in identities_dict.items():
        first_front_path = data["frontal"][0]
        img = cv2.imread(first_front_path)
        res = get_embedding(img)
        if res["status"] == "success":
            id_embeddings[ident_id] = res["embedding"]
            
    if len(id_embeddings) < 2:
        print("[day34] Warning: Less than 2 identities successfully embedded.")
        return []

    impostor_scores = []
    pairs = list(itertools.combinations(id_embeddings.keys(), 2))
    
    # Sort or shuffle deterministically to make it reproducible
    pairs = sorted(pairs)
    
    pair_count = 0
    for id_a, id_b in pairs:
        if pair_count >= max_pairs:
            break
        # Compare cached embeddings
        sim = cosine_similarity(id_embeddings[id_a], id_embeddings[id_b])
        impostor_scores.append(sim)
        pair_count += 1
        
    return impostor_scores

def build_real_genuine_pairs_from_cfp(identities_dict):
    """
    Computes real within-identity genuine cross-angle scores (frontal vs profile).
    To keep the compute bounded, we limit to the first 2 frontal images and
    first 2 profile images per identity.
    """
    print("[day34] Generating real genuine cross-angle pairs from CFP...")
    genuine_scores = []
    
    for ident_id, data in identities_dict.items():
        # Limit target lists to avoid combinatorial explosion
        fronts = data["frontal"][:2]
        profs = data["profile"][:2]
        
        # Pre-compute embeddings for this identity's sample
        front_embs = []
        for p in fronts:
            img = cv2.imread(p)
            res = get_embedding(img)
            if res["status"] == "success":
                front_embs.append(res["embedding"])
                
        prof_embs = []
        for p in profs:
            img = cv2.imread(p)
            res = get_embedding(img)
            if res["status"] == "success":
                prof_embs.append(res["embedding"])
                
        # Compute all cross-angle combinations within this identity
        for f_emb in front_embs:
            for p_emb in prof_embs:
                sim = cosine_similarity(f_emb, p_emb)
                genuine_scores.append(sim)
                
    return genuine_scores

def main():
    try:
        cfp_dir = get_cfp_images_dir()
        print(f"[day34] Loading identities from: {cfp_dir}")
        identities = load_cfp_identities(cfp_dir, max_identities=25)
        print(f"[day34] Successfully loaded {len(identities)} CFP identities.")
        
        impostors = build_real_impostor_pairs(identities, max_pairs=200)
        genuines = build_real_genuine_pairs_from_cfp(identities)
        
        print(f"[day34] Built {len(impostors)} real impostor pairs.")
        print(f"[day34] Built {len(genuines)} real genuine pairs.")
        
        if impostors:
            print(f"[day34] Impostor Scores: min={min(impostors):.4f}, mean={np.mean(impostors):.4f}, max={max(impostors):.4f}")
        if genuines:
            print(f"[day34] Genuine Scores: min={min(genuines):.4f}, mean={np.mean(genuines):.4f}, max={max(genuines):.4f}")
            
    except Exception as e:
        print(f"[day34] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
