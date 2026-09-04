# app/generation/resume_builder.py
# normalisation layer

import re
from collections import defaultdict
from datetime import datetime
from app.core.profile_loader import load_profile

_CURRENT_YEAR = datetime.now().year

def group_chunks(chunks):
    grouped = defaultdict(list)
    for chunk in chunks:
        key = chunk.get("group_key") or chunk["id"]
        grouped[key].append(chunk)
    return grouped


def _group_sort_key(bullets: list) -> int:
    """Most recent year from first bullet's date_range; 'present' resolves to current year."""
    if not bullets:
        return 0
    # Prefer explicit end_year if set
    ey = bullets[0].get("end_year")
    if ey is not None:
        return int(ey) if ey != 0 else _CURRENT_YEAR
    dr = bullets[0].get("date_range", "")
    dr = re.sub(r"\bpresent\b", str(_CURRENT_YEAR), dr, flags=re.IGNORECASE)
    years = [int(y) for y in re.split(r"[-–]", dr) if y.strip().isdigit()]
    return max(years) if years else 0


def group_chunks_sorted(chunks):
    """Groups chunks by group_key, sorted most-recent-first by date_range.
    Within each group, bullets are ordered by seq (ascending) if set, else score descending."""
    grouped = group_chunks(chunks)
    for key, bullets in grouped.items():
        if all("seq" in b for b in bullets):
            bullets.sort(key=lambda b: b["seq"])
        # else: leave in the order they arrived (score descending from matcher)
    return dict(sorted(grouped.items(), key=lambda kv: _group_sort_key(kv[1]), reverse=True))


def normalize_skills(skill_chunks):
    """
    Converts flat skill chunks into template-ready grouped structure.

    Output shape:
    {
        "languages": [...],
        "tools": [...],
        "soft_skills": [...]
        other: 
    }

    Renderer should not understand raw chunk schema.
    """

    grouped = {}

    for skill in skill_chunks:

        group = skill.get("display_group", "other")

        grouped.setdefault(group, [])

        grouped[group].append(skill["title"])

    # dedupe
    for group in grouped:
        grouped[group] = sorted(
            list(set(grouped[group]))
        )

    return grouped


def build_resume_data(matched_chunks):
    """
    Converts matched chunks into canonical resume schema.

    This becomes the single normalized structure
    consumed by templates/renderers.
    """

    experiences = [
        c for c in matched_chunks
        if c["type"] == "experience"
    ]

    projects = [
        c for c in matched_chunks
        if c["type"] == "project"
    ]

    skills = [
        c for c in matched_chunks
        if c["type"] == "skill"
    ]

    summaries = [
        c for c in matched_chunks
        if c["type"] == "summary"
    ]

    education = sorted(
        [c for c in matched_chunks if c["type"] == "education"],
        key=lambda c: c.get("priority", 5),
        reverse=True
    )

    return {
        "header": load_profile(),

        "summary": summaries,

        "experience": group_chunks_sorted(experiences),

        "projects": group_chunks_sorted(projects),

        "education": education,

        "skills": normalize_skills(skills)
    }