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

# BRIGHTNESS_MIN_P90 -- the "too dark" side of the brightness check, based
# on the 90th-percentile pixel intensity (highlights: cheekbones, forehead,
# nose bridge) rather than the whole-image mean BRIGHTNESS_MIN above.
# Real bias-testing data (Evaluation_Report.md Section 6 item 3's
# correction) found the mean-based measurement genuinely disadvantages
# darker skin under identical lighting -- real Dark-skin mean grayscale
# intensity measured 91.0 vs. Light/Medium's 122-123, because base skin
# reflectance, not scene lighting, dominates a whole-image mean. A face's
# brightest highlights exist regardless of base skin tone given adequate
# light, so they separate "insufficient light" from "darker skin" better:
# real measured 90th-percentile values across all 40 real annotated CFP
# identities (80 images) ranged Dark 106-255 (mean 170.8), Light 157-255
# (mean 194.6), Medium 109-255 (mean 195.0) -- the lowest real genuine
# value observed, across every skin tone, was 106. A synthetic moderate
# darkening (70% of original intensity) of a real Dark-skin genuine photo
# measured 89, a more severe darkening (55%) measured 70 -- both clearly
# below every real genuine value observed. 90 sits just below that real
# genuine floor (106) with real margin, while still catching the tested
# degraded cases. This measurably shrinks, not eliminates, the skin-tone
# gap (aggregate mean-of-p90 gap Light-vs-Dark: 34.2 with the old mean
# metric, 23.7 with this one, on the same real sample) -- the whole-image
# mean's confound between skin tone and lighting isn't a threshold problem,
# it can't be tuned away, only reduced by measuring something less
# confounded. Only replaces the "too dark" side -- the "too bright" side
# (BRIGHTNESS_MAX above) stays mean-based, since real genuine photos
# routinely hit 255 at the 90th percentile from ordinary specular
# highlights (glasses, glossy skin, jewelry) even when correctly exposed
# overall, making a percentile-based overexposure check unusable.
BRIGHTNESS_MIN_P90 = 90

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
    Returns the average pixel intensity (0-255) of the image ("value",
    unchanged meaning -- kept for backward compatibility with every
    existing caller) and whether it falls inside the acceptable brightness
    range. The "too dark" side of that range gate, and the separate
    "p90_value" field, use the 90th-percentile pixel intensity instead of
    the mean -- see BRIGHTNESS_MIN_P90's calibration comment for why.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    mean_brightness = float(cv2.mean(gray)[0])
    p90_brightness = float(np.percentile(gray, 90))

    if p90_brightness < BRIGHTNESS_MIN_P90:
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
        "p90_value": round(p90_brightness, 2),
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


# TEXTURE_UNIFORMITY_MIN calibrated against real measurements (Phase 3
# screen-replay investigation, scratch/build_screen_replay_attack_videos.py):
# local sharpness (Laplacian variance) measured in a 8x8 grid of 32x32
# patches over a 256x256-resized frame, then the coefficient of variation
# (std/mean) of those 64 patch-variances across the frame. Real skin has
# uneven detail across a face -- sharp eyes/brows, smoother cheeks -- so
# genuine captures show real spread between patches. A display's pixel-grid
# resolution imposes a comparatively uniform sharpness ceiling across
# whatever it's showing, so screen-replay content measures LOWER (more
# spatially uniform) on this metric than genuine skin.
# Real measured values:
#   Genuine (5 real captures: front_001/002, left_001, right_001,
#   different_001): 1.099-1.183 -- all clustered tight and high.
#   Real screen-replay (screen_001.jpg laptop + its 5 sharpened/brightened/
#   cropped derivatives from the Phase 3 attack videos, AND video_001.jpg,
#   the real photographed phone-screen replay): 0.567-0.846 -- all well
#   below the genuine cluster, and NOT restored back into it by the same
#   sharpen+brighten adjustments that DO clear the blur/brightness quality
#   sub-scores (confirmed: this signal survives the exact attacker
#   optimization that defeats those two).
#   Other real attack types, correctly NOT expected to trigger a screen-
#   specific signal: printed_001.jpg (paper, not a screen) measured 1.041;
#   frozen_001.jpg (a real direct photo standing in for a paused live feed,
#   no print/screen artifact by design -- see data/Evaluation_Report.md
#   Section 5.1) measured 0.956.
# 0.90 sits in the gap between the worst real screen-replay case (0.846)
# and the closest real non-screen case (frozen_001 at 0.956), with margin
# on both sides.
# Sample size caveat, disclosed honestly: only TWO independent real
# screen-replay base captures exist in this project (screen_001.jpg,
# video_001.jpg) -- the other 5 "screen-replay" values above are
# photometric derivatives of screen_001.jpg, not independent real captures.
# This is the same real-data-availability constraint documented in
# data/Evaluation_Report.md Section 5.1 for the passive-liveness expanded
# eval. A genuinely different physical screen/monitor, lighting setup, or
# distance has not been tested against this threshold.
TEXTURE_UNIFORMITY_MIN = 0.90   # below this = unnaturally uniform surface texture (possible screen replay)


def check_screen_surface_texture(image):
    """
    Cheap, non-ML supplementary signal for screen-replay detection -- same
    pattern as check_contrast()/is_frame_corrupted(), not a second heavy
    model. Distinct from and additional to passive liveness (MiniFASNet):
    this measures a different, simpler property (spatial uniformity of
    local sharpness) and is meant to catch what an attacker's sharpen/
    brighten adjustment to clear the blur/brightness quality sub-scores
    does NOT also fix -- see TEXTURE_UNIFORMITY_MIN's calibration comment.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    gray = cv2.resize(gray, (256, 256)).astype(np.float64)
    lap = cv2.Laplacian(gray, cv2.CV_64F)

    patch = 32
    local_vars = []
    for y in range(0, 256, patch):
        for x in range(0, 256, patch):
            local_vars.append(lap[y:y + patch, x:x + patch].var())
    local_vars = np.array(local_vars)

    uniformity = float(local_vars.std() / (local_vars.mean() + 1e-6))
    status = "pass" if uniformity >= TEXTURE_UNIFORMITY_MIN else "fail"
    reason = "" if status == "pass" else "unnaturally uniform surface texture (possible screen replay)"

    return {
        "check": "screen_surface_texture",
        "value": round(uniformity, 3),
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
