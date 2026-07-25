"""
day18_test_duplicate_detection.py

Day 18: Tests duplicate detection against real data.
Registers one identity (Alice) from generated Session 1 images,
then attempts three more duplicate checks:
    1. Same image check (front_001) -> should be flagged as duplicate
    2. Different image of same person (front_002) -> should be flagged as duplicate
    3. Different person (different_001) -> should NOT be flagged as duplicate
"""
import cv2
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.registration import register_new_user
from src.duplicate_check import check_for_duplicate, DUPLICATE_THRESHOLD
from src.face_matching import get_embedding
from src.db import init_db, insert_user, insert_template, _get_connection

SELF_DIR = os.path.join("data", "self_collected")


def setup_test_database():
    """Clears the DB and manually registers Alice with generated templates."""
    init_db()
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM templates")
    cur.execute("DELETE FROM users")
    conn.commit()
    conn.close()

    print("Registering Alice in database for duplicate testing...")
    
    # Load and embed Alice's front, left, and right templates
    front_img = cv2.imread(os.path.join(SELF_DIR, "front", "front_001.jpg"))
    left_img = cv2.imread(os.path.join(SELF_DIR, "left", "left_001.jpg"))
    right_img = cv2.imread(os.path.join(SELF_DIR, "right", "right_001.jpg"))

    front_emb = get_embedding(front_img)
    left_emb = get_embedding(left_img)
    right_emb = get_embedding(right_img)

    if front_emb["status"] != "success" or left_emb["status"] != "success" or right_emb["status"] != "success":
        print("[ERROR] Failed to extract embeddings for registration templates.")
        sys.exit(1)

    user_id = insert_user("Alice")
    insert_template(user_id, "front", front_emb["embedding"])
    insert_template(user_id, "left", left_emb["embedding"])
    insert_template(user_id, "right", right_emb["embedding"])
    print(f"Alice registered successfully with user_id={user_id}.\n")
    return user_id


def run_tests():
    setup_test_database()

    results = []

    # Test 1: Same Image (front_001)
    print("Test 1: Same Person, Same Image (front_001.jpg)...")
    img1 = cv2.imread(os.path.join(SELF_DIR, "front", "front_001.jpg"))
    emb1 = get_embedding(img1)["embedding"]
    res1 = check_for_duplicate(emb1)
    results.append({
        "case": "1. Same Image (front_001)",
        "expected": "is_duplicate: True",
        "actual": f"is_duplicate: {res1['is_duplicate']}",
        "score": res1["score"],
        "status": "PASS" if res1["is_duplicate"] else "FAIL"
    })
    print(f"  -> Match score: {res1['score']} (is_duplicate: {res1['is_duplicate']})\n")

    # Test 2: Same Person, Different Image (front_002)
    print("Test 2: Same Person, Different Image (front_002.jpg)...")
    img2 = cv2.imread(os.path.join(SELF_DIR, "front", "front_002.jpg"))
    emb2 = get_embedding(img2)["embedding"]
    res2 = check_for_duplicate(emb2)
    results.append({
        "case": "2. Same Person, Diff Image (front_002)",
        "expected": "is_duplicate: True",
        "actual": f"is_duplicate: {res2['is_duplicate']}",
        "score": res2["score"],
        "status": "PASS" if res2["is_duplicate"] else "FAIL"
    })
    print(f"  -> Match score: {res2['score']} (is_duplicate: {res2['is_duplicate']})\n")

    # Test 3: Different Person (different_001)
    print("Test 3: Different Person (different_001.jpg)...")
    img3 = cv2.imread(os.path.join(SELF_DIR, "different", "different_001.jpg"))
    emb3 = get_embedding(img3)["embedding"]
    res3 = check_for_duplicate(emb3)
    results.append({
        "case": "3. Different Person",
        "expected": "is_duplicate: False",
        "actual": f"is_duplicate: {res3['is_duplicate']}",
        "score": res3["score"],
        "status": "PASS" if not res3["is_duplicate"] else "FAIL"
    })
    print(f"  -> Match score: {res3['score']} (is_duplicate: {res3['is_duplicate']})\n")

    # Print Summary Table
    print("=" * 70)
    print(f"{'DUPLICATE DETECTION HARDENING EVALUATION':^70}")
    print("=" * 70)
    print(f"{'Test Case':<36} | {'Expected':<12} | {'Score':<6} | {'Status':<6}")
    print("-" * 70)
    for r in results:
        score_str = f"{r['score']:.4f}" if r['score'] is not None else "N/A"
        print(f"{r['case']:<36} | {r['expected']:<12} | {score_str:<6} | {r['status']:<6}")
    print("=" * 70)
    print(f"Duplicate Detection Threshold: {DUPLICATE_THRESHOLD}")


if __name__ == "__main__":
    run_tests()
