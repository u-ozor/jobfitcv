# app/rewriters/rewrite_diff.py
# Runs rewrite hooks on a copy of resume_data and returns a structured
# before/after diff for items that changed. Does not modify the original.

import logging
from copy import deepcopy

from app.rewrites.summary_rewriter import rewrite_summary
from app.rewrites.experience_rewriter import rewrite_experience
from app.rewrites.project_rewriter import rewrite_projects

logger = logging.getLogger(__name__)

RECOMMEND_THRESHOLD = 0.65


def _tag(similarity):
    if similarity is None:
        return None
    return "recommended" if similarity < RECOMMEND_THRESHOLD else "optional"


def compute_rewrite_diff(resume_data: dict, job_text: str) -> list:
    """
    Returns a list of changed items with before/after content.
    Each item carries an index used by the apply endpoint.
    No output_dir passed → rewriters skip snapshot writes.
    """
    original = deepcopy(resume_data)
    rewritten = deepcopy(resume_data)

    rewritten = rewrite_summary(rewritten, job_text)
    rewritten = rewrite_experience(rewritten, job_text)
    rewritten = rewrite_projects(rewritten, job_text)

    items = []

    for i, (o, r) in enumerate(zip(
        original.get("summary", []),
        rewritten.get("summary", [])
    )):
        before, after = o.get("content", ""), r.get("content", "")
        if before != after:
            items.append({
                "index":        len(items),
                "chunk_id":     o.get("id", ""),
                "section":      "summary",
                "group_key":    None,
                "chunk_index":  i,
                "label":        o.get("title") or "Summary",
                "organization": "",
                "before":       before,
                "after":        after,
                "recommend":    _tag(o.get("similarity")),
            })

    for gk, group in original.get("experience", {}).items():
        rew_group = rewritten.get("experience", {}).get(gk, [])
        for i, (o, r) in enumerate(zip(group, rew_group)):
            before, after = o.get("content", ""), r.get("content", "")
            if before != after:
                items.append({
                    "index":        len(items),
                    "chunk_id":     o.get("id", ""),
                    "section":      "experience",
                    "group_key":    gk,
                    "chunk_index":  i,
                    "label":        o.get("title", ""),
                    "organization": o.get("organization", ""),
                    "before":       before,
                    "after":        after,
                    "recommend":    _tag(o.get("similarity")),
                })

    for gk, group in original.get("projects", {}).items():
        rew_group = rewritten.get("projects", {}).get(gk, [])
        for i, (o, r) in enumerate(zip(group, rew_group)):
            before, after = o.get("content", ""), r.get("content", "")
            if before != after:
                items.append({
                    "index":        len(items),
                    "chunk_id":     o.get("id", ""),
                    "section":      "project",
                    "group_key":    gk,
                    "chunk_index":  i,
                    "label":        o.get("title", ""),
                    "organization": o.get("organization", ""),
                    "before":       before,
                    "after":        after,
                    "recommend":    _tag(o.get("similarity")),
                })

    logger.info(f"[rewrite_diff] {len(items)} changed items")
    return items
