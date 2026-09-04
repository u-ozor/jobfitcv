# app/api/routers/wizard.py

import os
import json
import re
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.core.llm_client import generate_completion

router = APIRouter()

CHUNKS_PATH = "data/resume_chunks.json"

TYPE_PREFIX = {
    "experience":    "exp",
    "project":       "proj",
    "summary":       "sum",
    "skill":         "skl",
    "education":     "edu",
    "certification": "cert",
}

VALID_DISPLAY_GROUPS = [
    "languages", "tools", "security",
    "frameworks", "web", "cloud", "databases", "networking", "soft_skills",
]

CHUNK_SYSTEM = """\
You are a resume engineer converting plain-language entries into structured resume chunks.
Each chunk is one strong resume bullet point.
Output only valid JSON — no markdown fences, no explanation, no preamble."""

EXPERIENCE_PROMPT = """\
<input>
Title: {title}
Organization: {organization}
Period: {date_range}
Description:
{description}
</input>

<schema>
Return a JSON array. Each element is one bullet chunk:
{{
  "title": "{title}",
  "organization": "{organization}",
  "date_range": "{date_range}",
  "group_key": "<snake_case_org_year — e.g. acme_2023, globex_2020>",
  "content": "<one bullet: past-tense action verb + specific task + quantifiable outcome if present>",
  "tags": ["<3-6 lowercase kebab-case skill or tool tags>"],
  "keywords": ["<3-8 recruiter-phrasing terms: tool names, role terms, JD language — e.g. 'Python', 'CI/CD', 'Linux administration'>"],
  "priority": <integer 1-10 based on impact and specificity>,
  "track": <null or one of: "soc", "sysadmin", "backend", "cloud", "it", "ai">
}}
</schema>

Rules:
- Generate 2-5 bullets from the description — one chunk per bullet
- group_key must be identical across all chunks from this entry
- Each bullet starts with a past-tense action verb
- Preserve any numbers, metrics, or outcomes from the description
- Output ONLY the JSON array, nothing else"""

PROJECT_PROMPT = """\
<input>
Name: {title}
Organization: {organization}
Period: {date_range}
Links: {links}
Description:
{description}
</input>

<schema>
Return a JSON array. Each element is one bullet chunk:
{{
  "title": "{title}",
  "organization": "{organization}",
  "date_range": "{date_range}",
  "group_key": "<snake_case_project_name — e.g. ext_analyzer, iot_scanner>",
  "content": "<one bullet: what was built, how, and measurable outcome or feature>",
  "tags": ["<3-6 lowercase kebab-case tags>"],
  "keywords": ["<3-8 recruiter-phrasing terms: tool names, role terms, JD language — e.g. 'Docker', 'REST API', 'security monitoring'>"],
  "priority": <integer 1-10>,
  "track": <null or "soc" | "sysadmin" | "backend" | "cloud" | "it" | "ai">,
  "links": {links_json}
}}
</schema>

Rules:
- Generate 2-4 bullets covering distinct technical aspects
- group_key = snake_case of the project name, same for all bullets
- Output ONLY the JSON array"""

SUMMARY_PROMPT = """\
<input>
{description}
</input>

Convert the above into a polished professional summary chunk.

<schema>
Return a JSON array with exactly ONE element:
{{
  "title": "<concise role label — e.g. 'SOC Analyst', 'Backend Engineer', 'IT Systems Administrator'>",
  "organization": "",
  "date_range": "",
  "group_key": "<sum_auto>",
  "content": "<2-3 sentence professional summary. Specific, strong, zero clichés. Reference technologies, experience level, and track record.>",
  "tags": ["<5-8 skill tags>"],
  "keywords": ["<5-10 recruiter-phrasing terms: role titles, tool names, domain terms a JD would use>"],
  "priority": <integer 1-10>,
  "track": <null or "soc" | "sysadmin" | "backend" | "cloud" | "it" | "ai">
}}
</schema>

Output ONLY the JSON array."""

SKILLS_PROMPT = """\
<input>
Category: {{title}}
Skills: {{description}}
</input>

Valid display groups (pick the single best match — exact spelling required):
{display_groups}

<schema>
Return a JSON array with exactly ONE element:
{{{{
  "title": "{{title}}",
  "organization": "",
  "date_range": "",
  "group_key": "<snake_case_category — e.g. cloud_platforms, programming_languages>",
  "content": "{{title}}: <comma-separated list of skills in natural order>",
  "tags": ["<individual skill tags, lowercase kebab-case>"],
  "keywords": ["<3-8 recruiter-phrasing terms: tool names, role terms, JD language a recruiter would search for>"],
  "display_group": "<one of the valid display groups listed above — exact spelling>",
  "soft_skill": false,
  "priority": <integer 1-10>,
  "track": <null or "soc" | "sysadmin" | "backend" | "cloud" | "it" | "ai">
}}}}
</schema>

Output ONLY the JSON array."""


def _load_chunks() -> list:
    if not os.path.exists(CHUNKS_PATH):
        return []
    with open(CHUNKS_PATH) as f:
        return json.load(f)


CHUNKS_BACKUP_DIR = "data/chunks_backup"

def _save_chunks(chunks: list):
    # Backup at most once per 10 minutes — prevents burning through slots in a single editing session
    if os.path.exists(CHUNKS_PATH):
        os.makedirs(CHUNKS_BACKUP_DIR, exist_ok=True)
        existing = sorted(os.listdir(CHUNKS_BACKUP_DIR))
        skip_backup = False
        if existing:
            import time as _time
            newest = os.path.join(CHUNKS_BACKUP_DIR, existing[-1])
            if _time.time() - os.path.getmtime(newest) < 600:  # 10 min
                skip_backup = True
        if not skip_backup:
            from app.utils.time_utils import file_stamp
            import shutil as _shutil
            backup_path = os.path.join(CHUNKS_BACKUP_DIR, f"chunks_{file_stamp()}.json")
            _shutil.copy2(CHUNKS_PATH, backup_path)
            for old in existing[:-9]:  # keep last 10 total
                os.remove(os.path.join(CHUNKS_BACKUP_DIR, old))
    with open(CHUNKS_PATH, "w") as f:
        json.dump(chunks, f, indent=2)


def _next_id(chunks: list, chunk_type: str, offset: int = 0) -> str:
    prefix = TYPE_PREFIX.get(chunk_type, chunk_type[:3])
    nums = []
    for c in chunks:
        m = re.search(r"_(\d+)$", c.get("id", ""))
        if m and c.get("type") == chunk_type:
            nums.append(int(m.group(1)))
    n = max(nums, default=0) + 1 + offset
    return f"{prefix}_{n:03d}"


def _build_prompt(req) -> str:
    links_json = json.dumps(req.links or [])
    if req.type == "experience":
        return EXPERIENCE_PROMPT.format(
            title=req.title, organization=req.organization or "",
            date_range=req.date_range or "", description=req.description
        )
    if req.type == "project":
        return PROJECT_PROMPT.format(
            title=req.title, organization=req.organization or "Personal Project",
            date_range=req.date_range or "", description=req.description,
            links=req.links or [], links_json=links_json
        )
    if req.type == "summary":
        return SUMMARY_PROMPT.format(description=req.description)
    if req.type == "skill":
        return SKILLS_PROMPT.format(
            display_groups=" | ".join(VALID_DISPLAY_GROUPS)
        ).replace("{title}", req.title).replace("{description}", req.description)
    raise ValueError(f"Unknown chunk type: {req.type}")


class PreviewRequest(BaseModel):
    type: str
    title: str = ""
    organization: Optional[str] = ""
    date_range: Optional[str] = ""
    description: str
    track: Optional[str] = None
    priority: int = 7
    links: Optional[List[str]] = []


class CommitRequest(BaseModel):
    chunks: List[Dict[str, Any]]


@router.get("/wizard", response_class=HTMLResponse)
def wizard_page():
    path = os.path.join(os.path.dirname(__file__), "../../static/wizard.html")
    with open(os.path.abspath(path)) as f:
        return f.read()


@router.get("/wizard/status")
def wizard_status():
    chunks = _load_chunks()
    counts: Dict[str, int] = {}
    for c in chunks:
        t = c.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    next_ids = {t: _next_id(chunks, t) for t in TYPE_PREFIX}
    return {"chunk_counts": counts, "next_ids": next_ids, "total": len(chunks)}


WIZARD_PROVIDER = os.environ.get("WIZARD_PROVIDER", "anthropic")


@router.post("/wizard/preview")
def wizard_preview(req: PreviewRequest):
    if WIZARD_PROVIDER == "anthropic":
        try:
            import anthropic  # noqa: F401
        except ImportError:
            raise HTTPException(status_code=500, detail="anthropic package not installed")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    model = os.environ.get("WIZARD_MODEL", "claude-haiku-4-5-20251001")
    prompt = _build_prompt(req)

    raw = generate_completion(
        prompt,
        system=CHUNK_SYSTEM,
        provider=WIZARD_PROVIDER,
        model=model,
        max_tokens=1500
    ).strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        generated = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Model returned invalid JSON: {e}\n\nRaw: {raw[:300]}")

    if not isinstance(generated, list):
        generated = [generated]

    chunks = _load_chunks()
    result = []
    for i, chunk in enumerate(generated):
        if req.track and req.track != "auto":
            chunk["track"] = req.track
        if "priority" not in chunk:
            chunk["priority"] = req.priority
        stored_type = req.type

        raw_dg = chunk.get("display_group", "")
        display_group = raw_dg if raw_dg in VALID_DISPLAY_GROUPS else None

        ordered = {
            "id":           _next_id(chunks, req.type, offset=i),
            "type":         stored_type,
            "title":        chunk.get("title", ""),
            "organization": chunk.get("organization", ""),
            "date_range":   chunk.get("date_range", ""),
            "group_key":    chunk.get("group_key", ""),
            "content":      chunk.get("content", ""),
            "tags":         chunk.get("tags", []),
            "keywords":     chunk.get("keywords", []),
            "priority":     chunk.get("priority", req.priority),
            "active":       True,
            "track":        chunk.get("track"),
        }
        if stored_type == "skill":
            ordered["display_group"] = display_group or "tools"
            ordered["soft_skill"] = chunk.get("soft_skill", False)
        if "links" in chunk:
            ordered["links"] = chunk["links"]
        result.append(ordered)

    return {"chunks": result, "model": model}


@router.post("/wizard/commit")
def wizard_commit(req: CommitRequest):
    if not req.chunks:
        raise HTTPException(status_code=400, detail="No chunks to commit")

    chunks = _load_chunks()
    original = list(chunks)
    type_offsets: Dict[str, int] = {}
    added_ids = []

    for chunk in req.chunks:
        t = chunk.get("type", "experience")
        offset = type_offsets.get(t, 0)
        chunk["id"]     = _next_id(original, t, offset=offset)
        chunk["active"] = True
        type_offsets[t] = offset + 1
        added_ids.append(chunk["id"])
        chunks.append(chunk)

    _save_chunks(chunks)
    return {"added": len(req.chunks), "ids": added_ids, "total": len(chunks)}


# =========================================================
# GET /wizard/chunks  — list all chunks for the edit UI
# =========================================================

@router.get("/wizard/chunks")
def list_chunks():
    return {"chunks": _load_chunks()}


# =========================================================
# PUT /wizard/chunks/{chunk_id}  — update an existing chunk
# =========================================================

class ChunkUpdate(BaseModel):
    title:        Optional[str]       = None
    organization: Optional[str]       = None
    date_range:   Optional[str]       = None
    start_year:   Optional[int]       = None
    end_year:     Optional[int]       = None
    group_key:    Optional[str]       = None
    content:      Optional[str]       = None
    tags:         Optional[List[str]] = None
    keywords:     Optional[List[str]] = None
    priority:     Optional[int]       = None
    active:       Optional[bool]      = None
    track:        Optional[str]       = None
    display_group: Optional[str]      = None
    links:        Optional[List[str]] = None


@router.put("/wizard/chunks/{chunk_id}")
def update_chunk(chunk_id: str, body: ChunkUpdate):
    chunks = _load_chunks()
    target = next((c for c in chunks if c["id"] == chunk_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id!r} not found")

    update = body.model_dump(exclude_unset=True)
    for k, v in update.items():
        target[k] = v

    _save_chunks(chunks)

    from scripts.embed_resume import embed_resume_chunks
    embed_resume_chunks()

    return {"ok": True, "chunk": target}
