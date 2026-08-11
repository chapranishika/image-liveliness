# Client Demonstration Video Storyboard & Script

This document details the structured storyboard, visual layout, and verbal script for recording the **Client Demonstration Video** matching the current automated-capture user interface. **Updated 2026-08-08 (Phase 4)** to reflect everything built across Phases 1-3 of the post-delivery stability/security pass: the live "checks passing" checklist, the active-liveness challenge (blink/head-turn) now actually running in both flows, rPPG collection in Verify Identity, and the WebRTC reconnect messaging. The previous version (last updated during the Phase 8 UI redesign) described a simple "align → 1.5s countdown → capture" flow with no challenge step — that is no longer what the app does, and recording against the old script would show a screen that doesn't match the narration.

---

## Video Goals
1. Demonstrate the live multi-stage verification pipeline (Quality → Passive Liveness → Active Liveness challenge → rPPG → Matching) and the live checklist that shows each stage resolving in real time.
2. Show guided front-facing enrollment (automatic capture gated by pose, quality, and an active-liveness challenge).
3. Verify security and legal compliance (GDPR/BIPA consent validation, duplicate prevention, soft/hard deletions).
4. Highlight system diagnostics and health audit tools.

---

## Setup & Recording Specifications
* **Target Duration:** 3:00 to 4:00 minutes (longer than the prior 2:00-3:00 target — the active-liveness challenge and rPPG collection genuinely take real time now, see the per-scene timing notes below).
* **Recording Mode:** Screen recording (1080p, 30fps) with clear microphone audio.
* **Pre-Recording Prep:**
  1. Close CPU-heavy applications to ensure zero camera frame lag — per-tick timing is measurably affected by competing processes (Phase 1 finding).
  2. Launch both servers: `python run_app.py`. Wait for the "System successfully initialized!" message before opening the browser — this absorbs the ~10-15s one-time model-warmup cost so it doesn't happen live on camera.
  3. Ensure clean user data in the database (delete `data/face_verification.db` if starting fresh, or use the existing one and simply pick unused demo names).
  4. **Known risk, plan around it, don't edit around it as if it can't happen:** an intermittent WebRTC connection hiccup can occur mid-session (typically 30-90s into a connection per past investigation; timing not fully consistent — see `docs/scope_decision_worksheet.md`'s WebRTC finding). If the camera feed shows "Reconnecting... this can briefly take up to 30 seconds" mid-take, that is expected, self-recovering behavior, not a bug — either pause and wait for it to recover, or do one hard cut/retry of that scene. Keep individual continuous camera segments under ~60 seconds where practical to reduce how often a take gets caught mid-hiccup.
  5. Do a dry run of the active-liveness challenge before recording — it randomly asks for either a blink ("Please blink twice") or a head turn ("Please turn your head left/right"), so know both gestures and don't be caught off guard by which one appears on the actual take.

---

## Scene Breakdown & Script

### Scene 1: Dashboard Overview (0:00 – 0:25)
* **Visual on Screen:**
  * Show the Streamlit interface defaulting to the **Verify Identity** view.
  * Point out the clean split-pane design: live camera feed with a pixel-burned head-alignment guide on the left, and actions/status on the right.
  * Show the view toggle switch between "Verify Identity" and "Guided Enrollment".
* **Verbal Script:**
  > *"Hello, this is a demonstration of the Secure Face Registration and Verification Framework, branded as 'Nishika'. We are looking at the Streamlit user interface, running alongside a FastAPI secure backend.*
  >
  > *The dashboard uses a clean, single-page split layout. The live webcam feed on the left features a pixel-burned head alignment guide. On the right, we have the active actions console and outcomes dashboard."*

---

### Scene 2: The Live Checklist (0:25 – 0:45) — NEW scene, didn't exist in the prior storyboard
* **Visual on Screen:**
  * Stay on **Verify Identity**, camera not yet aligned. Point out the compact checklist below the camera feed — rows like "One face detected," "Head angle," "Brightness," "Sharpness," "Contrast," "Distance / framing," "Face not covered," "Resolution," "Blink / head-turn," "Heartbeat pattern (Verify only)," "Skin-texture / anti-spoof scan."
  * Slowly align your face. Narrate what's happening as dots flip from gray/pending to green/pass in real time.
* **Verbal Script:**
  > *"Before we verify, notice this live checklist — every check the pipeline runs is shown here, ticking green the moment it passes, so there's no black box about what the system is actually evaluating. Right now, as I align my face, you can see the quality checks — brightness, sharpness, framing — resolve first."*

---

### Scene 3: Guided Enrollment — Quality Hold, Then a Real Challenge (0:45 – 1:45)
* **Visual on Screen:**
  * Toggle view to **Guided Enrollment**.
  * Type a new user name (e.g., `Alice`).
  * Check the **Legal Consent Checkbox** ("I agree to store my encrypted facial signature...").
  * Align face inside the outline: the guide turns green, shows a circular progress countdown (~1.5s).
  * **New step, not in the prior recording**: after the quality hold, the instructions text changes to a specific request — either "Please blink twice" or "Please turn your head left" / "right" (chosen at random each attempt). Actually perform the requested gesture. The checklist's "Blink / head-turn" row flips from pending to in-progress to pass.
  * Only after the gesture is confirmed does the system play the success beep and capture. The captured front photo appears at the bottom.
  * Click **Register Face ID** to complete enrollment.
* **Verbal Script:**
  > *"Let's register a new user named Alice. Compliance guidelines like GDPR and BIPA require explicit user consent before storing biometrics — the backend blocks templates if consent is missing.*
  >
  > *Once consent is checked and I'm aligned, the system doesn't just capture immediately — it asks for a live gesture, in this case a blink, to confirm this is an active, present person and not a static photo held up to the camera. Only once that's confirmed does it capture a single front-facing template. Registration is deliberately single-angle: duplicate-check and live verification are both calibrated on frontal-vs-frontal matching, which is far stronger than cross-angle matching, so a left/right capture step wasn't adding verification accuracy — see `docs/scope_decision_worksheet.md` for the full rationale. The database now securely encrypts and registers Alice's template."*
* **Timing note:** this scene now genuinely takes longer than the old ~15s "align and capture" — budget for the ~1.5s quality hold plus however long the gesture takes to perform and register, realistically several seconds. Don't rush the take; a real gesture takes real time and that's the honest demonstration.

---

### Scene 4: Duplicate Prevention Gating (1:45 – 2:05)
* **Visual on Screen:**
  * Try to enroll a different user name (e.g., `Charlie`) using the exact same face — same quality hold, same gesture step.
  * Click Register.
  * Show the error message: `🔴 Registration Failed: Duplicate biometric profile detected!`
* **Verbal Script:**
  > *"To prevent credential duplication and fraud, the backend runs a 1-to-N matching check on registration. If I attempt to register another identity under the name Charlie with the same face, the similarity score flags the collision and the registration is blocked."*

---

### Scene 5: Real-Time Automatic Verification — Quality, Liveness, and rPPG (2:05 – 3:00)
* **Visual on Screen:**
  * Switch view to **Verify Identity**.
  * Align your face with the guide. Same quality hold, same active-liveness gesture prompt as enrollment.
  * **New in this scene**: point out the "Heartbeat pattern (Verify only)" checklist row — this only appears in Verify Identity, not Guided Enrollment. While the gesture challenge is happening, this row is silently collecting a physiological pulse signal from subtle skin-color variation in the video feed, running concurrently rather than as an extra wait.
  * Once the gesture and pulse checks resolve, the countdown completes, captures automatically, and presents the animated success card with Alice's name and similarity score.
* **Verbal Script:**
  > *"Now, let's verify. Navigating back to 'Verify Identity', I align my face and perform the requested gesture, same as enrollment. But watch the checklist here — there's an extra row: a heartbeat-pattern check. While I'm doing the gesture, the system is also quietly analyzing subtle color changes in my skin caused by blood flow, a real physiological signal a printed photo or a screen replay simply doesn't have. Once every check resolves, the pipeline runs the final quality, liveness, and template-matching comparison against all registered templates at our calibrated threshold, successfully verifying me as Alice."*

---

### Scene 6: Compliance Audit & Diagnostics (3:00 – 3:45)
* **Visual on Screen:**
  * Open the bottom expander: **System Management & Audits**, then check
    "📊 Load compliance data & diagnostics" — this panel's queries and
    health checks only run once explicitly loaded, not in the background.
  * Show the user table, access logs, and verification logs.
  * Soft-delete Alice. Show that subsequent verifications fail.
  * Scroll down and click **Run System Diagnostics & Health Checks**. Green checkmarks appear verifying database, encryption keys, and hardware.
* **Verbal Script:**
  > *"Lastly, under compliance rules, we support BIPA's 'Right to be Forgotten'. Inside our compliance console, administrators can soft-delete or hard-delete profiles, immediately removing them from matching query pools. We also have full access logs for security audits.*
  >
  > *Finally, we can click 'Run Diagnostics' to test backend database, encryption key integrity, and camera availability. This completes the walk-through of the secure face framework."*

---

## Recording Checklist (follow directly)

**Equipment**
- [ ] A working webcam already granted browser camera permission (test this before hitting record — a fresh permission prompt mid-take looks bad and wastes a take)
- [ ] Quiet room, external microphone if available (built-in laptop mics pick up fan/keyboard noise)
- [ ] Consistent, front-facing lighting — avoid strong backlight from a window behind you (this directly affects the brightness quality sub-score, per Phase 4's fairness investigation into exactly this measurement)
- [ ] Screen recording software configured for 1080p/30fps before opening the app

**Before hitting record**
- [ ] Close other camera-using apps and CPU-heavy background processes
- [ ] Launch `python run_app.py`, wait for "System successfully initialized!"
- [ ] Open the app in browser, grant camera permission once, confirm the feed is live
- [ ] Do one silent dry run of the full Verify Identity flow (quality hold → gesture → capture) so you know what to expect and aren't surprised on camera
- [ ] Decide/confirm the demo user name(s) you'll register (avoid names already in the DB unless intentionally demonstrating a duplicate)

**Recording order (matches `docs/scope_decision_worksheet.md` Section 3's original ACTION list)**
1. [ ] Dashboard overview + live checklist introduction (Scenes 1-2)
2. [ ] Guided Enrollment: consent → quality hold → gesture challenge → capture → register (Scene 3)
3. [ ] Duplicate-prevention rejection (Scene 4)
4. [ ] Verify Identity: 1-to-N matching, including the rPPG checklist row (Scene 5)
5. [ ] Compliance/health panels: user table, soft/hard delete, diagnostics (Scene 6)

**If something goes wrong mid-take**
- [ ] "Reconnecting..." message appears → pause, wait up to ~30s, or cut and retry that segment. Not a bug, don't stop the whole recording session over it.
- [ ] Active-liveness challenge times out (~20s) → the app shows a friendly retry prompt; just try the gesture again, keep rolling or cut cleanly at that point.
- [ ] Wrong gesture requested for your planned narration → it's randomized each attempt; either adapt the script live ("today it's asking for a head turn instead of a blink") or retry the take until it matches what you rehearsed.

**After recording**
- [ ] Review the full take for audio sync and screen legibility (checklist text is small — consider a zoomed capture region or callout)
- [ ] Trim to the 3:00-4:00 target duration
