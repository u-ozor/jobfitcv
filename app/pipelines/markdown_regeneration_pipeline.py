# app/pipelines/markdown_regeneration_pipeline.py

from app.core.markdown_parser import (
    parse_markdown_resume
)

from app.generation.renderer import (
    render_html,
    render_markdown
)

from app.generation.artifact_writer import (
    write_resume_bundle,
    ensure_variant_dirs,
    write_edited_markdown
)

from app.rewrites.manager import (
    save_resume_snapshot
)


# =========================================================
# Markdown regeneration pipeline
# =========================================================

def regenerate_from_markdown(
    markdown_path,
    output_dir,
    template_name
):
    """
    Rebuilds resume artifacts
    from manually edited markdown.

    IMPORTANT:
    This pipeline intentionally skips:
    - embeddings
    - matching
    - chunk scoring
    - rewrites

    Manual edits become authoritative.
    """

    # =====================================================
    # Load markdown
    # =====================================================

    with open(
        markdown_path,
        "r",
        encoding="utf-8"
    ) as f:

        markdown_text = f.read()
        
    dirs = ensure_variant_dirs(
        output_dir
    )

    write_edited_markdown(
        dirs["edited"],
        markdown_text
    )

    # =====================================================
    # Parse markdown
    # =====================================================

    resume_data = parse_markdown_resume(
        markdown_text
    )

    # -----------------------------------------------------
    # Snapshot editable state
    # -----------------------------------------------------

    save_resume_snapshot(
        output_dir=output_dir,
        resume_data=resume_data,
        source="markdown_regeneration"
    )
    
    # =====================================================
    # Render
    # =====================================================

    html = render_html(
        resume_data,
        template_name=template_name
    )
    
    regenerated_markdown = render_markdown(
        resume_data
    )

    # =====================================================
    # Export artifacts
    # =====================================================

    artifacts = write_resume_bundle(
        output_dir=output_dir,
        markdown=regenerated_markdown,
        html=html,
        resume_data=resume_data,
        write_generated_markdown=False
    )

    # =====================================================
    # Return payload
    # =====================================================

    return {
        "resume_data": resume_data,
        "artifacts": artifacts
    }