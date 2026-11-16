# Dockerfile

# Base image — slim Python 3.11 on Debian, no desktop/GUI packages.
# "slim" cuts the image from ~1GB to ~130MB by stripping docs and dev tools.
FROM python:3.11-slim

# All subsequent commands and paths inside the container are relative to this.
# Created automatically if it doesn't exist.
WORKDIR /app

# Must match .env.example's HF_HOME/PLAYWRIGHT_BROWSERS_PATH. env_file only
# applies at container START, not at build time — if these aren't also set
# here, the build-time fetch steps below cache into the default system
# locations while the running container (with .env's paths) looks elsewhere
# and finds nothing.
ENV HF_HOME=./.cache/huggingface
ENV PLAYWRIGHT_BROWSERS_PATH=./.cache/playwright

# Copy requirements first, install, THEN copy code.
# Docker builds in layers — each instruction is a cached layer.
# requirements.txt changes rarely; code changes constantly.
# This order means a code edit doesn't invalidate the pip install layer,
# so rebuilds that don't touch requirements are fast.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-fetch the embedding model into the image at build time.
# embedder.py loads it with local_files_only=True — without this,
# the first embed call at runtime would fail with no network fallback.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5')"

# Install the Chromium browser Playwright needs (the pip package alone doesn't
# ship a browser binary). --with-deps pulls the OS-level libs (fonts, etc.)
# python:3.11-slim lacks. Adds real image size (~300MB) but keeps PDF export
# on the exact same rendering path as local dev — no second PDF library to
# maintain or risk diverging output from.
RUN playwright install --with-deps chromium

# Copy only what the API needs at runtime.
# data/ and outputs/ are excluded — they're mounted as volumes.
# extension/, assets/, dev docs — not needed inside the container.
COPY app/ ./app/
COPY templates/ ./templates/
COPY scripts/ ./scripts/

# Bootstrap script — seeds data/ from templates on first run, ensures DB
# tables + chunk embeddings exist, then execs into CMD. See entrypoint.sh
# for exactly what it does and why; every step there is idempotent, so this
# runs safely on every container start, not just the first.
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

# Documents the port the app binds to. Doesn't actually open anything —
# that's docker-compose's job. Acts as a declaration for tooling and humans.
EXPOSE 8000

# Periodic liveness check — hits the root endpoint (returns {"status":"ok"}).
# Lets `restart: unless-stopped` know when to actually restart, and lets
# anything orchestrating multiple containers know real readiness, not just
# "the process didn't crash."
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/', timeout=3)" || exit 1

# Default command when the container starts — passed to entrypoint.sh's
# `exec "$@"` after bootstrap runs.
# --host 0.0.0.0 binds to all interfaces inside the container.
# Required even with --network=host so uvicorn doesn't refuse connections.
# No --reload in production — that's a dev-only flag.
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
