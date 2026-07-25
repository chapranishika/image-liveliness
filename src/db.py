"""
src/db.py

Day 16: SQLite storage layer implementing the schema from the Approach &
Design Document (Part 0.4.1): three tables — users, templates (up to three
per user: front/left/right), and verification_logs.

This is the first day anything in this project is actually PERSISTED.
Every previous day's functions took an image in and returned a result out,
with nothing remembered between calls. Registration cannot work that way —
a template captured today must still exist tomorrow when someone tries to
verify against it.

Usage:
    from src.db import init_db, insert_user, insert_template, get_templates_for_user, get_all_front_templates

    init_db()
    user_id = insert_user("Alice")
    insert_template(user_id, "front", embedding_front)
    insert_template(user_id, "left", embedding_left)
    insert_template(user_id, "right", embedding_right)
"""
import sqlite3
import numpy as np
import os
from datetime import datetime

DB_PATH = os.path.join("data", "face_verification.db")


def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite disables this by default
    return conn


def init_db():
    """
    Creates all three tables if they do not already exist. Safe to call
    every time the application starts — CREATE TABLE IF NOT EXISTS never
    destroys existing data.
    """
    conn = _get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
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

    conn.commit()
    conn.close()


def insert_user(name):
    """Creates a new identity row and returns its auto-generated user_id."""
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, created_at) VALUES (?, ?)",
        (name, datetime.now().isoformat()),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id


def _embedding_to_blob(embedding):
    """
    SQLite has no native array type, so a NumPy embedding (a 512-number
    array) is serialized to raw bytes for storage, and deserialized back
    to a NumPy array on read. tobytes()/frombuffer() round-trips exactly,
    with no precision loss, unlike converting to a string representation.
    """
    return np.asarray(embedding, dtype=np.float64).tobytes()


def _blob_to_embedding(blob):
    return np.frombuffer(blob, dtype=np.float64)


def insert_template(user_id, angle_type, embedding):
    """
    Stores one embedding (front, left, or right) for a given user. A user
    should end up with exactly three rows here, one per angle — this
    function does not enforce that count itself; registration logic
    (Day 16's register() function) is responsible for calling this exactly
    three times per successful registration.
    """
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO templates (user_id, angle_type, embedding, captured_at) VALUES (?, ?, ?, ?)",
        (user_id, angle_type, _embedding_to_blob(embedding), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_templates_for_user(user_id):
    """
    Returns a dict like {"front": embedding, "left": embedding, "right": embedding}
    for one user — exactly the shape match_against_templates() (Day 15,
    src/face_matching.py) expects as input.
    """
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT angle_type, embedding FROM templates WHERE user_id = ?", (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return {angle: _blob_to_embedding(blob) for angle, blob in rows}


def get_all_front_templates():
    """
    Returns every registered user's FRONT template only, as a list of
    (user_id, name, embedding) tuples. Used exclusively by duplicate
    detection (Day 17-18) — comparing against every angle for every user
    would triple the comparison cost for no real benefit, since the front
    template alone is distinctive enough to catch an already-registered
    identity (Approach & Design Document, Part 0.1).
    """
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.user_id, u.name, t.embedding
        FROM templates t
        JOIN users u ON t.user_id = u.user_id
        WHERE t.angle_type = 'front'
    """)
    rows = cur.fetchall()
    conn.close()
    return [(user_id, name, _blob_to_embedding(blob)) for user_id, name, blob in rows]


def log_verification(user_id, quality_result, liveness_result, match_score, decision):
    """Records one verification attempt for later evaluation reporting (Day 25)."""
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
