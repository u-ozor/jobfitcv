#app/services/markdown_rebuild_service.py
#
# Rebuilds resume artifacts (HTML/PDF) from the user's hand-edited
# markdown at edited/resume.edited.md. Unrelated to AI rewrites —
# see app/rewrite_manager.py for that snapshot/revert system instead.

from pathlib import Path
import shutil

from app.pipelines.markdown_regeneration_pipeline import (
    regenerate_from_markdown
)

from dotenv import load_dotenv

from app.core.config import TEMPLATE_NAME


def regenerate_resume(
    output_dir
):
    """
    Re-renders resume artifacts from the manually edited markdown file.

    If editable markdown does not exist yet,
    bootstrap it from generated markdown.
    """
    
    load_dotenv()

    output_path = Path(output_dir)

    edited_md = (
        output_path
        / "edited"
        / "resume.edited.md"
    )
    
    if not edited_md.exists():
        raise FileNotFoundError(
            f"Editable markdown missing: {edited_md}"
        )
    # ==========================================
    # Regenerate
    # ==========================================

    return regenerate_from_markdown(
        markdown_path=str(edited_md),
        output_dir=output_dir,
        template_name=TEMPLATE_NAME
    )