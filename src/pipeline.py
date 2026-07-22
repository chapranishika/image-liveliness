"""
src/pipeline.py

Day 14: Wire quality checks (Day 7-9), passive liveness (Day 10), and active
liveness (Day 11) into a single orchestrated function. This file does not
introduce any new detection logic — every check it calls already exists and
was already tested independently. Today's job is purely the ORDER and
SHORT-CIRCUIT LOGIC that combines them correctly, matching Diagram 1 in the
Approach & Design Document (Capture -> Face Detection -> Quality Assessment
-> Liveness Detection -> Face Embedding).

Usage:
    import cv2
    from src.pipeline import run_quality_and_liveness_stage

    frame = cv2.imread("some_frame.jpg")
    result = run_quality_and_liveness_stage(frame, run_active_challenge=True)
    print(result)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from quality_checks import check_brightness, check_blur
from quality_checks_day8_9 import check_single_face, check_pose, check_position, check_occlusion
from liveness_passive import check_passive_liveness
from liveness_active import run_random_active_challenge
from face_matching import get_embedding, match_against_templates


def run_quality_stage(frame):
    """
    Runs every Day 7-9 quality check, in the cheapest-first order, and
    stops at the FIRST failure rather than running every remaining check.
    This is a deliberate design choice, not just an optimization: if a
    frame has no face at all, there is no point measuring its pose or
    checking for occlusion — those checks would either error out or
    return meaningless results.
    """
    checks_in_order = [
        check_single_face,   # cheapest, and gates everything else
        check_brightness,
        check_blur,
        check_pose,
        check_position,
        check_occlusion,     # most expensive, runs last
    ]

    results = {}
    for check_fn in checks_in_order:
        result = check_fn(frame)
        check_name = result.get("check", check_fn.__name__)
        results[check_name] = result
        if result["status"] == "fail":
            return {
                "stage": "quality",
                "status": "fail",
                "failed_check": check_name,
                "reason": result.get("reason", ""),
                "all_results": results,
            }

    return {
        "stage": "quality",
        "status": "pass",
        "failed_check": None,
        "reason": "",
        "all_results": results,
    }


def run_liveness_stage(frame, run_active_challenge=True):
    """
    Runs passive liveness (Day 10) always, and active liveness (Day 11)
    only if requested — active liveness needs a live webcam session, not
    just a single static frame, so it is optional here to allow this
    pipeline to also run against static test images (e.g. the Day 7-10
    calibration datasets) without requiring a webcam.
    """
    passive_result = check_passive_liveness(frame)
    if passive_result["status"] == "fail":
        return {
            "stage": "liveness",
            "status": "fail",
            "failed_check": "passive_liveness",
            "reason": passive_result.get("reason", ""),
            "passive_result": passive_result,
            "active_result": None,
        }

    active_result = None
    if run_active_challenge:
        active_result = run_random_active_challenge()
        if active_result["status"] != "pass":
            return {
                "stage": "liveness",
                "status": "fail",
                "failed_check": active_result.get("check", "active_liveness"),
                "reason": active_result.get("reason", ""),
                "passive_result": passive_result,
                "active_result": active_result,
            }

    return {
        "stage": "liveness",
        "status": "pass",
        "failed_check": None,
        "reason": "",
        "passive_result": passive_result,
        "active_result": active_result,
    }


def run_quality_and_liveness_stage(frame, run_active_challenge=True):
    """
    The single entry point Day 14 delivers: runs quality first, and only
    proceeds to liveness if quality passed. This mirrors Diagram 1 exactly —
    Quality Assessment must pass before Liveness Detection is even attempted.
    Face embedding (Day 15) is NOT called here; this function's job stops
    at "is this frame usable and does it show a live person," matching are
    two separate, composable stages.
    """
    quality_result = run_quality_stage(frame)
    if quality_result["status"] == "fail":
        return {
            "overall_status": "reject",
            "rejected_at_stage": "quality",
            "detail": quality_result,
        }

    liveness_result = run_liveness_stage(frame, run_active_challenge=run_active_challenge)
    if liveness_result["status"] == "fail":
        return {
            "overall_status": "reject",
            "rejected_at_stage": "liveness",
            "detail": liveness_result,
        }

    return {
        "overall_status": "pass",
        "rejected_at_stage": None,
        "quality_detail": quality_result,
        "liveness_detail": liveness_result,
    }


def verify(frame, stored_templates, run_active_challenge=True, match_threshold=0.68):
    """
    Day 15: The complete pipeline, matching Diagram 1 end to end.

        Capture -> Quality -> Liveness -> Face Embedding -> Match -> Accept/Reject

    stored_templates is a dict like:
        {"front": embedding_front, "left": embedding_left, "right": embedding_right}
    normally fetched from SQLite for a claimed identity (Day 16 wires this
    to the actual database; today it is passed in directly so this function
    can be tested standalone first).

    This is the FIRST point in the whole project where every previous day's
    work runs together in one call: Day 7-9 quality, Day 10 passive liveness,
    Day 11 active liveness, and Day 15's new matching step.
    """
    stage_result = run_quality_and_liveness_stage(frame, run_active_challenge=run_active_challenge)
    if stage_result["overall_status"] == "reject":
        return {
            "verified": False,
            "rejected_at_stage": stage_result["rejected_at_stage"],
            "detail": stage_result["detail"],
            "match_result": None,
        }

    embedding_result = get_embedding(frame)
    if embedding_result["status"] != "success":
        return {
            "verified": False,
            "rejected_at_stage": "embedding",
            "detail": embedding_result,
            "match_result": None,
        }

    match_result = match_against_templates(
        embedding_result["embedding"], stored_templates, threshold=match_threshold
    )

    return {
        "verified": match_result["status"] == "accept",
        "rejected_at_stage": None if match_result["status"] == "accept" else "matching",
        "detail": stage_result,
        "match_result": match_result,
    }
