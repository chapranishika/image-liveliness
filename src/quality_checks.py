"""
src/quality_checks.py

Day 7: Brightness and blur checks.
Both functions take an image already loaded via cv2.imread() (or a frame
straight from the webcam) and return a small dict with the measured value
and a pass/fail flag, using thresholds you will calibrate in day7_calibrate.py
against your own self-collected images.

Usage:
    import cv2
    from src.quality_checks import check_brightness, check_blur

    img = cv2.imread("data/self_collected/front/front_session1_2026-07-16_001.jpg")
    print(check_brightness(img))
    print(check_blur(img))
"""
import cv2

# ---- Placeholder thresholds ----
# These are starting guesses only. Day 7's actual job is to replace these
# with values justified by the real numbers your own images produce â
# see day7_calibrate.py, which prints exactly that.
BRIGHTNESS_MIN = 100      # below this = too dark (calibrated Day 7)
BRIGHTNESS_MAX = 220      # above this = overexposed (calibrated Day 7)
BLUR_MIN = 1000           # below this = too blurry (calibrated Day 7)


def check_brightness(image):
    """
    Returns the average pixel intensity (0-255) of the image and whether
    it falls inside the acceptable brightness range.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    mean_brightness = float(cv2.mean(gray)[0])

    if mean_brightness < BRIGHTNESS_MIN:
        status = "fail"
        reason = "too dark"
    elif mean_brightness > BRIGHTNESS_MAX:
        status = "fail"
        reason = "overexposed"
    else:
        status = "pass"
        reason = ""

    return {
        "check": "brightness",
        "value": round(mean_brightness, 2),
        "status": status,
        "reason": reason,
    }


def check_blur(image):
    """
    Returns the Laplacian variance of the image (higher = sharper) and
    whether it clears the minimum sharpness threshold.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    status = "pass" if variance >= BLUR_MIN else "fail"
    reason = "" if status == "pass" else "too blurry"

    return {
        "check": "blur",
        "value": round(variance, 2),
        "status": status,
        "reason": reason,
    }


def check_brightness_and_blur(image):
    """Convenience wrapper returning both results together."""
    return {
        "brightness": check_brightness(image),
        "blur": check_blur(image),
    }
