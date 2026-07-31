"""
day23_ui_test_checklist.py

Day 23: Full end-to-end testing through the actual UI, not just the
underlying functions. This is a genuinely different kind of testing than
every previous day's calibration scripts -- those tested functions
directly; this tests the REAL user experience, including things no
function-level test can catch (does the webcam feed actually render, is
the profile selector's effect visible and correct, does the status
update in a way an actual person can follow).

This is deliberately a printed checklist to work through manually while
running `streamlit run app/streamlit_app.py`, not an automated script --
UI testing at this stage is a human task. Log your pass/fail for each
row directly into your OneNote Daily Log and the Excel tracker.

Usage:
    python day23_ui_test_checklist.py
    (then follow the printed checklist while the Streamlit app is running
    in another terminal: streamlit run app/streamlit_app.py)
"""

CHECKLIST = [
    ("Sidebar", "Quality profile dropdown shows all 3 profiles with correct threshold %", ""),
    ("Sidebar", "Switching profile does not crash or require a page reload", ""),
    ("Register tab", "Webcam feed renders and updates smoothly (no visible lag)", ""),
    ("Register tab", "Capture FRONT button saves a frame (confirmed via success message)", ""),
    ("Register tab", "Capture LEFT/RIGHT buttons work while actually turning head", ""),
    ("Register tab", "Submit button stays disabled until name + consent + all 3 captures present", ""),
    ("Register tab", "Consent checkbox genuinely blocks registration when unchecked", ""),
    ("Register tab", "Per-stage status (quality/liveness/embedding) shows for EACH of front/left/right", ""),
    ("Register tab", "A deliberately bad capture (cover part of face) is correctly rejected with a clear reason", ""),
    ("Register tab", "Successful registration shows the assigned user_id", ""),
    ("Verify tab", "Capture and Verify button captures the CURRENT live frame, not a stale one", ""),
    ("Verify tab", "Genuine verification (same registered person) shows VERIFIED with a plausible match score", ""),
    ("Verify tab", "A different/unregistered person shows NOT VERIFIED, not a crash", ""),
    ("Verify tab", "A printed photo held to the camera is rejected at the liveness stage, not matching", ""),
    ("Cross-cutting", "Switching to 'strict' profile causes a previously-accepted borderline capture to now be rejected", ""),
    ("Cross-cutting", "Switching to 'lenient' profile causes a previously-rejected borderline capture to now pass", ""),
    ("Cross-cutting", "No unhandled Python exception/traceback appears in the Streamlit UI at any point above", ""),
]


def print_checklist():
    print("=" * 90)
    print("DAY 23 — FULL END-TO-END UI TEST CHECKLIST")
    print("Run 'streamlit run app/streamlit_app.py' in another terminal, then work through this list.")
    print("=" * 90)
    current_section = None
    for section, item, _ in CHECKLIST:
        if section != current_section:
            print(f"\n[{section}]")
            current_section = section
        print(f"  [ ] {item}")

    print("\n" + "=" * 90)
    print("For every unchecked / failed item: note the exact reproduction steps in OneNote,")
    print("fix it, then re-run this checklist from the top before considering Day 23 complete --")
    print("a UI bug fixed in isolation can still break something else in the same session.")
    print("=" * 90)


if __name__ == "__main__":
    print_checklist()
