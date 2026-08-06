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
import numpy as np

# ---- Placeholder thresholds ----
# These are starting guesses only. Day 7's actual job is to replace these
# with values justified by the real numbers your own images produce â
# see day7_calibrate.py, which prints exactly that.
BRIGHTNESS_MIN = 100      # below this = too dark (calibrated Day 7)
BRIGHTNESS_MAX = 220      # above this = overexposed (calibrated Day 7)
BLUR_MIN = 1000           # below this = too blurry (calibrated Day 7)

# CONTRAST_MIN calibrated against real measured values (brief Phase 2
# Section 3's registration check, previously missing entirely -- confirmed
# by grep before adding): real genuine self-collected captures (front,
# left, right, a second identity) all measure grayscale std between 85.65
# and 93.18. A synthetic washed-out version of a real photo (contrast
# reduced toward mid-gray by 70%) measures 26.71; a more severe wash-out
# (85% reduction) measures 13.37. 30 sits just above the moderate wash-out
# case and gives every real genuine capture measured so far more than 2.5x
# headroom above it.
CONTRAST_MIN = 30         # below this = flat/washed-out (calibrated against real + synthetic washed-out images)

# GRID_EDGE_RATIO_MAX calibrated against real measurements: a real frame
# corrupted by the documented intermittent WebRTC connection hiccup
# (scope_decision_worksheet.md -- macroblock tearing, scratch/
# captured_verify_frame.jpg) measured ratio 1.49. Every realistic
# legitimate-degradation case measured alongside it -- genuine capture
# (0.91), heavy Gaussian blur up to sigma=15 (1.00-1.01), a very dark
# frame (0.93), and 8x downscale/upscale pixelation (1.05) -- stayed at or
# below 1.05. 1.15 sits comfortably above every legitimate case and
# comfortably below the real corrupted one. (Heavy JPEG block compression,
# quality<=30, also trips this at 2.1+ -- expected and fine, since a frame
# that blocky is equally unusable regardless of whether the cause is
# decode corruption or extreme compression.)
GRID_EDGE_RATIO_MAX = 1.15


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


def check_contrast(image):
    """
    Returns the standard deviation of grayscale pixel intensity (higher =
    more tonal range) and whether it clears the minimum contrast threshold.
    A cheap statistical proxy for "flat/washed-out" -- no ML model, same
    pattern as check_brightness/check_blur.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    std_dev = float(gray.std())

    status = "pass" if std_dev >= CONTRAST_MIN else "fail"
    reason = "" if status == "pass" else "flat/washed-out (low contrast)"

    return {
        "check": "contrast",
        "value": round(std_dev, 2),
        "status": status,
        "reason": reason,
    }


def is_frame_corrupted(image):
    """
    Cheap, non-ML sanity check for macroblock/decode corruption -- distinct
    from check_blur()/check_contrast(), which measure legitimate quality
    (a blurry-but-coherent frame). Real video codecs decode in fixed-size
    (typically 8x8 or 16x16 pixel) blocks; a frame that arrived mid-decode
    error shows sharp discontinuities concentrated right at those block
    boundaries, not spread evenly across the image the way real content's
    edges are. This measures the ratio of edge energy landing exactly on
    the 8-pixel grid vs. everywhere else -- a ratio well above 1 means the
    frame is dominated by block-boundary artifacts, not real content.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    if gray.shape[1] < 16:
        return False

    gx = np.abs(np.diff(gray.astype(np.int16), axis=1))
    grid_cols = gx[:, 7::8]
    other_cols = np.delete(gx, np.arange(7, gx.shape[1], 8), axis=1)
    ratio = float(grid_cols.mean()) / max(float(other_cols.mean()), 0.01)

    return ratio > GRID_EDGE_RATIO_MAX


def check_brightness_and_blur(image):
    """Convenience wrapper returning both results together."""
    return {
        "brightness": check_brightness(image),
        "blur": check_blur(image),
    }
