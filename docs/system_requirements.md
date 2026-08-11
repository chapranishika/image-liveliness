# System Requirements and Production Readiness

This document answers a specific question a mentor raised after reviewing this
project from an industry, client-facing angle rather than a student-project
angle: what does this system actually cost to run, on what kind of machine,
and what should a client be told before deploying it? Every number below was
measured directly against the running code, not estimated from documentation
or guessed at — the method for each measurement is stated so it can be
re-run and checked.

## How this was measured

The application is two local processes: a FastAPI backend (`api/api.py`,
for any external/API client integration) and a Streamlit frontend
(`app/streamlit_app.py`, the live camera UI a person actually uses). They
are independent Python processes and do **not** share loaded model weights
— each one that actually gets used loads its own copy of MediaPipe and
DeepFace/TensorFlow into its own memory. In normal use, only the Streamlit
process is exercised (the live UI calls the checking functions in `src/`
directly, in-process — it does not call the FastAPI backend over HTTP); the
FastAPI backend is a separate integration surface for a client's own
external systems, and only pays its own model-loading cost the moment
something actually calls it.

Two measurements were taken:

1. A direct, single-process script (`scratch/profile_resources.py`) that
   imports every model-backed check the live app uses — the combined
   quality score, head-pose geometry, face-embedding extraction, and
   passive-liveness (anti-spoofing) check — and runs them against a real
   captured photo from this project's own test data
   (`data/self_collected/front/front_001.jpg`), first once (to capture the
   one-time model-loading cost) and then 30 times back to back (to capture
   steady-state, models-already-warm cost).
2. The actual two-process deployment, launched the normal way
   (`python run_app.py`), measured at rest via `psutil` immediately after
   the launcher's own warm-up step completed.

**Machine this was measured on:** a 16-physical/22-logical-core desktop
with 34 GB of RAM. This is a development workstation, not a typical
client laptop — every number below is reported as what was actually
measured on that machine, with an explicit, separately-reasoned minimum
recommendation for a normal laptop underneath it, not a claim that a
lighter machine was tested and passed. That gap — this has not yet been
run on a genuinely low-spec machine — is called out honestly in the "Not
yet validated" section at the end, in the same spirit as every other open
item in this project's main report.

## Memory (RAM)

| Stage | Measured RSS |
|---|---|
| Bare Python interpreter, nothing imported | 41 MB |
| After importing MediaPipe/DeepFace/TensorFlow (no inference yet) | 399 MB |
| After the first full check cycle (models fully loaded into memory) | 1,222 MB (~1.2 GB) |
| Steady state, after 30 more check cycles | 1,236 MB |
| The two-process deployment at rest, backend idle | 420 MB |
| The two-process deployment at rest, frontend idle | 449 MB |

The single-process number (~1.2 GB) is the realistic ceiling for what one
active browser session actually costs once someone has used the camera at
least once, since that is what actually triggers the lazy model imports
inside the checking functions. The two-process at-rest numbers are lower
because the FastAPI backend had not yet been called by anything and so had
not yet paid its own model-loading cost — the moment any external client
does call it, its RSS will climb toward the same ~1.2 GB the frontend
reaches, independently, since the two processes do not share memory.

**Recommendation:** at least **4 GB of RAM free** for the Streamlit-only
deployment most users will actually run (covers the ~1.2 GB model
footprint plus the browser, the OS, and a comfortable safety margin for
the temporary spikes described below). If a client also runs the FastAPI
backend concurrently for their own integration, budget **8 GB of RAM
free** to cover both processes independently loading the same models.

## CPU

Running the same three model-backed checks (quality score, pose, face
embedding) 30 times back to back, with nothing else competing for the CPU,
measured **168% of one core** (`psutil`'s `cpu_percent`, where 100% is one
full core saturated) — in other words, this workload comfortably uses
close to two cores when they're available, and does not meaningfully
benefit from more than that per single active session, since the
underlying models are not internally parallelized much beyond that on
CPU. Each full cycle averaged **747 ms**.

**Recommendation:** a minimum of **4 logical CPU cores** for a single
active session with comfortable headroom for the browser, OS, and the
capture pipeline's own JPEG encode/decode work running alongside it — not
because the checks themselves need four cores, but because two cores fully
occupied by inference leaves too little margin on a 2-core machine for
everything else the OS and browser are also doing at the same time. A
machine with only 1-2 logical cores was not tested directly, but is
expected to make the "hold still" and challenge-gesture windows feel
noticeably slower, since less CPU headroom is left over between checks.

## One-time cost vs. per-session cost — a real distinction that matters for demos

Importing the ML libraries and loading their model weights from disk into
memory took **28 seconds** the first time, combined across import and
first inference. This matches something already noted elsewhere in this
project (`run_app.py`'s own warm-up step, and the seventeen-hour-stale-
server finding in the main report's Phase 8): **this cost is paid once per
process start, not once per user action.** `run_app.py` already
deliberately absorbs this cost itself, firing a warm-up request before
printing "ready," specifically so a real user's first camera session never
has to wait through it. After that one-time cost, a live check cycle
during actual use is well under a second (747 ms measured, steady state).

This has a direct, practical consequence for anyone demonstrating or
deploying this system: **always start from a freshly launched process**,
not one left running for hours, and expect the first ~30 seconds after
`python run_app.py` to be pure warm-up before the system is at its
documented steady-state responsiveness — the launcher's own console output
already says so, but it is worth stating here explicitly for anyone
reading this document without having read the launcher's source.

## Camera

Requirements here are derived directly from the actual thresholds this
project's own code checks against, not a generic recommendation:

- The capture pipeline requests **1280×720 at ideal**
  (`app/frame_capture_component/index.html`'s `getUserMedia` constraints)
  and encodes each captured frame as JPEG at quality 0.95 — a camera that
  cannot supply at least 720p will still work (the browser negotiates
  downward), but face-width-in-pixels and sharpness scores will sit closer
  to this project's "acceptable" floor rather than its "good" range.
- `score_resolution()` (`src/quality_score.py`) treats a detected face
  narrower than 50 pixels across as a hard 0, 100 pixels as the low end of
  acceptable, and 200 pixels or wider as full score — at a typical laptop
  camera's field of view, this means sitting roughly arm's length or
  closer from the camera, not a webcam quality requirement as such.
- `score_blur()`'s calibration (good ≥ 450, worst ≤ 150, on an
  OpenCV Laplacian-variance sharpness measurement) was itself recalibrated
  earlier in this project specifically against a real, ordinary laptop
  webcam in ordinary indoor lighting (see the main report's Phase 8) — an
  integrated laptop webcam or a basic USB webcam is sufficient; nothing
  here assumes specialized or high-end camera hardware.

**Recommendation:** any camera capable of 720p, autofocus not required but
helpful, in a reasonably lit indoor space — no external or specialized
hardware needed.

## Internet / network

This is worth stating plainly because it is a genuine point of difference
from many commercial face-verification products: **this system needs no
internet connection at all during actual use.** The frontend, backend, and
database are all local — `127.0.0.1` only, a local SQLite file, no cloud
API calls in the live verification or enrollment path. A network
connection is needed exactly once, during initial setup, to `pip install`
the Python dependencies and let MediaPipe/DeepFace download their
pretrained model weights the first time they are imported; after that,
the system runs fully offline, including in the remote-location scenario a
mentor specifically asked about (a client site with a poor or firewalled
internet connection is not a deployment risk for this system the way it
would be for a cloud-dependent verification API).

## Prerequisites checklist

For a client evaluating whether their hardware can run this system:

- [ ] 64-bit Windows, macOS, or Linux, with Python 3.9+ available
- [ ] 4 GB of RAM free at the moment the app is launched (8 GB if also
      running the FastAPI backend concurrently for an external integration)
- [ ] 4 logical CPU cores recommended for comfortable headroom
- [ ] A 720p-capable camera (built-in laptop webcam is sufficient)
- [ ] Internet access for one-time setup only (package install + model
      weight download); none required afterward
- [ ] `FACE_DB_ENCRYPTION_KEY` and `FACE_API_KEY` configured in a local
      `.env` file before first launch (`run_app.py` checks for and refuses
      to start without these, by design)
- [ ] A fresh process start (not a session left running for many hours)
      before any live demonstration or high-stakes use, per the Phase 8
      finding in the main report

## Not yet validated — disclosed honestly, not hidden

In the same spirit as the rest of this project's reporting: what has and
has not actually been tested should be stated plainly.

- **Tested on one machine only.** Every number above was measured on a
  single, high-spec development workstation. This system has not yet been
  run on a genuinely low-spec laptop (2-4 GB RAM, 2 logical cores, an
  older integrated GPU-less CPU), nor on a second physical machine at all,
  of any spec. The 4 GB RAM / 4-core recommendation above is a reasoned
  safety-margin estimate built from the real measured numbers, not a
  second measurement on lighter hardware — that is real follow-up work,
  not something this document can respond to.
- **Not tested on someone else's laptop, browser, or webcam.** Every real
  live test in this project's main report, across every phase, was run on
  the same person's machine and camera. A different laptop's default
  camera driver, browser (Chrome was used throughout; Edge, Firefox, and
  Safari have not been separately tested), or OS-level camera permission
  flow could behave differently and has not yet been checked.
- **No macOS or Linux testing at all.** Every measurement and every live
  test in this project so far was run on Windows. The application code
  itself is not Windows-specific, but this has not been confirmed by
  actually running it anywhere else.
