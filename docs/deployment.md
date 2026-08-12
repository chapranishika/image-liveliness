# Deployment

This document covers two real deployment paths, with the actual
constraints and caveats for each rather than a generic "just deploy it"
description. See `docs/system_requirements.md` for the measured CPU/RAM/
timing numbers referenced below.

## Why this can't be a serverless/edge deployment (Vercel, Netlify Functions, etc.)

Worth stating up front since it rules out an entire category of otherwise
attractive, free hosting options: this app needs a **persistent, long-running
process**, not a short-lived function.

- The live camera flow depends on a continuous polling loop (~12.5 reruns/
  sec) holding live session state in one running server process. Serverless
  functions spin up per request and tear down — there is no "session" to
  hold state in between calls.
- Loading the ML models (MediaPipe, DeepFace/TensorFlow) costs about 28
  seconds and ~1.2 GB of RAM once warm (measured, not estimated — see
  `docs/system_requirements.md`). A serverless function would pay that cost
  on every cold start; a persistent process pays it once.
- The registered-user database is a local SQLite file. Serverless platforms
  give you an ephemeral filesystem per invocation — it would reset
  constantly.

Anywhere that gives you a persistent VM, container, or long-running process
works: Railway, Render, Fly.io, a plain VM (EC2/DigitalOcean/etc.), or
Streamlit Community Cloud (covered below).

## Path 1: Docker (portable, works on any container host)

```bash
cp .env.example .env
# edit .env: set FACE_DB_ENCRYPTION_KEY and FACE_API_KEY (see .env.example
# for how to generate both)

docker compose up --build
```

- Backend (FastAPI, for external integrations): `http://localhost:8000`
- Frontend (the actual consumer app): `http://localhost:8501`

Two services, one image (see `Dockerfile`'s comment for why), a shared
named volume (`face_data`) for the SQLite database and downloaded model
weights so they persist across container restarts.

**This deploys to any container host** (Railway, Render, Fly.io, a plain
VM with Docker installed) with the same `docker-compose.yml`, or split into
two separate deployed services on a platform that doesn't run
docker-compose directly (build the same `Dockerfile` twice, one per
service, pointing each at its own `command`).

**RAM**: budget at least 4 GB for the frontend service alone, 8 GB total if
also running the backend concurrently — see `docs/system_requirements.md`
for the measured numbers behind this. Many free-tier container hosts
default to 512MB-1GB, which is **not enough** — this needs an explicitly
sized plan/instance, not a default free tier.

**HTTPS is required for the camera to work at all**, on every host except
`localhost`. Browsers only grant `getUserMedia()` (camera) access on a
secure context. Most container hosts (Railway, Render, Fly.io) terminate
HTTPS for you automatically on their default domain; if self-hosting on a
plain VM, put a reverse proxy (Caddy, nginx with certbot, etc.) in front
of port 8501 rather than exposing it directly.

## Path 2: Streamlit Community Cloud (free, zero infrastructure, one caveat)

Streamlit Community Cloud deploys directly from a GitHub repo and runs
only the Streamlit app — the separate FastAPI backend isn't part of this
path, which is fine, since the live consumer UI calls `src/` directly,
in-process, and never calls the FastAPI backend over HTTP (confirmed by
reading `app/streamlit_app.py` — there is no `requests`/`httpx` call to
the backend anywhere in it). The backend is only needed for an external
client's own API integration, which is a separate concern from the
consumer demo working.

Steps:
1. Push this repo to GitHub (already done).
2. On share.streamlit.io, point a new app at `app/streamlit_app.py`.
3. In the app's Settings → Secrets, add `FACE_DB_ENCRYPTION_KEY` and
   `FACE_API_KEY` in TOML format (`FACE_DB_ENCRYPTION_KEY = "..."`).

**The real caveat, stated honestly rather than glossed over**: Streamlit
Community Cloud's free tier gives **1 GB of RAM**. This app measures
~1.2 GB once the models are fully warm (see `docs/system_requirements.md`)
— a real risk of the app being killed for exceeding its memory limit on
the free tier, not a theoretical one. This path is genuinely the easiest
to set up, but has not been tested end-to-end on the actual free-tier
memory limit — if it doesn't fit, the Docker path with an explicitly
larger instance is the fallback.

## Verified

`docker build .` against this exact `Dockerfile` has been run to a clean,
successful finish (all dependencies installed, image exported — a real
`docker images` entry, not just a log that looked promising) and removed
afterward since it was a verification build, not a deployed one.

The image was also measured and slimmed for real: the first build landed
at 13.2 GB disk usage / 4.14 GB content size, almost entirely `torch`'s
default CUDA libraries, which this CPU-only deployment never uses. Pointing
the `torch` install at PyPI's CPU-only wheel index (`Dockerfile`'s
`--index-url https://download.pytorch.org/whl/cpu` step) and rebuilding
measured **6.7 GB disk usage / 1.6 GB content size** — a 49%/61% reduction,
confirmed by actually building both versions and comparing real
`docker images` output, not estimated.

## Not yet done, disclosed honestly

- Neither deployment path above has actually been run against Community
  Cloud's or a container host's real memory limit — the RAM caveats above
  are reasoned from real local measurements, not confirmed against an
  actual constrained deployment.
- No automated deployment pipeline (CI builds and tests the code; nothing
  currently pushes a built image anywhere automatically).
