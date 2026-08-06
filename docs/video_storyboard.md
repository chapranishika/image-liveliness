# Client Demonstration Video Storyboard & Script

This document details the structured storyboard, visual layout, and verbal script for recording the **Client Demonstration Video** matching the current automated-capture user interface.

---

## Video Goals
1. Demonstrate the live multi-stage verification pipeline (Quality check, Passive Liveness check, Matching).
2. Show guided multi-angle enrollment (automatic capture gated by Front, Left, and Right poses).
3. Verify security and legal compliance (GDPR/BIPA consent validation, duplicate prevention, soft/hard deletions).
4. Highlight system diagnostics and health audit tools.

---

## 🎬 Setup & Recording Specifications
* **Target Duration:** 2:30 to 3:30 minutes.
* **Recording Mode:** Screen recording (1080p, 30fps) with clear microphone audio.
* **Pre-Recording Prep:**
  1. Close CPU-heavy applications to ensure zero camera frame lag.
  2. Launch both servers: `python run_app.py`.
  3. Ensure clean user data in the database (delete `data/face_verification.db` if starting fresh).

---

## 📽️ Scene Breakdown & Script

### Scene 1: Dashboard Overview (0:00 – 0:30)
* **Visual on Screen:** 
  * Show the Streamlit interface defaulting to the **Verify Identity** view.
  * Point out the clean split-pane design: live camera feed with a pixel-burned head-alignment guide on the left, and actions/status on the right.
  * Show the view toggle switch between "Verify Identity" and "Guided Enrollment".
* **Verbal Script:**
  > *"Hello, this is a demonstration of the Secure Face Registration and Verification Framework, branded as 'Nishika'. We are looking at the Streamlit user interface, running alongside a FastAPI secure backend.*
  >
  > *The dashboard uses a clean, single-page split layout. The live webcam feed on the left features a pixel-burned head alignment guide, which eliminates external browser CSS positioning bugs. On the right, we have the active actions console and outcomes dashboard."*

---

### Scene 2: Automatic Multi-Angle Enrollment (0:30 – 1:30)
* **Visual on Screen:**
  * Toggle view to **Guided Enrollment**.
  * Type a new user name (e.g., `Alice`).
  * Check the **Legal Consent Checkbox** ("I agree to store my encrypted facial signature...").
  * Show the progress tracker at Step 1 of 3: Look directly at the camera.
  * Align face: the guide turns green, shows a circular progress countdown (1.5s), plays a success beep, and advances to Step 2.
  * Turn head Left: an arrow cue appears on the video frame, captures automatically, and advances to Step 3.
  * Turn head Right: an arrow cue appears, captures automatically, and displays all three registered photo templates at the bottom.
  * Click **Register Face ID** to complete enrollment.
* **Verbal Script:**
  > *"Let's register a new user named Alice. Compliance guidelines like GDPR and BIPA require explicit user consent before storing biometrics. The backend blocks templates if consent is missing.*
  >
  > *Once consent is checked, enrollment proceeds completely hands-free using automatic capture. The system gates capture by head pose. When I look front, it starts a 1.5-second countdown, play a soft beep, and captures. As I turn left and then right, arrow guides appear directly on the video pixels, and the camera captures when the target angle is matched. The database now securely encrypts and registers Alice's templates."*

---

### Scene 3: Duplicate Prevention Gating (1:30 – 2:00)
* **Visual on Screen:**
  * Try to enroll a different user name (e.g., `Charlie`) using the exact same face.
  * Let the front photo capture automatically.
  * Click Register.
  * Show the error message: `🔴 Registration Failed: Duplicate biometric profile detected!`
* **Verbal Script:**
  > *"To prevent credential duplication and fraud, the backend runs a 1-to-N matching check on registration. If I attempt to register another identity under the name Charlie with the same face, the similarity score flags the collision and the registration is blocked."*

---

### Scene 4: Real-Time Automatic Verification (2:00 – 2:40)
* **Visual on Screen:**
  * Switch view to **Verify Identity**.
  * Align your face with the guide.
  * The countdown completes, captures automatically, and presents a beautiful animated success card with Alice's name and similarity score.
* **Verbal Script:**
  > *"Now, let's verify. Navigating back to 'Verify Identity', I align my face. The automated capture loop detects proper positioning and starts the countdown. Once captured, the pipeline runs quality checks, liveness checks, and template matching. The backend compares the live embedding against all registered templates at our calibrated threshold of 0.50, successfully verifying me as Alice."*

---

### Scene 5: Compliance Audit & Diagnostics (2:40 – 3:30)
* **Visual on Screen:**
  * Open the bottom expander: **System Management & Audits**.
  * Show the user table, access logs, and verification logs.
  * Soft-delete Alice. Show that subsequent verifications fail.
  * Scroll down and click **Run System Diagnostics & Health Checks**. Green checkmarks appear verifying database, encryption keys, and hardware.
* **Verbal Script:**
  > *"Lastly, under compliance rules, we support BIPA's 'Right to be Forgotten'. Inside our compliance console, administrators can soft-delete or hard-delete profiles, immediately removing them from matching query pools. We also have full access logs for security audits.*
  >
  > *Finally, we can click 'Run Diagnostics' to test backend database, AES-128 encryption key integrity, and camera availability. Restricting these diagnostics to a manual button prevents webcam resource locks during capture loop runs. This completes the walk-through of the secure face framework!"*
