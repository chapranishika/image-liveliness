"""
tests/test_duplicate_check.py

src/duplicate_check.py's check_for_duplicate() -- called live by both
app/streamlit_app.py and api/api.py to block re-registering the same face
under a different name -- had 0% pytest coverage before this file, despite
being real, currently-used security logic (unlike src/registration.py,
which defines its own standalone register_new_user() but is never actually
called from the live app or api/ -- see docs disclosure, not covered here
for that reason).
"""
import numpy as np

from src.duplicate_check import check_for_duplicate, DUPLICATE_THRESHOLD


def _unit_embedding(index, dim=512):
    v = np.zeros(dim)
    v[index] = 1.0
    return v


def test_no_duplicate_when_database_empty(temp_db):
    result = check_for_duplicate(_unit_embedding(0))
    assert result["is_duplicate"] is False
    assert result["matched_user_id"] is None


def test_flags_duplicate_when_new_embedding_matches_existing_user(temp_db):
    user_id = temp_db.insert_user("Alice", consent_given=True)
    temp_db.insert_template(user_id, "front", _unit_embedding(0))

    # Near-identical embedding (same direction, tiny perturbation) --
    # should score above DUPLICATE_THRESHOLD (0.68) against Alice's template.
    near_duplicate = _unit_embedding(0) + np.full(512, 1e-6)
    result = check_for_duplicate(near_duplicate)

    assert result["is_duplicate"] is True
    assert result["matched_user_id"] == user_id
    assert result["matched_name"] == "Alice"
    assert result["score"] >= DUPLICATE_THRESHOLD


def test_does_not_flag_a_genuinely_different_face(temp_db):
    user_id = temp_db.insert_user("Alice", consent_given=True)
    temp_db.insert_template(user_id, "front", _unit_embedding(0))

    # Orthogonal embedding -- cosine similarity 0.0, nowhere near threshold.
    different_person = _unit_embedding(1)
    result = check_for_duplicate(different_person)

    assert result["is_duplicate"] is False


def test_exclude_user_id_skips_a_users_own_template(temp_db):
    """
    Registration calls this with exclude_user_id unset (no self yet to
    exclude), but the Day 18 test-harness use case this parameter exists
    for -- checking a user's own just-inserted template doesn't flag itself
    -- is real, reachable behavior and needs its own coverage.
    """
    user_id = temp_db.insert_user("Alice", consent_given=True)
    temp_db.insert_template(user_id, "front", _unit_embedding(0))

    result = check_for_duplicate(_unit_embedding(0), exclude_user_id=user_id)
    assert result["is_duplicate"] is False


def test_reports_the_best_matching_existing_user_when_multiple_exist(temp_db):
    alice_id = temp_db.insert_user("Alice", consent_given=True)
    temp_db.insert_template(alice_id, "front", _unit_embedding(0))

    bob_id = temp_db.insert_user("Bob", consent_given=True)
    temp_db.insert_template(bob_id, "front", _unit_embedding(1))

    result = check_for_duplicate(_unit_embedding(1) + np.full(512, 1e-6))

    assert result["is_duplicate"] is True
    assert result["matched_user_id"] == bob_id
    assert result["matched_name"] == "Bob"
