# Client Demonstration Video Storyboard & Script

This document details the structured storyboard, visual layout, and verbal script for recording the **Client Demonstration Video** required by the project brief.

---

## Video Goals
1. Demonstrate the live multi-stage verification pipeline (Quality check, Passive Liveness check, Matching).
2. Show guided multi-angle enrollment (Front, Left, and Right pose gating).
3. Verify security and legal compliance (GDPR/BIPA consent validation, duplicate prevention, soft-deletions).
4. Highlight system health diagnostics.

---

## 🎬 Setup & Recording Specifications
* **Target Duration:** 2:30 to 3:30 minutes.
* **Recording Mode:** Screen recording (1080p, 30fps) with clear microphone audio.
* **Pre-Recording Prep:**
  1. Close any CPU-heavy background apps to prevent camera frame lag.
  2. Launch both apps with the unified launcher: `python run_app.py`.
  3. Ensure your webcam is connected and the lighting is clear (no heavy shadows or bright backlights).
  4. Ensure you have clean user data in the database (or start with a fresh SQLite file by deleting `data/face_verification.db` if you want a clean walkthrough).

---

## 📽️ Scene Breakdown & Script

### Scene 1: Dashboard Overview & Health Audit (0:00 – 0:30)
* **Visual on Screen:** 
  * Show the running Streamlit interface on the **Enrollment** tab.
  * Point out the sidebar with quality presets ("Lenient", "Balanced", "Strict").
  * Show the sidebar's **System Health Status** panel displaying green checkmarks:
    * `Database Connected`
    * `MediaPipe Active`
    * `Camera Streaming`
* **Verbal Script:**
  > *"Hello, this is a demonstration of the Secure Face Registration and Verification Framework. We are currently looking at the Streamlit user interface, running concurrently with our FastAPI secure backend.*
  >
  > *In the sidebar, we can customize our quality validation profiles—ranging from Lenient to Strict—and monitor real-time system health checks verifying database connectivity, liveness models, and camera streams."*

---

### Scene 2: Guided Multi-Angle Enrollment (0:30 – 1:30)
* **Visual on Screen:**
  * Type a new user name (e.g., `Alice`).
  * Check the **Legal Consent Checkbox** ("I consent to biometric collection and storage...").
  * Click **Start Multi-Angle Capture**.
  * Stand front-facing: show the webcam live-feed updating with green bounding boxes and capturing the **Front** template.
  * Turn your head to the Left: show the pose detector tracking your yaw angle, capturing the **Left** template.
  * Turn your head to the Right: show the system capturing the **Right** template.
  * Show the success message: `"User registered successfully with 3 templates!"`
* **Verbal Script:**
  > *"Let's register a new user named Alice. Under compliance guidelines like BIPA and GDPR, we cannot register a user without explicit consent. If we attempt to enroll without checking the consent box, the FastAPI backend will block the transaction.*
  >
  > *Once consent is given, we start our guided multi-angle enrollment. The system uses MediaPipe to capture three independent templates: Front, Left, and Right. Notice how the capture gates do not trigger until I rotate my head to the correct yaw angles, securing a robust 3D representation of the face."*

---

### Scene 3: Duplicate Prevention Gating (1:30 – 2:00)
* **Visual on Screen:**
  * Try to enroll a different user name (e.g., `Charlie`) using the exact same face.
  * Complete the front capture.
  * Show the error message: `🔴 Registration Failed: Duplicate biometric profile detected!`
* **Verbal Script:**
  > *"To prevent identity spoofing and duplicate fraud, the registration backend performs a 1-to-N comparison of the captured frontal template against all registered active profiles.*
  >
  > *If I attempt to register another identity under the name Charlie with the same face, the backend flags the cosine similarity match and immediately rejects the registration to maintain database integrity."*

---

### Scene 4: Real-Time Verification & Liveness (2:00 – 2:45)
* **Visual on Screen:**
  * Navigate to the **Verification** tab.
  * Click **Verify Face**.
  * Show the pipeline diagnostics completing step-by-step:
    * `Quality Score: PASS (Balanced Preset)`
    * `Passive Liveness Score: PASS (is_real: True)`
    * `1-to-N Matching: MATCH (Matched: Alice, Similarity: 0.94)`
  * (Optional) Try showing a photo of yourself on a phone screen to the camera to demonstrate a **Spoof Rejection**.
* **Verbal Script:**
  > *"Now let's verify. When I click 'Verify Face', the system runs a three-stage validation pipeline.*
  >
  > *First, it computes the composite quality score, validating brightness, blur, and head alignment. Second, it runs a passive liveness check using MiniFASNet to detect spoofing. Lastly, if liveness passes, the frontal embedding is extracted and compared against the stored multi-angle templates. The system chooses the best-scoring angle, matching me successfully with Alice at a similarity of 94%."*

---

### Scene 5: Deletion Compliance & Closeout (2:45 – 3:30)
* **Visual on Screen:**
  * Go to the **Management** tab.
  * Show the list of registered users.
  * Click **Delete User (Soft)** for Alice.
  * Navigate back to the Verification tab and try to verify. Show that the match fails or says "No match found," proving soft-deleted users are immediately excluded from verification pools.
  * Close out the presentation.
* **Verbal Script:**
  > *"Finally, compliance requires a clear right-to-deletion audit. In our Management tab, we can soft-delete Alice. This immediately flags the database record as deleted, purging the template from duplicate checking pools and match queries.*
  >
  > *This completes the overview of our biometric security framework. It combines unified quality metrics, passive liveness, secure encryption-at-rest, and absolute legal compliance. Thank you!"*
