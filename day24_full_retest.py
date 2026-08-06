"""
day24_full_retest.py

Day 24: Buffer / Full Re-Test
Automated batch test runner that executes all prior calibration and testing scripts
as independent subprocesses, verifying that recent architectural changes (unified
quality scoring, liveness updates) have not introduced regressions.
"""
import os
import sys
import subprocess
import time

TEST_SCRIPTS = [
    {"filename": "day7_calibrate.py", "needs_webcam": False, "desc": "Calibrate brightness and blur sub-scores"},
    {"filename": "day8_9_calibrate.py", "needs_webcam": False, "desc": "Calibrate MediaPipe pose and alignment"},
    {"filename": "day10_test.py", "needs_webcam": False, "desc": "Verify passive liveness classifications"},
    {"filename": "day11_calibrate_ear.py", "needs_webcam": True, "desc": "Calibrate active eye blink detection (manual only)"},
    {"filename": "day12_test_active_liveness.py", "needs_webcam": True, "desc": "Verify active turn/blink challenges (manual only)"},
    {"filename": "day15_end_to_end_demo.py", "needs_webcam": False, "desc": "Verify core 3-stage validation and matching demo"},
    {"filename": "day18_test_duplicate_detection.py", "needs_webcam": False, "desc": "Verify duplicate template detection logic"},
    {"filename": "day19_attack_testing_matrix.py", "needs_webcam": False, "desc": "Execute presentation attack testing matrix"},
    {"filename": "day20_test_rppg.py", "needs_webcam": False, "desc": "Validate remote photoplethysmography filter peaks"},
    {"filename": "day21_quality_profile_calibration.py", "needs_webcam": False, "desc": "Audit quality score profile presets"},
    {"filename": "day21_matching_roc_calibration.py", "needs_webcam": False, "desc": "Audit ArcFace matching EER thresholds"},
    {"filename": "day21_spoof_detection_calibration.py", "needs_webcam": False, "desc": "Audit MiniFASNet passive liveness boundary"},
]

def main():
    print("=" * 90)
    print("DAY 24 — AUTOMATED FULL SYSTEM RE-TEST DASHBOARD")
    print("Verifying backward compatibility across all historical pipeline tests.")
    print("=" * 90)

    # Initialize environment and secure local keys
    from src.keys import init_keys_in_env
    init_keys_in_env()
    env = os.environ.copy()
    env["PYTHONPATH"] = "."

    results = []
    
    for item in TEST_SCRIPTS:
        filename = item["filename"]
        needs_webcam = item["needs_webcam"]
        desc = item["desc"]
        
        print(f"\n[TEST] {filename} — {desc}")
        if needs_webcam:
            print("  --> SKIPPED (Requires webcam hardware interaction — manual validation needed)")
            results.append({"filename": filename, "status": "MANUAL_REQUIRED", "duration": 0.0, "error": ""})
            continue

        if not os.path.exists(filename):
            print(f"  --> ERROR: Script file '{filename}' not found!")
            results.append({"filename": filename, "status": "ERROR", "duration": 0.0, "error": "File not found"})
            continue

        start_time = time.time()
        try:
            # Execute script as a separate Python process
            proc = subprocess.run(
                [sys.executable, filename],
                env=env,
                capture_output=True,
                text=True,
                timeout=500
            )
            duration = time.time() - start_time
            
            if proc.returncode == 0:
                print(f"  --> PASS ({duration:.2f} seconds)")
                results.append({"filename": filename, "status": "PASS", "duration": duration, "error": ""})
            else:
                print(f"  --> FAIL ({duration:.2f} seconds) [Exit Code: {proc.returncode}]")
                print("--- stdout ---")
                print(proc.stdout)
                print("--- stderr ---")
                print(proc.stderr)
                print("--------------")
                results.append({
                    "filename": filename,
                    "status": "FAIL",
                    "duration": duration,
                    "error": proc.stderr or proc.stdout
                })
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"  --> TIMEOUT ({duration:.2f} seconds)")
            results.append({"filename": filename, "status": "TIMEOUT", "duration": duration, "error": "Execution timed out"})
        except Exception as e:
            duration = time.time() - start_time
            print(f"  --> ERROR: {str(e)}")
            results.append({"filename": filename, "status": "ERROR", "duration": duration, "error": str(e)})

    # Final summary report
    print("\n" + "=" * 90)
    print("FINAL INTEGRATION SYSTEM TESTING RESULTS SUMMARY")
    print("=" * 90)
    
    passed_count = 0
    failed_count = 0
    manual_count = 0
    
    for r in results:
        status_symbol = "[PASS]"
        if r["status"] == "FAIL":
            status_symbol = "[FAIL]"
            failed_count += 1
        elif r["status"] == "MANUAL_REQUIRED":
            status_symbol = "[MANUAL]"
            manual_count += 1
        elif r["status"] in ["TIMEOUT", "ERROR"]:
            status_symbol = "[ERROR]"
            failed_count += 1
        else:
            passed_count += 1

        err_msg = ""
        if r["error"]:
            clean_err = str(r["error"]).replace("\n", " ").replace("\r", "")
            err_msg = f"| Error: {clean_err[:40]}"
        print(f"{status_symbol:<10} | {r['filename']:<35} | Duration: {r['duration']:5.2f}s {err_msg}")

    print("-" * 90)
    print(f"Total passed: {passed_count}  |  Total failed: {failed_count}  |  Webcam manual required: {manual_count}")
    print("=" * 90)
    
    if failed_count > 0:
        print("WARNING: Resolving failures is required before building the Day 25 Evaluation Report!")
        sys.exit(1)
    else:
        print("SUCCESS: All automated checks passed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()
