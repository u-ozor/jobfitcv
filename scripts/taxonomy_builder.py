#!/usr/bin/env python3
"""
scripts/taxonomy_builder.py — interactive track builder for fields outside
security/IT (the 6 tracks in build_taxonomy_embeddings.py are hardcoded to
that domain). Opt-in, low-priority — targeting SOC/sysadmin/cloud/etc.
never needs this.

Usage: kratos/bin/python scripts/taxonomy_builder.py
Safe to re-run: existing tracks are shown, nothing is deleted unless you
explicitly choose to replace.
"""

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import glob
from app.core.embedder import embed_text

TAXONOMY_DIR = "data/taxonomy"

AI_PROMPT_TEMPLATE = """\
I'm building a job-taxonomy classifier for the field "{field}". I need a single
dense paragraph (100-200 words) that sits at the semantic centroid of this
field's job postings — not just its most distinctive buzzwords, but also the
generic-sounding terms that are actually common across postings in this field
(e.g. "monitoring" or "infrastructure" might sound generic but are core
vocabulary in some fields, not others). Include: common tools/platforms,
recurring responsibilities, typical job titles, and domain vocabulary a real
job posting in this field would use. Output only the paragraph, no preamble."""


def existing_tracks():
    return sorted(
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(TAXONOMY_DIR, "*.npy"))
    )


def section(title):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


def build_track():
    print("\n  Short track name (filename-safe, e.g. 'product_marketing'):")
    print("  Careful: the classifier splits on the FIRST underscore to get the")
    print("  short label used everywhere else in the app — 'product_marketing'")
    print("  becomes just 'product'. Pick the split you actually want.")
    name = input("  Name: ").strip().lower().replace(" ", "_")
    if not name:
        return None

    print(f"\n  Describe the '{name}' field for the classifier.")
    print("  Not sure what makes a good description? Paste this into any AI chat tool:\n")
    print(f"  {'-' * 46}")
    for line in AI_PROMPT_TEMPLATE.format(field=name).splitlines():
        print(f"  {line}")
    print(f"  {'-' * 46}\n")
    description = input("  Description (paste your own, or the AI's output): ").strip()
    if not description:
        print("  Empty description, skipping this track.")
        return None

    return name, description


def main():
    print("\n  Taxonomy builder")
    current = existing_tracks()
    if current:
        print(f"  Existing tracks: {', '.join(current)}")
    else:
        print("  No tracks found yet.")

    print("\n  (a) Add new tracks alongside existing ones")
    print("  (r) Replace everything — start fresh")
    print("  (q) Quit\n")
    mode = input("  Choice: ").strip().lower()

    if mode == "q" or not mode:
        print("  No changes made.")
        return

    if mode == "r" and current:
        confirm = input(f"  This deletes {len(current)} existing track(s). Type 'yes' to confirm: ").strip()
        if confirm.lower() != "yes":
            print("  Cancelled.")
            return
        for name in current:
            os.remove(os.path.join(TAXONOMY_DIR, f"{name}.npy"))
        print("  Existing tracks removed.")

    os.makedirs(TAXONOMY_DIR, exist_ok=True)
    built = []
    while True:
        section(f"Track {len(built) + 1}")
        result = build_track()
        if result:
            name, description = result
            import numpy as np
            vector = embed_text(description)
            np.save(os.path.join(TAXONOMY_DIR, f"{name}.npy"), vector)
            built.append(name)
            print(f"  ✓ Saved {name}.npy")

        again = input("\n  Add another track? [y/N]: ").strip().lower()
        if again != "y":
            break

    if built:
        print(f"\n  Done. Built: {', '.join(built)}")
        print("  Restart the API for the new tracks to take effect on the next ingest.")
    else:
        print("\n  No tracks were built.")


if __name__ == "__main__":
    main()
