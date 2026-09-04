#!/bin/bash
# scripts/regen.sh — re-embed resume chunks and re-run generation for one job.
# Usage: ./scripts/regen.sh <job_id>  (run from project root)
# Find job_ids with: kratos/bin/python -m scripts.review_variant --list

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -z "$1" ]; then
  echo "Usage: ./scripts/regen.sh <job_id>"
  echo "Find job_ids with: kratos/bin/python -m scripts.review_variant --list"
  exit 1
fi

echo "Embedding resume chunks..."
PYTHONPATH=. kratos/bin/python scripts/embed_resume.py

echo "Running generation pipeline for job $1..."
PYTHONPATH=. kratos/bin/python scripts/run_generation.py "$1"

echo "Done."
