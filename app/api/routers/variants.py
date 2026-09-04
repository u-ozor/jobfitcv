# app/api/routers/variants.py

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.models import Variant
from app.database.session import get_db


class MarkdownBody(BaseModel):
    markdown: str

router = APIRouter()


# =========================================================
# GET /variants
# =========================================================

@router.get("/")
def list_variants(db: Session = Depends(get_db)):
    variants = db.query(Variant).order_by(Variant.created_at.desc()).all()
    return [
        {
            "id": v.id,
            "job_id": v.job_id,
            "track": v.track,
            "focus": v.focus,
            "version": v.version,
            "created_at": v.created_at
        }
        for v in variants
    ]


# =========================================================
# GET /variants/{variant_id}
# =========================================================

@router.get("/{variant_id}")
def get_variant(variant_id: str, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    return {
        "id": v.id,
        "job_id": v.job_id,
        "track": v.track,
        "focus": v.focus,
        "version": v.version,
        "output_path": v.output_path,
        "reused": bool(v.reused),
        "created_at": v.created_at
    }


# =========================================================
# GET /variants/{variant_id}/html
# =========================================================

@router.get("/{variant_id}/html", response_class=HTMLResponse)
def get_variant_html(variant_id: str, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    html_path = os.path.join(v.output_path, "generated", "resume.html")
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="HTML artifact not found")

    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


# =========================================================
# GET /variants/{variant_id}/pdf
# =========================================================

@router.get("/{variant_id}/markdown", response_class=PlainTextResponse)
def get_variant_markdown(variant_id: str, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    md_path = os.path.join(v.output_path, "edited", "resume.edited.md")
    if not os.path.exists(md_path):
        raise HTTPException(status_code=404, detail="Edited markdown not found")
    with open(md_path, "r", encoding="utf-8") as f:
        return f.read()


@router.post("/{variant_id}/regenerate")
def regenerate_variant(variant_id: str, body: MarkdownBody, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    md_path = os.path.join(v.output_path, "edited", "resume.edited.md")
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(body.markdown)
    from app.services.markdown_rebuild_service import regenerate_resume
    result = regenerate_resume(v.output_path)
    return {"status": "ok", "artifacts": result["artifacts"]}


@router.get("/{variant_id}/pdf")
def get_variant_pdf(variant_id: str, db: Session = Depends(get_db)):
    v = db.query(Variant).filter(Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    pdf_path = os.path.join(v.output_path, "generated", "resume.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF artifact not found on this instance")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{variant_id}.pdf"
    )
