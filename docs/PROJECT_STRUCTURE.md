# Project File Structure — "Nishika" (Secure Face Registration & Verification Framework)

## Top-level layout

```
ML liveliness/
├── app/          — Streamlit frontend
├── api/          — FastAPI backend
├── src/          — core pipeline logic (shared by both app/ and api/)
├── tests/        — pytest suite
├── data/         — datasets, evaluation results, the live database
├── docs/         — reports, calibration docs, diagrams
├── scratch/      — throwaway test/debug artifacts (gitignored working area)
├── venv/         — Python virtual environment
├── dayNN_*.py    — one-off calibration/testing scripts from each day of development
└── (root config: run_app.py, requirements.txt, .env, README.md, etc.)
```

## `src/` — the actual pipeline (the heart of the project)

| File | Purpose |
|---|---|
| `pipeline.py` | Central coordinator — wires quality → liveness → matching into one `verify()` call used by both registration and verification |
| `quality_checks.py` | Brightness, blur, contrast checks + `is_frame_corrupted()` (macroblock/decode-corruption detector) |
| `quality_checks_day8_9.py` | Face detection, pose (solvePnP), position/centering, occlusion, resolution checks |
| `quality_score.py` | Combines all 7 sub-checks into one weighted 0-100 score, with Strict/Balanced/Lenient profiles |
| `liveness_passive.py` | Layer 1 — DeepFace/MiniFASNet anti-spoofing on a single frame |
| `liveness_active.py` | Layer 2 — blink (EAR) and head-turn challenge-response |
| `rppg.py` | Layer 3 — heartbeat detection via remote photoplethysmography (built, calibrated, not wired into the live app — a disclosed, deliberate gap) |
| `face_matching.py` | ArcFace embeddings via DeepFace + cosine similarity comparison |
| `duplicate_check.py` | 1-to-N comparison against existing templates at registration time, blocks re-registration under a new name |
| `registration.py` | Full registration flow — front capture + reuses the head-turn challenge to also capture left/right profile templates |
| `encryption.py` | Fernet AES-128 encrypt/decrypt for templates at rest |
| `db.py` | SQLite interface — `users`, `templates`, `access_log`, `verification_logs` tables, soft/hard delete |
| `keys.py` | Loads `.env`, auto-generates encryption/API keys if missing |

## `api/` — FastAPI backend (port 8000)

| File | Purpose |
|---|---|
| `api.py` | `/register`, `/verify` and related endpoints |
| `security.py` | X-API-Key auth middleware + sliding-window rate limiter |
| `health.py` | Backs the admin panel's "System Diagnostics & Health Checks" (DB, encryption key, cached models, camera) |

## `app/` — Streamlit frontend (port 8501)

| File | Purpose |
|---|---|
| `streamlit_app.py` | The whole UI — Verify Identity / Guided Enrollment toggle, live WebRTC camera card (`render_camera_card()`, now an `@st.fragment`), the admin/compliance expander at the bottom |
| `styles.py` | CSS tokens/styling |
| `branding_config.py` | Company name, logo path, primary color |

## `tests/` — pytest suite (13 tests, all passing)

`conftest.py` (fixtures) + `test_database_and_security.py`, `test_matching.py`, `test_quality_and_liveness.py` — covers encryption round-trip, consent enforcement, soft/hard delete, embedding math, template matching, and quality/liveness structure.

## `data/`

- `face_verification.db` — the live SQLite database (currently has real registered users from your testing)
- `self_collected/` — your own captured photos, organized by angle (`front/`, `left/`, `right/`, `different/`) plus a fuller `session_1/` with attack-sample subfolders (`attacks/`, `rppg_window_photo_attack/`, `rppg_window_screen_attack/`) used for liveness testing
- `Evaluation_Report.md` + various `dayNN_*.csv`/`.png` — calibration measurements (ROC curves, quality thresholds, bias testing results) that back every threshold used in the code

## `docs/`

- `Final_Report_Full.docx` / `.pdf` — the final project report (verbatim project narrative + diagrams)
- `Final_Report.md`, `Final_Report_Print.md`, `Project_Story.md` — earlier report drafts/variants
- `scope_decision_worksheet.md` — the authoritative log of known limitations (WebRTC hiccup, screen-replay liveness gap, etc.) — worth reading if you want the single source of truth on "what's still open"
- `architecture_diagram.png`/`.svg` — pipeline diagram

## `scratch/` — not part of the shipped project

This is the working scratchpad — test videos (`quality_scenarios/`), Playwright driver scripts, debug logs, screenshots from testing. Safe to ignore or clean out; nothing here is imported by the app.

## Root-level `dayNN_*.py` files

One script per development day (`day7_calibrate.py` through `day43_scope_decision_worksheet.py`) — these are the original calibration/testing scripts that produced the numbers now baked into `src/`. They're historical/reproducibility artifacts, not run as part of the live app.

## How it all connects

`run_app.py` launches `api/api.py` (uvicorn, backend) and `app/streamlit_app.py` (streamlit, frontend) as two subprocesses. The Streamlit app imports directly from `src/` for its own pipeline calls (registration/verification happen in-process, not via HTTP to the backend) — the FastAPI backend in `api/` is a separate, parallel access path into the same `src/` logic, for programmatic/external callers.
