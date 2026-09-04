# app/markdown_parser.py
import re


class ResumeParseError(Exception):
    pass


def parse_markdown_resume(markdown):
    """
    Parses structured editable markdown
    back into canonical resume_data schema.

    Designed to be reversible with:
        render_markdown()
    """

    lines = markdown.splitlines()

    resume_data = {
        "header": {},
        "summary": [],
        "experience": {},
        "projects": {},
        "education": [],
        "skills": {}
    }

    current_section = None
    current_entry = None
    i = 0

    while i < len(lines):

        line = lines[i].strip()

        # -------------------------------------------------
        # Skip blanks and horizontal rules
        # -------------------------------------------------

        if not line or line == "---":
            i += 1
            continue

        # -------------------------------------------------
        # Header
        # -------------------------------------------------

        if line.startswith("# "):
            resume_data["header"]["name"] = line[2:].strip()
            i += 1
            continue

        if line.startswith("EMAIL:"):
            resume_data["header"]["email"] = line.replace("EMAIL:", "").strip()
            i += 1
            continue

        if line.startswith("LINKEDIN:"):
            resume_data["header"]["linkedin"] = line.replace("LINKEDIN:", "").strip()
            i += 1
            continue

        if line.startswith("GITHUB:"):
            resume_data["header"]["github"] = line.replace("GITHUB:", "").strip()
            i += 1
            continue

        # -------------------------------------------------
        # Section headers (## SUMMARY etc.) — skip, we use [[tags]]
        # -------------------------------------------------

        if line.startswith("## "):
            i += 1
            continue

        # -------------------------------------------------
        # Section tags
        # -------------------------------------------------

        if line == "[[summary]]":
            current_section = "summary"
            i += 1
            continue

        if line == "[[experience]]":
            current_section = "experience"
            i += 1
            continue

        if line == "[[project]]":
            current_section = "projects"
            i += 1
            continue

        if line == "[[education]]":
            current_section = "education"
            i += 1
            continue

        if line == "[[skills]]":
            current_section = "skills"
            i += 1
            continue

        # -------------------------------------------------
        # Summary
        # -------------------------------------------------

        if current_section == "summary":

            summary_item = {}

            if line.startswith("[id="):
                summary_item["id"] = line[4:-1]
                i += 1
                if i >= len(lines):
                    break
                line = lines[i].strip()

            summary_item["content"] = line
            resume_data["summary"].append(summary_item)
            i += 1
            continue

        # -------------------------------------------------
        # Experience / Projects / Education entries
        # -------------------------------------------------

        if line.startswith("### "):

            header = line[4:].strip()
            parts = [p.strip() for p in header.split("|")]

            title        = parts[0] if len(parts) > 0 else ""
            organization = parts[1] if len(parts) > 1 else ""
            date_range   = parts[2] if len(parts) > 2 else ""

            current_entry = {
                "title": title,
                "organization": organization,
                "date_range": date_range,
                "content": [],
                "tags": []
            }

            i += 1

            # -- metadata lines ([id=], [group=], [links=], [tags=]) --
            while i < len(lines):

                meta = lines[i].strip()

                if meta.startswith("[id="):
                    current_entry["id"] = meta[4:-1]

                elif meta.startswith("[group="):
                    current_entry["group_key"] = meta[7:-1]

                elif meta.startswith("[links="):
                    current_entry["links"] = [
                        x.strip() for x in meta[7:-1].split(",")
                    ]

                elif meta.startswith("[tags="):
                    current_entry["tags"] = [
                        x.strip() for x in meta[6:-1].split(",")
                    ]

                else:
                    break  # not a metadata line — stop

                i += 1

            # -- route to correct bucket --
            group_key = current_entry.get("group_key", current_entry["title"])

            if current_section == "experience":
                bucket = resume_data["experience"]
                bucket.setdefault(group_key, [])

            elif current_section == "projects":
                bucket = resume_data["projects"]
                bucket.setdefault(group_key, [])

            elif current_section == "education":
                resume_data["education"].append({
                    "id":           current_entry.get("id"),
                    "title":        current_entry.get("title"),
                    "organization": current_entry.get("organization"),
                    "date_range":   current_entry.get("date_range"),
                    "tags":         current_entry.get("tags", []),
                    "content":      ""
                })
                bucket = None

            else:
                raise ResumeParseError(
                    f"Invalid section for entry: {current_section}"
                )

            # -- bullet lines --
            while i < len(lines):

                bullet = lines[i].strip()

                # stop at next entry or section tag
                if bullet.startswith("### ") or bullet.startswith("[["):
                    break

                # skip blanks, rules, section headers
                if not bullet or bullet == "---" or bullet.startswith("## "):
                    i += 1
                    continue

                if bullet.startswith("- "):
                    content = bullet[2:].strip()

                    if current_section == "education":
                        resume_data["education"][-1]["content"] = content
                    else:
                        entry = current_entry.copy()
                        entry["content"] = content
                        bucket[group_key].append(entry)

                i += 1

            # CRITICAL: do not fall through to the bottom i += 1
            # The inner loop already advanced i to the next ### or [[
            continue

        # -------------------------------------------------
        # Skills
        # -------------------------------------------------

        if current_section == "skills":

            if ":" in line:
                group, values = line.split(":", 1)
                group = group.strip().lower().replace(" ", "_")
                items = [x.strip() for x in values.split(",")]
                resume_data["skills"][group] = items

            i += 1
            continue

        i += 1

    # -----------------------------------------------------
    # Inline validation
    # -----------------------------------------------------

    required = ["header", "summary", "experience", "projects", "education", "skills"]

    for key in required:
        if key not in resume_data:
            raise ResumeParseError(f"Missing section: {key}")

    return resume_data