# DEPLOY.md
# Deployment methods, what each carries, and required input state.

---

## Deployment methods

### 1. Local dev (uvicorn direct)

**What runs:** FastAPI via uvicorn on your machine. Ollama runs as a separate local service.
**How to start:** `./start.sh` / `./stop.sh`
**PDF generation:** yes — Playwright runs locally.
**Use when:** developing, testing, day-to-day personal use.

Required before starting:
- kratos venv created and requirements installed
- Ollama running (`ollama serve`) — needed for the chunk review "Assess Fit" feature (`mistral:latest`, fallback `qwen2.5-coder:7b`), NOT for embeddings (see note below)
- `data/` in the state described below
- `data/jobs.db` initialised (`kratos/bin/python app/database/init_db.py`)

---

### 2. Docker (local)

**What runs:** the same FastAPI app inside a container. Ollama still runs on the host.
**PDF generation:** yes — the image installs Chromium via `playwright install --with-deps chromium`
at build time, same rendering path as local dev. Adds ~300MB to the image.
**Use when:** local Docker use in general, or testing the clean-room build before pushing to EC2.

**Note on the extension:** running the backend in Docker changes nothing about how the Chrome
extension loads — it's still loaded unpacked via `chrome://extensions`, same as always. Docker
only replaces how the *backend* runs; `extension/config.js`'s `BASE_URL` just needs to point at
wherever that backend actually is (bare-metal `localhost:8000`, this container, or a remote host).
There's no scenario where the extension becomes a webpage — Chrome extensions can't be delivered
that way regardless of backend.

Default config (`deploy/docker-compose.yml`) runs standard bridge networking with an explicit
`ports: ["8000:8000"]` mapping — this is the portable option, works identically on Mac, Windows,
and Linux. Because of that, `localhost` *inside* the container refers to the container itself, not
your machine — so `OLLAMA_BASE_URL` needs `http://host.docker.internal:11434` (Docker's special
DNS name for reaching the host) rather than plain `localhost`.

Deploying to a real Linux host instead (EC2, below) can use `network_mode: host` — genuinely
simpler there, since the container then shares the host's actual network namespace and
`localhost` really does mean the host. That mode is Linux-only; the switch is documented inline
in `docker-compose.yml`.

What's INSIDE the image (baked in at build time):
```
app/           application code
templates/     Jinja2 HTML templates
scripts/       maintenance scripts (init_db, etc.)
requirements.txt + installed packages
```

What's NOT in the image (either mounted or irrelevant):
```
data/          MOUNTED as volume — personal data, never baked in
outputs/       MOUNTED as volume — generated artifacts
extension/     browser-side only, not served by the API
assets/        icon generation is a local one-time step, not needed at runtime
kratos/        virtualenv — image has its own Python environment
.env           secrets — passed via env_file in compose, never baked in
logs/          runtime output — optionally mounted
dev-log.md, PLAN.md, DEPLOY.md   development docs, not needed in container
```

---

### 3. AWS EC2 (production-ish)

**What runs:** Docker container on a t2.micro instance, behind nginx.
**PDF generation:** yes — same image as Docker local, Chromium baked in.
**Use when:** running the app persistently, accessible from anywhere.

EC2 setup steps (high level — full walkthrough TBD):
1. Launch t2.micro, Amazon Linux 2 or Ubuntu
2. Install Docker, nginx
3. Install Ollama for Linux (only needed for the "Assess Fit" chunk review feature — embeddings do not need Ollama, see note below)
4. Clone repo, populate `data/` (see below), run `docker-compose up -d`
5. Configure nginx to proxy `localhost:8000`
6. Extension: change `BASE_URL` in `background.js` and `panel.js` to EC2 public IP or domain

Ollama runs on the EC2 instance. Container uses `--network=host` so `localhost:11434`
resolves correctly — same as every other environment. No URL changes across environments.

---

## Required state of `data/` before running

`data/` is mounted as a volume in Docker and lives on-disk in local dev.
It is gitignored — it must be populated manually on each new machine or EC2 instance.

```
data/
  resume_chunks.json          REQUIRED — your chunked resume data (authoring source)
  resume_embeddings.npy       REQUIRED — precomputed chunk embeddings (BAAI/bge-base-en-v1.5, 768-dim)
  resume_embedding_ids.json   REQUIRED — maps embedding indices to chunk IDs
  user_profile.json           REQUIRED — contact info, name, etc. rendered into resume header
  taxonomy/                   REQUIRED — .npy files for taxonomy classification
    backend_api.npy
    cloud_devops.npy
    it_support.npy
    soc_security.npy
    sysadmin_itops.npy
  jobs.db                     CREATED on first run via init_db.py — do not need to copy
```

To prepare a new environment:
1. Copy your `data/` directory from a working local instance, or
2. Re-run the preprocessing pipeline: `embed_resume.py`, `build_taxonomy_embeddings.py`
3. Run `init_db.py` to create a fresh `jobs.db`

---

## Embedding model note

All `.npy` files are computed with `BAAI/bge-base-en-v1.5` via `sentence-transformers`
(768-dim output) — loaded directly in-process (`app/embedder.py`), no Ollama or other
external service involved. Do NOT switch embedding models without re-running
`embed_resume.py` and `build_taxonomy_embeddings.py` — dimensions must match across
all vectors.

`embedder.py` loads the model with `local_files_only=True`, so it must already be
cached before the app can embed anything:
- **Local dev / first run anywhere**: run once without `local_files_only` (or just
  run the app normally — `sentence-transformers` will fetch and cache it under
  `~/.cache/huggingface` on first use if network is available), then it's cached.
- **Docker**: the model is pre-fetched into the image at build time (see `Dockerfile`)
  so the container never needs network access to embed at runtime.

Ollama is unrelated to embeddings in this app — it's only used for the optional
"Assess Fit" feature in chunk review (`mistral:latest`, fallback `qwen2.5-coder:7b`)
and, if enabled, the disabled-by-default rewrite pipeline.

---

## Installer

`install.sh` exists — run once on a fresh clone, safe to re-run. It handles:
- venv creation (`kratos`)
- pip install
- `init_db.py`
- Playwright Chromium install
- Extension icon generation

Still outstanding:
- Ollama check + model pull (not automated — install Ollama and pull models manually)
- Guided `data/` population (or copy from a backup) — currently manual
- A config step for timezone / default template / rewrite toggle — currently edited directly in `app/config.py`
- Instructions for loading the extension in Chrome — not yet printed at the end of the script
