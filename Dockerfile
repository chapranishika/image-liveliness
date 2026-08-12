# Dockerfile
#
# Single image, shared by both services in docker-compose.yml (the FastAPI
# backend and the Streamlit frontend) -- they need almost entirely the same
# Python dependencies (both eventually call into src/, which is where the
# ML stack lives), so one image with a different CMD per service is
# simpler to build and keep in sync than two separate images.
#
# Direct containerized equivalent of what run_app.py does for local
# development: two independent long-running processes (not one process
# doing both, and not a serverless/short-lived function -- see
# docs/deployment.md for why this app specifically needs a persistent-
# process host, not something like Vercel).

FROM python:3.11-slim

# libgl1/libglib2.0-0: OpenCV and MediaPipe both need these for image
# decoding/processing even in a headless container with no display.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# torch's default PyPI wheel bundles CUDA libraries (several GB) that this
# CPU-only deployment never uses -- confirmed as real, unnecessary bloat
# in an actual build of this image (~13GB, mostly nvidia-* packages).
# Installing the CPU-only wheel from PyTorch's own index first means the
# requirements.txt install below finds torch already satisfied and skips
# pulling the GPU variant, since requirements.txt itself pins no specific
# torch build.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# MediaPipe/DeepFace model weights and the SQLite database both write into
# this directory at runtime (see src/quality_checks_day8_9.py's
# ensure_models_exist() and src/db.py's DB_PATH) -- mounted as a volume in
# docker-compose.yml so they persist across container restarts instead of
# re-downloading or resetting to empty every time.
VOLUME ["/app/data"]

EXPOSE 8000 8501
