# app/api/routers/jobs.py

import uuid
import os
import shutil
import hashlib
import logging
from typing import Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.models import Job, Variant
from app.database.session import get_db, SessionLocal
from app.jobs.taxonomy_classifier import classify_job
from app.pipelines.generation_pipeline import generate_resume_pipeline
from app.utils.time_utils import local_timestamp
from app.jobs.cleaner import clean_job_text
from app.jobs.fit_scorer import score_role_fit
from app.jobs.summarizer import summarize_job_text

router = APIRouter()
logger = logging.getLogger(__name__)


# =========================================================
# Schemas
# =========================================================

class JobIngest(BaseModel):
    raw_text: str
    url: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    job_category: Optional[str] = "Main"


class JobPatch(BaseModel):
    app_status:            Optional[str] = None
    notes:                 Optional[str] = None
    figurative_assessment: Optional[str] = None
    job_category:          Optional[str] = None
    week_label:            Optional[str] = None


class CleanPreviewRequest(BaseModel):
    raw_text: str


# =========================================================
# POST /jobs/clean_preview
# =========================================================

@router.post("/clean_preview")
def clean_preview(body: CleanPreviewRequest):
    return {"cleaned_text": clean_job_text(body.raw_text)}


# =========================================================
# POST /jobs/ingest
# =========================================================

def _normalize_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return url
    try:
        p = urlparse(url)
        if "indeed.com" in p.netloc:
            from urllib.parse import parse_qs, urlencode
            keep = {k: v for k, v in parse_qs(p.query).items() if k == "jk"}
            return urlunparse(p._replace(query=urlencode(keep, doseq=True), fragment=""))
        return urlunparse(p._replace(query="", fragment=""))
    except Exception:
        return url


def _text_fingerprint(text: str) -> str:
    # Use up to 2000 chars so company-boilerplate intros don't collide across different roles
    return hashlib.sha256(text[:2000].encode()).hexdigest()[:16]


def _week_label(ts: str) -> str:
    """Return the Monday of the week containing ts as YYYY-MM-DD."""
    try:
        dt = datetime.fromisoformat(ts)
        monday = dt.date() - timedelta(days=dt.weekday())
        return monday.isoformat()
    except Exception:
        return None


@router.post("/ingest")
def ingest_job(body: JobIngest, db: Session = Depends(get_db)):
    # The panel UI already blocks submission without a company client-side —
    # this is the server-side backstop for any direct API caller (including
    # batch-review sessions) that bypasses the UI. "—" is accepted as the
    # explicit marker for an intentional general-purpose CV (matches the
    # convention default_cv.py already uses) — only a truly empty/missing
    # company is rejected.
    if not body.company:
        raise HTTPException(
            status_code=400,
            detail='company is required — pass "—" explicitly if this is intentionally a general-purpose CV, not a specific job posting.'
        )

    normalized_url = _normalize_url(body.url)

    if normalized_url:
        existing = db.query(Job).filter(Job.url == normalized_url).first()
        if existing:
            return {
                "job_id": existing.id,
                "track": existing.track,
                "focus": existing.focus,
                "status": existing.status,
                "duplicate": True
            }

    cleaned_text = clean_job_text(body.raw_text)
    fingerprint  = _text_fingerprint(cleaned_text)

    # Secondary dedup — catches same job on different boards or jobs with no URL
    fp_existing = db.query(Job).filter(Job.text_fingerprint == fingerprint).first()
    if fp_existing:
        return {
            "job_id": fp_existing.id,
            "track": fp_existing.track,
            "focus": fp_existing.focus,
            "status": fp_existing.status,
            "duplicate": True
        }

    taxonomy   = classify_job(cleaned_text)
    fit        = score_role_fit(body.title or "", cleaned_text)
    ts         = local_timestamp()
    job_id     = str(uuid.uuid4())

    # Full verbatim posting — interview reference only, never fed into scoring.
    jd_actual_dir = os.path.join("outputs", "jobs", job_id)
    os.makedirs(jd_actual_dir, exist_ok=True)
    with open(os.path.join(jd_actual_dir, "jd_actual.txt"), "w") as f:
        f.write(body.raw_text)

    # Short structured summary — this is what scoring/embedding, Ollama assess,
    # and rewrite hooks actually consume. Falls back to the cleaned full text
    # if the summarizer call fails, so ingestion never breaks over this.
    try:
        summarized_text = summarize_job_text(cleaned_text)
    except Exception as e:
        logger.warning(f"[ingest] JD summarization failed, falling back to cleaned text: {e}")
        summarized_text = cleaned_text

    job = Job(
        id=job_id,
        url=normalized_url,
        title=body.title,
        company=body.company,
        raw_text=summarized_text,
        track=taxonomy["track"],
        focus=taxonomy["focus"],
        status="ingested",
        text_fingerprint=fingerprint,
        ingested_at=ts,
        role_match=fit["score"],
        week_label=_week_label(ts),
        job_category=body.job_category or "Main",
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info(f"[ingest] job={job.id} track={job.track} focus={job.focus} role_match={fit['score']}")
    return {
        "job_id":     job.id,
        "track":      job.track,
        "focus":      job.focus,
        "status":     job.status,
        "role_match": fit["score"],
        "role_label": fit["label"]
    }


# =========================================================
# GET /jobs
# =========================================================

@router.get("/")
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(Job).order_by(Job.ingested_at.desc()).all()
    return [
        {
            "job_id":     j.id,
            "title":      j.title,
            "company":    j.company,
            "url":        j.url,
            "track":      j.track,
            "focus":      j.focus,
            "status":     j.status,
            "app_status":            j.app_status,
            "notes":                 j.notes,
            "figurative_assessment": j.figurative_assessment,
            "ingested_at":           j.ingested_at,
            "role_match":            j.role_match,
            "week_label":            j.week_label,
            "job_category":          j.job_category or "Main",
        }
        for j in jobs
    ]


# =========================================================
# GET /jobs/{job_id}
# =========================================================

@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "title": job.title,
        "company": job.company,
        "url": job.url,
        "track": job.track,
        "focus": job.focus,
        "status": job.status,
        "app_status": job.app_status,
        "notes": job.notes,
        "ingested_at": job.ingested_at,
        "raw_text": job.raw_text
    }


# =========================================================
# GET /jobs/{job_id}/jd-actual
# =========================================================

@router.get("/{job_id}/jd-actual")
def get_jd_actual(job_id: str):
    path = f"outputs/jobs/{job_id}/jd_actual.txt"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No actual JD file for this job. Re-ingest with WebFetch to generate one.")
    from fastapi.responses import PlainTextResponse
    with open(path) as f:
        return PlainTextResponse(f.read())


# =========================================================
# POST /jobs/{job_id}/generate
# =========================================================

def _run_pipeline(job_id: str, raw_text: str, track: str, focus: str):
    """Background task — runs pipeline, writes variant row, updates job status."""
    db = SessionLocal()
    try:
        logger.info(f"[generate] started job={job_id} track={track} focus={focus}")
        result = generate_resume_pipeline(
            job_text=raw_text,
            track=track,
            focus=focus,
            job_id=job_id
        )
        v = result["variant"]

        db.add(Variant(
            id=job_id,
            job_id=job_id,
            track=track,
            focus=focus,
            version=1,
            output_path=v["output_dir"],
            reused=0,
            created_at=local_timestamp()
        ))

        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "done"

        db.commit()
        logger.info(f"[generate] done job={job_id} output={v['output_dir']}")

    except Exception as e:
        logger.error(f"[generate] failed job={job_id} error={e}", exc_info=True)
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "error"
            db.commit()
        raise

    finally:
        db.close()


@router.patch("/{job_id}")
def patch_job(job_id: str, body: JobPatch, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if body.app_status is not None:
        job.app_status = body.app_status
    if body.notes is not None:
        job.notes = body.notes
    if body.figurative_assessment is not None:
        job.figurative_assessment = body.figurative_assessment
    if body.job_category is not None:
        job.job_category = body.job_category
    if body.week_label is not None:
        job.week_label = body.week_label
    db.commit()
    return {"ok": True}


@router.delete("/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db), confirm_protected: bool = False):
    if job_id == "default-cv":
        raise HTTPException(status_code=400, detail="Cannot delete the system-seeded default CV")
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.is_general_purpose and not confirm_protected:
        raise HTTPException(
            status_code=409,
            detail=f"'{job_id}' is a general-purpose CV (not tied to one job posting) — "
                   f"pass ?confirm_protected=true to delete anyway."
        )
    variants = db.query(Variant).filter(Variant.job_id == job_id).all()
    for v in variants:
        if v.output_path and os.path.exists(v.output_path):
            shutil.rmtree(v.output_path)
        db.delete(v)
    cl_dir = os.path.join("outputs", "cover_letters", job_id)
    if os.path.exists(cl_dir):
        shutil.rmtree(cl_dir)
    db.delete(job)
    db.commit()
    return {"ok": True}


@router.post("/{job_id}/generate")
def generate_for_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    force: bool = False
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "generating":
        raise HTTPException(status_code=409, detail="Generation already in progress")

    if not force:
        existing = db.query(Variant).filter(Variant.job_id == job_id).first()
        if existing:
            job.status = "done"
            db.commit()
            return {"job_id": job_id, "status": "done", "variant_id": existing.id}
    else:
        existing = db.query(Variant).filter(Variant.job_id == job_id).first()
        if existing:
            if existing.output_path and os.path.exists(existing.output_path):
                shutil.rmtree(existing.output_path)
            db.delete(existing)
            db.commit()

    job.status = "generating"
    db.commit()

    background_tasks.add_task(_run_pipeline, job.id, job.raw_text, job.track, job.focus)
    return {"job_id": job_id, "status": "generating"}


