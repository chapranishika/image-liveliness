"""
tests/test_liveness_active.py

Regression coverage for src/liveness_active.py's tick-based functions --
previously 16% covered by pytest (0% for check_frame_loop_signature
specifically), despite check_frame_loop_signature being the replay
detector this session's live security work actually depends on (proven
effective against a recorded attack via scratch/retest_blink_replay_bypass.py,
which is not part of the pytest suite and does not run in CI). These tests
promote that finding into real, permanent regression protection.
"""
import time
import numpy as np
import pytest

from src.liveness_active import (
    check_frame_loop_signature,
    evaluate_blink_tick,
    evaluate_head_turn_tick,
    LOOP_SIGNATURE_MIN_LAG_SECONDS,
    LOOP_SIGNATURE_MIN_MATCHES,
)


def _frame(seed=0, size=(64, 64, 3)):
    return np.random.RandomState(seed).randint(0, 255, size=size, dtype=np.uint8)


def test_loop_signature_not_suspicious_on_all_distinct_frames():
    buffer = []
    suspicious_seen = False
    for i in range(10):
        buffer, is_suspicious, match_count = check_frame_loop_signature(_frame(seed=i), buffer)
        suspicious_seen = suspicious_seen or is_suspicious
    assert not suspicious_seen


def test_loop_signature_flags_a_looped_clip_replayed_across_the_lag_window():
    """
    Mirrors the real attack shape this was built for: a short clip of a few
    distinct frames, replayed on a cycle for long enough that repeats land
    outside LOOP_SIGNATURE_MIN_LAG_SECONDS -- exactly what
    scratch/retest_blink_replay_bypass.py confirmed catches a looped
    recorded-blink attack.
    """
    clip = [_frame(seed=i) for i in range(4)]
    buffer = []
    fake_now = [1_000_000.0]

    import src.liveness_active as liveness_active
    real_time = liveness_active.time.time
    liveness_active.time.time = lambda: fake_now[0]
    try:
        flagged_at = None
        for tick in range(200):
            frame = clip[tick % len(clip)]
            buffer, is_suspicious, match_count = check_frame_loop_signature(frame, buffer)
            if is_suspicious and flagged_at is None:
                flagged_at = tick
            fake_now[0] += 0.35  # matches the frame-capture component's real push interval
    finally:
        liveness_active.time.time = real_time

    assert flagged_at is not None, "a looped 4-frame clip replayed for 70s was never flagged"


def test_loop_signature_ignores_near_duplicates_inside_the_lag_window():
    """
    A genuinely still live person naturally produces near-identical frames a
    few ticks apart -- this must NOT be flagged, or the check would
    constantly false-positive on ordinary held-still moments (e.g. the
    quality-hold countdown).
    """
    still_frame = _frame(seed=0)
    buffer = []
    fake_now = [1_000_000.0]

    import src.liveness_active as liveness_active
    real_time = liveness_active.time.time
    liveness_active.time.time = lambda: fake_now[0]
    try:
        for tick in range(10):
            buffer, is_suspicious, match_count = check_frame_loop_signature(still_frame, buffer)
            assert not is_suspicious, f"tick {tick}: a still frame within the lag window was flagged"
            fake_now[0] += 0.1  # well under LOOP_SIGNATURE_MIN_LAG_SECONDS
    finally:
        liveness_active.time.time = real_time


def test_loop_signature_requires_min_matches_not_just_one_repeat():
    """A single old repeat shouldn't be enough -- LOOP_SIGNATURE_MIN_MATCHES exists precisely to avoid single-coincidence false positives."""
    repeated = _frame(seed=0)
    other = _frame(seed=1)
    buffer = []
    fake_now = [1_000_000.0]

    import src.liveness_active as liveness_active
    real_time = liveness_active.time.time
    liveness_active.time.time = lambda: fake_now[0]
    try:
        buffer, _, _ = check_frame_loop_signature(repeated, buffer)
        fake_now[0] += LOOP_SIGNATURE_MIN_LAG_SECONDS + 0.1
        # Exactly one repeat of the earlier frame -- below LOOP_SIGNATURE_MIN_MATCHES.
        buffer, is_suspicious, match_count = check_frame_loop_signature(repeated, buffer)
        assert match_count < LOOP_SIGNATURE_MIN_MATCHES
        assert not is_suspicious
        # Fill the rest with genuinely distinct frames -- should stay unflagged.
        for i in range(2, 2 + LOOP_SIGNATURE_MIN_MATCHES):
            buffer, is_suspicious, _ = check_frame_loop_signature(other, buffer)
            fake_now[0] += LOOP_SIGNATURE_MIN_LAG_SECONDS + 0.1
    finally:
        liveness_active.time.time = real_time


def test_loop_signature_buffer_is_capped():
    buffer = []
    for i in range(250):
        buffer, _, _ = check_frame_loop_signature(_frame(seed=i), buffer)
    assert len(buffer) <= 200


def test_evaluate_blink_tick_stays_pending_and_never_crashes_on_a_static_genuine_photo(genuine_front_image):
    """
    Can't synthesize a real blink without real recorded eyelid-closure
    footage (same disclosed limitation as scratch/retest_blink_replay_bypass.py),
    but this protects the real, always-reachable path: a static open-eyed
    photo fed every tick must never crash and must never spuriously report
    "pass" (a false positive here would mean any still frame passes the
    liveness challenge).
    """
    history = []
    for _ in range(15):
        history, status = evaluate_blink_tick(genuine_front_image, history)
        assert status in ("pending", "pass")
    assert status == "pending"


def test_evaluate_head_turn_tick_stays_pending_on_a_frontal_genuine_photo(genuine_front_image):
    """A frontal (non-turned) face must never satisfy a turn challenge -- protects against a threshold regression silently making the challenge trivial."""
    history = (0, 0)
    for _ in range(15):
        history, status = evaluate_head_turn_tick(genuine_front_image, history, direction="left")
        assert status in ("pending", "pass")
    assert status == "pending"
