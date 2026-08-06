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

---

## 3. Key Findings & Actions

### Finding: Stale Documentation resolved
* The synthetic impostor matching distribution warning has been **fully resolved** by implementing real CFP pairing calibration (EER = 0.2850). Stale warnings in walkthroughs and PDFs have been programmatically scanned and removed.

### Finding: The Missing Video Deliverable
* While Phase 8 introduced massive security and operational upgrades, the original brief's required **client demonstration video** is still missing. 
* **ACTION**: Shift focus immediately to recording a video demonstrating:
  1. Smooth WebRTC camera streams and preset adjustments.
  2. The enrollment sequence (guided Front, Left, Right captures).
  3. Live 1-to-N matching identification.
  4. Legal compliance features (deletions and consent gates) and the `/health` diagnostic audit panels.

---
