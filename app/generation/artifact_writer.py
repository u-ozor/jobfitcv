# app/generation/artifact_writer.py

import os
import json
from app.core.pdf_export import export_pdf



# =========================================================
# Directories
# =========================================================

def ensure_variant_dirs(output_dir):

    generated_dir = os.path.join(
        output_dir,
        "generated"
    )

    edited_dir = os.path.join(
        output_dir,
        "edited"
    )

    snapshots_dir = os.path.join(
        output_dir,
        "snapshots"
    )

    os.makedirs(generated_dir, exist_ok=True)
    os.makedirs(edited_dir, exist_ok=True)
    os.makedirs(snapshots_dir, exist_ok=True)

    return {
        "generated": generated_dir,
        "edited": edited_dir,
        "snapshots": snapshots_dir
    }


# =========================================================
# Writer
# =========================================================
def write_text(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# =========================================================
# Markdown
# =========================================================

def write_markdown(
    generated_dir,
    markdown
):
    path = os.path.join(
        generated_dir,
        "resume.md"
    )

    write_text(path, markdown)

    return path

# =========================================================

def write_edited_markdown(
    edited_dir,
    markdown
):
    path = os.path.join(
        edited_dir,
        "resume.edited.md"
    )

    write_text(path, markdown)

    return path



# =========================================================
# HTML
# =========================================================

def write_html(
    generated_dir,
    html
):

    path = os.path.join(
        generated_dir,
        "resume.html"
    )

    write_text(path, html)

    return path


# =========================================================
# PDF
# =========================================================

def write_pdf(
    generated_dir,
    html
):
    path = os.path.join(
        generated_dir,
        "resume.pdf"
    )

    export_pdf(
        html,
        path
    )

    return path


# =========================================================
# Editable Resume Data Snapshots
# =========================================================

def write_resume_data(
    output_dir,
    resume_data
):
    path = os.path.join(
        output_dir,
        "resume_data.json"
    )

    with open(path, "w") as f:
        json.dump(
            resume_data,
            f,
            indent=2
        )

    return path


# =========================================================
# Full bundle
# =========================================================

def write_resume_bundle(
    output_dir,
    markdown,
    html,
    resume_data,
    write_generated_markdown=True
):
    """
    Centralized artifact export.

    Writer owns:
    - filesystem writes
    - artifact persistence

    Renderer owns:
    - styling
    - templating
    """
    
    artifacts = {}
    
    dirs = ensure_variant_dirs(
        output_dir
    )
    
    generated_dir = dirs["generated"] 
    
    if write_generated_markdown:

        artifacts["markdown"] = write_markdown(
            generated_dir,
            markdown
        )
    artifacts["html"] = write_html(
        generated_dir,
        html
    )

    artifacts["pdf"] = write_pdf(
        generated_dir,
        html
    )

    artifacts["resume_data"] = write_resume_data(
        generated_dir,
        resume_data
    )

    return artifacts