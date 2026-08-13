"""
tests/test_database_and_security.py

Automated pytest tests asserting security and legal compliance features:
biometric encryption at rest, BIPA/GDPR consent validation, and soft/hard deletions.
"""
import pytest
import numpy as np
from src.encryption import encrypt_bytes, decrypt_bytes
from src.db import (
    insert_user,
    insert_template,
    get_all_front_templates,
    delete_user
)

def query_user_from_db(temp_db, user_id):
    """Directly queries the temporary test database to inspect row fields."""
    conn = temp_db._get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, name, created_at, consent_given_at, deleted_at FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "name": row[1],
            "created_at": row[2],
            "consent_given_at": row[3],
            "deleted_at": row[4]
        }
    return None

def test_encryption_roundtrip_matches_original():
    """Asserts that encrypting and then decrypting returns the exact original bytes."""
    data = b"biometric_embedding_data_mock_bytes_12345"
    ciphertext = encrypt_bytes(data)
    
    # Decrypt and check
    decrypted = decrypt_bytes(ciphertext)
    assert decrypted == data

def test_encrypted_bytes_do_not_contain_plaintext():
    """
    Asserts that the encrypted ciphertext does not contain the plaintext raw bytes,
    guarding against weak no-op or simple offset encryption implementations.
    """
    plaintext = b"sensitive_biometric_data_987654"
    ciphertext = encrypt_bytes(plaintext)
    
    assert plaintext not in ciphertext
    # Encryption must produce ciphertext different from plaintext
    assert ciphertext != plaintext

def test_consent_enforcer_blocks_registration_without_consent(temp_db):
    """
    Asserts that insert_user throws a ValueError if consent is not explicitly given,
    satisfying legal biometric protection regulations (BIPA, GDPR).
    """
    with pytest.raises(ValueError) as excinfo:
        temp_db.insert_user("Alice", consent_given=False)
    
    assert "Cannot register a user without explicit consent" in str(excinfo.value)

def test_consent_logs_timestamp_on_success(temp_db):
    """Asserts that a successful registration correctly records consent_given_at."""
    user_id = temp_db.insert_user("Alice", consent_given=True)
    
    user = query_user_from_db(temp_db, user_id)
    assert user is not None
    assert user["consent_given_at"] is not None
    assert len(user["consent_given_at"]) > 0

def test_soft_deleted_user_excluded_from_duplicate_check_pool(temp_db):
    """
    Asserts that soft-deleted users are immediately excluded from duplicate checking pools
    to satisfy compliance right-to-deletion guidelines.
    """
    # 1. Register a user with a frontal template
    user_id = temp_db.insert_user("Charlie", consent_given=True)
    mock_emb = np.ones(512, dtype=np.float32) * 0.1
    temp_db.insert_template(user_id, "front", mock_emb)
    
    # Verify they are in the active duplicate check pool
    active_templates = temp_db.get_all_front_templates()
    assert any(item[0] == user_id for item in active_templates)
    
    # 2. Soft-delete the user
    temp_db.delete_user(user_id, hard_delete=False)
    
    # Verify they are immediately excluded from the template list
    active_templates_after = temp_db.get_all_front_templates()
    assert not any(item[0] == user_id for item in active_templates_after)
    
    # Verify the user record still exists in DB (marked deleted)
    user = query_user_from_db(temp_db, user_id)
    assert user is not None
    assert user["deleted_at"] is not None

def test_hard_delete_purges_record_irreversibly(temp_db):
    """Asserts that hard deletion completely expunges the user from the database."""
    user_id = temp_db.insert_user("David", consent_given=True)

    # Hard delete
    temp_db.delete_user(user_id, hard_delete=True)

    # User must not exist
    user = query_user_from_db(temp_db, user_id)
    assert user is None

def test_hard_delete_succeeds_after_a_verification_was_logged(temp_db):
    """
    verification_logs has a real FOREIGN KEY on user_id (unlike access_log,
    which deliberately stays unconstrained so the audit trail survives a
    deletion) -- found via a real end-to-end register->verify->hard-delete
    test that hard_delete previously failed outright (sqlite3.IntegrityError)
    for any user who had ever completed a single verification, since the
    test above never logged one first and so never exercised this path.
    """
    user_id = temp_db.insert_user("Eve", consent_given=True)
    temp_db.log_verification(
        user_id=user_id,
        quality_result={"status": "pass"},
        liveness_result={"status": "pass"},
        match_score=0.9,
        decision="accept",
    )

    temp_db.delete_user(user_id, hard_delete=True)

    user = query_user_from_db(temp_db, user_id)
    assert user is None
