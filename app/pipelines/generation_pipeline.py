# app/pipelines/generation_pipeline.py

# Resume Generation pipeline
import json
from app.core.embedder import embed_text
from app.generation.matcher import match_with_pool

from app.generation.resume_builder import build_resume_data

from app.rewrites.hooks import apply_rewrite_hooks

from app.generation.renderer import (
    render_markdown,
    render_html
)

from app.generation.variant_manager import (
    create_variant,
    update_variant_metadata
)

from app.generation.artifact_writer import (
    write_resume_bundle,
    ensure_variant_dirs,
    write_edited_markdown
)

from app.core.config import (
    TEMPLATE_NAME
)

# =========================================================
# Resume generation pipeline
# =========================================================

def generate_resume_pipeline(
    job_text,
    track,
    focus,
    job_id
):
    """
    Main resume generation pipeline.
    """

    # -----------------------------------------------------
    # Embed job
    # -----------------------------------------------------

    job_vec = embed_text(job_text)

    # -----------------------------------------------------
    # Match chunks
    # -----------------------------------------------------

    matched_chunks, scored_pool = match_with_pool(
        job_vec,
        job_text,
        track=track
    )

    # -----------------------------------------------------
    # Structured resume data object
    # -----------------------------------------------------

    resume_data = build_resume_data(
        matched_chunks
    )

    # DEBUG PRINT
    # print(json.dumps(resume_data, indent=2))
    # ____________
    
    # -----------------------------------------------------
    # Variant lifecycle
    # -----------------------------------------------------

    variant = create_variant(
        job_id=job_id,
        track=track,
        focus=focus,
        job_vec=job_vec,
        job_text=job_text,
        matched_chunks=matched_chunks,
        scored_pool=scored_pool
    )

    # -----------------------------------------------------
    # Rewrite Hook
    # -----------------------------------------------------

    resume_data = apply_rewrite_hooks(
        resume_data,
        job_text,
        variant["output_dir"]
    )

    # -----------------------------------------------------
    # Render
    # -----------------------------------------------------

    markdown = render_markdown(
        resume_data
    )

    html = render_html(
        resume_data,
        template_name=TEMPLATE_NAME
    )

    # -----------------------------------------------------
    # Artifact export
    # -----------------------------------------------------

    artifacts = write_resume_bundle(
        output_dir=variant["output_dir"],
        markdown=markdown,
        html=html,
        resume_data=resume_data      # writes resume data
    )
    
    # -----------------------------------------------------
    # Seed editable Markdown
    # -----------------------------------------------------
    dirs = ensure_variant_dirs(variant["output_dir"])

    write_edited_markdown(
        dirs["edited"],
        markdown
    )
    
    # -----------------------------------------------------
    # Metadate Updates
    # -----------------------------------------------------
    
    update_variant_metadata(
        variant_name=variant["variant"],
        artifacts=artifacts,
        template_name=TEMPLATE_NAME,
        matched_chunks=matched_chunks
    )
    
    

    return {
        "variant": variant,
        "artifacts": artifacts,
        "matched_chunks": matched_chunks
    }