"""
setup_folders.py
Run this once from inside your project root to create the full folder
structure matching the Approach & Design Document exactly.

Usage:
    python setup_folders.py
"""
import os

FOLDERS = [
    "data/celeba_spoof_sample",
    "data/cfp_sample",
    "data/lfw_sample",
    "data/self_collected/front",
    "data/self_collected/left",
    "data/self_collected/right",
    "data/self_collected/bad_quality",
    "data/self_collected/attacks",
    "src",
    "api",
    "app",
    "tests",
    "docs",
]

FILES_TO_TOUCH = [
    "src/__init__.py",
    "src/quality_checks.py",
    "src/liveness_passive.py",
    "src/liveness_active.py",
    "src/rppg.py",
    "src/face_matching.py",
    "src/pipeline.py",
    "src/db.py",
    "api/__init__.py",
    "api/api.py",
    "app/streamlit_app.py",
]

def main():
    for folder in FOLDERS:
        os.makedirs(folder, exist_ok=True)
        print(f"created: {folder}/")

    for f in FILES_TO_TOUCH:
        if not os.path.exists(f):
            with open(f, "w") as fh:
                fh.write(f'"""{f} â placeholder, fill in during implementation."""\n')
            print(f"created: {f}")
        else:
            print(f"already exists, skipped: {f}")

    print("\nDone. Folder structure now matches the Approach & Design Document.")

if __name__ == "__main__":
    main()
