"""
src/rppg.py

Day 19: Physiological liveness via remote photoplethysmography (rPPG).
Uses the modern MediaPipe Tasks API face landmarker to locate the forehead ROI
across a sequence of frames, extract the green channel, bandpass filter, and FFT.
"""
import cv2
import numpy as np
import os
import mediapipe as mp
from scipy.signal import butter, filtfilt
from scipy.fft import rfft, rfftfreq
from src.quality_checks_day8_9 import get_landmarker, get_cached_landmarks

# A patch of forehead landmarks, chosen because this region is large, flat,
# usually unobstructed by hair/glasses, and stays relatively still.
FOREHEAD_LANDMARKS = [10, 108, 151, 337]

# Plausible human heart rate range: 42-240 beats per minute, expressed in Hz (0.7 to 4.0 Hz)
LOW_FREQ_HZ = 0.7
HIGH_FREQ_HZ = 4.0

# Calibrated peak prominence threshold based on genuine vs spoof separation
PEAK_PROMINENCE_MIN = 30.0

# Nyquist's theorem sets a hard floor: a bandpass filter targeting
# LOW_FREQ_HZ needs a sample rate of at least 2 * LOW_FREQ_HZ just to
# represent that frequency at all, and butter()'s Wn must stay strictly
# below 1.0 (i.e. strictly below the Nyquist frequency), not just reach it.
# 1.3x that theoretical minimum leaves enough headroom for the low cutoff
# to sit meaningfully inside (0, 1) rather than pinned at its edge, where a
# 3rd-order Butterworth filter becomes numerically unstable.
# Below this, there's no fps fix within this function -- the sample rate
# itself is too low for a heart-rate signal, full stop.
MIN_FPS_FOR_ANY_SIGNAL = LOW_FREQ_HZ * 2 * 1.3


def _extract_forehead_roi(frame, landmarks):
    h, w = frame.shape[:2]
    # For modern Tasks API, landmarks is results.face_landmarks[0], which is list-indexed directly
    xs = [landmarks[i].x * w for i in FOREHEAD_LANDMARKS]
    ys = [landmarks[i].y * h for i in FOREHEAD_LANDMARKS]
    x0, x1 = int(min(xs)), int(max(xs))
    y0, y1 = int(min(ys)), int(max(ys))
    pad = 5
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(w, x1 + pad), min(h, y1 + pad)
    return frame[y0:y1, x0:x1]


def _bandpass_filter(signal, fps):
    """
    Raises ValueError (caller catches it) if fps is too low to represent
    even the bottom of the target band -- see MIN_FPS_FOR_ANY_SIGNAL.
    Otherwise clamps the high cutoff to what this fps can actually
    represent instead of always requesting the full clinical band (up to
    240bpm): a real, narrower band beats an outright filter-design failure
    when the live capture rate only covers part of it. This matters in
    practice -- the live app's frame-capture component pushes at most one
    new frame every 350ms (2.86 fps), and measured real-world delivery has
    been well below even that (see debug log: 0.52-0.92 fps), both of
    which sit under HIGH_FREQ_HZ's required 8fps Nyquist rate.
    """
    nyquist = fps / 2.0
    if nyquist <= MIN_FPS_FOR_ANY_SIGNAL / 2.0:
        raise ValueError(
            f"sample rate too low for any heart-rate signal: {fps:.2f} fps "
            f"(need at least {MIN_FPS_FOR_ANY_SIGNAL:.2f} fps)"
        )
    low = LOW_FREQ_HZ / nyquist
    high = min(HIGH_FREQ_HZ, nyquist * 0.95) / nyquist
    b, a = butter(N=3, Wn=[low, high], btype="band")
    return filtfilt(b, a, signal)


def extract_green_mean_from_frame(frame, landmarker=None):
    """
    Single-frame counterpart to the per-frame body of check_rppg_liveness()'s
    loop -- detects the face, extracts the forehead ROI, and returns its
    mean green-channel intensity, or None if no usable face was found in
    this frame. Used both by check_rppg_liveness() (reading from disk) and
    by the live app (accumulating samples tick-by-tick from the WebRTC feed,
    where there's no folder of frames to read from).

    Uses get_cached_landmarks(), which reuses the same detection result
    other checks (e.g. check_pose(), evaluate_blink_tick()) already computed
    for this exact frame object within the same live tick, instead of
    re-running MediaPipe's landmark detector from scratch -- confirmed
    necessary via real live testing, where three independent detect() calls
    per tick (quality check, blink EAR, this) on the identical frame dropped
    the effective tick rate to ~1/sec instead of the designed ~12.5/sec.

    landmarker: accepted for backward compatibility but no longer used --
    get_cached_landmarks() manages the shared singleton internally.
    """
    results = get_cached_landmarks(frame, 0.5)
    if not results.face_landmarks:
        return None

    roi = _extract_forehead_roi(frame, results.face_landmarks[0])
    if roi.size == 0:
        return None
    return float(np.mean(roi[:, :, 1]))


def check_rppg_liveness_from_samples(green_samples, fps_estimate=20.0):
    """
    The bandpass-filter + FFT peak-prominence decision itself, taking an
    already-collected list of per-frame green-channel means (from
    extract_green_mean_from_frame()) rather than reading frames from disk.
    Pulled out of check_rppg_liveness() so the live app can collect samples
    tick-by-tick from the WebRTC feed and evaluate them the same way an
    offline frame folder is evaluated -- same thresholds, same math.
    """
    # fps_estimate * 5 (~5 seconds' worth) is the intended floor, but at a
    # very low real fps_estimate that ratio alone rounds to almost nothing
    # (e.g. 2 samples at 0.52 fps) -- nowhere near enough for the FFT below
    # to resolve a real peak. 20 is an absolute floor under that ratio.
    if len(green_samples) < max(int(fps_estimate * 5), 20):
        return {"check": "rppg", "status": "error",
                "reason": f"too few usable samples ({len(green_samples)}) for a reliable signal"}

    signal = np.array(green_samples)
    signal = signal - np.mean(signal)

    try:
        filtered = _bandpass_filter(signal, fps_estimate)
    except ValueError as e:
        return {"check": "rppg", "status": "error", "reason": str(e)}
    except Exception as e:
        return {"check": "rppg", "status": "error", "reason": f"bandpass filter failed: {e}"}

    n = len(filtered)
    fft_magnitude = np.abs(rfft(filtered))
    freqs = rfftfreq(n, d=1.0 / fps_estimate)

    band_mask = (freqs >= LOW_FREQ_HZ) & (freqs <= HIGH_FREQ_HZ)
    if not np.any(band_mask):
        return {"check": "rppg", "status": "error", "reason": "no frequency bins in the plausible heart-rate band"}

    band_magnitudes = fft_magnitude[band_mask]
    band_freqs = freqs[band_mask]
    peak_idx = np.argmax(band_magnitudes)
    peak_freq_hz = band_freqs[peak_idx]
    peak_magnitude = band_magnitudes[peak_idx]

    background_magnitude = np.median(fft_magnitude[~band_mask]) if np.any(~band_mask) else 1e-6
    prominence = peak_magnitude / (background_magnitude + 1e-6)

    status = "pass" if prominence >= PEAK_PROMINENCE_MIN else "fail"
    estimated_bpm = peak_freq_hz * 60.0

    return {
        "check": "rppg",
        "status": status,
        "estimated_bpm": round(estimated_bpm, 1),
        "peak_prominence": round(float(prominence), 2),
        "frames_used": len(green_samples),
        "reason": "" if status == "pass" else f"no clear pulse peak (prominence {prominence:.2f} below {PEAK_PROMINENCE_MIN})",
    }


def check_rppg_liveness(frame_folder, fps_estimate=20.0):
    """
    Reads every frame in frame_folder (produced by Day 10's capture_rppg_window.py),
    extracts the average green-channel intensity of the forehead region per frame,
    bandpass filters the resulting signal, and checks for a clear dominant peak via FFT.
    """
    if not os.path.isdir(frame_folder):
        return {"check": "rppg", "status": "error", "reason": f"Folder {frame_folder} not found"}

    frame_files = sorted(f for f in os.listdir(frame_folder) if f.lower().endswith((".jpg", ".png")))
    if len(frame_files) < int(fps_estimate * 5):
        return {"check": "rppg", "status": "error",
                "reason": f"too few frames ({len(frame_files)}) for a reliable signal"}

    green_signal = []
    landmarker = get_landmarker()

    for fname in frame_files:
        frame = cv2.imread(os.path.join(frame_folder, fname))
        if frame is None:
            continue
        green_mean = extract_green_mean_from_frame(frame, landmarker=landmarker)
        if green_mean is not None:
            green_signal.append(green_mean)

    if len(green_signal) < int(fps_estimate * 5):
        return {"check": "rppg", "status": "error",
                "reason": f"face detected in only {len(green_signal)} of {len(frame_files)} frames -- insufficient for a signal"}

    return check_rppg_liveness_from_samples(green_signal, fps_estimate=fps_estimate)
