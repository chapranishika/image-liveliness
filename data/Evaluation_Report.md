# Calibration & System Evaluation Report
**Version:** 1.1.0  
**Generated Date:** 2026-08-03  
**Target Architecture:** Secure Face Registration & Verification Framework

---

## 1. Executive Summary
This report summarizes the performance metrics, thresholds, and boundary profiles calibrated across the full framework. The metrics describe a 4-stage pipeline (Quality Scorer -> Passive Liveness -> Face Embedding -> Template Matching) built with local databases, Fernet encryption at rest, sliding rate-limiters, and accessibility challenge fallbacks.

* **Deployed Face Matching Cosine Similarity Threshold:** `0.68` (Real EER: `0.2850`)
* **Deployed Passive Antispoofing Score Threshold:** `0.90` (ACER: `0.200`)
* **Default Deployed Quality Score Preset:** `Balanced` (Score threshold >= 70%)

---

## 2. Quality Assessment Profile Audits
Transitioned from rigid cutoffs to a composite 0-100 score combining Blur, Brightness, Pose Yaw/Pitch/Roll, Position alignment, and Face Occlusion. The acceptance rates below are computed against genuine frontal captures:

| Profile Preset | Score Threshold | Acceptance Rate | Target Deployments |
|---|---|---|---|
| **Lenient** | 50% | 100.0% (2/2) | Older devices, accessibility-first sites |
| **Balanced** | 70% | 0.0% (0/2) | Standard onboarding (Default configuration) |
| **Strict** | 85% | 0.0% (0/2) | High-security re-authentication |

### Scientific Profile Note:
Frontal calibration images average `67.8%` score, passing Lenient but failing Balanced. This is because clean AI-generated flat backgrounds lack Laplacian variance (raw blur check), resulting in a `0.0` blur sub-score. With blur having a `0.30` weight, the composite score is bounded to a maximum of `70.0%`.

---

## 3. Face Matching Accuracy (1-to-N Identification)
Matching performance evaluated by comparing live embeddings against registered multi-angle templates:

* **Equal Error Rate (EER):** `0.2850` at threshold `0.1346`
* **ROC Area Under Curve (AUC):** `0.8016`

At the **deployed threshold of 0.68**, the system registers the following error rates:
* **False Accept Rate (FAR):** `0.00%` (0/200)
* **False Reject Rate (FRR):** `98.11%` (104/106)
* **Half Total Error Rate (HTER):** `49.06%`  
  $$\text{HTER} = \frac{\text{FAR} + \text{FRR}}{2} = \frac{0.0000 + 0.9811}{2} = 0.4906$$

---

## 4. Change History and Remaining Limitations
The biometric metrics have been updated through development phases to resolve key calibration gaps:

1. **RESOLVED (Day 34-35): Real Impostor Baseline**: Previously, matching metrics relied on a synthetic impostor distribution due to having a single genuine identity in the self-collected dataset. This has been resolved by utilizing 200 real, cross-identity different-person matching pairs from the CFP dataset. Genuine distributions have also been expanded to include cross-angle (front vs profile) pairings from the same CFP identities.
2. **No Demographic Bias Auditing**: The system has not been tested for demographic fairness. Differential accuracy across skin tones, genders, or age ranges remains unknown.
3. **SQLite Concurrency Ceilings**: SQLite does not support highly concurrent writes. Multiple parallel registrations risk locking conflicts. Rate limiters act as a safety buffer but do not replace a concurrent server database.
4. **Single-frame Active Challenge Limitations**: Active turn challenges run on a frame sequence, whereas API endpoints operate on a single static frame, naturally requiring client-side challenge execution.

---

## 5. Passive Antispoofing Accuracy (APCER / BPCER / ACER)
Passive liveness (MiniFASNet) is swept across candidate score thresholds. The error rates are calculated against genuine sessions (front/left/right) and staged attacks (printed photo, screen replay, video replay, frozen frames):

* **APCER** (False Acceptance of Spoofs at 0.9): `40.00%` (2/5 if attack_liveness else "0/0")
* **BPCER** (False Rejection of Genuine at 0.9): `0.00%` (0/4 if genuine_liveness else "0/0")
* **Average Classification Error Rate (ACER) at Deployed Boundary:** `0.200`

---

## 6. Architectural Alignment & Finalization
This report confirms that the architectural diagrams compiled during development remain **100% current and structurally accurate** after Days 21-23 improvements:

1. **Diagram 1 (Core Pipeline):** The transition from rigid pass/fail gates to a unified, weighted quality score occurred entirely *within* the "Quality Assessment" modular boundary. Inputs (BGR frame) and outputs (pass/fail status with details) did not change.
2. **Diagram 2 (System Layers):** The layers (UI Streamlit, API routing, Business logic, Cryptographic SQLite storage) remain aligned.
3. **Diagram 3 (Guided Registration sequence):** The sequential captures (FRONT, LEFT, RIGHT) triggered by explicit operator clicks correctly verify quality checkpoints per frame.
4. **Diagram 4 (Verification sequence):** Matches are evaluated in a best-of-three 1-to-N search loop as shown in the sequence trace.

---
