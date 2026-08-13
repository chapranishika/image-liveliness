# Final Confirmation Report — End of the 5-Phase Stability/Security Pass

> **Update (2026-08-13):** this document is the confirmation pass for the
> 5-phase Stability/Security work that ended 2026-08-08. Real, substantial
> work happened after this date -- a security-hardening round (structural
> active-liveness gate, the loop-signature replay detector, a critical live
> regression found and fixed, real-image replay-signal calibration), a
> Docker/admin-console/CI production-readiness pass, and an rPPG bandpass
> fix, matching-threshold optimization, and testing-rigor pass (26->43
> tests, 50%->62% coverage) -- none of which is reflected below. See
> `docs/Final_Report_Full.docx`, Phase 11 and Phase 12, for that work. Left
> below unchanged rather than rewritten, per this project's own discipline
> of keeping superseded numbers auditable instead of silently replacing them.

**Date:** 2026-08-08
**Structure:** one update per item in `docs/phase0_baseline.md`'s 8-item list, in the same order, so this diffs cleanly against that baseline. Each item gets a final status — **closed**, **substantially mitigated**, **disclosed-open-by-design**, or **still-open** — with the real number or evidence backing it, not prose confidence.

**Re-verification run this pass** (2026-08-08, current code): full pytest suite (14/14), `day19_attack_testing_matrix.py`, `scratch/run_expanded_liveness_eval.py`, `day36_38_bias_testing.py` (extended, Phase 4), and a live Playwright smoke pass of both Verify Identity and Guided Enrollment. All results below reflect this run, not stale numbers from earlier phases carried forward without re-checking.

| # | Item | Final status |
|---|---|---|
| 1 | Screen-replay liveness gap | **Partially mitigated — real generalization gap found in Phase 5, not patched over** |
| 2 | Active-liveness blink-replay bypass | **Disclosed-open-by-design** |
| 3 | Per-tick response time | **Closed** (characterized, no change needed) |
| 4 | Stability pass | **Closed** (the specific crash) / **still-open** (live-feedback timing tuning) |
| 5 | Fairness/bias gaps | **Disclosed-open-by-design**, now root-caused |
| 6 | WebRTC hiccup | **Closed** (app-side recovery bug) / **still-open** (mitigation's real-world effectiveness) |
| 7 | Demo video | **Still-open** (not recorded), prep complete |
| 8 | Final confirmation pass | **Closed** — this document |

---

## 1. Screen-replay liveness gap — Partially mitigated (real generalization gap found, Phase 5)

**What changed:** Phase 3 found the originally-reported 73.7% laptop-screen-replay miss rate was computed from a metric (`antispoof_score >= 0.90`) the live app never actually uses. The real decision (`check_passive_liveness()`'s `is_real` flag) misses laptop-replay only 5.3% of the time (1/19) — better than reported — but misses **phone**-screen-replay 63.2% of the time (12/19), a previously-invisible real gap. A new supplementary signal, `check_screen_surface_texture()` (`src/quality_checks.py`), closes that to 0/19 missed with zero new false rejections across 75 genuine samples, confirmed on this run:

```
day19_attack_testing_matrix.py: 5/5 attacks still correctly rejected (unchanged — quality gate alone
already blocks the current 5 raw single-image samples, so the new liveness-stage check was never
reached in this specific test)
```

**Not closed, disclosed plainly:**
- Calibrated on only 2 independent real screen-replay base captures. `docs/screen_replay_capture_checklist.md` specifies what real, independently-staged captures would need to validate this further — not executed, needs a human with a camera.
- The active-liveness blink-timing compounding attack (item #2) was directly confirmed exploitable given favorable tick timing — this new check reduces exposure at the passive-liveness gate, it does not close the active-challenge weakness itself.
- rPPG's effectiveness against a screen-replay-plus-motion attack remains unmeasured — none of Phase 3's 10 live attack attempts survived long enough to reach it.
- The broader Evaluation_Report.md APCER/BPCER methodology (the score-threshold approach) has not been reconciled against the real `is_real` signal beyond the screen-replay category — flagged as a follow-up, not attempted.

**Update (2026-08-08, Phase 5 Part A — real capture session run, and it found a real problem, not a confirmation):** a live capture session with the project owner produced 13 new real images (9 genuine live photos, 4 real screen-replay attacks — phone and tablet). Full detail in `docs/screen_replay_capture_checklist.md`. Two things came out of it:

- **The full pipeline still rejected all 13 samples — but not via the mechanism being tested.** Every sample was caught by the pre-existing composite quality score (poor lighting/focus), before ever reaching `check_screen_surface_texture()`. So this batch, as captured, could not actually test the new check's role in a live decision.
- **Tested in isolation (bypassing the quality gate that masked it), the check does not generalize to this new sample:** it correctly flagged 0 of 4 real attacks (all scored 1.03–1.50, above the 0.90 threshold meant to catch them) and incorrectly flagged 3 of 9 genuine photos as screen-like (0.51–0.68, below threshold). In isolation, on this new sample, it performed worse than chance at telling screen from genuine.
- **Leading hypothesis, not confirmed:** the metric may be picking up "well-lit and in-focus" vs. "dark or blurry" more than "screen" vs. "genuine" — the capture session's photos were mostly dark/blurry rather than a clean, controlled set, and the original 2-sample calibration was never tested against that variation.
- **Explicitly not done as a quick fix:** retuning `TEXTURE_UNIFORMITY_MIN` against these 13 uncontrolled samples, which would just overfit to this specific batch. A cleaner, well-lit, in-focus capture set (the original breadth-first plan in `docs/screen_replay_capture_checklist.md`) is what's actually needed to tell brightness/focus and screen-vs-genuine apart as separate variables — not yet done.

**Net effect on this item's status:** the 0% missed / 0 new false rejections number reported above was measured against the original 2-photo calibration set, not against independent new data — and the first independent real test found the check does not currently generalize. This item moves from "substantially mitigated" to "partially mitigated": the underlying screen-replay decision is still caught by the quality gate in every sample tested so far, but the specific new signal built to close this gap has not yet been shown to work on data it wasn't calibrated on. Parts B–D of Phase 5 (timing feedback, WebRTC reproduction, demo video) are separate and unaffected by this finding.

**Update (2026-08-13):** the specific gap this item's original testing could never close -- whether a real, physically-presented replay attack (not a static uncontrolled photo batch) is caught live, end to end, during an actual Verify Identity attempt -- was tested live this pass with `DEBUG_CHALLENGE=1` active, real-time log capture, not a screenshot after the fact. Two different real attack presentations: a video of the project owner's face played on a second screen and held up to the camera, and a printed/on-screen photo held in hand and moved continuously. Both were caught, every time attempted (2/2 and 3/3 sub-attempts respectively), rejected with `"We couldn't confirm a live camera feed..."`. The real signal driving every rejection was `check_passive_liveness()`'s majority-vote sampling, flagging the clear majority of samples in each attempt (as low as 3/5, as high as 11/11) -- `check_frame_loop_signature()` (the frame-repetition heuristic) recorded 0 matches in every single attempt, real, live confirmation that a moving/varied real attack defeats it as designed, and the trained anti-spoof model is what's actually carrying this defense, not the cheaper heuristic beside it. A genuine live face passed cleanly in the same session immediately afterward (0/6 flagged samples), confirming a flagged attack attempt doesn't lock out the real user. The 60-second worst-case timeout (`MAX_CHALLENGE_ROUNDS=3` x `ACTIVE_CHALLENGE_TIMEOUT_S=20s`) was also confirmed live, matching its designed bound exactly.

---

## 2. Active-liveness blink-replay bypass — Disclosed-open-by-design

**No change in mitigation status** — this was already disclosed as a known limitation the system doesn't rely on any single layer to catch, and that remains the design. What's new: **direct, controlled confirmation**, not just theoretical concern. Phase 3 fed a synthetic closed-eyelid sequence through `evaluate_blink_tick()` with a favorable (2 consecutive closed-frame ticks + 1 recovery tick) timing pattern:

```
open   status=pending
open   status=pending
closed status=pending
closed status=pending
closed status=pending
open   status=pass      <-- registers a pass
```

This strengthens rather than changes the disclosure: a replayed/spliced blink **can** pass the active challenge under the right timing, confirmed with real code output, not asserted. No fix planned within this delivery — this is exactly why the pipeline layers passive liveness, active liveness, rPPG, and (now) the screen-surface check rather than trusting any one of them alone.

---

## 3. Per-tick response time — Closed (characterized; constants left unchanged with margin shown)

Phase 1 produced real numbers from two live 65s/100s Playwright soaks (n=91 ticks): **median 659.5ms, mean 980.3ms, p95 2643ms, max 14366ms**. The single large outlier was explained, not just reported — it lands immediately after a fresh-session marker and matches `run_app.py`'s own documented ~10-15s one-time model-warmup cost, not the WebRTC hiccup (which is a different order of magnitude, 20-32s).

Timeout constants checked against these real numbers:

| Constant | Value | Ticks @ median | Ticks @ p95 |
|---|---|---|---|
| `ACTIVE_CHALLENGE_TIMEOUT_S` | 20.0s | ~30 | ~7.6 |
| `RPPG_MIN_WINDOW_S` | 5.0s | ~7.6 | ~1.9 (wall-clock gate, still fires correctly) |
| `RPPG_TIMEOUT_S` | 20.0s | ~30 | ~7.6 |

Worst case (5 consecutive in-zone ticks for a head-turn at p95 rate) needs ~13.2s, leaving ~6.8s margin inside the 20s budget — tight but not broken. **No constant changed** — the real numbers didn't show a genuine problem, and per this project's own discipline, nothing was tuned just because the phase budgeted time for it.

---

## 4. Stability pass — Closed (the crash) / Still-open (live-feedback timing)

**Closed**: the `StreamlitAPIException` crash from commit `0139ddb` (`st.rerun(scope="fragment")` raised during a full-script rerun) is now behind a named, testable helper (`_safe_polling_rerun()`) with a dedicated regression test:

```
tests/test_polling_rerun_fallback.py::test_safe_polling_rerun_falls_back_on_streamlit_api_exception PASSED
```

Confirmed present and passing in this run's full pytest suite (14/14).

**Still-open**: "real-world timing tuning against live user feedback" — how long to wait for a challenge or pulse signal before giving up — genuinely needs a human doing live verification/enrollment passes and reporting what felt slow. No script can close this out; not attempted here, consistent with every phase's flag on this item.

---

## 5. Fairness/bias gaps — Disclosed-open-by-design, now root-caused

**Numbers re-measured and current** (Phase 0 found they'd drifted from the 2026-08-04 baseline; that update was deferred to this phase and is now done): Quality pass rate Female 32.5% (13/40) vs. Male 55.0% (22/40); skin tone Dark 38.5% (10/26) vs. Light 50.0% (14/28); passive liveness Senior 25.0% (6/24) vs. Middle-aged 46.2% (12/26) — unchanged from Phase 0's figures, reconfirmed on this run.

**New this phase — root cause, not just the aggregate**: extended `day36_38_bias_testing.py` to break down `compute_quality_score()`'s 7 sub-scores by subgroup.
- **Skin-tone gap → brightness is the dominant driver** (weighted contribution ~40% of the total score gap). Real mean grayscale intensity: Dark 110.4 vs. Light 120.1 vs. Medium 124.8 — Dark sits closest to the `BRIGHTNESS_MIN=100` floor, consistent with cameras under-exposing darker skin.
- **Gender gap → a completely different driver, blur/sharpness** (weighted contribution ~90% of that gap). Brightness actually runs the opposite direction for gender (slightly favors Female) — proof the two gaps are not the same phenomenon.
- **Age gap lives in passive liveness, not quality** — Senior's quality pass rate (45.8%) is nearly identical to Middle-aged's (46.2%); this breakdown has no explanatory power there by construction.

**Status unchanged by design**: full rebalancing/retraining remains explicitly out of scope per the original 2026-08-04 decision. This phase adds *why*, not a fix.

> **CORRECTION (2026-08-13):** every number in this section, and the "root cause" breakdown below it, was computed against demographic labels that were never real -- `day36_38_bias_testing.py` auto-generates them from array-index arithmetic as a placeholder when no annotation file exists, and the file was never actually hand-corrected (confirmed via git history: written once, never touched again). Re-annotated all 40 identities for real and fixed a second bug in the same script (liveness pass/fail was computed via `antispoof_score >= 0.90`, not the real `is_real` decision, the same class of error Section 1 above already found and fixed for the screen-replay evaluation). The real, corrected numbers are a genuinely different picture, not a smaller version of this one -- notably, the gender gap **reverses direction** (Male, not Female, is the lower-scoring group on both quality and liveness) and the skin-tone finding shifts (Medium, not Dark, has the lowest liveness pass rate). Full corrected table and analysis in `data/Evaluation_Report.md`, Section 6 item 3's correction. The brightness/camera-under-exposure root cause for the skin-tone quality gap is the one piece of the original analysis that held up under real labels.

> **MITIGATION (2026-08-13):** the brightness root cause above now has a real fix, not just a diagnosis. `check_brightness()`'s "too dark" gate switched from whole-image mean intensity to the 90th-percentile intensity (a face's brightest highlights, present under adequate light regardless of skin tone) -- confirmed via a real sweep that the old mean-based threshold could not be tuned to help without equally helping a genuinely underexposed negative control. Re-measured end to end against all 40 real photos: Dark's brightness sub-score rose from 60.0 to 82.9, the Light-vs-Dark brightness gap shrank 34% (20.4 -> 13.5 points), and overall composite quality pass rate rose 82.5% -> 87.5% with no subgroup scoring worse. Dark's own overall pass rate stayed exactly 75.0% (9/12) -- other, untouched sub-checks (blur, contrast, resolution) still held those same photos back, so this closes the specific brightness cause, not the whole gap. The gender/contrast gap was investigated the same way and found to have no equally clear physical cause and too small a sample (n=20 Female) to fix responsibly without overfitting to this one dataset -- left disclosed, not force-fitted. Full detail in `data/Evaluation_Report.md`, Section 6 item 3.

---

## 6. WebRTC hiccup — Closed (app-side bug) / Still-open (mitigation effectiveness)

**Closed**: Phase 2 found and fixed a real, separate bug — once `ctx.state.playing` went `False`, nothing in the app caused it to check again on its own, confirmed empirically via three live soaks where logging simply stopped dead and never resumed. Fixed with a slower (0.8s) keep-alive reschedule branch; measured CPU cost ~0.05 CPU-sec/5s idle vs. ~2.8 CPU-sec/5s active polling (~60x lower, not "noticeably more" per the phase's own requirement). This fix is independent of whether the underlying `CONSENT_FAILURES` tuning does anything, and is confirmed present in this run's clean smoke pass (both flows render and behave normally, no regressions).

**Still-open**: the original `CONSENT_FAILURES=20` mitigation's real-world effectiveness against the documented 20-32s self-recovering hiccup remains unconfirmed. Phase 2's synthetic re-measurement attempts showed a *different* failure pattern (drops at 10-19s, never recovering within the observation window) that doesn't match the original phenomenon closely enough to count as validation either way — explicitly reported as inconclusive, not claimed as fixed. Needs a human on a real camera/browser, the same method that produced the original 2026-08-04 finding.

---

## 7. Demo video — Still-open (not recorded); prep complete

**Still not recorded** — needs a human on camera, cannot be done in this environment. What's ready:
- `docs/video_storyboard.md` rewritten this phase to match everything built across Phases 1-3: the live checklist UI (didn't exist when the storyboard was last updated), the active-liveness challenge now actually running in both flows (the old storyboard described a simple align-and-capture flow with no challenge step), the rPPG checklist row in Verify Identity, and the WebRTC reconnect messaging as a known, plan-around-it risk during recording.
- A concrete recording checklist (equipment, pre-recording steps, scene order matching the worksheet's original ACTION list, and what to do if a hiccup or challenge timeout happens mid-take) is included in the same document.

---

## 8. Final confirmation pass — Closed

This document is that pass. Everything above reflects a fresh run of the full verification suite against current code on 2026-08-08, not numbers carried forward from earlier phases without re-checking:

- **pytest**: 14/14 passed
- **`day19_attack_testing_matrix.py`**: 5/5 attacks correctly rejected, unchanged from every prior phase's run
- **`scratch/run_expanded_liveness_eval.py`**: reproduces bit-identically (fixed RNG seed) — APCER 46.05%, screen-replay-laptop 73.7% missed *by the score-threshold metric Phase 3 found isn't what the app uses* (see item #1 above for the corrected, real number)
- **`day36_38_bias_testing.py` (extended)**: reproduces Phase 0's re-measured aggregate numbers exactly, plus the new per-sub-score breakdown (item #5)
- **Live Playwright smoke pass, both flows**: checklist grid renders correctly (11 rows Verify Identity including rPPG, 10 rows Guided Enrollment excluding it), zero console errors, normal pass/in-progress/pending pattern on a genuine test face — no regression from any of the four phases' changes
