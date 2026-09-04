# app/api/routers/chunk_review.py

import os
import json
import logging
import requests

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.models import Variant, Job
from app.database.session import get_db
from app.generation.resume_builder import build_resume_data
from app.generation.renderer import render_html, render_markdown
from app.generation.artifact_writer import (
    write_resume_bundle,
    write_edited_markdown,
    ensure_variant_dirs,
)
from app.core.config import TEMPLATE_NAME, QUOTAS
from app.core.llm_client import generate_completion
from app.utils.atomic_io import atomic_write_json

router = APIRouter()
logger = logging.getLogger(__name__)

CHUNKS_PATH     = "data/resume_chunks.json"
OUTPUT_ROOT     = "outputs/resumes"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY", "")

CANDIDATE_FLOOR = 0.42   # score below this → dropped tier


# =========================================================
# Helpers
# =========================================================

def _load_metadata(output_path: str) -> dict:
    path = os.path.join(output_path, "metadata.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="metadata.json not found — generate first")
    with open(path) as f:
        return json.load(f)


def _save_metadata(output_path: str, metadata: dict):
    path = os.path.join(output_path, "metadata.json")
    atomic_write_json(path, metadata)


def _load_chunks_map() -> dict:
    with open(CHUNKS_PATH) as f:
        chunks = json.load(f)
    return {c["id"]: c for c in chunks}


def _compute_flags(entry: dict) -> list:
    flags = []
    sim  = entry.get("similarity", 0)
    kw   = entry.get("keyword_score", 0)
    pri  = entry.get("priority_score", 0)

    if sim >= 0.70:
        flags.append("strong_signal")
    if sim < 0.56:
        flags.append("marginal_fit")
    if kw == 0.0:
        flags.append("no_keyword_overlap")
    elif kw * 8 < 3:          # fewer than 3 raw matches
        flags.append("low_keyword_overlap")
    if pri >= 0.9 and sim < 0.60:
        flags.append("priority_carried")

    return flags


def _enrich(entry: dict, chunk: dict, ollama_cache: dict) -> dict:
    return {
        "id":               entry["id"],
        "type":             chunk.get("type", ""),
        "title":            chunk.get("title", entry["id"]),
        "content":          chunk.get("content", ""),
        "score":            entry["score"],
        "similarity":       entry["similarity"],
        "keyword_score":    entry["keyword_score"],
        "priority_score":   entry["priority_score"],
        "selected":         entry["selected"],
        "cut_reason":       entry["cut_reason"],
        "flags":            _compute_flags(entry),
        "ollama_assessment": ollama_cache.get(entry["id"]),
    }


# =========================================================
# GET /variants/{variant_id}/chunk-review
# =========================================================

@router.get("/{variant_id}/chunk-review")
def get_chunk_review(variant_id: str, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    metadata    = _load_metadata(v.output_path)
    scored_pool = metadata.get("scored_pool", [])
    if not scored_pool:
        raise HTTPException(status_code=404, detail="No scored_pool in metadata — regenerate this variant")

    chunk_map     = _load_chunks_map()
    ollama_cache  = metadata.get("ollama_assessments", {})

    job          = db.query(Job).filter(Job.id == v.job_id).first()
    job_raw_text = (job.raw_text if job else "") or ""

    selected   = []
    candidates = []
    dropped    = []

    for entry in scored_pool:
        chunk = chunk_map.get(entry["id"], {})
        enriched = _enrich(entry, chunk, ollama_cache)

        if entry["cut_reason"] is None:
            selected.append(enriched)
        elif entry["score"] >= CANDIDATE_FLOOR:
            candidates.append(enriched)
        else:
            dropped.append(enriched)

    return {
        "variant":      variant_id,
        "job_id":       v.job_id,
        "job_preview":  metadata.get("job_preview", ""),
        "job_raw_text": job_raw_text,
        "quotas":       QUOTAS,
        "tiers": {
            "selected":   selected,
            "candidates": candidates,
            "dropped":    dropped,
        },
    }


# =========================================================
# POST /variants/{variant_id}/chunk-review/preview
# =========================================================

class PreviewRequest(BaseModel):
    chunk_ids: List[str]


@router.post("/{variant_id}/chunk-review/preview")
def preview_selection(variant_id: str, body: PreviewRequest, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    chunk_map = _load_chunks_map()
    chunks    = [chunk_map[cid] for cid in body.chunk_ids if cid in chunk_map]

    resume_data = build_resume_data(chunks)
    html        = render_html(resume_data, template_name=TEMPLATE_NAME)

    return {"html": html}


# =========================================================
# POST /variants/{variant_id}/chunk-review/apply
# =========================================================

class ApplyRequest(BaseModel):
    chunk_ids:         List[str]
    summary_override:  Optional[str] = None
    rewrite_overrides: Optional[dict] = None   # {chunk_id: after_content}
    confirm_protected: bool = False    # required true to apply to a general-purpose CV


@router.post("/{variant_id}/chunk-review/apply")
def apply_selection(variant_id: str, body: ApplyRequest, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    job = db.query(Job).filter(Job.id == v.job_id).first()
    if job and job.is_general_purpose and not body.confirm_protected:
        raise HTTPException(
            status_code=409,
            detail=f"'{variant_id}' is a general-purpose CV (not tied to one job posting) — "
                   f"pass confirm_protected: true to apply anyway."
        )

    chunk_map = _load_chunks_map()
    chunks    = [chunk_map[cid] for cid in body.chunk_ids if cid in chunk_map]

    if body.rewrite_overrides:
        chunks = [
            {**c, "content": body.rewrite_overrides[c["id"]]}
            if c["id"] in body.rewrite_overrides else c
            for c in chunks
        ]

    resume_data = build_resume_data(chunks)

    if body.summary_override and resume_data.get("summary"):
        resume_data["summary"][0]["content"] = body.summary_override

    html        = render_html(resume_data, template_name=TEMPLATE_NAME)
    markdown    = render_markdown(resume_data)

    artifacts = write_resume_bundle(
        output_dir=v.output_path,
        markdown=markdown,
        html=html,
        resume_data=resume_data,
    )

    dirs = ensure_variant_dirs(v.output_path)
    write_edited_markdown(dirs["edited"], markdown)

    metadata = _load_metadata(v.output_path)
    metadata["chunk_ids"] = body.chunk_ids
    _save_metadata(v.output_path, metadata)

    logger.info(f"[chunk_review] apply variant={variant_id} chunks={len(chunks)}")
    return {"status": "ok", "artifacts": artifacts}


# =========================================================
# POST /variants/{variant_id}/chunk-review/assess
# =========================================================

class AssessRequest(BaseModel):
    chunk_ids:            List[str]
    job_preview_override: Optional[str] = None


def _ollama_assess(job_preview: str, chunk_content: str, tags: list[str] | None = None) -> str:
    tags_line = f"\nSkills/tools: {', '.join(tags)}" if tags else ""
    prompt = (
        f"[INST]\nYou are a strict resume screener.\n\n"
        f"Job posting excerpt:\n{job_preview}\n\n"
        f"Resume bullet:\n{chunk_content}{tags_line}\n\n"
        "Does this bullet directly demonstrate a skill, tool, or experience "
        "explicitly listed as required or preferred in the job posting above?\n"
        "RULE: If the specific skill, tool, technology, or domain in the bullet is NOT "
        "explicitly named in the job posting excerpt, you MUST start with \"Weak:\". "
        "Do NOT infer, extrapolate, or assume requirements from vague phrases like "
        "\"technical background\" or \"relevant experience\".\n"
        "Reply in exactly one sentence. Start with \"Relevant:\" only if there is a "
        "clear, direct match to a stated requirement. Start with \"Weak:\" if the "
        "match is vague, generic, or the requirement is not mentioned in the excerpt.\n[/INST]"
    )

    for model in ("mistral:latest", "qwen2.5-coder:7b"):
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.2}},
                timeout=90,
            )
            if resp.status_code == 200:
                return resp.json()["response"].strip()
        except Exception:
            continue

    return "Assessment unavailable — Ollama not reachable."


@router.post("/{variant_id}/chunk-review/assess")
def assess_chunks(variant_id: str, body: AssessRequest, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    metadata     = _load_metadata(v.output_path)
    job          = db.query(Job).filter(Job.id == v.job_id).first()
    job_preview  = body.job_preview_override or (job.raw_text if job else None) or metadata.get("job_preview", "")
    force_rerun  = bool(body.job_preview_override)
    cache        = metadata.setdefault("ollama_assessments", {})
    chunk_map    = _load_chunks_map()
    assessments  = {}

    for cid in body.chunk_ids:
        if cid in cache and not force_rerun:
            assessments[cid] = cache[cid]
            continue
        chunk   = chunk_map.get(cid)
        if not chunk:
            continue
        content = chunk.get("content", "")
        tags    = chunk.get("tags", [])
        result  = _ollama_assess(job_preview, content, tags)
        cache[cid]       = result
        assessments[cid] = result

    _save_metadata(v.output_path, metadata)
    logger.info(f"[chunk_review] assessed variant={variant_id} chunks={len(assessments)}")
    return {"assessments": assessments}


# =========================================================
# POST /variants/{variant_id}/summary/synthesize
# =========================================================

class SynthesizeRequest(BaseModel):
    chunk_ids: List[str]


SUMMARY_SYNTH_PROVIDER = os.environ.get("SUMMARY_SYNTH_PROVIDER", "anthropic")
SUMMARY_SYNTH_MODEL    = os.environ.get("SUMMARY_SYNTH_MODEL", "claude-haiku-4-5-20251001")


def _haiku_synthesize(job_text: str, chunk_contents: list, current_summary: str) -> str:
    sections = "\n\n".join(chunk_contents)
    prompt = (
        f"Job role: {job_text}\n\n"
        f"These resume sections are selected for this application:\n{sections}\n\n"
        "Write a 3-sentence professional summary that:\n"
        "- Opens with identity and the strongest credential for this specific role\n"
        "- Highlights 2-3 themes visible across the sections above, without restating specific metrics or event IDs already in those sections\n"
        "- Closes with what this candidate brings to this role\n"
        "- No \"I\", no bullet points, plain paragraph"
    )

    return generate_completion(
        prompt,
        provider=SUMMARY_SYNTH_PROVIDER,
        model=SUMMARY_SYNTH_MODEL,
        max_tokens=200
    ).strip()


@router.post("/{variant_id}/summary/synthesize")
def synthesize_summary(variant_id: str, body: SynthesizeRequest, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    job = db.query(Job).filter(Job.id == v.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    chunk_map = _load_chunks_map()

    # Exclude summary chunks from the content list (we're synthesizing a new one)
    contents = [
        chunk_map[cid]["content"]
        for cid in body.chunk_ids
        if cid in chunk_map and chunk_map[cid].get("type") != "summary"
    ]

    # Current summary for display
    current_summary = ""
    for cid in body.chunk_ids:
        if cid in chunk_map and chunk_map[cid].get("type") == "summary":
            current_summary = chunk_map[cid].get("content", "")
            break

    if not contents:
        raise HTTPException(status_code=400, detail="No non-summary chunks in selection")

    if SUMMARY_SYNTH_PROVIDER == "anthropic" and not ANTHROPIC_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")

    proposed = _haiku_synthesize(job.raw_text, contents, current_summary)

    logger.info(f"[chunk_review] synthesized summary variant={variant_id}")
    return {"proposed": proposed, "current": current_summary}


# =========================================================
# GET /variants/{variant_id}/chunk-review-ui
# =========================================================

CHUNK_REVIEW_HTML = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "extension", "chunk_review.html"
)


@router.get("/{variant_id}/chunk-review-ui", response_class=HTMLResponse)
def chunk_review_ui(variant_id: str, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    html_path = os.path.normpath(CHUNK_REVIEW_HTML)
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="chunk_review.html not found")

    with open(html_path, encoding="utf-8") as f:
        return f.read()
