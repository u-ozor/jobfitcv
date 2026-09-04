# app/api/routers/rewrites.py

import os
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.models import Job, Variant
from app.database.session import get_db
from app.rewrites.rewrite_diff import compute_rewrite_diff
from app.generation.renderer import render_html, render_markdown
from app.generation.artifact_writer import (
    write_html,
    write_edited_markdown,
    write_resume_data,
    ensure_variant_dirs,
)
from app.core.config import TEMPLATE_NAME
from app.utils.time_utils import local_timestamp, file_stamp

router = APIRouter()
logger = logging.getLogger(__name__)

PENDING_FILENAME = "pending_rewrite.json"


def _load_resume_data(output_path: str) -> dict:
    path = os.path.join(output_path, "generated", "resume_data.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="resume_data.json not found — generate first")
    with open(path) as f:
        return json.load(f)


def _rewrites_dir(output_path: str) -> str:
    d = os.path.join(output_path, "rewrites")
    os.makedirs(d, exist_ok=True)
    return d


def _is_safe_diff_filename(filename: str) -> bool:
    return (
        filename.startswith("diff_")
        and filename.endswith(".json")
        and "/" not in filename
        and ".." not in filename
    )


def _build_diff_payload(variant_id: str, items: list) -> dict:
    return {
        "variant_id":        variant_id,
        "created_at":        local_timestamp(),
        "item_count":        len(items),
        "recommended_count": sum(1 for i in items if i.get("recommend") == "recommended"),
        "items":             items,
    }


# =========================================================
# POST /variants/{variant_id}/rewrite/preview
# =========================================================

@router.post("/{variant_id}/rewrite/preview")
def preview_rewrite(variant_id: str, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    job = db.query(Job).filter(Job.id == v.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    logger.info(f"[rewrite] preview started variant={variant_id}")

    resume_data = _load_resume_data(v.output_path)
    items = compute_rewrite_diff(resume_data, job.raw_text)

    payload = _build_diff_payload(variant_id, items)

    pending_path = os.path.join(v.output_path, PENDING_FILENAME)
    with open(pending_path, "w") as f:
        json.dump(payload, f, indent=2)

    rdir = _rewrites_dir(v.output_path)
    diff_path = os.path.join(rdir, f"diff_{file_stamp()}.json")
    with open(diff_path, "w") as f:
        json.dump(payload, f, indent=2)

    existing = sorted(
        f for f in os.listdir(rdir) if f.startswith("diff_") and f.endswith(".json")
    )
    for old in existing[:-10]:
        os.remove(os.path.join(rdir, old))

    logger.info(f"[rewrite] preview complete variant={variant_id} items={len(items)}")
    return {"variant_id": variant_id, "items": items}


# =========================================================
# GET /variants/{variant_id}/rewrite/pending
# =========================================================

@router.get("/{variant_id}/rewrite/pending")
def get_pending_rewrite(variant_id: str, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    pending_path = os.path.join(v.output_path, PENDING_FILENAME)
    if not os.path.exists(pending_path):
        raise HTTPException(status_code=404, detail="No pending rewrite")

    with open(pending_path) as f:
        return json.load(f)


# =========================================================
# GET /variants/{variant_id}/rewrite/diffs
# Lists saved diff snapshots, newest first.
# =========================================================

@router.get("/{variant_id}/rewrite/diffs")
def list_rewrite_diffs(variant_id: str, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    rdir = os.path.join(v.output_path, "rewrites")
    if not os.path.exists(rdir):
        return []

    filenames = sorted(
        f for f in os.listdir(rdir) if f.startswith("diff_") and f.endswith(".json")
    )

    result = []
    for filename in reversed(filenames):
        try:
            with open(os.path.join(rdir, filename)) as f:
                data = json.load(f)
            result.append({
                "filename":          filename,
                "created_at":        data.get("created_at", ""),
                "item_count":        data.get("item_count", len(data.get("items", []))),
                "recommended_count": data.get("recommended_count", 0),
            })
        except Exception:
            pass

    return result


# =========================================================
# GET /variants/{variant_id}/rewrite/diffs/{filename}
# Loads one saved diff by filename.
# =========================================================

@router.get("/{variant_id}/rewrite/diffs/{filename}")
def get_rewrite_diff(variant_id: str, filename: str, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    if not _is_safe_diff_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = os.path.join(v.output_path, "rewrites", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Diff not found")

    with open(path) as f:
        return json.load(f)


# =========================================================
# POST /variants/{variant_id}/rewrite/apply
# =========================================================

class ApplyRequest(BaseModel):
    approved_indices:  List[int]
    source_filename:   Optional[str] = None


@router.post("/{variant_id}/rewrite/apply")
def apply_rewrite(variant_id: str, body: ApplyRequest, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    if body.source_filename:
        if not _is_safe_diff_filename(body.source_filename):
            raise HTTPException(status_code=400, detail="Invalid source_filename")
        source_path = os.path.join(v.output_path, "rewrites", body.source_filename)
        if not os.path.exists(source_path):
            raise HTTPException(status_code=404, detail="Source diff not found")
        with open(source_path) as f:
            pending = json.load(f)
    else:
        pending_path = os.path.join(v.output_path, PENDING_FILENAME)
        if not os.path.exists(pending_path):
            raise HTTPException(status_code=404, detail="No pending rewrite — run preview first")
        with open(pending_path) as f:
            pending = json.load(f)

    items = pending["items"]
    resume_data = _load_resume_data(v.output_path)

    applied    = 0
    mismatches = []

    for idx in body.approved_indices:
        if idx >= len(items):
            continue
        item    = items[idx]
        section = item["section"]
        gk      = item.get("group_key")
        ci      = item["chunk_index"]
        before  = item.get("before", "")
        after   = item["after"]

        if section == "summary":
            summaries = resume_data.get("summary", [])
            if ci < len(summaries):
                if summaries[ci]["content"] != before:
                    mismatches.append(idx)
                    continue
                summaries[ci]["content"] = after
                applied += 1

        elif section == "experience":
            group = resume_data.get("experience", {}).get(gk, [])
            if ci < len(group):
                if group[ci]["content"] != before:
                    mismatches.append(idx)
                    continue
                group[ci]["content"] = after
                applied += 1

        elif section == "project":
            group = resume_data.get("projects", {}).get(gk, [])
            if ci < len(group):
                if group[ci]["content"] != before:
                    mismatches.append(idx)
                    continue
                group[ci]["content"] = after
                applied += 1

    dirs     = ensure_variant_dirs(v.output_path)
    html     = render_html(resume_data, template_name=TEMPLATE_NAME)
    markdown = render_markdown(resume_data)

    write_html(dirs["generated"], html)
    write_edited_markdown(dirs["edited"], markdown)
    write_resume_data(dirs["generated"], resume_data)

    # Only delete pending if applying from it
    if not body.source_filename:
        pending_path = os.path.join(v.output_path, PENDING_FILENAME)
        if os.path.exists(pending_path):
            os.remove(pending_path)

    logger.info(
        f"[rewrite] applied variant={variant_id} applied={applied} mismatches={len(mismatches)}"
    )
    return {"status": "ok", "applied": applied, "mismatches": mismatches}


# =========================================================
# DELETE /variants/{variant_id}/rewrite/pending
# =========================================================

@router.delete("/{variant_id}/rewrite/pending")
def discard_rewrite(variant_id: str, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    pending_path = os.path.join(v.output_path, PENDING_FILENAME)
    if os.path.exists(pending_path):
        os.remove(pending_path)

    return {"status": "ok"}
