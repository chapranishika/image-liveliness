# Calibration & System Evaluation Report
**Version:** 1.2.0  
**Generated Date:** 2026-08-06  
**Target Architecture:** Secure Face Registration & Verification Framework

---

## 1. Executive Summary
This report summarizes the performance metrics, thresholds, and boundary profiles calibrated across the full framework. The metrics describe a 4-stage pipeline (Quality Scorer -> Passive Liveness -> Face Embedding -> Template Matching) built with local databases, Fernet encryption at rest, sliding rate-limiters, and accessibility challenge fallbacks.

* **Deployed Face Matching Cosine Similarity Threshold:** `0.38` (Specifically calibrated for Frontal-vs-Frontal; updated 2026-08-13 from 0.40, see Section 3.1)
* **Deployed Passive Antispoofing Score Threshold:** `0.90` (ACER: `0.230` on the expanded n=76/n=75 sample — see Section 5; APCER is uneven across attack types, not a single clean number)
* **Default Deployed Quality Score Preset:** `Balanced` (Score threshold >= 70%)

---

## 2. Quality Assessment Profile Audits
Transitioned from rigid cutoffs to a composite 0-100 score. As of this pass, the composite combines **7** sub-checks (previously 5) — Brightness, Blur, Pose Yaw/Pitch/Roll, Position, Occlusion, plus two new checks added to close a real gap against the brief's Phase 2 Section 3 registration-check list (Contrast and Resolution were confirmed missing from the codebase by direct grep before being added — see Section 7). Current weights: Brightness 0.15, Blur 0.25, Pose 0.20, Position 0.15, Occlusion 0.15, Contrast 0.05, Resolution 0.05 (blur and pose were each trimmed 0.05 from their prior 0.30/0.25 to fund the two new checks, keeping blur and pose the two highest-weighted checks). The acceptance rates below are computed against genuine frontal captures, at the weights in effect at the time this table was generated:

| Profile Preset | Score Threshold | Acceptance Rate | Target Deployments |
|---|---|---|---|
| **Lenient** | 50% | 100.0% (2/2) | Older devices, accessibility-first sites |
| **Balanced** | 70% | 0.0% (0/2) | Standard onboarding (Default configuration) |
| **Strict** | 85% | 0.0% (0/2) | High-security re-authentication |

### Scientific Profile Note:
Frontal calibration images average `67.8%` score, passing Lenient but failing Balanced. This is because clean AI-generated flat backgrounds lack Laplacian variance (raw blur check), resulting in a `0.0` blur sub-score. With blur weighted highest among the sub-checks, a `0.0` blur sub-score meaningfully caps the composite regardless of how well every other check scores.

---

## 3. Deployed Face Verification Accuracy (Frontal-vs-Frontal)
Production verification strictly prompts for and captures a frontal face image. Therefore, the **primary metric for deployed verification accuracy** is calibrated on the Frontal-vs-Frontal distribution:

* **Equal Error Rate (EER):** `0.0319` (3.19%) at EER-optimal threshold `0.2642`
* **ROC Area Under Curve (AUC):** `0.9953`

At the **deployed operational threshold of 0.38** (updated from 0.40, see 3.1 below):
* **False Accept Rate (FAR):** `0.34%` (2/595)
* **False Reject Rate (FRR):** `14.15%` (15/106)
* **Half Total Error Rate (HTER):** `7.24%`

$$\text{HTER} = \frac{\text{FAR} + \text{FRR}}{2} = \frac{0.0034 + 0.1415}{2} = 0.0724$$

### Calibrated Operational Rationale:
The EER-optimal threshold of `0.2642` is not used in production because a False Acceptance Rate of `3.19%` is too high for security-critical environments. Setting the threshold to `0.38` forces a near-zero False Acceptance Rate (`0.34%`), meaning impostors are rejected with absolute certainty. The corresponding `14.15%` False Rejection Rate is easily tolerated in the live streaming UI, as the user is automatically verified within milliseconds once a high-quality frame passes the matching criteria.

### 3.1 Threshold sweep (2026-08-13): 0.40 was not actually the best point on its own curve
Section 3's operational numbers were only ever reported at the single deployed point (0.40) — never swept across candidate values the way the passive-liveness threshold is in Section 5.1.2. `scratch/sweep_matching_threshold.py` reruns the exact same real data-building logic as this section (same CFP identities, same self-collected frontal images, same embedding pipeline — confirmed by reproducing the 0.40 row exactly: FAR 0.34% (2/595), FRR 15.09% (16/106), matching the previous version of this report bit for bit) across a range of thresholds:

| Threshold | FAR | FRR | HTER | Impostors accepted | Genuine rejected |
|---|---|---|---|---|---|
| 0.264 (EER-optimal) | 3.36% | 2.83% | 3.10% | 20/595 | 3/106 |
| 0.30 | 2.02% | 4.72% | 3.37% | 12/595 | 5/106 |
| 0.34 | 1.01% | 9.43% | 5.22% | 6/595 | 10/106 |
| 0.36 | 0.84% | 10.38% | 5.61% | 5/595 | 11/106 |
| **0.38 (now deployed)** | **0.34%** | **14.15%** | **7.24%** | **2/595** | **15/106** |
| 0.40 (previous default) | 0.34% | 15.09% | 7.72% | 2/595 | 16/106 |
| 0.42 | 0.17% | 16.98% | 8.57% | 1/595 | 18/106 |

**The finding:** 0.38 gives the *identical* FAR as 0.40 (same 2/595 impostors accepted — no security cost) while rejecting one fewer genuine user (15/106 vs 16/106). 0.40 was strictly dominated by 0.38 in this data — same security, more friction, for no reason. The deployed threshold has been moved to 0.38 (`app/streamlit_app.py`'s `matching_threshold`, `src/pipeline.py`'s `verify()` default) on that basis. 0.36 and below are real, disclosed security-for-convenience trades (lower FRR, but a real, non-zero rise in FAR) — not applied, since they change what the system is actually willing to accept, not just where a tie is broken. Same n=106 genuine / n=595 impostor pairs as the rest of this section — small enough that these percentages have real sampling noise (±3-4 points on FRR is plausible at this n), not precise to the reported decimal.

---

## 4. Explanatory Benchmarks: Multi-Angle and Profile Distributions
Guided Enrollment now captures a single front angle (see `docs/scope_decision_worksheet.md`, Multi-Angle Enrollment: SIMPLIFIED) -- the cross-angle and same-angle benchmarks below remain as offline evaluation data explaining *why* that simplification was safe: cross-angle matching EER does not drive the live verification threshold, and left/right templates were not meaningfully contributing to verification accuracy.

### A. Cross-Angle Matching (Frontal-vs-Profile)
* **Equal Error Rate (EER):** `0.2706` (27.06%) at threshold `0.1116`
* **ROC Area Under Curve (AUC):** `0.8087`
* *Rationale:* Cross-angle matching between a live frontal query and a profile template has a very high EER, demonstrating why verification strictly enforces frontal-only query capture.

### B. Same-Angle Profile-vs-Profile Matching
* **Equal Error Rate (EER):** `0.3983` (39.83%) at threshold `0.3652`
* **ROC Area Under Curve (AUC):** `0.6598`
* *Rationale:* Same-angle profile matches are unstable due to facial occlusion during 90-degree profile turns, showing that the system's live accuracy is driven by frontal-vs-frontal matches.

---

## 5. Passive Antispoofing Accuracy (APCER / BPCER / ACER)

### 5.1 Sample size correction (superseding the old n=5 figure)
The previous version of this report calculated APCER/BPCER from exactly 5 images in `session_1/attacks/` — one per file in that folder, run through the same code path with no distinction between attack categories. That was too small a sample to trust in either direction, and it also had a real methodology bug: `multiple_001.jpg` (a two-person image, meant to test `check_single_face()`) was being scored through the *passive liveness* model along with the real spoof-presentation images, diluting the liveness-specific number with an unrelated failure mode. That has been corrected — the multi-face image is now tested separately against `check_single_face()` only (Section 5.3).

**Real physical constraint, disclosed up front:** this evaluation environment has no camera, printer, or second phone/laptop available to physically re-stage new attack presentations. The project's `self_collected/session_1/attacks/` folder contains exactly one real photographed instance per attack medium:
- `printed_001.jpg` — a real printed photo, photographed in hand
- `screen_001.jpg` — a real MacBook laptop screen, photographed (moiré visible)
- `video_001.jpg` — a real phone screen showing a video call, photographed (moiré visible) — used to represent both "screen replay (phone)" and "video replay," since no separate pre-recorded-video-on-phone capture exists
- `frozen_001.jpg` — a real direct photo standing in for "a paused live feed"; it has no print/screen artifact by design (freezing a feed doesn't introduce one), which is exactly why the brief's own attack-scenario table assigns Frozen Frame to **active** liveness ("no response to challenge"), not passive — see 5.1.1 below for why this matters to the numbers

Each of these 4 real base captures was expanded to **19 variants** (76 total attack attempts) via disclosed photometric/geometric augmentation (±4% crop jitter, ±3° rotation, brightness/contrast jitter, occasional mild blur, JPEG re-compression at varying quality) that **preserves the base image's real optical signature** — the real paper grain in the printed photo, the real screen moiré in the two screen captures — rather than synthesizing a new one. This is **19 variants of 4 real staged captures, not 76 independently re-staged real-world attempts**, and is reported as such rather than implying a larger physical test than was actually run.

Genuine (bona fide) samples got the same treatment for a comparable BPCER sample: 5 real distinct genuine photos across 2 identities (`front_001`, `front_002`, `left_001`, `right_001` — one identity — and `different_001`, a second identity), each expanded to 15 variants via milder benign jitter (no artifacts), for 75 total genuine attempts.

**Validation that augmentation isn't skewing the result:** the raw, unmodified base images alone (before any augmentation) were also scored directly: `printed_001.jpg`=0.8702 (correctly caught), `screen_001.jpg`=0.9712 (**missed** at threshold 0.90), `video_001.jpg`=0.5262 (correctly caught), `frozen_001.jpg`=0.9999 (**missed**, expected). The same two attack types fail on the raw, real, un-augmented photos as fail on the expanded set below — confirming the miss pattern is a real property of these captures under this model, not an artifact of the augmentation pipeline.

### 5.1.1 Results at the deployed threshold (0.90), n=76 attacks / n=75 genuine
* **APCER** (False Acceptance of Spoofs at 0.90): **`46.05%`** (35/76) — worse than the old n=5 figure of 40%, not better; the larger sample did not flatter the number.
* **BPCER** (False Rejection of Genuine at 0.90): **`0.00%`** (0/75)
* **Average Classification Error Rate (ACER):** **`0.230`**

**Per-attack-type breakdown at 0.90** (this is the useful part — the aggregate number hides a very uneven picture):

| Attack Type | Missed at 0.90 | Miss Rate | Note |
|---|---|---|---|
| Printed Photo | 1/19 | 5.3% | Reliably caught |
| Screen Replay (Phone) | 1/19 | 5.3% | Reliably caught |
| Screen Replay (Laptop) | 14/19 | **73.7%** | **Real, confirmed weakness** — MiniFASNet is not picking up this specific laptop screen's moiré reliably |
| Frozen Frame | 19/19 | **100%** | **Expected, not a passive-liveness defect** — a frozen frame has no print/screen texture artifact to detect; the brief's own attack table assigns this attack type to active liveness (no response to challenge), not passive. Passive liveness was never supposed to be the layer that catches this one. |

Excluding the architecturally-expected frozen-frame category, real-texture-based passive liveness misses **15/57 (26.3%)** of the printed/screen/video attacks — still a real, non-trivial weakness, concentrated almost entirely in the laptop-screen-replay category.

### 5.1.2 Threshold tradeoff analysis (not applied — reported for disclosure, same discipline as the face-matching threshold decision)
BPCER stays at exactly 0.000 from threshold 0.10 up to 0.95 in this sample — genuine scores cluster very tightly (0.964–1.000), so there is some room to raise the threshold before any genuine user is affected. Beyond that, further APCER gains cost real BPCER:

| Threshold | APCER | BPCER | ACER | Attacks missed |
|---|---|---|---|---|
| 0.90 (current) | 46.1% | 0.0% | 0.230 | 35/76 |
| 0.95 | 38.2% | 0.0% | 0.191 | 29/76 |
| 0.96 | 36.8% | 0.0% | 0.184 | 28/76 |
| 0.975 | 32.9% | 2.7% | 0.178 | 25/76 |
| 0.985 | 27.6% | 5.3% | **0.165 (best in range)** | 21/76 |
| 0.99 | 26.3% | 8.0% | 0.172 | 20/76 |
| 0.999 | 23.7% | 30.7% | 0.272 | 18/76 |

Raising the threshold to **0.95–0.96 is a free improvement** in this sample (APCER drops ~8-9 points, BPCER stays at 0). Beyond ~0.97, every further APCER gain trades against a real, rising BPCER — exactly the kind of tradeoff that must be shown, not hidden, per this project's own threshold-calibration discipline (Section 3). **This report does not change the deployed threshold** — that's a deliberate security decision for the project owner to make with this evidence in hand, not something to slip in as a side effect of an evaluation update. Even at the best-ACER threshold in this sweep (0.985), APCER remains 27.6% — raising the threshold alone does not fix the underlying screen-replay-laptop weakness; it only trims the margins around it.

### 5.1.3 IMPORTANT CORRECTION (Phase 3, 2026-08-08): Section 5.1's numbers do not describe what the live app actually decides

Everything above in Section 5.1 (APCER/BPCER/ACER, the per-attack-type breakdown, the threshold sweep) is computed by thresholding `antispoof_score` directly: `sum(1 for s in scores if s >= threshold)`. **This is not the decision the live application actually makes.** `src/liveness_passive.py`'s `check_passive_liveness()` — the function `src/pipeline.py` and the live app both actually call — returns `status = "pass" if is_real else "fail"`, using DeepFace's own internal `is_real` boolean, and neither `src/pipeline.py` nor the live app ever reads or thresholds `antispoof_score` themselves. Discovered while directly instrumenting the real decision function for a Phase 3 screen-replay investigation, and confirmed with concrete counter-examples that rule out a simple threshold relationship in either direction:

| Sample | antispoof_score | is_real (real decision) | What a `score >= 0.90` reading would imply |
|---|---|---|---|
| `printed_001.jpg` (real photo attack) | 0.8702 | **False** (correctly rejected) | below 0.90 → "correctly caught" — happens to agree here |
| `screen_001.jpg` (real laptop screen-replay) | 0.9712 | **False** (correctly rejected) | above 0.90 → would read as "missed" — **wrong** |
| `video_001.jpg` (real phone screen-replay) | 0.5262 | **True** (incorrectly accepted) | below 0.90 → would read as "correctly caught" — **wrong** |

`screen_001.jpg` scores higher than `printed_001.jpg` yet is correctly rejected while `video_001.jpg` scores far lower yet is incorrectly accepted — score does not predict the real decision's direction. Most likely explanation (not confirmed against DeepFace's internals, flagged as a follow-up, not asserted as fact): `antispoof_score` may be a confidence-in-the-winning-class value (high whichever class was picked) rather than strictly `P(real)`, which would make a raw threshold comparison meaningless regardless of where the threshold is set.

**Practical consequence, re-measured directly against `is_real` (the real signal, same 76-attack/75-genuine images, same RNG seed 1234 — see `scratch/run_expanded_eval_with_screen_check.py`):**

| Attack type | Missed by `antispoof_score >= 0.90` (Section 5.1, not real) | Missed by `is_real` (the actual live decision) |
|---|---|---|
| Printed Photo | 5.3% (1/19) | 21.1% (4/19) |
| Screen Replay (Laptop) | **73.7% (14/19)** | **5.3% (1/19)** |
| Screen Replay (Phone) | 5.3% (1/19) | **63.2% (12/19)** |
| Frozen Frame | 100% (19/19) | 100% (19/19) — unchanged, architecturally expected either way |

The headline "73.7% screen-replay-laptop miss rate" this report has led with since the prior pass **does not describe what the deployed system does** — the real figure for that specific category is 5.3%, better than reported. But the real figure surfaces a previously-undisclosed gap in the opposite category: **screen-replay-phone is missed 63.2% of the time by the actual live decision**, worse than the 5.3% this report previously implied. Net effect on the combined attack pool: 36/76 (47.4%) missed by the real decision, vs. 46.05% (35/76) previously reported for the (not-real) score-threshold measure — similar in aggregate, but concentrated in a different, previously-uninvestigated category.

**This report does not attempt to fully reconcile Section 5.1's threshold-sweep methodology (5.1.1/5.1.2 above) with this finding** — that requires re-deriving APCER/BPCER against the real `is_real` signal across the full sweep, a larger undertaking than this correction, and is flagged as a dedicated follow-up rather than attempted as a side effect here. Section 5.1's numbers are left as originally computed (not deleted, so the change is auditable) but should not be read as a description of live behavior going forward — Section 5.4 below is.

### 5.1.4 Phase 3: full-pipeline screen-replay investigation and a new supplementary signal

A live-pipeline test (`scratch/drive_screen_replay_attacks.py`, driving the actual `app/streamlit_app.py` Verify Identity flow via Playwright + a fake camera device, not a batch script) built 10 video variants from the real `screen_001.jpg` capture — sharpened/brightened to plausibly clear the quality gate's blur/brightness sub-scores, some with a synthetic blink spliced in over the real detected eye landmarks (same technique as Section 5.2's recorded-gesture test). None of the 10 live attempts fully bypassed the pipeline in this run, but a direct, controlled test of the active-challenge evaluator (`evaluate_blink_tick()`) confirmed the spliced blink **does** register a pass under favorable tick timing — the live runs' 0/10 result reflects the low per-attempt probability of a ~0.5-1s tick landing inside a ~0.6s synthetic blink window across a short test, not a robust defense. This is the same limitation Section 5.2 already discloses (a replayed blink can pass the active challenge), now confirmed to compound with a screen-replay capture specifically, and none of the 10 attempts ever reached rPPG, so rPPG's effectiveness against a screen-replay-with-motion attack remains untested.

**New signal added**: `check_screen_surface_texture()` (`src/quality_checks.py`) — a cheap, non-ML check measuring spatial uniformity of local sharpness (a display's pixel-grid resolution imposes a more uniform sharpness ceiling across whatever it shows than real skin's naturally uneven micro-texture). Calibrated against real measurements documented in the function's own code comment; real genuine samples measured 1.099-1.183, real screen-replay-derived samples measured 0.567-0.846, with `TEXTURE_UNIFORMITY_MIN = 0.90` sitting in the gap. Wired into `src/pipeline.py`'s `run_liveness_stage()` and `app/streamlit_app.py`'s `verify_pose_and_quality()` as an **additional** signal alongside passive liveness (MiniFASNet's own `is_real` result is untouched, not replaced) — either failing rejects at the liveness stage.

**Measured effect** (same 76-attack/75-genuine images used throughout Section 5.1, `scratch/run_expanded_eval_with_screen_check.py`):

| Attack type | Missed before (is_real alone) | Missed after (+ screen-surface check) | Closed |
|---|---|---|---|
| Printed Photo | 21.1% (4/19) | 21.1% (4/19) | 0 (expected — not a screen) |
| Screen Replay (Laptop) | 5.3% (1/19) | 5.3% (1/19) | 0 (already well-handled by `is_real` alone) |
| Screen Replay (Phone) | **63.2% (12/19)** | **0.0% (0/19)** | **12 — full closure** |
| Frozen Frame | 100% (19/19) | 100% (19/19) | 0 (expected — active liveness's job) |
| **Total** | **47.37% (36/76)** | **31.58% (24/76)** | **12** |
| Genuine false-rejections (75 samples) | 0.00% (0/75) | 0.00% (0/75) | 0 new false rejections |

Sample-size caveat, disclosed the same way Section 5.1 discloses its own: only two independent real screen-replay base captures exist in this project (`screen_001.jpg`, `video_001.jpg`) — the threshold is calibrated against those two plus their photometric derivatives, not against a genuinely different physical screen, room, or distance. `docs/screen_replay_capture_checklist.md` lays out what a real capture session would need to validate this further; not executed here (needs a human with a camera).

### 5.2 Recorded-gesture attack vs. active liveness (blink challenge) — CONFIRMED, real result
The brief flags this as a known limitation: "a pre-recorded video of the correct action can, in principle, pass an active check alone." This was tested directly against the actual production `run_blink_challenge()` function (not a reimplementation), fed a video file via `cv2.VideoCapture`.

No real captured footage of a genuine blink exists in this project's data to replay as-is — the one available genuine continuous-capture window (`session_1/rppg_window/`, 150 real frames, ~10s) shows a flat EAR of 0.284–0.286 throughout, never dipping below the 0.25 blink threshold (no natural blink occurred in that specific window). A semi-synthetic test video was built instead: the real genuine `front_001.jpg` photo, held static, with a few consecutive frames showing a synthetic closed-eyelid overlay painted over the same eye-landmark coordinates the production landmarker detects on that exact photo — geometrically equivalent to what a real recorded blink would show a frame-by-frame EAR calculation, without a real recorded blink to draw on.

**Real result:** `run_blink_challenge()` returned `{'status': 'pass', 'min_ear_observed': 0.24}` — the recorded/replayed blink pattern **successfully passed** the active liveness blink challenge. This confirms the brief's own documented limitation with concrete, reproducible evidence rather than leaving it as a theoretical concern: `cv2.VideoCapture` accepts a file path exactly as it accepts a live camera index, and the blink-detection algorithm has no mechanism to distinguish the two — it only ever looks at per-frame landmark geometry, which a replayed recording reproduces identically to a live feed. Named as a limitation in Section 6 below and in the Final Report.

### 5.3 Multiple-face attack vs. `check_single_face()` — CONFIRMED, real result, with a caveat
Two separate real tests were run, because the first one revealed the original attack image doesn't actually exercise the intended rejection path:

1. **`multiple_001.jpg`** (the original self-collected two-person image, a full-body shot against a plain background): `{'face_count': 0, 'status': 'fail', 'reason': 'no face detected'}`. The image **is** rejected — satisfying the brief's "Multiple Face → Rejected" requirement on outcome — but for the wrong reason: both faces are too small/distant in this full-body framing for the short-range BlazeFace detector to register *either* one, so the intended "more than one face" branch was never actually reached by this test image.
2. A second test image was built specifically to exercise that path: a close-up composite of two different real registered identities' faces, cropped and scaled the way a real registration/verification attempt would frame a face. Result: `{'face_count': 2, 'detection_score': 0.981, 'status': 'fail', 'reason': '2 faces detected'}` — this **directly confirms** the intended multi-face rejection logic works correctly when both faces are within the detector's effective range.

Net finding: the system correctly rejects multi-face presentations either way, but the *specific* "2 faces detected" code path had never actually been exercised by a real test image before this pass, only assumed to work by construction, exactly as flagged. It now has been, with a real, reproducible passing result — and the original attack image's failure mode (detector range) is itself a small, real, worth-noting finding about the short-range BlazeFace model's effective distance.

---

## 6. Change History and Remaining Limitations
1. **RESOLVED (Day 34-35): Real Impostor Baseline**: Resolved by utilizing real cross-identity pairs from the CFP dataset.
2. **RESOLVED (Phase 3): Frontal-Only Prod Calibration**: Re-calibrated matching EER on the production frontal-vs-frontal verification path.
3. **CONFIRMED, UNMITIGATED: Demographic Bias**: Bias testing (day36_38_bias_testing.py, 80 CFP images across skin tone/gender/age subgroups) found real, measured gaps — quality pass rate 20.0% (Female) vs. 42.5% (Male); passive liveness pass rate 25.0% (Senior) vs. 46.2% (Middle-aged); skin tone gap present but smaller (26.9% Dark vs. 35.7% Light). Sample sizes (24-40 per subgroup) are large enough to treat as a real signal, not large enough for regulatory-grade certainty. No mitigation has been attempted — this should be disclosed to any client or reviewer, not treated as resolved.
4. **SQLite Concurrency Ceilings**: SQLite does not support highly concurrent writes. Multiple parallel registrations risk locking conflicts. Rate limiters act as a safety buffer but do not replace a concurrent server database.
5. **CONFIRMED, UNMITIGATED: Passive Liveness Attack Detection Is Weaker Than the Old n=5 Sample Suggested**: Re-measured on a larger, disclosed-methodology sample (Section 5.1, 76 attack attempts / 75 genuine attempts), APCER at the deployed 0.90 threshold is 46.05%, not 40%. Screen-replay-laptop is missed 73.7% of the time (a real, confirmed model weakness on this capture, not a sample-size artifact — confirmed on the raw unaugmented photo too). Frozen-frame is missed 100% of the time, but this is architecturally expected, not a passive-liveness defect — the brief's own attack table assigns frozen-frame detection to active liveness, not passive. Printed-photo and screen-replay-phone are both reliably caught (~95%). A threshold tradeoff analysis (Section 5.1.2) shows raising the threshold to 0.95-0.96 is free (BPCER stays 0%), but no threshold in the tested range fixes the screen-replay-laptop gap without a real, rising BPCER cost. The deployed threshold has not been changed as part of this evaluation — this is a disclosed finding for the project owner to act on, not a silent fix.
   **CORRECTION (Phase 3, 2026-08-08 — see Section 5.1.3):** the numbers directly above are computed by thresholding `antispoof_score`, which is NOT the decision the live app actually makes (`check_passive_liveness()` uses DeepFace's own `is_real` flag, never read against any threshold by application code). Re-measured against the real signal: screen-replay-laptop is actually missed only 5.3% of the time (better than reported), but screen-replay-phone — previously reported as reliably caught — is missed 63.2% of the time by the real decision (a previously-undisclosed gap). A new supplementary signal (Section 5.1.4, `check_screen_surface_texture()`) closes that phone-replay gap to 0% missed in the same sample with zero new false rejections on genuine images, while leaving the already-well-handled laptop category unchanged. The printed-photo and frozen-frame figures above are also affected by the same score-vs-`is_real` discrepancy (real figures: 21.1% and 100% missed respectively) — see Section 5.1.3 for the full corrected table. Reconciling Section 5.1.1/5.1.2's threshold-sweep methodology against the real signal has not been done and is flagged as a follow-up, not attempted here.
6. **CONFIRMED, UNMITIGATED: Recorded-Gesture Attacks Bypass Active Liveness Blink Detection**: Directly tested against the real `run_blink_challenge()` function (Section 5.2) — a replayed blink recording passes (`status: 'pass'`, `min_ear_observed: 0.24`). This was already a named, expected limitation in the Approach & Design Document; it is now confirmed with reproducible code-level evidence rather than left as a theoretical concern. `cv2.VideoCapture` cannot distinguish a live camera from a replayed file, and the blink algorithm only ever evaluates per-frame landmark geometry.
7. **CONFIRMED: Multi-Face Rejection Works, But the Original Test Image Didn't Exercise It**: Section 5.3. The original `multiple_001.jpg` self-collected attack image is rejected on outcome, but via "no face detected" (both faces too small/distant for the short-range detector), not "2 faces detected" — the intended rejection branch had never actually been exercised by a real test image. A close-up two-face composite built for this pass confirms the intended branch does work correctly (`face_count: 2, reason: '2 faces detected'`).

---

## 7. Registration Quality Checks: Contrast and Resolution (added this pass)
The brief's Phase 2 Section 3 lists four registration image-quality checks: brightness, contrast, blur, resolution. Brightness and blur existed (`check_brightness`, `check_blur`); contrast and resolution did **not** exist anywhere in `src/quality_checks_day8_9.py` or `src/quality_score.py` — confirmed by direct grep across the codebase before writing any code, per the same "confirm before assuming" discipline used throughout this report.

* **`check_contrast()`** (`src/quality_checks.py`): standard deviation of grayscale pixel intensity — a cheap statistical proxy for "flat/washed-out," matching the existing brightness/blur pattern rather than a trained model. `CONTRAST_MIN = 30`, calibrated against real measurements: genuine self-collected captures measure std 85.65-93.18; a synthetic moderate wash-out (70% contrast reduction toward mid-gray) measures 26.71; a severe wash-out (85% reduction) measures 13.37. 30 sits just above the moderate wash-out case, leaving every real genuine capture measured more than 2.5x headroom above it.
* **`check_resolution()`** (`src/quality_checks_day8_9.py`): face bounding-box width in absolute pixels, reusing the same detector call `check_position()` already makes. Distinct from `check_position()`'s `face_area_ratio` — a face can occupy a reasonable *fraction* of a low-resolution frame and still lack the *absolute* pixel detail matching needs; this catches that case directly. `MIN_FACE_WIDTH_PX = 100`, calibrated against real measurements: at the app's negotiated 640x360 capture resolution, real genuine close-up captures measure face bounding-box widths of 207-253px — 100px leaves more than 2x headroom below every real measured capture.

Both are wired into `compute_quality_score()` (weights: 0.05 each, funded by trimming blur 0.30→0.25 and pose 0.25→0.20 — see Section 2), which is the shared function behind both the registration capture-quality gate and the live per-tick guide overlay; per the task's own framing this was permitted ("not necessarily" required to exclude from the live path), and keeping one shared scoring function was judged simpler and more consistent than maintaining a parallel registration-only scoring path. Both were added to `explain_quality_failure()`'s post-capture correction card ("🌗 Contrast: Avoid strong backlighting or glare" / "📷 Image Detail: Move closer so your face fills more of the frame") and to the live short-guide message dictionary, so a contrast or resolution failure now produces a specific corrective message rather than falling through to the generic fallback.

Verified with a functional smoke test: a genuine real capture scores contrast=100/resolution=100 (raw std=89.02, raw width=342px); a synthetically washed-out version of the same photo correctly drops contrast to score=13.1 (raw std=17.84) and flips the overall decision to reject; a shrunk/distanced face correctly drops the resolution score in proportion to its shrinking pixel width. Full pytest suite (13/13) still passes after the weight rebalancing — see `docs/Final_Report.md` for the fresh confirmed run.

---
