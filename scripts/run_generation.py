# scripts/run_generation.py

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # allow direct invocation
# Manual re-run of the generation pipeline for an already-ingested job.
# Usage: python scripts/run_generation.py <job_id>
# Find job_ids with: kratos/bin/python -m scripts.review_variant --list

import sys
from dotenv import load_dotenv

from app.database.session import SessionLocal
from app.database.models import Job
from app.pipelines.generation_pipeline import generate_resume_pipeline

if __name__ == "__main__":

    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python scripts/run_generation.py <job_id>")
        print("Find job_ids with: kratos/bin/python -m scripts.review_variant --list")
        sys.exit(1)

    job_id = sys.argv[1]

    db = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    db.close()

    if not job:
        print(f"[error] no job found with id={job_id}")
        sys.exit(1)

    print(
        f"[taxonomy] "
        f"{job.track} / "
        f"{job.focus}"
    )

    result = generate_resume_pipeline(
        job_text=job.raw_text,
        track=job.track,
        focus=job.focus,
        job_id=job.id
    )

    print(result["variant"])
