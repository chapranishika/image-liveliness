"""
day20_test_rppg.py

Day 20: Tests the Day 19 rPPG function against three real conditions,
exactly as the plan specifies: a genuine live face (the still window
captured back on Day 10), a printed photo, and a screen replay. A dedicated
rPPG capture folder is needed for each condition -- see the instructions
printed by this script for how to capture the photo/screen-replay windows,
since Day 10 only captured the genuine "hold still" window.

Usage:
    python day20_test_rppg.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.rppg import check_rppg_liveness

SESSION_DIR = os.path.join("data", "self_collected", "session_1")

TEST_CONDITIONS = {
    "genuine": os.path.join(SESSION_DIR, "rppg_window"),
    "photo": os.path.join(SESSION_DIR, "rppg_window_photo_attack"),
    "screen_replay": os.path.join(SESSION_DIR, "rppg_window_screen_attack"),
}


def main():
    print("=" * 60)
    print("DAY 20 - rPPG Testing Against Real Conditions")
    print("=" * 60)

    missing = [label for label, path in TEST_CONDITIONS.items() if not os.path.isdir(path)]
    if missing:
        print(f"\nMissing capture folders for: {', '.join(missing)}")
        print("To capture these before running the real test:")
        print("  1. genuine: already captured on Day 10 via capture_rppg_window.py")
        print("  2. photo: hold your printed front photo steady in front of the")
        print("     webcam and run: python capture_rppg_window.py --seconds 12")
        print("     then rename/move the output folder to rppg_window_photo_attack")
        print("  3. screen_replay: display that same photo on your phone screen,")
        print("     hold it steady in front of the webcam, run the same capture")
        print("     script, and move the output to rppg_window_screen_attack")
        print("\nRunning against whichever folders DO exist...\n")

    results = {}
    for label, folder in TEST_CONDITIONS.items():
        if not os.path.isdir(folder):
            continue
        print(f"\nTesting condition: {label} ({folder})")
        result = check_rppg_liveness(folder)
        results[label] = result
        print(f"  status: {result['status']}")
        if result["status"] != "error":
            print(f"  estimated_bpm: {result.get('estimated_bpm')}")
            print(f"  peak_prominence: {result.get('peak_prominence')}")
        print(f"  reason: {result.get('reason', '')}")

    print("\n" + "=" * 60)
    print("WHAT TO EXPECT, AND WHAT TO DO WITH EACH OUTCOME")
    print("=" * 60)
    print("genuine: should show status='pass' with a plausible estimated_bpm")
    print("  (roughly 50-110 for a calm adult) and a clear peak_prominence.")
    print("photo: should show status='fail' -- a static photo has zero blood")
    print("  flow, so no periodic signal should exist in the forehead region.")
    print("screen_replay: may show status='fail' OR an artifact tied to the")
    print("  screen's own refresh rate rather than a real pulse -- if the")
    print("  estimated_bpm looks suspiciously exact (e.g. very close to a")
    print("  round number like 60.0 or tied to 30/60 Hz refresh harmonics),")
    print("  that itself is useful evidence worth logging, not a clean pass.")
    print("\nIf 'genuine' does not show a clean pass, do not force")
    print("PEAK_PROMINENCE_MIN down until it does -- first check webcam")
    print("compression settings and lighting stability (both flagged as real")
    print("limitations in the Approach & Design Document, Section 5.3), since")
    print("a lowered threshold that only 'fixes' your own test data will also")
    print("silently let weaker spoofs through later.")

    print("\n\nBUFFER TIME:")
    print("If rPPG testing above took less time than expected, use remaining")
    print("time today to revisit Day 19's attack matrix results -- especially")
    print("any attack that was 'NOT CAUGHT' by quality+passive liveness alone --")
    print("and confirm whether active liveness (Day 11) or this rPPG check")
    print("would catch it, closing the loop on the full three-layer design.")


if __name__ == "__main__":
    main()
