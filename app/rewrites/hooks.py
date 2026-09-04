# app/rewrites/hooks.py

from app.rewrites.summary_rewriter import (
    rewrite_summary
)

from app.rewrites.experience_rewriter import (
    rewrite_experience
)

from app.rewrites.project_rewriter import (
    rewrite_projects
)

from app.core.config import (
    ENABLE_REWRITES,
    REWRITE_SECTIONS
)

# =========================================================
# Main rewrite pipeline
# =========================================================

def apply_rewrite_hooks(
    resume_data,
    job_text,
    output_dir=None
):
    """
    Applies controlled section rewrites.

    Rules:
    - preserve structure
    - preserve factual accuracy
    - improve ATS alignment
    """
    if not ENABLE_REWRITES:
        return resume_data
        
    if REWRITE_SECTIONS.get("summary"):    
        resume_data = rewrite_summary(
            resume_data,
            job_text,
            output_dir
        )

    if REWRITE_SECTIONS.get("experience"):
        resume_data = rewrite_experience(
            resume_data,
            job_text,
            output_dir
        )

    if REWRITE_SECTIONS.get("projects"):
        resume_data = rewrite_projects(
            resume_data,
            job_text,
            output_dir
        )

    return resume_data