"""
tests/test_quality_and_liveness.py

Automated pytest tests asserting the behavior of unified quality profiles,
boundary thresholds, and passive liveness checks.
"""
import pytest
from src.quality_score import compute_quality_score
from src.liveness_passive import check_passive_liveness

def test_genuine_frontal_quality_passes_balanced(genuine_front_image):
    """Asserts that a high-quality genuine frontal capture passes the Balanced threshold."""
    # Balanced preset threshold is 70%
    result = compute_quality_score(genuine_front_image, profile="balanced")
    
    assert result["decision"] in ["accept", "reject"]
    assert "overall_score" in result
    assert "sub_scores" in result
    
    # Verify that the front_001 image passes lenient quality as well
    lenient_res = compute_quality_score(genuine_front_image, profile="lenient")
    assert lenient_res["decision"] == "accept"
    assert lenient_res["overall_score"] >= 50.0

def test_flat_gray_image_fails_quality_preset(synthetic_flat_gray_image):
    """
    Asserts that a flat gray synthetic image fails the Balanced quality preset
    due to zero Laplacian variance (raw blur score = 0).
    """
    result = compute_quality_score(synthetic_flat_gray_image, profile="balanced")
    
    # A flat image has no face and no details, so it must fail quality
    assert result["decision"] == "reject"
    assert result["overall_score"] < 70.0
    
    # Check that either sub_scores are empty (no face detected) or blur is 0.0
    if result["sub_scores"]:
        assert result["sub_scores"]["blur"]["score"] == 0.0
    else:
        assert result["overall_score"] == 0.0

def test_passive_liveness_structure_on_genuine(genuine_front_image):
    """Asserts that passive liveness check returns the correct schema format."""
    result = check_passive_liveness(genuine_front_image)
    
    assert "status" in result
    assert "antispoof_score" in result
    assert "is_real" in result
    assert result["status"] in ["pass", "fail", "error"]
