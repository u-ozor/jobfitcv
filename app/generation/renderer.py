# app/generation/renderer.py

import os

from jinja2 import Environment, BaseLoader

from app.generation.template_manager import (
    load_template,
    load_css
)

env = Environment(
    loader=BaseLoader()
)


def render_html(
    resume_data,
    template_name="technical_compact"
):
    """
    Fully rendered self-contained HTML.

    Renderer owns:
    - template loading
    - CSS loading
    - CSS inlining
    """

    template_str = load_template(
        template_name
    )

    template = env.from_string(
        template_str
    )

    html = template.render(
        resume=resume_data
    )

    css = load_css(
        template_name
    )

    html = html.replace(
        '<link rel="stylesheet" href="styles.css">',
        f"<style>{css}</style>"
    )

    return html


# =========================================================
# Markdown renderer
# =========================================================

def render_markdown(resume_data):
    """
    Converts canonical resume_data schema into
    editable reversible markdown format.

    IMPORTANT:
    This is NOT presentation markdown.

    It is an editable intermediate representation
    used for regeneration pipelines.
    """

    lines = []

    header = resume_data.get("header", {})

    # =====================================================
    # HEADER
    # =====================================================

    lines.append(f"# {header.get('name', '')}")
    lines.append("")

    if header.get("email"):
        lines.append(f"EMAIL: {header['email']}")

    if header.get("phone"):
        lines.append(f"PHONE: {header['phone']}")

    if header.get("linkedin"):
        lines.append(f"LINKEDIN: {header['linkedin']}")

    if header.get("github"):
        lines.append(f"GITHUB: {header['github']}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # =====================================================
    # SUMMARY
    # =====================================================

    summaries = resume_data.get("summary", [])

    if summaries:

        lines.append("## SUMMARY")
        lines.append("")
        lines.append("[[summary]]")
        lines.append("")

        for item in summaries:

            if item.get("id"):
                lines.append(f"[id={item['id']}]")

            lines.append(item.get("content", ""))
            lines.append("")

        lines.append("---")
        lines.append("")

    # =====================================================
    # EXPERIENCE
    # =====================================================

    experiences = resume_data.get("experience", {})

    if experiences:

        lines.append("## EXPERIENCE")
        lines.append("")
        lines.append("[[experience]]")
        lines.append("")

        for group_key, group in experiences.items():

            if not group:
                continue

            first = group[0]

            title        = first.get("title", "")
            organization = first.get("organization", "")
            date_range   = first.get("date_range") or first.get("duration") or ""

            lines.append(f"### {title} | {organization} | {date_range}")

            if first.get("id"):
                lines.append(f"[id={first['id']}]")

            if first.get("group_key"):
                lines.append(f"[group={first['group_key']}]")

            if first.get("tags"):
                lines.append(f"[tags={','.join(first['tags'])}]")

            lines.append("")

            for bullet in group:
                lines.append(f"- {bullet.get('content', '').strip()}")

            lines.append("")
            lines.append("---")
            lines.append("")

    # =====================================================
    # PROJECTS
    # =====================================================

    projects = resume_data.get("projects", {})

    if projects:

        lines.append("## PROJECTS")
        lines.append("")
        lines.append("[[project]]")
        lines.append("")

        for group_key, group in projects.items():

            if not group:
                continue

            first = group[0]

            title        = first.get("title", "")
            organization = first.get("organization", "")
            date_range   = first.get("date_range") or first.get("duration") or ""

            lines.append(f"### {title} | {organization} | {date_range}")

            if first.get("id"):
                lines.append(f"[id={first['id']}]")

            if first.get("group_key"):
                lines.append(f"[group={first['group_key']}]")

            if first.get("links"):
                lines.append(f"[links={','.join(first['links'])}]")

            if first.get("tags"):
                lines.append(f"[tags={','.join(first['tags'])}]")

            lines.append("")

            for bullet in group:
                lines.append(f"- {bullet.get('content', '').strip()}")

            lines.append("")
            lines.append("---")
            lines.append("")

    # =====================================================
    # EDUCATION
    # =====================================================

    education = resume_data.get("education", [])

    if education:

        lines.append("## EDUCATION")
        lines.append("")
        lines.append("[[education]]")
        lines.append("")

        for edu in education:

            title        = edu.get("title", "")
            organization = edu.get("organization", "")
            date_range   = edu.get("date_range") or edu.get("duration") or ""

            lines.append(f"### {title} | {organization} | {date_range}")

            if edu.get("id"):
                lines.append(f"[id={edu['id']}]")

            # FIX: tags were stored by parser but never emitted — breaks round-trip
            if edu.get("tags"):
                lines.append(f"[tags={','.join(edu['tags'])}]")

            lines.append("")

            if edu.get("content"):
                lines.append(f"- {edu['content']}")

            lines.append("")
            lines.append("---")
            lines.append("")

    # =====================================================
    # SKILLS
    # =====================================================

    skills = resume_data.get("skills", {})

    if skills:

        lines.append("## SKILLS")
        lines.append("")
        lines.append("[[skills]]")
        lines.append("")

        for group, items in skills.items():

            if not items:
                continue

            label  = group.replace("_", " ").title()
            joined = ", ".join(items)
            lines.append(f"{label}: {joined}")

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)