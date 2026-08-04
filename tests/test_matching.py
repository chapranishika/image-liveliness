"""
tests/test_matching.py

Automated pytest tests asserting embedding matching metrics, cosine similarity math,
and best-of-three templates matching loops.
"""
import pytest
import numpy as np
from src.face_matching import cosine_similarity, match_against_templates

def test_orthogonal_vectors_have_similarity_of_zero(orthogonal_embedding_pair):
    """
    Asserts that perpendicular vectors have a cosine similarity of exactly 0.0.
    Ensures the normalized vector dot product mathematical foundation is intact.
    """
    v1, v2 = orthogonal_embedding_pair
    sim = cosine_similarity(v1, v2)
    assert abs(sim) < 1e-12

def test_identical_vectors_have_similarity_of_one():
    """Asserts that identical vectors have a cosine similarity of exactly 1.0."""
    v = np.random.randn(512)
    sim = cosine_similarity(v, v)
    assert abs(sim - 1.0) < 1e-12

def test_match_against_templates_identifies_best_angle():
    """Asserts that match_against_templates chooses the template with the highest score."""
    # Setup perpendicular template vectors
    emb_front = np.zeros(512)
    emb_front[0] = 1.0
    
    emb_left = np.zeros(512)
    emb_left[1] = 1.0
    
    emb_right = np.zeros(512)
    emb_right[2] = 1.0
    
    stored = {
        "front": emb_front,
        "left": emb_left,
        "right": emb_right
    }
    
    # Query vector is closest to 'left' template
    # query = 0.2 * front + 0.8 * left + 0.0 * right
    query = np.zeros(512)
    query[0] = 0.2
    query[1] = 0.8
    
    result = match_against_templates(query, stored, threshold=0.5)
    
    assert result["status"] == "accept"
    assert result["best_match_angle"] == "left"
    assert result["best_score"] > 0.7

def test_match_against_templates_rejects_below_threshold():
    """Asserts that match_against_templates rejects query when best score is below threshold."""
    emb_front = np.zeros(512)
    emb_front[0] = 1.0
    
    stored = {"front": emb_front}
    
    # Query is orthogonal to stored template
    query = np.zeros(512)
    query[1] = 1.0
    
    result = match_against_templates(query, stored, threshold=0.68)
    
    assert result["status"] == "reject"
    assert "below threshold" in result["reason"]
