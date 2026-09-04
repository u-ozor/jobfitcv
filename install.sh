#!/bin/bash
# install.sh — local setup for jobfitcv.
# Run once on a fresh clone. Safe to re-run.

set -e
cd "$(dirname "$0")"

# Pin caches inside the project so nothing scatters to system directories.
export HF_HOME="$(pwd)/.cache/huggingface"
export PLAYWRIGHT_BROWSERS_PATH="$(pwd)/.cache/playwright"
mkdir -p "$HF_HOME" "$PLAYWRIGHT_BROWSERS_PATH"

echo ""
echo "=== jobfitcv installer ==="
echo ""

# ── 1. Virtualenv ─────────────────────────────────────────────────────────────
echo "[1/6] Creating virtualenv (kratos)..."
python3 -m venv kratos
echo "      done."

# ── 2. Dependencies ───────────────────────────────────────────────────────────
echo "[2/6] Installing dependencies..."
kratos/bin/pip install --upgrade pip -q
kratos/bin/pip install -r requirements.txt -q
echo "      done."

# ── 3. Embedding model ────────────────────────────────────────────────────────
# Runtime scoring/ingest loads this with local_files_only=True (no network call
# mid-request) — so it must be cached here, once, during setup. Skipping this
# step is why a fresh install can ingest-crash on the very first job capture.
echo "[3/6] Pre-fetching embedding model (BAAI/bge-base-en-v1.5, ~270MB)..."
kratos/bin/python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5')"
echo "      done."

# ── 4. Database ───────────────────────────────────────────────────────────────
echo "[4/6] Initialising database (data/jobs.db)..."
kratos/bin/python app/database/init_db.py
echo "      done."

# ── 5. Playwright ─────────────────────────────────────────────────────────────
echo "[5/6] Installing Playwright Chromium (local PDF generation)..."
kratos/bin/playwright install chromium
echo "      done."

# ── 6. Extension icons ────────────────────────────────────────────────────────
echo "[6/6] Generating extension icons..."
if [ -f "app/static/fonts/icon_font.ttf" ]; then
  kratos/bin/pip install pillow -q
  kratos/bin/python scripts/generate_icons.py
  echo "      done."
else
  echo "      [skipped] No font found at app/static/fonts/icon_font.ttf"
  echo "      Add a bold TTF font there and run: kratos/bin/python scripts/generate_icons.py"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Setup complete ==="
echo ""
echo "Next, run the guided setup (API key, port, LLM providers, contact info,"
echo "resume content):"
echo "  cp .env.example .env"
echo "  kratos/bin/python scripts/setup_wizard.py"
echo ""
echo "Then:"
echo "  ./start.sh"
echo "  Load extension/ as an unpacked extension in Chrome"
echo "  (chrome://extensions → Developer mode → Load unpacked)"
echo ""
echo "Not using the wizard? Edit data/*.json by hand instead, then re-embed:"
echo "  kratos/bin/python scripts/embed_resume.py"
echo ""
echo "NOTE: LLM rewrites (ENABLE_REWRITES) require Ollama running separately."
echo "      Embeddings and core pipeline do not need Ollama."
