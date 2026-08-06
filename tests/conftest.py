"""
tests/conftest.py

Defines shared pytest fixtures for image testing, synthetic mathematical validations,
and temporary, isolated database sessions.
"""
import os
import sys
import tempfile
import pytest
import cv2
import numpy as np

# Ensure the project root and src/ are in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import db

@pytest.fixture(scope="session", autouse=True)
def configure_env():
    """Sets default environment variables dynamically for testing session."""
    from src.encryption import generate_new_key
    import secrets
    os.environ["FACE_DB_ENCRYPTION_KEY"] = generate_new_key()
    os.environ["FACE_API_KEY"] = f"test_api_key_{secrets.token_hex(16)}"

@pytest.fixture
def genuine_front_image():
    """Loads a real self-collected genuine frontal face image."""
    path = os.path.join("data", "self_collected", "session_1", "front", "front_001.jpg")
    if not os.path.exists(path):
        pytest.skip(f"Genuine front image '{path}' not found.")
    img = cv2.imread(path)
    if img is None:
        pytest.skip(f"Failed to read genuine front image '{path}'.")
    return img

@pytest.fixture
def dark_image():
    """Loads a real self-collected bad-quality dark face image if present."""
    path = os.path.join("data", "self_collected", "bad_quality", "dark_image.jpg")
    if not os.path.exists(path):
        pytest.skip(f"Optional dark image '{path}' not present, skipping test.")
    img = cv2.imread(path)
    if img is None:
        pytest.skip(f"Failed to read dark image '{path}'.")
    return img

@pytest.fixture
def blurry_image():
    """Loads a real self-collected bad-quality blurry face image if present."""
    path = os.path.join("data", "self_collected", "bad_quality", "blurry_image.jpg")
    if not os.path.exists(path):
        pytest.skip(f"Optional blurry image '{path}' not present, skipping test.")
    img = cv2.imread(path)
    if img is None:
        pytest.skip(f"Failed to read blurry image '{path}'.")
    return img

@pytest.fixture
def synthetic_flat_gray_image():
    """
    Generates a synthetic flat gray matrix to test math boundary conditions.
    A perfectly flat image has zero Laplacian variance (raw blur score = 0).
    """
    return np.ones((224, 224, 3), dtype=np.uint8) * 128

@pytest.fixture
def orthogonal_embedding_pair():
    """Returns two mathematically perpendicular vectors of dimension 512."""
    v1 = np.zeros(512, dtype=np.float64)
    v1[0] = 1.0
    
    v2 = np.zeros(512, dtype=np.float64)
    v2[1] = 1.0
    
    return v1, v2

@pytest.fixture
def temp_db():
    """
    Sets up an isolated, temporary SQLite database session for unit tests.
    Ensures test registrations do not pollute the primary data file.
    """
    # Create unique temp db file path
    fd, temp_db_path = tempfile.mkstemp(suffix=".db", prefix="test_pytest_")
    os.close(fd)
    
    # Save original db path if set
    orig_db_path = os.environ.get("FACE_DB_PATH")
    os.environ["FACE_DB_PATH"] = temp_db_path
    
    # Force db module to reload the new DB_PATH
    import importlib
    importlib.reload(db)
    
    # Initialize the temporary database schema
    db.init_db()
    
    yield db
    
    # Cleanup database file after test teardown
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except Exception:
            pass
            
    # Restore original environment
    if orig_db_path:
        os.environ["FACE_DB_PATH"] = orig_db_path
    else:
        os.environ.pop("FACE_DB_PATH", None)
        
    importlib.reload(db)
