"""
capture_images.py

Webcam capture module for self-collected face datasets.
Supports multiple sessions, face detection constraints, real-time feedback,
and structured logging. All submenus are handled directly in the OpenCV window
for a seamless, non-blocking user experience.

Usage:
    python capture_images.py --session 1
"""
import os
import sys
import csv
import json
import time
import urllib.request
import argparse
from datetime import datetime
import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Model URL and local name
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
MODEL_PATH = "blaze_face_short_range.tflite"

def ensure_model_exists():
    if not os.path.exists(MODEL_PATH):
        print(f"[INFO] Face detector model not found. Downloading from:\n{MODEL_URL}...")
        try:
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
            print("[INFO] Model downloaded successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to download model: {e}")
            sys.exit(1)

def get_next_filename(directory, prefix, category_name):
    """
    Finds the next unused index for files named like prefix_001.jpg, prefix_002.jpg, etc.
    """
    idx = 1
    while True:
        filename = f"{category_name}_{idx:03d}.jpg"
        path = os.path.join(directory, filename)
        if not os.path.exists(path):
            return filename, path
        idx += 1

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=int, default=1, help="Session number (1, 2, or 3)")
    args = parser.parse_args()

    session = args.session
    ensure_model_exists()

    # Define base paths
    base_dir = os.path.join("data", "self_collected", f"session_{session}")
    categories = {
        "front": os.path.join(base_dir, "front"),
        "left": os.path.join(base_dir, "left"),
        "right": os.path.join(base_dir, "right"),
        "bad_quality": os.path.join(base_dir, "bad_quality"),
        "attacks": os.path.join(base_dir, "attacks")
    }

    # Ensure all directories exist
    for path in categories.values():
        os.makedirs(path, exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # Initialize MediaPipe FaceDetector
    try:
        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceDetectorOptions(base_options=base_options)
        detector = vision.FaceDetector.create_from_options(options)
    except Exception as e:
        print(f"[ERROR] Failed to initialize MediaPipe FaceDetector: {e}")
        sys.exit(1)

    # Open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open webcam. Please verify connection and permissions.")
        detector.close()
        sys.exit(1)

    # Count existing captures to initialize session counters
    counts = {
        "front": len([f for f in os.listdir(categories["front"]) if f.startswith("front_")]),
        "left": len([f for f in os.listdir(categories["left"]) if f.startswith("left_")]),
        "right": len([f for f in os.listdir(categories["right"]) if f.startswith("right_")]),
        "bad_quality": len([f for f in os.listdir(categories["bad_quality"])]),
        "attacks": len([f for f in os.listdir(categories["attacks"])])
    }

    bad_quality_types = {
        "dark": len([f for f in os.listdir(categories["bad_quality"]) if "dark" in f]),
        "bright": len([f for f in os.listdir(categories["bad_quality"]) if "bright" in f]),
        "blur": len([f for f in os.listdir(categories["bad_quality"]) if "blur" in f]),
        "angle": len([f for f in os.listdir(categories["bad_quality"]) if "angle" in f]),
        "occlusion": len([f for f in os.listdir(categories["bad_quality"]) if "occlusion" in f])
    }

    attack_types = {
        "printed": len([f for f in os.listdir(categories["attacks"]) if "printed" in f]),
        "screen": len([f for f in os.listdir(categories["attacks"]) if "screen" in f]),
        "video": len([f for f in os.listdir(categories["attacks"]) if "video" in f]),
        "frozen": len([f for f in os.listdir(categories["attacks"]) if "frozen" in f]),
        "multiple": len([f for f in os.listdir(categories["attacks"]) if "multiple" in f])
    }

    print("\n" + "="*50)
    print(f"Self-Data Collection Module â Session {session}")
    print("="*50)
    print("Webcam feed opening. Focus the window and use these keys:")
    print("  F -> Front Face")
    print("  L -> Left Pose")
    print("  R -> Right Pose")
    print("  B -> Bad Quality Menu (select type on screen using keys 1-5)")
    print("  A -> Attack Sample Menu (select type on screen using keys 1-5)")
    print("  Q -> Quit & Generate Summary")
    print("="*50 + "\n")

    # Metrics for FPS
    prev_time = time.time()
    fps = 0.0
    fps_frames = 0

    # Feedback message state
    feedback_text = ""
    feedback_color = (0, 255, 0)
    feedback_expiry = 0.0

    # Submenu state: None, "bad_quality", or "attacks"
    active_menu = None

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Failed to read frame from webcam.")
            break

        current_time = time.time()
        fps_frames += 1
        if current_time - prev_time >= 1.0:
            fps = fps_frames / (current_time - prev_time)
            fps_frames = 0
            prev_time = current_time

        # Run Face Detection
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb_frame))
        detection_result = detector.detect(mp_image)
        num_faces = len(detection_result.detections) if detection_result.detections else 0

        # Draw bounding boxes and confidence score on display copy
        display_frame = frame.copy()
        if detection_result.detections:
            for detection in detection_result.detections:
                bbox = detection.bounding_box
                score = detection.categories[0].score
                
                # Bounding box
                cv2.rectangle(display_frame, (bbox.origin_x, bbox.origin_y), 
                              (bbox.origin_x + bbox.width, bbox.origin_y + bbox.height), 
                              (0, 255, 0), 2)
                
                # Confidence label
                label = f"Confidence: {int(score * 100)}%"
                cv2.putText(display_frame, label, (bbox.origin_x, bbox.origin_y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Overlay text interface on display frame
        y_offset = 25
        # Status header
        cv2.putText(display_frame, f"Session: {session}  |  FPS: {fps:.1f}", (15, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        y_offset += 25

        # Instructions (show only if no menu is active)
        if active_menu is None:
            instructions = [
                "F - Front Face", "L - Left Pose", "R - Right Pose",
                "B - Bad Quality", "A - Attack Sample", "Q - Quit"
            ]
            for inst in instructions:
                cv2.putText(display_frame, inst, (15, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
                y_offset += 20
        elif active_menu == "bad_quality":
            cv2.putText(display_frame, "Select Bad Quality (Press 1-5):", (15, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)
            y_offset += 22
            menu_opts = [
                "1 - Too Dark",
                "2 - Overexposed",
                "3 - Motion Blur",
                "4 - Extreme Angle",
                "5 - Occlusion",
                "ESC/Any - Cancel"
            ]
            for opt in menu_opts:
                cv2.putText(display_frame, opt, (15, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 255), 1)
                y_offset += 20
        elif active_menu == "attacks":
            cv2.putText(display_frame, "Select Attack (Press 1-5):", (15, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            y_offset += 22
            menu_opts = [
                "1 - Printed Photo",
                "2 - Screen Replay",
                "3 - Video Replay",
                "4 - Frozen Frame",
                "5 - Multiple Faces",
                "ESC/Any - Cancel"
            ]
            for opt in menu_opts:
                cv2.putText(display_frame, opt, (15, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 255), 1)
                y_offset += 20
        
        # Display counters
        y_offset += 15
        cv2.putText(display_frame, "Saved:", (15, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
        y_offset += 20
        
        counters = [
            f"Front  : {counts['front']}",
            f"Left   : {counts['left']}",
            f"Right  : {counts['right']}",
            f"Bad    : {counts['bad_quality']}",
            f"Attack : {counts['attacks']}"
        ]
        for cnt in counters:
            cv2.putText(display_frame, cnt, (15, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            y_offset += 18

        # Draw feedback text
        if current_time < feedback_expiry:
            cv2.putText(display_frame, feedback_text, (15, display_frame.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, feedback_color, 2)

        cv2.imshow("Self-Collection Capture", display_frame)

        # Wait for keypress
        key = cv2.waitKey(1) & 0xFF

        # Functions to log captures
        def save_captured_image(category, prefix, sub_cat=None, is_multiple_attack=False):
            # Face Count Validation
            if num_faces == 0:
                print("[WARN] No face detected. Capture cancelled.")
                return "[WARN] No face detected", (0, 0, 255)
            elif num_faces >= 2 and not is_multiple_attack:
                print("[WARN] Multiple faces detected. Please keep only one face in frame.")
                return "[WARN] Multiple faces detected", (0, 0, 255)

            # Unique Naming & Path resolution
            dir_path = categories[category]
            fname, full_path = get_next_filename(dir_path, prefix, prefix)
            
            # Save original resolution frame
            try:
                cv2.imwrite(full_path, frame)
            except Exception as ex:
                print(f"[ERROR] Failed to save image: {ex}")
                return "[ERROR] Save failure", (0, 0, 255)

            # Increment counters
            counts[category] += 1
            if category == "bad_quality" and sub_cat:
                bad_quality_types[sub_cat] += 1
            elif category == "attacks" and sub_cat:
                attack_types[sub_cat] += 1

            # Log to CSV
            log_path = os.path.join("logs", "capture_log.csv")
            csv_exists = os.path.exists(log_path)
            try:
                with open(log_path, "a", newline="") as csvfile:
                    fieldnames = ["Timestamp", "Session", "Category", "Filename"]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    if not csv_exists:
                        writer.writeheader()
                    writer.writerow({
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Session": session,
                        "Category": f"{category.capitalize()}-{sub_cat.capitalize()}" if sub_cat else category.capitalize(),
                        "Filename": fname
                    })
            except Exception as ex:
                print(f"[WARN] Failed to write to CSV log: {ex}")

            print(f"[SAVED] {full_path}")
            return f"[SAVED] {fname}", (0, 255, 0)

        # Key action handlers
        if key == ord("q") or key == 27 and active_menu is None:
            break

        # If a submenu is active, process selections 1-5
        elif active_menu == "bad_quality":
            sub_map = {
                ord("1"): ("bad_dark", "dark"),
                ord("2"): ("bad_bright", "bright"),
                ord("3"): ("bad_blur", "blur"),
                ord("4"): ("bad_angle", "angle"),
                ord("5"): ("bad_occlusion", "occlusion")
            }
            if key in sub_map:
                prefix, sub_cat = sub_map[key]
                msg, color = save_captured_image("bad_quality", prefix, sub_cat)
                feedback_text = msg
                feedback_color = color
                feedback_expiry = time.time() + 2.0
                active_menu = None
            elif key != 255:  # Any other key cancels
                feedback_text = "Cancelled"
                feedback_color = (0, 0, 255)
                feedback_expiry = time.time() + 1.5
                active_menu = None

        elif active_menu == "attacks":
            sub_map = {
                ord("1"): ("attack_printed", "printed", False),
                ord("2"): ("attack_screen", "screen", False),
                ord("3"): ("attack_video", "video", False),
                ord("4"): ("attack_frozen", "frozen", False),
                ord("5"): ("attack_multiple", "multiple", True)
            }
            if key in sub_map:
                prefix, sub_cat, is_mult = sub_map[key]
                msg, color = save_captured_image("attacks", prefix, sub_cat, is_multiple_attack=is_mult)
                feedback_text = msg
                feedback_color = color
                feedback_expiry = time.time() + 2.0
                active_menu = None
            elif key != 255:  # Any other key cancels
                feedback_text = "Cancelled"
                feedback_color = (0, 0, 255)
                feedback_expiry = time.time() + 1.5
                active_menu = None

        # Normal main menu keys
        elif key == ord("f"):
            msg, color = save_captured_image("front", "front")
            feedback_text = msg
            feedback_color = color
            feedback_expiry = time.time() + 2.0

        elif key == ord("l"):
            msg, color = save_captured_image("left", "left")
            feedback_text = msg
            feedback_color = color
            feedback_expiry = time.time() + 2.0

        elif key == ord("r"):
            msg, color = save_captured_image("right", "right")
            feedback_text = msg
            feedback_color = color
            feedback_expiry = time.time() + 2.0

        elif key == ord("b"):
            active_menu = "bad_quality"

        elif key == ord("a"):
            active_menu = "attacks"

    # Cleanup webcam and window
    cap.release()
    cv2.destroyAllWindows()
    detector.close()

    # Generate Session Summary JSON
    summary_path = os.path.join("logs", "session_summary.json")
    summary_data = {
        "session": session,
        "date": datetime.today().strftime("%Y-%m-%d"),
        "front": counts["front"],
        "left": counts["left"],
        "right": counts["right"],
        "bad_quality": bad_quality_types,
        "attacks": attack_types
    }

    try:
        all_summaries = {}
        if os.path.exists(summary_path):
            with open(summary_path, "r") as jsonfile:
                try:
                    all_summaries = json.load(jsonfile)
                    if "session" in all_summaries:
                        prev_session = all_summaries["session"]
                        all_summaries = {str(prev_session): all_summaries}
                except Exception:
                    pass

        all_summaries[str(session)] = summary_data
        
        with open(summary_path, "w") as jsonfile:
            json.dump(summary_data, jsonfile, indent=2)
            
        print("\n" + "="*50)
        print(f"Capture Session {session} Finished")
        print("="*50)
        print(f"Summary JSON saved to: {summary_path}")
        print(json.dumps(summary_data, indent=2))
        print("="*50 + "\n")
    except Exception as ex:
        print(f"[ERROR] Failed to write session summary: {ex}")

if __name__ == "__main__":
    main()
