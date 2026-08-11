# Phase 0 Baseline — Honest, Evidence-Backed Status of "What's Still Open"

**Date:** 2026-08-08
**Purpose:** Get current, reproduced numbers for every item in the report's "What Is Still Open or Needs More Work" list before Phase 1 touches any code. No behavior changes were made in this phase (see 0.3 for the two doc-only edits). Later phases should diff against this file, not against prose summaries or old console output.

---

## 1. Screen-replay liveness gap

**Current measured status:** Real, reproduced on current code, unchanged from what's already disclosed in the report.

**Important correction to the Phase 0 brief's own premise:** `day19_attack_testing_matrix.py` is **not** the source of this finding. Re-running it (0.1) confirms it tests something different — it runs the 5 raw, un-augmented images in `data/self_collected/session_1/attacks/` through the *combined* quality+passive-liveness gate (`run_quality_and_liveness_stage`) and just checks whether each one gets rejected somewhere. On current code, **all 5/5 are now rejected — all at the `quality` stage**, not by passive liveness at all:

```
Frozen Frame Attack      frozen_001.jpg     caught_at=quality  reason=score 66.6 below balanced threshold 70
Multiple Face Attack     multiple_001.jpg   caught_at=quality  reason=single_face check failed: no face detected
Photograph Attack        printed_001.jpg    caught_at=quality  reason=score 48.5 below balanced threshold 70
Screen Replay Attack     screen_001.jpg     caught_at=quality  reason=score 51.0 below balanced threshold 70
Video Replay Attack      video_001.jpg      caught_at=quality  reason=score 36.8 below balanced threshold 70
```
(Full CSV: `data/day19_attack_matrix_results.csv`.) This is a coarse, n=1-per-category smoke test — useful for confirming the pipeline doesn't silently let a staged attack through end-to-end, but it says nothing about passive liveness specifically, since quality scoring caught everything first in this run.

**The actual source of the "73.7% screen-replay-laptop miss rate" finding is `scratch/run_expanded_liveness_eval.py`** (gitignored, not in the file list the Phase 0 brief named). This script takes the same 4 real base attack captures and expands each into ~19 photometric/geometric variants (crop jitter, rotation, brightness/contrast jitter, blur, JPEG re-compression) that preserve the base image's real optical signature (real paper grain, real screen moiré) rather than synthesizing a new one — disclosed explicitly in the script's own docstring and in `data/Evaluation_Report.md` Section 5.1 as "19 variants of 4 real staged captures, not 76 independently re-staged real-world attempts." This is what feeds the numbers in the report (`docs/Final_Report.md` Section 3.2, `data/Evaluation_Report.md` Section 5).

Re-ran it fresh against current `src/liveness_passive.py` (fixed RNG seed 1234 → bit-identical to the last saved run, confirming reproducibility on current code):

```
AT DEPLOYED THRESHOLD 0.9:
  APCER = 46.05% (35/76)
  BPCER = 0.00% (0/75)
  ACER  = 0.230

Per-attack-type breakdown at deployed threshold 0.90:
  printed_photo            1/19 missed (5.3%)
  screen_replay_laptop     14/19 missed (73.7%)
  screen_replay_phone      1/19 missed (5.3%)
  frozen_frame             19/19 missed (100.0%)
```
Full output: `scratch/expanded_liveness_eval_output_rerun.txt`. **Confirmed: the gap is real and reproduces exactly.**

**Evidence:** `scratch/run_expanded_liveness_eval.py`, `scratch/expanded_liveness_eval_output_rerun.txt`, `scratch/expanded_liveness_scores.json` (raw per-image scores), `data/Evaluation_Report.md` §5.1.

See section 0.2 audit below for the "larger, expanded sample" claim itself.

---

## 2. Active-liveness blink-replay bypass (disclosed limitation)

Restated as-is, per the Phase 0 brief — not re-tested this pass. The report already discloses this honestly: *"The active-liveness bypass described in Phase 3 (a replayed recording of a real blink can pass the blink challenge) is a known, disclosed limitation, not something planned to be fixed without a larger design change, since it is exactly why the system does not rely on that layer alone."* (`scratch/office/build_report.py`, `still_open` list.)

**Evidence it was actually tested at some point, not just asserted:** `scratch/build_recorded_gesture_attack.py` and `scratch/recorded_blink_attack.avi` exist on disk (gitignored, not re-run this phase per the brief's scope).

---

## 3. Per-tick response time

**Current measured status: partially blocked by this phase's own "no code changes" constraint — reported honestly rather than fabricated.**

`scratch/perf_loop_log.txt` is the old baseline (last modified 2026-08-06, 2279 lines, steady-state `iter_delta_ms` in the 650–1300ms range with some longer outliers). Per the brief, I re-ran `scratch/drive_polling_loop.py` against the current running app (fresh `run_app.py` launch, current code) to produce a new reading.

**Empirically confirmed (not assumed): this does not produce a fresh reading.** Line count before and after the 30s drive run was identical (2279 → 2279, zero new lines appended). Grepping `app/streamlit_app.py` confirms why: the code that used to write `iter_delta_ms=`/`script_exec_ms=` to that file no longer exists — only a comment referencing the old investigation remains (`app/streamlit_app.py:622`). That instrumentation was a temporary, one-time probe from an earlier debugging pass and was fully removed afterward (this session's established pattern for temporary debug instrumentation). Since this phase is explicitly scoped to **not** touch `app/streamlit_app.py` or any `src/` file, I cannot re-add that exact probe to regenerate a like-for-like number here.

**What I do have — a real, freshly-measured proxy number from earlier today, on current code (not fabricated, not from this phase's work):** while verifying the live-checklist feature's performance impact (a separate, already-completed task earlier in this session), I added a temporary tick-timing probe, drove a live Playwright session against the current app, and measured the interval between consecutive fragment-tick starts:

```
tick-to-tick interval (ms): n=26 mean=1254.8 median=469.5 max=12843.0
```
That probe has since been removed (same "temporary, fully reverted" pattern). This is not measuring the exact same instrumentation points as the old `iter_delta_ms` (which came from a since-deleted probe I can't inspect the source of to confirm identical semantics), so treat it as **directionally comparable, not a strict apples-to-apples re-measurement**: median ~470ms is in-line with or faster than the old baseline's 650-750ms "steady-state" figure, consistent with the redundant-MediaPipe-call fix already landed in commit `0139ddb` (~1.0s → ~0.65s per that commit's own message). The occasional multi-second outlier (max 12.8s) also appears in both old and new data and likely reflects WebRTC/model warm-up or GC pauses rather than steady-state cost.

**Recommendation for Phase 1:** if an exact like-for-like `iter_delta_ms`/`script_exec_ms` re-measurement is needed, re-adding a temporary, env-var-gated timing probe to `app/streamlit_app.py` (mirroring the removed one) should be an explicit, scoped Phase 1 task — not something done silently as a side effect of "just re-running the script."

**Evidence:** `scratch/perf_loop_log.txt` (old baseline, untouched, backed up as `scratch/perf_loop_log_OLD_baseline.txt`), `app/streamlit_app.py:622` (comment referencing the now-removed instrumentation), this session's checklist-perf verification (median 469.5ms tick interval, no corresponding file — was measured and removed within this conversation).

---

## 4. Stability pass

**The crash fix referenced in the report is real, identified, and already shipped — but has no regression test yet.**

`git log --oneline --all | grep -i -E "crash|stability|fix"` surfaces many `fix(...)` commits, but the specific one the report means (*"an early version crashed on a genuine failed verification (a Streamlit-internals interaction, now fixed and confirmed via live testing)"*) is commit **`0139ddb`** (`feat(liveness): wire active liveness (Layer 2) and rPPG (Layer 3) into the live app, attempt WebRTC hiccup mitigation`, 2026-08-07 19:52:14 +0530). Its own commit message documents the exact bug: *"Fixed a real crash found during live testing (`st.rerun(scope="fragment")` raising when called during a full-script rerun — a pre-existing latent bug in the fragment refactor, only triggered once a real face got past the new gates)."* The diff shows the actual fix — a try/except around `st.rerun(scope="fragment")` falling back to a plain `st.rerun()` on `StreamlitAPIException` (`app/streamlit_app.py`, "ACTIVE RERUN TRIGGER LOOP" block).

**Test coverage check:** `grep -rn "StreamlitAPIException\|scope=\"fragment\"\|fragment" tests/` returns nothing. **No regression test currently covers this crash path.** Per the brief, not adding one in this phase — flagged as a **Phase 1 task**.

**Also still open per the report, unverified this phase (real-world timing tuning):** *"real-world timing tuning (how long to wait for a challenge or a pulse signal before giving up) is still being adjusted against live user feedback rather than assumed correct from a first pass"* — this is a live-usage-feedback item, not something a script can confirm; no new evidence gathered this phase.

**Evidence:** `git show 0139ddb`, `tests/` (absence of coverage confirmed via grep).

---

## 5. Fairness/bias gaps

**Current measured status: reproduced, but the numbers have drifted from what's recorded in the worksheet — recording the new numbers, not silently keeping the old ones.**

Re-ran `day36_38_bias_testing.py` fresh (full output: `scratch/bias_testing_rerun_output.txt`). Comparison against `docs/scope_decision_worksheet.md` §3 ("Confirmed Demographic Bias"), which was last written 2026-08-04:

| Metric | Worksheet (2026-08-04) | Re-run today (2026-08-08) | Changed? |
|---|---|---|---|
| Quality pass rate, Female | 20.0% (8/40) | **32.5% (13/40)** | **Yes — drifted** |
| Quality pass rate, Male | 42.5% (17/40) | **55.0% (22/40)** | **Yes — drifted** |
| Quality pass rate, Dark skin tone | 26.9% | **38.5% (10/26)** | **Yes — drifted** |
| Quality pass rate, Light skin tone | 35.7% | **50.0% (14/28)** | **Yes — drifted** |
| Passive liveness pass rate, Senior | 25.0% (6/24) | **25.0% (6/24)** | No — identical |
| Passive liveness pass rate, Middle-aged | 46.2% (12/26) | **46.2% (12/26)** | No — identical |

**Every quality-pass-rate number moved (all upward); every passive-liveness-pass-rate number the worksheet recorded stayed bit-identical.** This is consistent with (not confirmed as caused by — no further investigation done this phase) quality-scoring code having changed since 2026-08-04 (commit `f1b7007`, "Phase 4: Stabilize aspect ratios...", touched `src/quality_checks.py`, `src/quality_checks_day8_9.py`, `src/quality_score.py`) while passive-liveness scoring (`src/liveness_passive.py`) did not change in that window.

**The direction of the bias itself is unchanged**: Male still passes quality checks meaningfully more often than Female (55.0% vs 32.5%, a 22.5-point gap now vs. 22.5-point gap before — same gap size, both numbers just shifted up together); Light skin tone still passes more than Dark (50.0% vs 38.5%, an 11.5-point gap, similar to before); Senior passive-liveness pass rate is still roughly half Middle-aged's. **Status is still UNMITIGATED** — no rebalancing or threshold adjustment has been attempted, matching the worksheet's existing conclusion.

**Action for Phase 1+:** update `docs/scope_decision_worksheet.md` §3's quality-pass-rate numbers to the current figures (not done in this phase — 0.3 only touched the two items explicitly named in the brief; this table drift is a new finding surfaced by 0.1b, not one of the two pre-identified stale-doc issues).

**Evidence:** `scratch/bias_testing_rerun_output.txt`, `docs/scope_decision_worksheet.md` §3 (current, unedited numbers).

---

## 6. WebRTC hiccup

**Current measured status: root cause and mitigation both already documented and applied; not re-measured this phase (would require driving a long live session, out of scope for a doc-only phase).**

`docs/scope_decision_worksheet.md` §3 documented the root-cause finding on 2026-08-04 (reproduced 3x, 20-32s `ctx.state.playing` drops matching aioice's consent-check cadence). A mitigation was applied **afterward**, in commit `0139ddb` (2026-08-07 19:52:14 +0530) — `_aioice_ice.CONSENT_FAILURES = 20` (was 6) at `app/streamlit_app.py` ~line 40. Since the code change post-dates the worksheet entry, the worksheet was stale on this point; fixed in 0.3 below by adding an update note rather than rewriting the original finding.

The current report (`scratch/office/build_report.py`'s `still_open` list) already describes this exact same mitigation ("a targeted tolerance increase applied as a testable mitigation — not a confirmed fix") — confirmed this is one finding with one mitigation, not two different descriptions that need reconciling.

**Not done this phase:** re-measuring hiccup frequency/duration with the mitigation in place (the original finding's own verification method — a long Playwright session with a frame-arrival heartbeat). That's a real before/after measurement Phase 2 should do if this item is in scope there.

**Evidence:** `docs/scope_decision_worksheet.md` §3 (as updated in 0.3), `app/streamlit_app.py:23-42`, `git log -1 --format=%ai 0139ddb`.

---

## 7. Demo video

**Still not recorded.** Confirmed via filesystem search (`docs/`, project root) — no `.mp4`/`.mov`/`.avi` or anything demo-video-named exists anywhere in the repo. `docs/video_storyboard.md` (the script/plan for it) exists and was already updated to match the current UI, but no recording has been made. No further investigation needed per the brief.

---

## 8. Final confirmation pass

**Not started.** The report's own `still_open` list states this plainly: *"One final confirmation pass, re-checking the most recent fixes together as one whole system, is still pending before this should be considered fully demo-ready."* Nothing to add — this is a Phase-1-or-later task, not an audit item.

---

## Files touched this phase (per the brief's stated scope)

- `docs/scope_decision_worksheet.md` — two edits (0.3): rPPG row DEFER→KEEP, WebRTC finding update note. Diffs below.
- `docs/phase0_baseline.md` — this file, new.
- `data/day19_attack_matrix_results.csv` — regenerated by re-running `day19_attack_testing_matrix.py` (the script's own normal output path, not a manual edit).
- `scratch/expanded_liveness_eval_output_rerun.txt`, `scratch/bias_testing_rerun_output.txt`, `scratch/perf_loop_log_OLD_baseline.txt` (backup copy) — new scratch output from re-running existing scripts, per 0.1/0.4.
- No changes to `app/streamlit_app.py` or any `src/` file.
