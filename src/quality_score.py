"""
src/quality_score.py

A UNIFIED, CLIENT-CONFIGURABLE QUALITY SCORE.
This directly addresses mentor feedback: instead of six separate hardcoded
pass/fail gates, every raw measurement is converted into a 0-100 sub-score,
combined into ONE weighted composite score, and compared against ONE single threshold.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.quality_checks import check_brightness, check_blur, check_contrast
from src.quality_checks_day8_9 import check_single_face, check_pose, check_position, check_occlusion, check_resolution

QUALITY_PROFILES = {
    "strict":   {"threshold": 85, "description": "High-security re-authentication; assumes good hardware/lighting"},
    "balanced": {"threshold": 70, "description": "Default -- general onboarding, typical consumer devices"},
    "lenient":  {"threshold": 50, "description": "Accessibility-first deployments; older devices, variable lighting expected"},
}

ACTIVE_PROFILE = os.environ.get("QUALITY_PROFILE", "balanced")


def _linear_score(value, good_value, acceptable_value, worst_value):
    if good_value >= worst_value:  # higher-is-better measurement
        if value >= good_value:
            return 100.0
        if value <= worst_value:
            return 0.0
        return round((value - worst_value) / (good_value - worst_value) * 100, 1)
    else:  # lower-is-better measurement
        if value <= good_value:
            return 100.0
        if value >= worst_value:
            return 0.0
        return round((worst_value - value) / (worst_value - good_value) * 100, 1)


def score_brightness(frame):
    """
    The "too dark" direction scores on p90_value (90th-percentile pixel
    intensity), not the whole-image mean -- see
    src/quality_checks.py's BRIGHTNESS_MIN_P90 comment for the real
    calibration data behind this and why it measurably reduces (not
    eliminates) a real skin-tone quality-score gap the mean-based version
    had. good_value=180/worst_value=20 calibrated against the same real
    data: genuine p90 means by skin tone were Dark 170.8, Light 194.6,
    Medium 195.0 -- 180 sits in that real cluster rather than only fitting
    the lighter-skinned groups. The "too bright" direction is unaffected,
    still mean-based (see BRIGHTNESS_MIN_P90's comment for why a
    percentile approach doesn't work for overexposure).
    """
    result = check_brightness(frame)
    mean_value = result["value"]
    p90_value = result["p90_value"]
    if mean_value <= 145:
        score = _linear_score(p90_value, good_value=180, acceptable_value=120, worst_value=20)
    else:
        score = _linear_score(mean_value, good_value=145, acceptable_value=190, worst_value=245)
    return {"name": "brightness", "raw_value": mean_value, "score": score}


def score_blur(frame):
    result = check_blur(frame)
    value = result["value"]
    # Recalibrated from the original Day 7 curve (good=1200, worst=500),
    # which hard-floored to a 0 score for genuinely in-focus captures under
    # some real lighting/camera conditions. Sample-size caveat: based on a
    # limited real-camera set, not a broad recalibration study -- same
    # caveat as TEXTURE_UNIFORMITY_MIN's comment in quality_checks.py.
    return {"name": "blur", "raw_value": value,
            "score": _linear_score(value, good_value=450, acceptable_value=300, worst_value=150)}


def score_pose(frame):
    result = check_pose(frame)
    if result["status"] == "fail" and result.get("classification") is None:
        return {"name": "pose", "raw_value": None, "score": 0.0}
    yaw = abs(result.get("yaw", 0))
    score = _linear_score(yaw, good_value=0, acceptable_value=25, worst_value=65)
    return {"name": "pose", "raw_value": result.get("yaw"), "score": score}


def score_position(frame):
    result = check_position(frame)
    if result["status"] == "fail" and result.get("face_area_ratio") is None:
        return {"name": "position", "raw_value": None, "score": 0.0}
    area = result.get("face_area_ratio", 0)
    score = _linear_score(area, good_value=0.06, acceptable_value=0.03, worst_value=0.015)
    return {"name": "position", "raw_value": area, "score": score}


def score_occlusion(frame):
    result = check_occlusion(frame)
    if result["status"] == "fail" and result.get("detection_score") is None:
        return {"name": "occlusion", "raw_value": None, "score": 0.0}
    det_score = result.get("detection_score", 0)
    score = _linear_score(det_score, good_value=0.95, acceptable_value=0.80, worst_value=0.60)
    return {"name": "occlusion", "raw_value": det_score, "score": score}


def score_contrast(frame):
    result = check_contrast(frame)
    value = result["value"]
    # good/acceptable/worst chosen from the same real-vs-synthetic measurements
    # documented next to CONTRAST_MIN in quality_checks.py: real genuine captures
    # measure ~85-93, a moderate wash-out measures ~27, a severe one ~13.
    score = _linear_score(value, good_value=70, acceptable_value=30, worst_value=10)
    return {"name": "contrast", "raw_value": value, "score": score}


def score_resolution(frame):
    result = check_resolution(frame)
    if result["status"] == "fail" and result.get("face_width_px") is None:
        return {"name": "resolution", "raw_value": None, "score": 0.0}
    width_px = result.get("face_width_px", 0)
    # good/acceptable/worst chosen from the same real measurements documented
    # next to MIN_FACE_WIDTH_PX in quality_checks_day8_9.py: real genuine
    # close-up captures at 640x360 measure 207-253px face width.
    score = _linear_score(width_px, good_value=200, acceptable_value=100, worst_value=50)
    return {"name": "resolution", "raw_value": width_px, "score": score}


WEIGHTS = {
    "brightness": 0.15,
    "blur": 0.25,        # was 0.30 -- trimmed 0.05 to fund contrast/resolution below, still highest weight
    "pose": 0.20,         # was 0.25 -- trimmed 0.05 for the same reason
    "position": 0.15,
    "occlusion": 0.15,
    "contrast": 0.05,     # new (brief Phase 2 Section 3) -- cheap statistical check, not meant to dominate
    "resolution": 0.05,   # new (brief Phase 2 Section 3) -- cheap statistical check, not meant to dominate
}

# Below this sub-score, a dimension is considered a genuine, callable-out
# problem rather than just "not perfect" -- used to pick which of the 7
# sub-scores to name in the user-facing message.
_FLAG_CUTOFF = 55.0


def _friendly_reason(sub_scores):
    """
    Turns the sub-score breakdown into a specific, plain-language sentence
    naming the actual weakest dimension(s), instead of a generic
    "score X below threshold Y" the person on the other end can't act on.
    """
    def brightness_msg(raw):
        if raw is not None and raw < 100:
            return "Lighting is too low — move to a brighter, more evenly lit area."
        return "Lighting is too bright or glaring — step back from direct light."

    messages = {
        "brightness": brightness_msg,
        "blur": lambda raw: "Image looks blurry — hold the camera steady and make sure the lens is clean.",
        "pose": lambda raw: "Please face the camera directly, without turning your head.",
        "position": lambda raw: "Move closer to the camera and center your face in the frame.",
        "occlusion": lambda raw: "Your face looks partially covered — clear away hair, a mask, or anything blocking it.",
        "contrast": lambda raw: "Lighting looks flat or washed out — try a more evenly lit background.",
        "resolution": lambda raw: "Move closer to the camera for a clearer image.",
    }

    flagged = sorted(
        ((name, s) for name, s in sub_scores.items() if s["score"] < _FLAG_CUTOFF),
        key=lambda kv: kv[1]["score"],
    )
    if not flagged:
        # Nothing individually bad enough to flag -- several dimensions are
        # each just mediocre. Name the single weakest one anyway.
        flagged = [min(sub_scores.items(), key=lambda kv: kv[1]["score"])]

    sentences = [messages[name](s["raw_value"]) for name, s in flagged[:2]]
    return " ".join(sentences)


def compute_quality_score(frame, profile=None):
    profile_name = profile or ACTIVE_PROFILE
    profile_config = QUALITY_PROFILES.get(profile_name, QUALITY_PROFILES["balanced"])

    face_check = check_single_face(frame)
    if face_check["status"] == "fail":
        face_reason = face_check.get("reason", "")
        if face_reason == "no face detected":
            friendly = "No face detected — please make sure your face is visible to the camera."
        elif "faces detected" in face_reason:
            friendly = "More than one face is in view — make sure only you are in the frame."
        else:
            friendly = face_reason
        return {
            "overall_score": 0.0,
            "decision": "reject",
            "profile": profile_name,
            "threshold": profile_config["threshold"],
            "reason": friendly,
            "sub_scores": {},
        }

    sub_results = {
        "brightness": score_brightness(frame),
        "blur": score_blur(frame),
        "pose": score_pose(frame),
        "position": score_position(frame),
        "occlusion": score_occlusion(frame),
        "contrast": score_contrast(frame),
        "resolution": score_resolution(frame),
    }

    overall = sum(sub_results[k]["score"] * WEIGHTS[k] for k in WEIGHTS)
    overall = round(overall, 1)

    decision = "accept" if overall >= profile_config["threshold"] else "reject"

    return {
        "overall_score": overall,
        "decision": decision,
        "profile": profile_name,
        "threshold": profile_config["threshold"],
        "reason": "" if decision == "accept" else _friendly_reason(sub_results),
        "sub_scores": sub_results,
    }
