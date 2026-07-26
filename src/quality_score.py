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
from src.quality_checks import check_brightness, check_blur
from src.quality_checks_day8_9 import check_single_face, check_pose, check_position, check_occlusion

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
    result = check_brightness(frame)
    value = result["value"]
    if value <= 145:
        score = _linear_score(value, good_value=145, acceptable_value=100, worst_value=10)
    else:
        score = _linear_score(value, good_value=145, acceptable_value=190, worst_value=245)
    return {"name": "brightness", "raw_value": value, "score": score}


def score_blur(frame):
    result = check_blur(frame)
    value = result["value"]
    return {"name": "blur", "raw_value": value,
            "score": _linear_score(value, good_value=1200, acceptable_value=1000, worst_value=500)}


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


WEIGHTS = {
    "brightness": 0.15,
    "blur": 0.30,        # weighted highest: blur most directly damages matching accuracy
    "pose": 0.25,
    "position": 0.15,
    "occlusion": 0.15,
}


def compute_quality_score(frame, profile=None):
    profile_name = profile or ACTIVE_PROFILE
    profile_config = QUALITY_PROFILES.get(profile_name, QUALITY_PROFILES["balanced"])

    face_check = check_single_face(frame)
    if face_check["status"] == "fail":
        return {
            "overall_score": 0.0,
            "decision": "reject",
            "profile": profile_name,
            "threshold": profile_config["threshold"],
            "reason": f"single_face check failed: {face_check.get('reason', '')}",
            "sub_scores": {},
        }

    sub_results = {
        "brightness": score_brightness(frame),
        "blur": score_blur(frame),
        "pose": score_pose(frame),
        "position": score_position(frame),
        "occlusion": score_occlusion(frame),
    }

    overall = sum(sub_results[k]["score"] * WEIGHTS[k] for k in WEIGHTS)
    overall = round(overall, 1)

    decision = "accept" if overall >= profile_config["threshold"] else "reject"

    return {
        "overall_score": overall,
        "decision": decision,
        "profile": profile_name,
        "threshold": profile_config["threshold"],
        "reason": "" if decision == "accept" else f"score {overall} below {profile_name} threshold {profile_config['threshold']}",
        "sub_scores": sub_results,
    }
