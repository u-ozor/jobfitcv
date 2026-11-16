#!/bin/sh
# Runs once every container start, before the real server process.
# Bootstraps data/ on a first-ever run (fresh/empty volume mount) so
# `docker-compose up -d` works without a separate manual setup step —
# then always ensures DB tables + chunk embeddings exist before handing off
# to the real CMD. Safe to run on every start: every step here is idempotent.
set -e

cd /app

seed_if_missing() {
  # $1 = real filename, $2 = template filename, both under data/
  if [ ! -f "data/$1" ] && [ -f "data/templates/$2" ]; then
    echo "[entrypoint] data/$1 missing — seeding from templates/$2"
    cp "data/templates/$2" "data/$1"
  fi
}

seed_if_missing "resume_chunks.json" "resume_chunks.template.json"
seed_if_missing "user_profile.json"  "user_profile.template.json"
seed_if_missing "job_targets.json"   "job_targets.template.json"
seed_if_missing "experience.json"    "experience.template.json"

# Idempotent — CREATE TABLE IF NOT EXISTS semantics, safe on every start.
echo "[entrypoint] ensuring DB tables exist"
python app/database/init_db.py

# Chunk embeddings are derived from resume_chunks.json and gitignored (not
# shipped, not baked into the image) — must exist before scoring works.
if [ ! -f "data/resume_embeddings.npy" ]; then
  echo "[entrypoint] data/resume_embeddings.npy missing — embedding resume chunks"
  python -m scripts.embed_resume
fi

echo "[entrypoint] bootstrap complete, starting server"
exec "$@"
