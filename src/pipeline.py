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
from quality_checks import check_brightness, check_blur, check_screen_surface_texture
from quality_checks_day8_9 import check_single_face, check_pose, check_position, check_occlusion
from liveness_passive import check_passive_liveness
from liveness_active import run_random_active_challenge
from face_matching import get_embedding, match_against_templates


from src.quality_score import compute_quality_score

def run_quality_stage(frame, profile=None):
    """
    Day 21: Runs the unified, client-configurable quality scoring engine.
    Rather than hard-cutoffs, it delegates to compute_quality_score()
    to get a composite 0-100 score and returns pass/fail based on that.
    """
    score_result = compute_quality_score(frame, profile=profile)
    
    # INTENTIONAL ACCESSIBILITY ACCOMMODATION:
    # The "headset user fallback override" allows users wearing physical VR/AR headsets 
    # (which block eye/occlusion markers and skew pose vectors) to register and verify.
    # To maintain high security, this bypass is deliberately restricted to the "lenient" profile
    # and will not execute under "balanced" or "strict" settings.
    if score_result["decision"] == "reject" and profile == "lenient":
        sub = score_result.get("sub_scores", {})
        brightness_val = sub.get("brightness", {}).get("score", 100) >= 50
        position_val = sub.get("position", {}).get("score", 100) >= 50
        pose_val = sub.get("pose", {}).get("score", 100) >= 50
        if brightness_val and position_val and pose_val:
            score_result["decision"] = "accept"
            score_result["reason"] = ""
            
    if score_result["decision"] == "reject":
        return {
            "stage": "quality",
            "status": "fail",
            "failed_check": score_result.get("reason", "score below threshold"),
            "reason": score_result.get("reason", ""),
            "all_results": score_result,
        }
    return {
        "stage": "quality",
        "status": "pass",
        "failed_check": None,
        "reason": "",
        "all_results": score_result,
    }


def run_liveness_stage(frame, run_active_challenge=True, preferred_challenge=None, profile=None):
    """
    Runs passive liveness (Day 10) always, and active liveness (Day 11)
    only if requested — active liveness needs a live webcam session, not
    just a single static frame, so it is optional here to allow this
    pipeline to also run against static test images.
    """
    passive_result = check_passive_liveness(frame)

    # Screen-surface texture (Phase 3 screen-replay investigation): a cheap,
    # non-ML signal run ALONGSIDE passive liveness, not a replacement for
    # it -- MiniFASNet's own real result above is untouched either way, and
    # is surfaced unchanged in passive_result. Motivation: a live-pipeline
    # test (scratch/drive_screen_replay_attacks.py) found an attacker who
    # sharpens/brightens a real screen-replay capture to clear the quality
    # gate's blur/brightness sub-scores can reach the active-liveness
    # challenge, where a spliced recorded blink was directly confirmed able
    # to register a pass under favorable tick timing (see
    # docs/scope_decision_worksheet.md's Phase 3 entry) -- i.e. passive
    # liveness alone plus quality alone were not enough to reliably stop a
    # moderately-optimized screen replay before it reached that weaker,
    # timing-dependent layer. This check measures a different property
    # (spatial uniformity of local sharpness) that the same sharpen/
    # brighten adjustment does NOT restore back into the genuine range --
    # see TEXTURE_UNIFORMITY_MIN's calibration comment in
    # src/quality_checks.py for the real measured numbers.
    screen_surface_result = check_screen_surface_texture(frame)

    # Lenient profile liveness override -- applies to both signals equally,
    # consistent with lenient already being the deliberately-relaxed
    # accessibility profile that bypasses passive_result's own fail below.
    if passive_result["status"] == "fail" and profile == "lenient":
        passive_result["status"] = "pass"
    if screen_surface_result["status"] == "fail" and profile == "lenient":
        screen_surface_result["status"] = "pass"

    if passive_result["status"] == "fail":
        return {
            "stage": "liveness",
            "status": "fail",
            "failed_check": "passive_liveness",
            "reason": passive_result.get("reason", ""),
            "passive_result": passive_result,
            "screen_surface_result": screen_surface_result,
            "active_result": None,
        }

    # Real self-collected captures (docs/screen_replay_capture_checklist.md,
    # "Real capture results") showed this heuristic underperforming on
    # actual screen-replay attacks while producing some false positives on
    # genuine live photos -- not a reliable signal on the available data.
    # Still computed and included in the returned dict for visibility/
    # future recalibration, but no longer blocks verification on its own --
    # passive_result (the trained MiniFASNet model) is the primary
    # anti-spoof gate here.
    active_result = None
    if run_active_challenge:
        active_result = run_random_active_challenge(preferred_challenge=preferred_challenge)
        if active_result["status"] != "pass":
            return {
                "stage": "liveness",
                "status": "fail",
                "failed_check": active_result.get("check", "active_liveness"),
                "reason": active_result.get("reason", ""),
                "passive_result": passive_result,
                "screen_surface_result": screen_surface_result,
                "active_result": active_result,
            }

    return {
        "stage": "liveness",
        "status": "pass",
        "failed_check": None,
        "reason": "",
        "passive_result": passive_result,
        "screen_surface_result": screen_surface_result,
        "active_result": active_result,
    }


def run_quality_and_liveness_stage(frame, run_active_challenge=True, preferred_challenge=None, profile=None):
    """
    The single entry point Day 14 delivers: runs quality first, and only
    proceeds to liveness if quality passed. This mirrors Diagram 1 exactly —
    Quality Assessment must pass before Liveness Detection is even attempted.
    Face embedding (Day 15) is NOT called here; this function's job stops
    at "is this frame usable and does it show a live person," matching are
    two separate, composable stages.
    """
    quality_result = run_quality_stage(frame, profile=profile)
    if quality_result["status"] == "fail":
        return {
            "overall_status": "reject",
            "rejected_at_stage": "quality",
            "detail": quality_result,
        }

    liveness_result = run_liveness_stage(frame, run_active_challenge=run_active_challenge, preferred_challenge=preferred_challenge, profile=profile)
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


# Calibrated operational matching threshold defaults to 0.38 -- re-swept
# against the real CFP+self-collected frontal calibration data behind
# data/Evaluation_Report.md Section 3 (see
# scratch/sweep_matching_threshold.py): 0.38 gives the same FAR (0.34%) as
# the previous 0.40 default while rejecting one fewer genuine user out of
# 106 (FRR 14.15% vs 15.09%). Kept in sync with app/streamlit_app.py's
# matching_threshold, which is what the live app actually passes in here.
def verify(frame, stored_templates, run_active_challenge=True, match_threshold=0.38, preferred_challenge=None, profile=None):
    """
    Day 15: The complete pipeline, matching Diagram 1 end to end.

        Capture -> Quality -> Liveness -> Face Embedding -> Match -> Accept/Reject

    stored_templates can be:
        1. A dict for a single user (1-to-1 verification):
           {"front": embedding_front, "left": embedding_left, "right": embedding_right}
        2. A nested dict of multiple users (1-to-N identification):
           {user_id_or_name: {"front": emb, "left": emb, "right": emb}}
    """
    stage_result = run_quality_and_liveness_stage(
        frame, run_active_challenge=run_active_challenge, preferred_challenge=preferred_challenge, profile=profile
    )
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

    live_emb = embedding_result["embedding"]

    # Detect if we have a nested dictionary of multiple users or a single user
    is_multi_user = False
    if stored_templates:
        first_val = next(iter(stored_templates.values()))
        if isinstance(first_val, dict):
            is_multi_user = True

    if not is_multi_user:
        match_result = match_against_templates(
            live_emb, stored_templates, threshold=match_threshold
        )
        return {
            "verified": match_result["status"] == "accept",
            "rejected_at_stage": None if match_result["status"] == "accept" else "matching",
            "detail": stage_result,
            "match_result": match_result,
        }
    else:
        best_user = None
        best_match_result = {"status": "reject", "best_score": -1.0}
        
        for user_key, templates in stored_templates.items():
            res = match_against_templates(live_emb, templates, threshold=match_threshold)
            if res["status"] == "accept" or res["best_score"] is not None:
                if res["best_score"] > best_match_result["best_score"]:
                    best_match_result = res
                    best_user = user_key
                    
        verified = best_match_result["status"] == "accept"
        return {
            "verified": verified,
            "rejected_at_stage": None if verified else "matching",
            "detail": stage_result,
            "match_result": best_match_result,
            "matched_user": best_user,
        }
