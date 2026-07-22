"""
day15_end_to_end_demo.py

Day 15: The first genuine end-to-end demonstration of this project.
Registers one identity manually from front/left/right self-collected
images (proper registration with duplicate-checking arrives Day 16), then
runs a full verify() call against a new frame of the same person, and
against a different person / attack image, printing the complete result
at every stage.

Usage:
    python day15_end_to_end_demo.py
"""
import cv2
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.face_matching import get_embedding
from src.pipeline import verify

SELF_DIR = os.path.join("data", "self_collected", "session_1")


def build_templates_from_front_left_right():
    """
    Manually builds the three stored templates for ONE identity, standing
    in for what Day 16's real registration + SQLite storage will do
    properly. This lets Day 15 test the matching logic today without
    waiting for the database layer to exist.
    """
    templates = {}
    for angle in ["front", "left", "right"]:
        folder = os.path.join(SELF_DIR, angle)
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".png")))
        if not files:
            print(f"[WARN] No images found in {folder}, skipping {angle} template.")
            continue
        img = cv2.imread(os.path.join(folder, files[0]))
        result = get_embedding(img)
        if result["status"] == "success":
            templates[angle] = result["embedding"]
            print(f"Built '{angle}' template from {files[0]}")
        else:
            print(f"[WARN] Could not embed {files[0]}: {result['reason']}")
    return templates


def run_and_report(label, frame, templates, run_active_challenge=False):
    print(f"\n{'='*60}\nVERIFY ATTEMPT: {label}\n{'='*60}")
    result = verify(frame, templates, run_active_challenge=run_active_challenge)
    print(f"verified: {result['verified']}")
    print(f"rejected_at_stage: {result['rejected_at_stage']}")
    if result["match_result"]:
        print(f"match_result: {result['match_result']}")
    else:
        print(f"detail: {result['detail']}")
    return result


if __name__ == "__main__":
    print("Building templates for the registered identity from Session 1 front/left/right images...")
    templates = build_templates_from_front_left_right()

    if not templates:
        print("No templates could be built. Make sure data/self_collected/session_1/{front,left,right}/ contain images.")
        sys.exit(1)

    # Test 1: a DIFFERENT image of the SAME person (a later front/left/right
    # capture not used to build the template) should be ACCEPTED.
    front_folder = os.path.join(SELF_DIR, "front")
    front_files = sorted(f for f in os.listdir(front_folder) if f.lower().endswith((".jpg", ".png")))
    if len(front_files) > 1:
        genuine_test_frame = cv2.imread(os.path.join(front_folder, front_files[-1]))
        run_and_report("Genuine — different photo, same person", genuine_test_frame, templates,
                        run_active_challenge=False)
    else:
        print("[INFO] Only one front image available, skipping genuine re-test.")

    # Test 2: a staged ATTACK image should be REJECTED, ideally at the
    # liveness stage before matching is even attempted.
    attacks_folder = os.path.join(SELF_DIR, "attacks")
    if os.path.isdir(attacks_folder):
        attack_files = sorted(f for f in os.listdir(attacks_folder) if f.lower().endswith((".jpg", ".png")))
        if attack_files:
            attack_frame = cv2.imread(os.path.join(attacks_folder, attack_files[0]))
            run_and_report(f"Attack — {attack_files[0]}", attack_frame, templates,
                            run_active_challenge=False)

    print("\nDone. This is the first point in the project where quality, passive")
    print("liveness, and matching have all run together in one call. Log the")
    print("results (and the architecture diagram sketch showing this flow) in OneNote.")
