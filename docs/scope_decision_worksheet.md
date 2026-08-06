# Scope Decision Worksheet
**Date:** 2026-08-04  
**Project:** Secure Face Registration & Verification Framework

---

## 1. Required Scope & Status (From Brief / A&D Plan)
These are core deliverables explicitly required by the project brief or the initial Approach & Design Document:

| Core Deliverable | Plan Reference | Status | Notes |
|---|---|---|---|
| **Quality Assessment Stage** | Days 7-9 | **DONE** | Unified composite scorer combining blur, brightness, pose, alignment, and occlusion checks. |
| **Passive Liveness Stage** | Day 10 | **DONE** | MiniFASNet CNN classification returning real/spoof decisions. |
| **Active Liveness Stage** | Day 11 | **DONE** | Challenge-response loops checking for eye blinks and head turns. |
| **Face Matching (1-to-N)** | Day 15 | **DONE** | ArcFace embeddings + cosine similarity comparison with best-of-three angle selection. |
| **Multi-Angle Enrollment** | Day 16 | **DONE** | Gated Front, Left, and Right angle capture workflow storing 3 templates per identity. |
| **SQLite Template Database** | Day 16 | **DONE** | Local database containing `users` and `templates` (1:N) schema. |
| **Duplicate Prevention Gating** | Day 17 | **DONE** | Compares frontal embedding against registered users before enrollment. |
| **Client Demonstration Video** | Original Brief | 🔴 **NOT DONE** | **CRITICAL FUTURE ACTION REQUIRED**: A walk-through demonstration recording is explicitly requested but not yet created. |

---

## 2. Extra Scope Items (Phase 8 & Later Additions)
These are production-grade engineering improvements added during development. They were not explicitly required by the original brief or initial plan, and must be reviewed to decide if they should be maintained (KEEP), locked down (FREEZE), or postponed (DEFER):

| Extra Feature | Implementation | Current Status | Scope Decision | Rationale |
|---|---|---|---|---|
| **Biometric Encryption at Rest** | Fernet AES-128-CBC | Completed (Day 27) | **FREEZE** | Code is complete, tested, and secure. Freeze further development unless a new encryption spec is required. |
| **Consent Compliance Gate** | `consent_given_at` | Completed (Day 28) | **FREEZE** | Basic GDPR/BIPA legal consent is fully functional. No active changes needed. |
| **Soft & Hard Deletions** | `deleted_at` + Purge | Completed (Day 28) | **FREEZE** | soft-deleted duplicate filtering and hard purges are fully tested in pytest. Freeze logic. |
| **API Auth & Rate Limiter** | API-Key + Sliding Window | Completed (Day 27/29) | **FREEZE** | Fully operational security gateway. Further auth features (OAuth, JWT) should be deferred. |
| **Dependency Health Checks** | `/health` gateway | Completed (Day 29) | **KEEP** | Essential operational metric for demo/verification tab diagnostics. Keep active. |
| **Accessibility Overrides** | `run_active_challenge=False` | Completed (Day 31) | **FREEZE** | Core motor-impairment bypass loops are built and verified. Freeze logic. |
| **rPPG Physiological Check** | MediaPipe FFT peaks | Completed (Days 19-20) | **DEFER** | Heart-rate pulse check is implemented as an offline evaluation module. Deferred from live execution pipeline (UI/API) due to multi-frame buffering complexity. |
| **Multi-Angle Enrollment** | Front/Left/Right pose-gated capture | Changed: DONE -> SIMPLIFIED | **SIMPLIFIED** | The 3-step pose-gated flow was glitching (getting stuck between Front and Left, never reaching Right). `duplicate_check.py` already only ever compares front templates by design. For a frontal live query, `pipeline.verify()`'s best-of-three matching resolves via the front template almost every time, since cross-angle matching (EER 27.06%, `data/Evaluation_Report.md` Section 4A) is far weaker than frontal-frontal matching (EER 3.19%, Section 3) -- left/right templates were not meaningfully contributing to verification accuracy. Simplified Guided Enrollment to a single front-facing auto-capture step; left/right pose-gated capture logic removed from `app/streamlit_app.py`. |

---

## 3. Key Findings & Actions

### Finding: Stale Documentation resolved
* The synthetic impostor matching distribution warning has been **fully resolved** by implementing real CFP pairing calibration (EER = 0.2850). Stale warnings in walkthroughs and PDFs have been programmatically scanned and removed.

### Finding: The Missing Video Deliverable
* While Phase 8 introduced massive security and operational upgrades, the original brief's required **client demonstration video** is still missing. 
* **ACTION**: Shift focus immediately to recording a video demonstrating:
  1. Smooth WebRTC camera streams and preset adjustments.
  2. The enrollment sequence (guided single front-facing capture; see Multi-Angle Enrollment scope decision in Section 2).
  3. Live 1-to-N matching identification.
  4. Legal compliance features (deletions and consent gates) and the `/health` diagnostic audit panels.
* `docs/video_storyboard.md` has been rewritten to match the actual current UI (no sidebar, no tabs, automatic capture, bottom admin expander) — the previous storyboard described a UI that no longer exists and would have produced a mismatched recording.

### Finding: Confirmed Demographic Bias (not merely untested)
* `day36_38_bias_testing.py` was executed against 80 real CFP images across skin tone, gender, and age subgroups. This moved bias from an "unknown" caveat to a **measured, disclosed problem**:
  * Quality pass rate (Balanced profile): Female 20.0% (8/40) vs. Male 42.5% (17/40).
  * Passive liveness pass rate: Senior 25.0% (6/24) vs. Middle-aged 46.2% (12/26).
  * Skin tone gap was smaller but present (Dark 26.9% vs. Light 35.7% quality pass rate).
* **Sample sizes (24-40 per subgroup) are large enough to take seriously as a signal, not large enough to be regulatory-grade proof.**
* **Status: UNMITIGATED.** No rebalancing, threshold adjustment per subgroup, or retraining has been attempted. This should be disclosed explicitly to any client or reviewer alongside the calibration numbers, not left implicit in a script's console output. **ACTION**: at minimum, add this finding to any client-facing evaluation summary before demo/handoff; full mitigation is out of scope for the current timeline.

### Finding: Intermittent WebRTC Connection Hiccup (environmental, not an app bug)
* Reproduced 3 times across separate sessions using a targeted probe on `ctx.state.playing` plus a frame-arrival heartbeat in `video_frame_callback`. Every time: `ctx.state.playing` flips `True` -> `False` for 20-32 seconds, then self-recovers, with frame arrival stopping and resuming in exact lockstep (e.g., last frame at t=514.79s, next at t=546.74s, a 32s gap matching the `playing=False` window precisely).
* The app's own polling loop (`if ctx.state.playing and keep_polling_alive: ... st.rerun()`) was confirmed working exactly as designed — it correctly pauses reruns during the drop and resumes after, so this is not a script freeze or polling-loop bug.
* Ruled out: no exception/traceback or ICE/connection-state log line during the stall window (aiortc/streamlit-webrtc don't surface this transition at the captured log level); zero Windows Defender or System event log entries in the exact wall-clock window; `aiortc` 1.15.0 / `streamlit-webrtc` 0.76.2 are both current, not a known-buggy stale version.
* **Conclusion**: most likely an aiortc peer-connection ICE consent-freshness/keepalive hiccup, self-healing without app intervention. Observed in every longer session tested, typically 30-90s into a connection, lasting 20-32s. There is no code-level cause identified to fix — this is a library/environment-level characteristic, not an application bug.
* **Status: KNOWN LIMITATION, not chased further** (diminishing-return risk this close to delivery outweighs an unconfirmed speculative fix). **Practical mitigation for recording**: keep continuous camera segments under ~30 seconds where possible, or be ready for one hard cut/retry if it hits mid-take. Disclose to the client as a known WebRTC characteristic rather than presenting the app as glitch-free.

---
