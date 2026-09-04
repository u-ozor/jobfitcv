# scripts/embed_resume.py

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import numpy as np
from app.core.embedder import embed_text


# ---------- Formatting Logic ----------

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


# ---------- Compile Resume Embeddings ----------

def embed_resume_chunks():
    with open("data/resume_chunks.json", "r") as f:
        chunks = json.load(f)

    active_chunks = [c for c in chunks if c.get("active", True)]

    embeddings = []
    ids = []

    for chunk in active_chunks:
        text = build_embedding_text(chunk)
        vector = embed_text(text)

        embeddings.append(vector)
        ids.append(chunk["id"])

    np.save("data/resume_embeddings.npy", np.array(embeddings))

    with open("data/resume_embedding_ids.json", "w") as f:
        json.dump(ids, f, indent=2)

    print("✅ Resume embeddings compiled.")


# ---------- Embed Job Description ----------

def embed_job_description(text: str):
    return np.array(embed_text(text))


# ---------- Entry ----------

if __name__ == "__main__":
    embed_resume_chunks()