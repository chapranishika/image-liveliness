# Secure Face Registration and Verification Framework
## Final Project Report

**Project Codename:** Nishika
**Report Date:** August 6, 2026

---

## 1. Problem Statement

Think of this project as building the brain of a security guard for face-based login. The guard has two jobs. First, when someone signs up (registration), take a clear photo of their face and remember it. Second, when someone tries to log in later (verification), look at their face again and answer two questions: is this a real, live person in front of the camera right now, and does this face actually belong to the person who signed up.

A face-matching system alone can be fooled by a printed photo, a video, or a photo on a phone screen. The system therefore needs two additional capabilities beyond matching: **liveness detection** (is this a real, live person) and **image quality assessment** (is the captured photo even usable in the first place). The original brief splits this into two phases — registration and verification — which this project merges into one shared pipeline with two entry points, since both phases reuse the same quality, liveness, and matching logic.

---

## 2. Approach & Architecture

**Shared pipeline** (both registration and verification):
Capture (WebRTC webcam frame) → Face Detection (MediaPipe, rejects 0 or >1 face) → Quality Assessment (7-check weighted composite score) → Liveness Detection (Passive: MiniFASNet; Active: randomly-selected blink or head-turn challenge) → Face Embedding (ArcFace via DeepFace, pretrained).

**Figure 1 — Shared Core Pipeline**

```
  ┌─────────────────────────────────┐
  │  Capture Input                   │   (gray)
  │  Webcam frame or short video     │
  └────────────────┬──────────────────┘
                   │
  ┌────────────────▼──────────────────┐
  │  Face Detection                   │   (gray)
  │  MediaPipe, single-face check      │
  └────────────────┬──────────────────┘
                   │
  ┌────────────────▼──────────────────┐
  │  Quality Assessment                │   (teal)
  │  Blur, brightness, pose, position   │
  └────────────────┬──────────────────┘
                   │
  ┌────────────────▼──────────────────┐
  │  Liveness Detection                │   (teal)
  │  Passive + Active challenge         │
  └────────────────┬──────────────────┘
                   │
  ┌────────────────▼──────────────────┐
  │  Face Embedding                    │   (purple)
  │  ArcFace via DeepFace               │
  └────────┬───────────────────┬──────┘
           │                   │
  ┌────────▼────────┐   ┌──────▼─────────┐
  │  Register Path    │   │  Verify Path    │   (orange / pink)
  │  Duplicate check   │   │  Match against  │
  │  vs. front templates│   │  all templates  │
  └────────┬─────────┘   └──────┬─────────┘
           │                    │
  ┌────────▼─────────┐  ┌───────▼──────────┐
  │  Store Template    │  │  Accept / Reject  │   (orange / pink)
  │  Fernet-encrypted   │  │  Logged to        │
  │  front-facing        │  │  verification_logs │
  └───────────────────┘  └────────────────────┘
```

*Both registration and verification share every stage up to Face Embedding, then split into two separate paths. Colors match the same scheme used in `docs/architecture_diagram.png`: gray = capture/detection, teal = quality/liveness checks, purple = embedding, orange = registration path, pink = verification path.*

**After embedding, the pipeline forks:**
- **Registration:** Consent gate (refuses without explicit consent) → Duplicate check (cosine similarity vs. every existing template, threshold 0.68) → Store template (Fernet AES-128 encrypted at rest, front-facing only).
- **Verification:** Fetch all active users' stored templates → 1-to-N cosine-similarity match, accept at score ≥ 0.40 → Accept/Reject, logged to `verification_logs`.

**Deployment:** three local components on one machine, no cloud dependency — Streamlit UI (with `streamlit-webrtc` for the camera feed) → FastAPI backend (`/register`, `/verify`) → SQLite (local file: `users`, `templates`, `access_log`, `verification_logs`). API-key auth and a sliding-window rate limiter sit in front of the backend.

**A deliberate design change from the original brief:** registration originally captured three angles (front/left/right) via a pose-gated head-turn sequence. This was simplified to a single front-facing capture — full rationale in Section 4.

*(Full pipeline diagram available separately: `docs/architecture_diagram.png` / `.svg`)*

---

## 3. Results — Real Measured Numbers

### 3.1 Face Matching Accuracy (Frontal-vs-Frontal, the production path)

| Metric | Value |
|---|---|
| Equal Error Rate (EER) | 3.19% at threshold 0.2642 |
| ROC AUC | 0.9953 |
| **At deployed threshold 0.40:** False Accept Rate | **0.34%** (2/595) |
| **At deployed threshold 0.40:** False Reject Rate | **15.09%** (16/106) |
| Half Total Error Rate (HTER) | 7.72% |

The mathematically "optimal" threshold (0.2642) was deliberately not used — its 3.19% false-accept rate is too high for a security-critical system. The deployed threshold of 0.40 was chosen to force near-zero false acceptance, accepting a higher false-rejection rate as the tradeoff: a false reject simply re-prompts the user automatically within milliseconds, while a false accept is a real security failure.

### 3.2 Passive Liveness / Attack Detection

Re-measured on an expanded sample (n=76 attacks / n=75 genuine), superseding an earlier n=5 figure that was too small to trust.

| Metric | Value |
|---|---|
| APCER (attacks wrongly accepted) | **46.05%** (35/76) — worse than the earlier estimate, reported as measured |
| BPCER (genuine users wrongly rejected) | 0.00% (0/75) |
| ACER | 0.230 |

**Per attack type — the aggregate number hides a very uneven picture:**

| Attack Type | Miss Rate | Assessment |
|---|---|---|
| Printed Photo | 5.3% | Reliably caught |
| Screen Replay (Phone) | 5.3% | Reliably caught |
| Screen Replay (Laptop) | **73.7%** | **Real, confirmed weakness** |
| Frozen Frame | 100% | Expected — this attack type is handled by active liveness, not passive |

A threshold sweep shows raising the deployed threshold to 0.95–0.96 is a free improvement in this sample (genuine users are unaffected), but no threshold fully closes the laptop-screen-replay gap without a real cost to genuine-user acceptance. That threshold decision is left to the project owner with this evidence in hand — it has not been silently changed.

### 3.3 Quality Assessment Profile Acceptance

Composite score now combines 7 sub-checks (Contrast and Resolution added this pass, see Section 5).

| Profile | Threshold | Acceptance Rate (genuine captures) |
|---|---|---|
| Lenient | 50% | 100% |
| Balanced (default) | 70% | 0% (small calibration sample; see full Evaluation Report) |
| Strict | 85% | 0% |

---

## 4. Limitations and Scope Decisions — Stated Plainly

**Physiological liveness (rPPG) — deferred.** Built and calibrated as an offline module (heartbeat detection from skin color changes) but not wired into the live pipeline, since it needs a stable 10–15 second capture window that doesn't fit the current per-tick UI model without a larger redesign.

**Active liveness covers 2 challenge types (blink, head-turn), not a wider set.** These were chosen because they reuse detection infrastructure the pipeline already needs elsewhere. A direct, reproducible test confirmed the expected consequence: a replayed video of a real blink is accepted by the blink challenge (`status: pass`) — landmark-based active liveness cannot distinguish a live blink from a recorded one. This is exactly why the system does not rely on active liveness alone.

**Occlusion detection is a visibility-based approximation, not a trained classifier.** It can flag that something is likely obstructing the face, but not identify what (mask vs. hand vs. hair vs. glasses).

**Demographic bias — confirmed, unmitigated.** Measured across 80 real images spanning skin tone, gender, and age: quality pass rate 20.0% (female) vs. 42.5% (male); liveness pass rate 25.0% (senior) vs. 46.2% (middle-aged); a smaller but present skin-tone gap. No rebalancing or mitigation has been attempted. Disclosed here explicitly rather than left implicit.

**Multi-angle enrollment simplified to front-only.** The original three-angle capture flow was unreliable in practice, and duplicate-detection and live verification were both already relying on the front template almost exclusively for accuracy — the side captures were adding failure risk without adding real security value.

**A known, intermittent WebRTC connection hiccup exists** — the camera connection can silently drop for 20–30 seconds and self-recover, reproduced and root-caused as far as the evidence allows to a library-level characteristic, not an application bug. Practical mitigation: keep continuous camera segments under ~30 seconds during live demonstrations.

---

## 5. Registration Quality Checks — Gap Closed This Pass

The original brief specifies four registration image-quality checks: brightness, contrast, blur, and resolution. Brightness and blur existed from early in the project; contrast and resolution did not exist anywhere in the codebase, confirmed before writing any new code. Both have now been added, calibrated against real captured images, and wired into the composite quality score, the corrective-guidance messages shown to the user, and the live camera guide overlay.

---

## 6. Verification — Fresh Automated Test Suite

Full suite run fresh for this report:

```
13 passed in 10.10s
```

Covering encryption round-trip integrity, consent enforcement, soft/hard delete behavior, embedding similarity math, template matching (best-of-angle and threshold rejection), and quality/liveness structure on genuine captures.

---

## 7. Learning Outcomes

- **Computer Vision:** face detection and landmark geometry, `solvePnP`-based head pose recovery, and classical statistical quality proxies (blur, brightness, contrast) chosen deliberately over a heavier trained model.
- **Face Recognition:** ArcFace embeddings, cosine similarity matching, and the distinction between a mathematically "optimal" threshold and one deliberately chosen off that point for a security-first tradeoff.
- **Liveness Detection:** a three-layer design motivated by the fact that single-method liveness is foolable — demonstrated concretely by this project's own testing, which shows the passive layer alone misses nearly half a realistic attack sample, and the active layer alone is bypassable by a replayed recording.
- **Biometric Authentication:** consent gating, duplicate detection, encryption at rest, and GDPR/BIPA-oriented deletion, implemented as core requirements rather than afterthoughts.
- **API Development:** a FastAPI backend with key-based auth and rate limiting, kept cleanly separate from the core pipeline logic so both the API and the UI share one source of truth.
- **Performance Evaluation:** industry-standard metrics (APCER/BPCER/ACER, EER/ROC/AUC, HTER) rather than a single invented accuracy figure, including the discipline of re-measuring a suspiciously small sample and reporting the result even when it came out worse than expected.

---

*This report consolidates findings already documented in `README.md`, `data/Evaluation_Report.md`, and `docs/scope_decision_worksheet.md`. No new analysis is introduced here beyond what those source documents already establish.*
