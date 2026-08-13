"""
src/duplicate_check.py

Day 17 (build) and Day 18 (hardening): Checks whether a new registration
attempt's front embedding matches any EXISTING registered user's front
embedding above the match threshold — catching someone trying to register
the same face twice under a different name.

Deliberately compares against front templates ONLY, not all three angles
per user, per the Approach & Design Document (Part 0.1): checking all
three would triple the comparison cost for no real accuracy benefit, since
the front template alone is distinctive enough to catch a duplicate.
"""
from src.face_matching import cosine_similarity
from src.db import get_all_front_templates

# Deployed duplicate threshold. Set to 0.68, which sits optimally in the wide gap between
# genuine frontal-vs-frontal matches (approx 0.9676) and impostor frontal-vs-frontal matches
# (approx 0.2850). This maximizes protection against false-positive duplicate detections
# while securely catching duplicate registrations.
DUPLICATE_THRESHOLD = 0.68


def check_for_duplicate(new_front_embedding, exclude_user_id=None):
    """
    Compares new_front_embedding against every existing registered user's
    front template. Returns the best match found, if any exceeds the
    threshold, so a rejection message can name which existing registration
    conflicts, not just say "duplicate found."

    exclude_user_id exists for the Day 18 test harness below, so a user's
    own just-inserted template does not immediately flag itself as a
    duplicate of itself during testing.
    """
    existing = get_all_front_templates()
    best_match = None
    best_score = -1.0

    for user_id, name, stored_embedding in existing:
        if exclude_user_id is not None and user_id == exclude_user_id:
            continue
        score = cosine_similarity(new_front_embedding, stored_embedding)
        if score > best_score:
            best_score = score
            best_match = (user_id, name)

    if best_match is not None and best_score >= DUPLICATE_THRESHOLD:
        return {
            "is_duplicate": True,
            "matched_user_id": best_match[0],
            "matched_name": best_match[1],
            "score": round(best_score, 4),
            "reason": f"matches existing registration for '{best_match[1]}' (user_id={best_match[0]}) at score {best_score:.4f}",
        }

    return {
        "is_duplicate": False,
        "matched_user_id": None,
        "matched_name": None,
        "score": round(best_score, 4) if best_match else None,
        "reason": "",
    }
