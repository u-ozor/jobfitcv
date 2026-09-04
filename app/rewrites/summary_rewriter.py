#app/rewriters/summary_rewriter

from copy import deepcopy

from app.core.llm_client import generate_completion

from app.rewrites.manager import (
    save_rewrite_snapshot
)

from app.rewrites.validator import is_rewrite_acceptable

def rewrite_summary(
    resume_data,
    job_text,
    output_dir=None
):
    
    """
    Improves ATS alignment of summary only.
    """

    if not resume_data.get("summary"):
        return resume_data
    
    # -----------------------------------------
    # Snapshot BEFORE rewrite
    # -----------------------------------------
    before = deepcopy(
        resume_data["summary"]
    )

    original = resume_data["summary"][0]["content"]

    prompt = f"""<job_context>
{job_text}
</job_context>

<original_summary>
{original}
</original_summary>

Rewrite the summary above for ATS alignment with the job context.
Rules: all facts must stay true, no invented skills, max 2 sentences and 60 words, no clichés, natural tone.
Output ONLY the rewritten summary — no explanation, no quotes, no labels."""

    rewritten = generate_completion(
        prompt
    ).strip()

    if is_rewrite_acceptable(original, rewritten):
        resume_data["summary"][0]["content"] = rewritten.replace("\n", " ")


    # -----------------------------------------
    # Snapshot AFTER rewrite
    # -----------------------------------------

    after = resume_data["summary"]

    # -----------------------------------------
    # Save rewrite snapshot
    # -----------------------------------------

    if output_dir and before != after:
        save_rewrite_snapshot(
            output_dir=output_dir,
            section="summary",
            before_data=before,
            after_data=after
        )

    return resume_data