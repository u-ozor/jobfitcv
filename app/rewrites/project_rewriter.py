# app/rewriters/project_rewriter.py

import logging
from copy import deepcopy
from app.core.llm_client import generate_completion

logger = logging.getLogger(__name__)

from app.rewrites.manager import (
    save_rewrite_snapshot
)

from app.rewrites.validator import is_rewrite_acceptable, MAX_PROJECT_WORDS

def rewrite_projects(
    resume_data, 
    job_text,
    output_dir=None
):
    
    """
    Improves project descriptions only.
    """

    if not resume_data.get("projects"):
        return resume_data

    # -----------------------------------------
    # Snapshot BEFORE rewrite
    # -----------------------------------------
    before = deepcopy(
        resume_data["projects"]
    )
    
    # -----------------------------------------
    # Rewrite bullets
    # -----------------------------------------
    
    for group in resume_data["projects"].values():

        for bullet in group:

            original = bullet["content"]

            prompt = f"""<job_context>
{job_text}
</job_context>

<project_bullet>
{original}
</project_bullet>

Rewrite this project bullet for ATS alignment with the job context.
Rules: preserve all facts and technologies, no invented features, one sentence, max 45 words, preserve technical specificity.
Output ONLY the rewritten bullet — no explanation, no quotes, no labels."""

            rewritten = generate_completion(
                prompt
            ).strip()

            if is_rewrite_acceptable(original, rewritten, max_words=MAX_PROJECT_WORDS):
                bullet["content"] = rewritten.replace("\n", " ")
            else:
                logger.info("[proj_rewriter] validator rejected: %s", rewritten[:80])

    # -----------------------------------------
    # Snapshot AFTER rewrite
    # -----------------------------------------

    after = resume_data["projects"]

    # -----------------------------------------
    # Save rewrite snapshot
    # -----------------------------------------

    if output_dir and before != after:

        save_rewrite_snapshot(
            output_dir=output_dir,
            section="projects",
            before_data=before,
            after_data=after
        )

    return resume_data