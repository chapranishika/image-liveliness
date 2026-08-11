# Screen-Replay Attack Capture Checklist

**Status: Part A of Phase 5 executed this against `check_screen_surface_texture()` (2026-08-08) — see "Real capture results" below. Short version: the check does not currently generalize to the new real samples, and this is disclosed plainly, not patched over.**

## Real capture results (Phase 5, Part A, 2026-08-08)

A live capture session with the project owner produced 13 new real images via `capture_screen_replay_samples.py`. **Narrower than originally planned**: the capture tool's device/lighting/distance labels were never actually cycled during the session (all files initially saved under one default label), and the images turned out to be a mix the owner hand-labeled afterward by looking at each photo, not the systematic breadth-then-depth sweep this checklist called for:

- **9 genuine samples**: real, live, direct webcam captures of the owner's own face (laptop camera, no screen involved) — varying lighting/focus quality, not a controlled set. 2 described as good lighting, 7 as dark/blurry/unfocused.
- **4 real attack samples**: a phone screen showing a photo (1), and a tablet showing a photo (3) — genuinely independent real screen-replay captures, the first this project has had beyond the original `screen_001.jpg`/`video_001.jpg`.

**No new lighting/distance/angle variation was captured for the laptop-screen category specifically, and no external monitor was tested.** This is real data, but it does not fulfill the original breadth (4+ device types × 3 lighting × 3 distance) this checklist asked for — treat the results below as a first real signal, not a full validation.

**Full pipeline result**: all 13 samples were rejected, but **entirely by the pre-existing composite quality score** (brightness/blur/pose/etc., all scored well under the balanced-profile threshold of 70 — even the "good lighting" genuine sample only reached 62.3) — none of the 13 samples ever reached the liveness stage where `check_screen_surface_texture()` would actually influence the decision. So this batch could not test the check's real role in the pipeline's decision at all.

**Isolated result (`check_screen_surface_texture()` computed directly, bypassing the quality gate that masked it)** — this is the real, disclosed problem:

| | Result |
|---|---|
| Real attacks (phone/tablet) correctly flagged as screen-like | **0/4 (0%)** — the check passed all 4, values 1.032-1.499, all *above* the 0.90 threshold |
| Genuine live photos incorrectly flagged as screen-like | **3/9 (33%)** — values 0.512-0.682, all *below* the 0.90 threshold |

**This is a real miss, not calibration noise, and it is not being silently patched.** In isolation, on this new sample, the check performed worse than a coin flip at telling screen from genuine. The likely cause (a hypothesis, not confirmed): the metric measures spatial uniformity of local sharpness, and this new sample is dominated by darkness/blur variation rather than screen-vs-genuine variation — a dark or out-of-focus photo suppresses local sharpness variance regardless of whether the subject is a real face or a screen, so the metric may be picking up "well-lit and sharp" vs. "dark or blurry" more than "screen" vs. "genuine." The original 2-base-capture calibration (Phase 3) never tested this because those samples were all reasonably well-lit and in focus.

**Not done, and should not be attempted as a quick fix**: retuning `TEXTURE_UNIFORMITY_MIN` against this specific sample. That would fit the threshold to 13 uncontrolled, mostly-dark/blurry photos, which is exactly the overfitting this project's own discipline has avoided elsewhere. What's actually needed: a cleaner, well-lit, in-focus capture set across genuine and screen-replay samples, so brightness/focus and screen-vs-genuine can be told apart as separate variables — the original breadth-first plan below, done properly, would likely surface this anyway.

**Effect on `docs/final_confirmation_report.md` item #1**: downgraded from "substantially mitigated" — see that file's Phase 5 update.

---

**Original status before this pass: not executed. Needs a human holding a real screen up to a real camera — cannot be done inside this environment.** Everything in `data/self_collected/session_1/attacks/` and everything this Phase 3 investigation built from it (`scratch/screen_replay_attacks/*.y4m`) derives from exactly **one** real screen-replay photograph (`screen_001.jpg`, a laptop) plus one real phone-screen photograph (`video_001.jpg`). Every other "variant" used in this project's evaluations is a photometric/geometric transform of those two base captures, not an independently re-staged real attempt. That's disclosed honestly in `data/Evaluation_Report.md` §5.1 and reconfirmed by this phase — it is not "a larger, expanded test sample" in the sense a client would assume from that phrase.

This checklist is what an actual capture session needs to produce genuinely independent real data. Running it is a follow-up, not a blocker for this phase's completion.

## What to capture

For each combination below, capture **both a still photo and a ~10s video** of the same displayed face (a still image and a talking-head clip both feel like realistic attacker choices):

| Variable | Values to cover |
|---|---|
| Display type | At minimum: 1 laptop screen (different from the one already used), 1 phone screen, 1 external/desktop monitor, 1 tablet if available |
| Lighting | Normal indoor room light, a dim room, and near a window with daylight glare on the screen |
| Distance from camera to the displayed screen | Close (screen fills most of frame), medium (typical webcam distance), far (screen is a smaller portion of frame) |
| Angle | Straight-on, and ~15-20° off-axis (tests whether glare/moiré changes with viewing angle) |
| Content displayed | A still photo of a face, and a video of a face (ideally one that blinks/talks naturally, not staged) |

That's a minimum of 4 displays × 3 lighting conditions × 3 distances × 2 angles × 2 content types = a lot of combinations if fully crossed. Don't try to cross all of them — prioritize:
1. **Breadth first**: one reasonable capture (medium distance, normal lighting, straight-on) across all 4+ display types and both content types — this alone would give ~8-10 genuinely independent real base captures, an order of magnitude more than the 2 this project currently has.
2. **Depth second, only for the display type already shown to be a problem** (laptop, per the corrected Phase 3 findings): vary lighting/distance/angle specifically for that display type, since that's where the sharpen/brighten-defeats-quality-gate + is_real-vs-antispoof_score discrepancy findings both point.

## How to capture (matching this project's existing convention)

- Same camera/setup the live app actually uses (the registered webcam), not a phone camera photographing a screen and then that photo being re-uploaded — the whole point is testing what the live WebRTC pipeline actually receives.
- Save stills as `.jpg` into a new `data/self_collected/session_2/attacks/` (or similar) folder, following the existing `screen_001.jpg`/`video_001.jpg` naming pattern (e.g., `screen_laptop2_001.jpg`, `screen_phone_dim_001.jpg`).
- Save videos as short clips (10-15s) in whatever format the camera produces; they can be converted to the project's Y4M fake-camera format later the same way `scratch/build_screen_replay_attack_videos.py` and `scratch/build_quality_scenarios.py` already do it.
- Label each capture with its variables (display/lighting/distance/angle) in the filename or an accompanying manifest, so results can be broken down the same way `data/Evaluation_Report.md` §5.1 already breaks down "Screen Replay (Phone)" vs "Screen Replay (Laptop)."

## What to do with the new captures once they exist

1. Re-run `check_passive_liveness()` and `check_screen_surface_texture()` (`src/quality_checks.py`) directly against the new stills, the same way this phase's exploration scripts did (`scratch/run_expanded_eval_with_screen_check.py` is a ready template — swap in the new base images).
2. Re-check whether `TEXTURE_UNIFORMITY_MIN = 0.90` (calibrated from only 2 real base captures) still cleanly separates genuine from screen-replay on the new, independent displays — this is the single most important thing to verify, since a threshold calibrated on one laptop and one phone has no evidence yet that it generalizes to a different monitor, a different room's lighting, or a different distance.
3. If the new data cleanly supports the same threshold, that's strong confirmation. If it doesn't (e.g. a different monitor's pixel grid produces a different texture-uniformity range), the threshold needs recalibrating against the combined real dataset — do not just widen it without new evidence, same discipline this project has followed throughout.
4. Feed the new videos through the live app the same way `scratch/drive_screen_replay_attacks.py` does, to get a fresh full-pipeline read (quality → passive liveness → screen-surface → active challenge → rPPG) on genuinely new attack material, not variants of the same two base photos.
