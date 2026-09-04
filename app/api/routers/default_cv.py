# app/api/routers/default_cv.py

import os
import json
import logging

from fastapi import APIRouter

from app.database.models import Job, Variant
from app.database.session import SessionLocal
from app.generation.resume_builder import build_resume_data
from app.generation.renderer import render_html, render_markdown
from app.generation.artifact_writer import write_resume_bundle, write_edited_markdown, ensure_variant_dirs
from app.core.config import TEMPLATE_NAME
from app.utils.time_utils import local_timestamp
from app.utils.atomic_io import atomic_write_json

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_JOB_ID     = "default-cv"
DEFAULT_VARIANT_ID = "default"
DEFAULT_OUTPUT_DIR = "outputs/resumes/default"
CHUNKS_PATH        = "data/resume_chunks.json"

def _load_chunks():
    with open(CHUNKS_PATH) as f:
        return json.load(f)


def _select_all(chunks):
    """
    Returns (selected: list[dict], scored_pool: list[dict]).

    Default CV includes every active chunk — no quotas, no group cap.
    Exception: summary is capped at 1 (a CV cannot have multiple summary
    blocks). The highest-priority track=null summary is selected; all other
    summaries land in the candidates tier of chunk review so the user can
    swap if they want a track-specific one instead.
    """
    active = [c for c in chunks if c.get("active", True)]

    null_summaries   = sorted(
        [c for c in active if c["type"] == "summary" and c.get("track") is None],
        key=lambda c: c.get("priority", 5), reverse=True
    )
    other_summaries  = [c for c in active if c["type"] == "summary" and c.get("track") is not None]
    non_summaries    = [c for c in active if c["type"] != "summary"]

    chosen_summary   = null_summaries[:1]           # best universal summary
    unchosen         = null_summaries[1:] + other_summaries   # candidates in chunk review

    selected         = non_summaries + chosen_summary
    selected_ids     = {c["id"] for c in selected}

    # scored_pool includes everything — priority/10 as score proxy
    scored_pool = []
    for chunk in selected + unchosen:
        pri_score = round(chunk.get("priority", 5) / 10, 3)
        scored_pool.append({
            "id":             chunk["id"],
            "score":          pri_score,
            "similarity":     pri_score,   # no job embedding; priority is the only signal
            "keyword_score":  0.0,
            "priority_score": pri_score,
            "selected":       chunk["id"] in selected_ids,
            "cut_reason":     None if chunk["id"] in selected_ids else "quota",
        })

    return selected, scored_pool


def seed_default_rows():
    """
    Upsert the permanent default-cv Job and default Variant DB rows.
    Uses its own session — safe to call from lifespan or any endpoint.
    """
    db = SessionLocal()
    try:
        if not db.query(Job).filter(Job.id == DEFAULT_JOB_ID).first():
            db.add(Job(
                id=DEFAULT_JOB_ID,
                title="Default CV",
                company="—",
                raw_text="",
                track=None,
                focus=None,
                status="done",
                ingested_at=local_timestamp(),
            ))
        if not db.query(Variant).filter(Variant.id == DEFAULT_VARIANT_ID).first():
            db.add(Variant(
                id=DEFAULT_VARIANT_ID,
                job_id=DEFAULT_JOB_ID,
                track=None,
                focus=None,
                version=0,
                output_path=DEFAULT_OUTPUT_DIR,
                reused=0,
                created_at=local_timestamp(),
            ))
        db.commit()
    finally:
        db.close()


@router.get("/status")
def default_cv_status():
    meta_path = os.path.join(DEFAULT_OUTPUT_DIR, "metadata.json")
    if not os.path.exists(meta_path):
        return {"ready": False, "last_generated": None, "chunk_count": 0}
    try:
        with open(meta_path) as f:
            meta = json.load(f)
    except Exception:
        return {"ready": False, "last_generated": None, "chunk_count": 0}
    html_exists = os.path.exists(os.path.join(DEFAULT_OUTPUT_DIR, "generated", "resume.html"))
    return {
        "ready":          html_exists,
        "last_generated": meta.get("created_at"),
        "chunk_count":    len(meta.get("chunk_ids", [])),
    }


@router.post("/generate")
def generate_default_cv():
    seed_default_rows()

    chunks = _load_chunks()
    selected, scored_pool = _select_all(chunks)

    resume_data = build_resume_data(selected)
    markdown    = render_markdown(resume_data)
    html        = render_html(resume_data, template_name=TEMPLATE_NAME)

    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
    write_resume_bundle(
        output_dir=DEFAULT_OUTPUT_DIR,
        markdown=markdown,
        html=html,
        resume_data=resume_data,
    )
    dirs = ensure_variant_dirs(DEFAULT_OUTPUT_DIR)
    write_edited_markdown(dirs["edited"], markdown)

    now = local_timestamp()
    metadata = {
        "variant":     DEFAULT_VARIANT_ID,
        "track":       None,
        "focus":       None,
        "created_at":  now,
        "chunk_ids":   [c["id"] for c in selected],
        "scored_pool": scored_pool,
        "job_preview": "",
    }
    atomic_write_json(os.path.join(DEFAULT_OUTPUT_DIR, "metadata.json"), metadata)

    logger.info(f"[default_cv] generated {len(selected)} chunks")
    return {
        "status":         "ok",
        "chunk_count":    len(selected),
        "last_generated": now,
    }
