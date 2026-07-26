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
from src.quality_checks_day8_9 import get_landmarker

# A patch of forehead landmarks, chosen because this region is large, flat,
# usually unobstructed by hair/glasses, and stays relatively still.
FOREHEAD_LANDMARKS = [10, 108, 151, 337]

# Plausible human heart rate range: 42-240 beats per minute, expressed in Hz (0.7 to 4.0 Hz)
LOW_FREQ_HZ = 0.7
HIGH_FREQ_HZ = 4.0

# Calibrated peak prominence threshold based on genuine vs spoof separation
PEAK_PROMINENCE_MIN = 30.0


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
    nyquist = fps / 2.0
    low = LOW_FREQ_HZ / nyquist
    high = HIGH_FREQ_HZ / nyquist
    b, a = butter(N=3, Wn=[low, high], btype="band")
    return filtfilt(b, a, signal)


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
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        results = landmarker.detect(mp_image)
        if not results.face_landmarks:
            continue
        
        # results.face_landmarks[0] contains the landmark objects
        roi = _extract_forehead_roi(frame, results.face_landmarks[0])
        if roi.size == 0:
            continue
        green_signal.append(float(np.mean(roi[:, :, 1])))

    landmarker.close()

    if len(green_signal) < int(fps_estimate * 5):
        return {"check": "rppg", "status": "error",
                "reason": f"face detected in only {len(green_signal)} of {len(frame_files)} frames -- insufficient for a signal"}

    signal = np.array(green_signal)
    signal = signal - np.mean(signal)

    try:
        filtered = _bandpass_filter(signal, fps_estimate)
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
        "frames_used": len(green_signal),
        "reason": "" if status == "pass" else f"no clear pulse peak (prominence {prominence:.2f} below {PEAK_PROMINENCE_MIN})",
    }
