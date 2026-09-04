# app/pipelines/preprocessing_pipeline.py

import json
import numpy as np

from app.core.embedder import embed_text


# =========================================================
# Embedding text preparation
# =========================================================

def build_embedding_text(chunk):
    """
    Converts chunk into semantic embedding text.

    Goal:
    - maximize semantic retrieval quality
    - include ATS vocabulary coverage
    - preserve concise normalized tags
    """

    chunk_type = chunk["type"]

    title = chunk.get("title", "")
    content = chunk.get("content", "")
    tags = " ".join(chunk.get("tags", []))
    organization = chunk.get("organization", "")

    # EXPERIENCE / PROJECTS

    if chunk_type in ["experience", "project"]:

        return (
            f"{title} at {organization}. "
            f"{content}. "
            f"{tags}. "
        )

    # SKILLS

    if chunk_type == "skill":

        return (
            f"{title}. "
            f"{content}. "
            f"{tags}. "
        )

    # EDUCATION

    if chunk_type == "education":

        return (
            f"{title} at {organization}. "
            f"{content}."
        )

    # SUMMARY / FALLBACK

    return f"{title}. {content}"


# =========================================================
# Compile Resume chunk embedding pipeline
# =========================================================

def preprocess_resume_chunks():
    """
    Generates embedding assets.

    Outputs:
    - resume_embeddings.npy
    - resume_embedding_ids.json
    """

    with open("data/resume_chunks.json", "r") as f:
        chunks = json.load(f)

    embeddings = []
    ids = []

    for chunk in chunks:

        if not chunk.get("active", True):
            continue

        text = build_embedding_text(
            chunk
        )

        vec = embed_text(text)

        embeddings.append(vec)
        ids.append(chunk["id"])

    np.save(
        "data/resume_embeddings.npy",
        np.array(embeddings)
    )

    with open(
        "data/resume_embedding_ids.json",
        "w"
    ) as f:
        json.dump(ids, f, indent=2)

    print(
        f"✅ Embedded {len(ids)} chunks."
    )