"""
src/db.py  (Phase 8 revision: Days 27-28)

Adds, on top of Day 16's original schema:
  - Encryption at rest for every stored embedding (Day 27)
  - A consent_given_at column and consent-gated registration (Day 28)
  - delete_user() implementing the right-to-deletion requirement (Day 28)
  - A basic access_log table, separate from verification_logs, recording
    WHO queried the system and WHEN (Day 28)
"""
import sqlite3
import numpy as np
import os
from datetime import datetime

from src.encryption import encrypt_bytes, decrypt_bytes

DB_PATH = os.environ.get("FACE_DB_PATH", os.path.join("data", "face_verification.db"))


def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = _get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            consent_given_at TEXT,
            deleted_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            angle_type TEXT NOT NULL CHECK (angle_type IN ('front', 'left', 'right')),
            embedding BLOB NOT NULL,
            captured_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS verification_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            quality_result TEXT,
            liveness_result TEXT,
            match_score REAL,
            decision TEXT NOT NULL CHECK (decision IN ('accept', 'reject')),
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS access_log (
            access_id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            target_user_id INTEGER,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def _log_access(actor, action, target_user_id=None):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO access_log (actor, action, target_user_id, timestamp) VALUES (?, ?, ?, ?)",
        (actor, action, target_user_id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def insert_user(name, consent_given=False, actor="system"):
    if not consent_given:
        raise ValueError(
            "Cannot register a user without explicit consent. "
            "Biometric data processing requires documented consent under "
            "most applicable regulations (GDPR, BIPA, similar)."
        )

    conn = _get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.execute(
        "INSERT INTO users (name, created_at, consent_given_at, deleted_at) VALUES (?, ?, ?, NULL)",
        (name, now, now),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    _log_access(actor, "register", user_id)
    return user_id


def _embedding_to_blob(embedding):
    raw = np.asarray(embedding, dtype=np.float64).tobytes()
    return encrypt_bytes(raw)


def _blob_to_embedding(blob):
    raw = decrypt_bytes(blob)
    return np.frombuffer(raw, dtype=np.float64)


def insert_template(user_id, angle_type, embedding):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO templates (user_id, angle_type, embedding, captured_at) VALUES (?, ?, ?, ?)",
        (user_id, angle_type, _embedding_to_blob(embedding), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_templates_for_user(user_id, actor="system"):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT angle_type, embedding FROM templates WHERE user_id = ?", (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    _log_access(actor, "read_templates", user_id)
    return {angle: _blob_to_embedding(blob) for angle, blob in rows}


def get_all_front_templates(actor="system"):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.user_id, u.name, t.embedding
        FROM templates t
        JOIN users u ON t.user_id = u.user_id
        WHERE t.angle_type = 'front' AND u.deleted_at IS NULL
    """)
    rows = cur.fetchall()
    conn.close()
    _log_access(actor, "read_all_front_templates")
    return [(user_id, name, _blob_to_embedding(blob)) for user_id, name, blob in rows]


def log_verification(user_id, quality_result, liveness_result, match_score, decision):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO verification_logs
           (user_id, quality_result, liveness_result, match_score, decision, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, str(quality_result), str(liveness_result), match_score, decision, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def delete_user(user_id, hard_delete=False, actor="system"):
    conn = _get_connection()
    cur = conn.cursor()

    if hard_delete:
        cur.execute("DELETE FROM templates WHERE user_id = ?", (user_id,))
        # verification_logs has a real FOREIGN KEY on user_id (unlike
        # access_log, which deliberately keeps target_user_id unconstrained
        # so the audit trail survives a deleted user) -- deleting the user
        # row without clearing this first violates that constraint. Found
        # via a real end-to-end register -> verify -> hard-delete test
        # (tests/test_api_endpoints.py): any user who had ever completed a
        # single verification attempt made hard_delete fail outright, a gap
        # the previous test only missed because it never inserted a
        # verification log before calling delete_user().
        cur.execute("DELETE FROM verification_logs WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        action = "hard_delete"
    else:
        cur.execute(
            "UPDATE users SET deleted_at = ? WHERE user_id = ?",
            (datetime.now().isoformat(), user_id),
        )
        action = "soft_delete"

    conn.commit()
    conn.close()
    _log_access(actor, action, user_id)
    return {"status": "deleted", "user_id": user_id, "mode": "hard" if hard_delete else "soft"}
