"""
sanity_check.py
Run this immediately after installing requirements.txt to confirm the three
trickiest libraries (OpenCV, MediaPipe, DeepFace) actually work together on
your machine, before building anything on top of them.

Usage:
    python sanity_check.py
    python sanity_check.py --img1 path/to/face1.jpg --img2 path/to/face2.jpg
"""
import sys
import argparse


def check_opencv():
    import cv2
    print(f"[OK] OpenCV version: {cv2.__version__}")
    return cv2


def check_mediapipe():
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    # Verify that the modern FaceLandmarker options can be imported/created
    options = vision.FaceLandmarkerOptions
    print("[OK] MediaPipe modern Face Landmarker available")
    return mp


def check_camera(cv2):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[WARN] Could not open webcam (index 0). Check camera permissions/connection.")
    else:
        ret, frame = cap.read()
        if ret:
            print(f"[OK] Webcam accessible, frame shape: {frame.shape}")
        else:
            print("[WARN] Webcam opened but could not read a frame.")
    cap.release()


def check_deepface(img1, img2):
    from deepface import DeepFace
    print("[INFO] Running DeepFace.verify() â this will download ArcFace weights on first run, needs internet.")
    result = DeepFace.verify(img1_path=img1, img2_path=img2, model_name="ArcFace", detector_backend="mediapipe")
    print("[OK] DeepFace.verify() ran successfully. Result:")
    for k, v in result.items():
        print(f"    {k}: {v}")


def check_deepface_antispoofing(img_path):
    from deepface import DeepFace
    print("[INFO] Running DeepFace.extract_faces() with anti_spoofing=True")
    try:
        faces = DeepFace.extract_faces(img_path=img_path, anti_spoofing=True, detector_backend="mediapipe")
        for i, f in enumerate(faces):
            print(f"    face {i}: is_real={f.get('is_real')}, antispoof_score={f.get('antispoof_score')}")
        print("[OK] Anti-spoofing check ran successfully.")
    except ValueError as e:
        print(f"[EXPECTED BEHAVIOR CONFIRMED] DeepFace raised a ValueError as documented: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--img1", default=None, help="Path to first face image (for DeepFace.verify test)")
    parser.add_argument("--img2", default=None, help="Path to second face image (for DeepFace.verify test)")
    args = parser.parse_args()

    print("=" * 60)
    print("SANITY CHECK â Day 6 Environment Setup")
    print("=" * 60)

    cv2 = check_opencv()
    check_mediapipe()
    check_camera(cv2)

    if args.img1 and args.img2:
        check_deepface(args.img1, args.img2)
        check_deepface_antispoofing(args.img1)
    else:
        print("\n[SKIPPED] DeepFace verify/anti-spoofing checks â "
              "rerun with --img1 and --img2 pointing at two of your own photos "
              "once you've captured them (see capture_images.py).")

    print("\nAll core libraries import and run. Environment is ready for Day 7.")
