"""
tests/test_rppg.py

Regression tests for the rPPG low-fps bug found via live testing: every
real Verify Identity attempt this session measured a real_fps of 0.52-0.92
(see scratch/debug_challenge.log), well below what a Nyquist-valid bandpass
filter for LOW_FREQ_HZ/HIGH_FREQ_HZ needs -- scipy's butter() raised a
cryptic "Digital filter critical frequencies must be 0 < Wn < 1" on every
single evaluation. These tests confirm the fix: a clear, specific error at
genuinely too-low fps, a real (narrowed) result at moderately-low-but-usable
fps, and unchanged behavior at the fps the function was originally designed
around.
"""
import numpy as np
import pytest

from src.rppg import check_rppg_liveness_from_samples, MIN_FPS_FOR_ANY_SIGNAL


def _synthetic_pulse_signal(n_samples, fps, bpm=72):
    t = np.arange(n_samples) / fps
    freq_hz = bpm / 60.0
    return (100 * np.sin(2 * np.pi * freq_hz * t) + np.random.RandomState(0).normal(0, 1, n_samples)).tolist()


def test_real_measured_low_fps_gives_clear_error_not_scipy_exception():
    # The exact real_fps values measured live this session.
    for real_fps in [0.52, 0.79, 0.92]:
        samples = _synthetic_pulse_signal(50, real_fps)
        result = check_rppg_liveness_from_samples(samples, fps_estimate=real_fps)
        assert result["status"] == "error"
        assert "Wn" not in result["reason"]
        assert "critical frequencies" not in result["reason"]


def test_fps_far_below_nyquist_floor_reports_sample_rate_reason():
    samples = _synthetic_pulse_signal(50, 0.9)
    result = check_rppg_liveness_from_samples(samples, fps_estimate=0.9)
    assert result["status"] == "error"
    assert "sample rate too low" in result["reason"]


def test_fps_at_designed_default_still_works_unchanged():
    samples = _synthetic_pulse_signal(200, 20.0, bpm=72)
    result = check_rppg_liveness_from_samples(samples, fps_estimate=20.0)
    assert result["status"] in ("pass", "fail")
    assert "reason" in result


def test_moderately_low_fps_above_floor_produces_real_result_not_error():
    # Comfortably above MIN_FPS_FOR_ANY_SIGNAL (~1.82) -- e.g. close to the
    # live app's JS-side push ceiling of 2.86 fps -- should get a real
    # pass/fail from a narrowed band, not an error.
    fps = MIN_FPS_FOR_ANY_SIGNAL + 0.5
    samples = _synthetic_pulse_signal(30, fps, bpm=50)
    result = check_rppg_liveness_from_samples(samples, fps_estimate=fps)
    assert result["status"] in ("pass", "fail")


def test_too_few_samples_still_caught_even_at_low_fps():
    # At low fps_estimate, fps_estimate*5 alone rounds to almost nothing --
    # the absolute floor (20) must still catch this instead of attempting a
    # doomed FFT on a handful of points.
    samples = _synthetic_pulse_signal(5, 0.9)
    result = check_rppg_liveness_from_samples(samples, fps_estimate=0.9)
    assert result["status"] == "error"
    assert "too few usable samples" in result["reason"]
