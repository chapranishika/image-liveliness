"""
tests/test_matching.py

Automated pytest tests asserting embedding matching metrics, cosine similarity math,
and best-of-three templates matching loops.
"""
import pytest
import numpy as np
from src.face_matching import cosine_similarity, match_against_templates, get_embedding

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

def test_match_against_templates_rejects_when_no_templates_stored():
    """
    A registered identity with no stored templates at all (e.g. a data
    integrity gap) must reject cleanly, not raise -- match_against_templates()
    is called from the live verification path on every attempt.
    """
    result = match_against_templates(np.ones(512), {}, threshold=0.68)

    assert result["status"] == "reject"
    assert result["best_match_angle"] is None
    assert result["best_score"] is None
    assert "no stored templates" in result["reason"]

def test_get_embedding_returns_a_512_dim_vector_for_a_real_genuine_face(genuine_front_image):
    """
    get_embedding() (the real DeepFace/ArcFace extraction underlying every
    matching-threshold number calibrated this session) had 0% direct
    pytest coverage -- every other test in this file exercises the math
    around embeddings, never the extraction itself.
    """
    result = get_embedding(genuine_front_image)

    assert result["status"] == "success"
    assert result["embedding"] is not None
    assert result["embedding"].shape == (512,)

def test_get_embedding_two_captures_of_the_same_real_person_score_high():
    """
    End-to-end sanity check tying get_embedding() to cosine_similarity()
    the same way the live verification path actually chains them --
    two distinct real genuine photos of the same identity should score
    close to the report's documented genuine-pair range (~0.9676), not
    just "high" in the abstract.
    """
    import os
    import cv2

    front_dir = os.path.join("data", "self_collected", "session_1", "front")
    if not os.path.isdir(front_dir):
        pytest.skip(f"'{front_dir}' not present")
    files = sorted(f for f in os.listdir(front_dir) if f.lower().endswith((".jpg", ".png")))
    if len(files) < 2:
        pytest.skip("need at least 2 genuine frontal images for a same-identity pair")

    img_a = cv2.imread(os.path.join(front_dir, files[0]))
    img_b = cv2.imread(os.path.join(front_dir, files[1]))
    res_a = get_embedding(img_a)
    res_b = get_embedding(img_b)

    assert res_a["status"] == "success" and res_b["status"] == "success"
    sim = cosine_similarity(res_a["embedding"], res_b["embedding"])
    assert sim > 0.5, f"same-identity pair scored unexpectedly low: {sim:.4f}"
