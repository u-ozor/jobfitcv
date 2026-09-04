# app/rewriters/experience_rewriter.py

import logging
from copy import deepcopy

from app.core.llm_client import generate_completion

from app.rewrites.manager import (
    save_rewrite_snapshot
)

from app.rewrites.validator import is_rewrite_acceptable

logger = logging.getLogger(__name__)

MAX_BULLET_WORDS = 38

def rewrite_experience(
    resume_data,
    job_text,
    output_dir=None
):
    """
    Lightweight ATS rewrite layer.

    STRICT RULES:
    - preserve factual meaning
    - preserve single bullet structure
    - no fabrication
    - no markdown
    - no lists
    - no headings
    - concise only
    """

    if not resume_data.get("experience"):
        return resume_data

    # -----------------------------------------
    # Snapshot BEFORE rewrite
    # -----------------------------------------

    before = deepcopy(
        resume_data["experience"]
    )

    # -----------------------------------------
    # Rewrite bullets
    # -----------------------------------------

    for group in resume_data["experience"].values():

        for bullet in group:

            original = bullet["content"]

            prompt = f"""<job_context>
{job_text}
</job_context>

<bullet>
{original}
</bullet>

Rewrite this resume bullet for ATS alignment with the job context.
Rules: preserve all facts and technologies, no invented experience, one sentence, max {MAX_BULLET_WORDS} words, start with an action verb.
Output ONLY the rewritten bullet — no explanation, no quotes, no labels."""

            rewritten = generate_completion(
                prompt
            ).strip()

            if is_rewrite_acceptable(original, rewritten):
                bullet["content"] = rewritten.replace("\n", " ")
            else:
                logger.info("[exp_rewriter] validator rejected: %s", rewritten[:80])

    # -----------------------------------------
    # Snapshot AFTER rewrite
    # -----------------------------------------

    after = resume_data["experience"]

    # -----------------------------------------
    # Save rewrite snapshot
    # -----------------------------------------

    if output_dir and before != after:

        save_rewrite_snapshot(
            output_dir=output_dir,
            section="experience",
            before_data=before,
            after_data=after
        )

    return resume_data