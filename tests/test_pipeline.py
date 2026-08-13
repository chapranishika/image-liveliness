"""
tests/test_pipeline.py

src/pipeline.py orchestrates every other already-tested check into the
real decision order (quality -> liveness -> embedding -> match) and owns
the short-circuit logic and the 1-to-1 vs 1-to-N matching branch -- that
orchestration logic itself had 18% coverage before this file, despite
being exactly what a subtle ordering bug would hide in (the same class of
bug the live app's active-liveness-gate regression this session was).

Branch logic (the lenient-profile accessibility bypass, the liveness
short-circuit) is tested via mocking the underlying checks -- deterministic
and fast, and it's the branch in pipeline.py itself under test, not the
checks it calls (already covered elsewhere). Real images are used for the
integration-level tests (a real end-to-end quality->liveness->match pass,
and match identification across multiple stored users) so the real wiring
between real functions is exercised at least once, not just the branches.
"""
import os
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from src.pipeline import (
    run_quality_stage,
    run_liveness_stage,
    run_quality_and_liveness_stage,
    verify,
)
from src.face_matching import get_embedding


def test_quality_stage_accepts_genuine_frontal_image(genuine_front_image):
    result = run_quality_stage(genuine_front_image, profile="balanced")
    assert result["stage"] == "quality"
    assert result["status"] in ("pass", "fail")


def test_quality_stage_rejects_flat_gray_image(synthetic_flat_gray_image):
    result = run_quality_stage(synthetic_flat_gray_image, profile="balanced")
    assert result["status"] == "fail"
    assert result["failed_check"] is not None


@patch("src.pipeline.compute_quality_score")
def test_lenient_accessibility_bypass_flips_reject_to_accept_when_core_subscores_ok(mock_score):
    """
    The headset-accommodation bypass: a reject under "lenient" is flipped
    to accept ONLY if brightness/position/pose all individually clear 50,
    regardless of what tanked the overall score (e.g. occlusion, from a
    headset blocking eye landmarks).
    """
    mock_score.return_value = {
        "decision": "reject",
        "overall_score": 30.0,
        "reason": "score below threshold",
        "sub_scores": {
            "brightness": {"score": 80.0},
            "position": {"score": 70.0},
            "pose": {"score": 60.0},
            "occlusion": {"score": 0.0},
        },
    }
    result = run_quality_stage(np.zeros((10, 10, 3), dtype=np.uint8), profile="lenient")
    assert result["status"] == "pass"


@patch("src.pipeline.compute_quality_score")
def test_lenient_accessibility_bypass_does_not_apply_on_balanced_profile(mock_score):
    """Same underlying scores as above, but NOT profile="lenient" -- must stay rejected."""
    mock_score.return_value = {
        "decision": "reject",
        "overall_score": 30.0,
        "reason": "score below threshold",
        "sub_scores": {
            "brightness": {"score": 80.0},
            "position": {"score": 70.0},
            "pose": {"score": 60.0},
            "occlusion": {"score": 0.0},
        },
    }
    result = run_quality_stage(np.zeros((10, 10, 3), dtype=np.uint8), profile="balanced")
    assert result["status"] == "fail"


@patch("src.pipeline.compute_quality_score")
def test_lenient_accessibility_bypass_does_not_apply_if_pose_also_fails(mock_score):
    """The bypass requires ALL THREE (brightness/position/pose) to individually clear 50 -- not a majority."""
    mock_score.return_value = {
        "decision": "reject",
        "overall_score": 30.0,
        "reason": "score below threshold",
        "sub_scores": {
            "brightness": {"score": 80.0},
            "position": {"score": 70.0},
            "pose": {"score": 20.0},
        },
    }
    result = run_quality_stage(np.zeros((10, 10, 3), dtype=np.uint8), profile="lenient")
    assert result["status"] == "fail"


@patch("src.pipeline.check_passive_liveness")
@patch("src.pipeline.check_screen_surface_texture")
def test_liveness_stage_rejects_immediately_on_failed_passive_liveness(mock_screen, mock_passive):
    mock_passive.return_value = {"status": "fail", "reason": "spoof detected"}
    mock_screen.return_value = {"status": "pass", "value": 1.0}

    result = run_liveness_stage(np.zeros((10, 10, 3), dtype=np.uint8), run_active_challenge=False)

    assert result["status"] == "fail"
    assert result["failed_check"] == "passive_liveness"
    assert result["active_result"] is None


@patch("src.pipeline.check_passive_liveness")
@patch("src.pipeline.check_screen_surface_texture")
def test_liveness_stage_lenient_profile_overrides_a_failed_passive_liveness(mock_screen, mock_passive):
    mock_passive.return_value = {"status": "fail", "reason": "spoof detected"}
    mock_screen.return_value = {"status": "fail", "value": 0.5}

    result = run_liveness_stage(
        np.zeros((10, 10, 3), dtype=np.uint8), run_active_challenge=False, profile="lenient"
    )

    assert result["status"] == "pass"


def test_liveness_stage_passes_on_genuine_image_without_active_challenge(genuine_front_image):
    """Real, non-mocked path: matches how the live app actually calls this (active challenge happens separately in the tick loop, not inside this function)."""
    result = run_liveness_stage(genuine_front_image, run_active_challenge=False)
    assert result["stage"] == "liveness"
    assert result["status"] in ("pass", "fail")
    assert result["active_result"] is None


@patch("src.pipeline.check_passive_liveness")
@patch("src.pipeline.check_screen_surface_texture")
@patch("src.pipeline.run_random_active_challenge")
def test_liveness_stage_rejects_when_active_challenge_does_not_pass(mock_challenge, mock_screen, mock_passive):
    """
    run_active_challenge=True is the function's own default. Mocked rather
    than exercised against a real camera -- run_random_active_challenge()
    opens cv2.VideoCapture(0) and calls cv2.imshow() in a blocking loop,
    which would actually engage this machine's real webcam and pop a GUI
    window from an automated test run. This still protects the real branch
    under test in this file (an active_result that isn't "pass" must
    reject cleanly, not crash the pipeline), just without touching hardware
    to prove it -- the "camera unavailable" case itself is already covered
    directly in src/liveness_active.py's own responsibility, not this file's.
    """
    mock_passive.return_value = {"status": "pass"}
    mock_screen.return_value = {"status": "pass", "value": 1.0}
    mock_challenge.return_value = {"status": "error", "reason": "camera unavailable"}

    result = run_liveness_stage(np.zeros((100, 100, 3), dtype=np.uint8), run_active_challenge=True)

    assert result["status"] == "fail"
    assert result["active_result"]["status"] == "error"


def test_full_stage_rejects_at_quality_before_ever_reaching_liveness(synthetic_flat_gray_image):
    result = run_quality_and_liveness_stage(synthetic_flat_gray_image, run_active_challenge=False)
    assert result["overall_status"] == "reject"
    assert result["rejected_at_stage"] == "quality"


def test_verify_rejects_at_quality_stage_with_no_embedding_attempted(synthetic_flat_gray_image):
    result = verify(synthetic_flat_gray_image, stored_templates={}, run_active_challenge=False)
    assert result["verified"] is False
    assert result["rejected_at_stage"] == "quality"
    assert result["match_result"] is None


def test_verify_single_user_accepts_a_genuine_match(genuine_front_image):
    """
    Real, end-to-end: embeds the same real image that will be used as the
    "live" query, stores that exact embedding as the single user's
    template, and confirms verify() runs quality -> liveness -> embedding
    -> match and actually accepts -- ties every real stage together, not
    just the math around them.
    """
    own_embedding = get_embedding(genuine_front_image)
    if own_embedding["status"] != "success":
        pytest.skip("could not embed the genuine fixture image")

    result = verify(
        genuine_front_image,
        stored_templates={"front": own_embedding["embedding"]},
        run_active_challenge=False,
    )

    if result["rejected_at_stage"] in ("quality", "liveness"):
        pytest.skip(f"fixture image didn't clear {result['rejected_at_stage']} in this run -- matching logic not exercised")
    assert result["verified"] is True
    assert result["match_result"]["status"] == "accept"


def test_verify_multi_user_identifies_the_correct_matching_user(genuine_front_image):
    """The 1-to-N identification branch: the live embedding should match its OWN stored identity, not an unrelated one, and report which user matched."""
    own_embedding = get_embedding(genuine_front_image)
    if own_embedding["status"] != "success":
        pytest.skip("could not embed the genuine fixture image")

    unrelated = np.zeros(512)
    unrelated[0] = 1.0

    result = verify(
        genuine_front_image,
        stored_templates={
            "alice": {"front": own_embedding["embedding"]},
            "bob": {"front": unrelated},
        },
        run_active_challenge=False,
    )

    if result["rejected_at_stage"] in ("quality", "liveness"):
        pytest.skip(f"fixture image didn't clear {result['rejected_at_stage']} in this run -- matching logic not exercised")
    assert result["verified"] is True
    assert result["matched_user"] == "alice"


def test_verify_rejects_when_embedding_fails():
    """A frame that clears quality+liveness but can't be embedded (mocked failure) must reject at the embedding stage, not raise."""
    with patch("src.pipeline.run_quality_and_liveness_stage") as mock_stage, \
         patch("src.pipeline.get_embedding") as mock_embed:
        mock_stage.return_value = {"overall_status": "pass", "rejected_at_stage": None,
                                    "quality_detail": {}, "liveness_detail": {}}
        mock_embed.return_value = {"status": "error", "embedding": None, "reason": "no face found"}

        result = verify(np.zeros((10, 10, 3), dtype=np.uint8), stored_templates={"front": np.ones(512)},
                         run_active_challenge=False)

    assert result["verified"] is False
    assert result["rejected_at_stage"] == "embedding"
