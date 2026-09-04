# app/generation/variant_manager.py

import os
import json
import numpy as np

from app.utils.time_utils import local_timestamp
from app.utils.atomic_io import atomic_write_json
from app.generation.extract_keywords import extract_keywords

OUTPUT_ROOT = "outputs/resumes"


# =========================================================
# Metadata export
# =========================================================

def export_metadata(
    output_dir,
    variant_name,
    track,
    focus,
    matched_chunks,
    job_text,
    job_keywords,
    embedding_path,
    scored_pool=None
):
    metadata = {
        "variant": variant_name,
        "track": track,
        "focus": focus,
        "created_at": local_timestamp(),
        "chunk_ids": [c["id"] for c in matched_chunks],
        "job_preview": job_text[:800],
        "job_keywords": sorted(list(job_keywords)),
        "job_embedding_file": embedding_path,
        "scored_pool": scored_pool or [],
        "ollama_assessments": {}
    }

    atomic_write_json(os.path.join(output_dir, "metadata.json"), metadata)

    return metadata


# =========================================================
# Metadata update
# =========================================================

def update_variant_metadata(variant_name, artifacts, template_name, matched_chunks):
    path = os.path.join(OUTPUT_ROOT, variant_name, "metadata.json")

    if not os.path.exists(path):
        return

    with open(path, "r") as f:
        metadata = json.load(f)

    metadata["artifacts"] = artifacts
    metadata["template"] = template_name
    metadata["chunk_ids"] = [c["id"] for c in matched_chunks]

    atomic_write_json(path, metadata)


# =========================================================
# Main creation flow
# =========================================================

def create_variant(job_id, track, focus, job_vec, job_text, matched_chunks, scored_pool=None):
    """
    Creates a new variant directory keyed by job_id.
    One job → one directory, always. No reuse.
    """
    variant_name = job_id
    output_dir = os.path.join(OUTPUT_ROOT, variant_name)
    os.makedirs(output_dir, exist_ok=True)

    embedding_path = os.path.join(output_dir, "job_embedding.npy")
    np.save(embedding_path, np.array(job_vec))

    job_keywords = extract_keywords(job_text)

    export_metadata(
        output_dir=output_dir,
        variant_name=variant_name,
        track=track,
        focus=focus,
        matched_chunks=matched_chunks,
        job_text=job_text,
        job_keywords=job_keywords,
        embedding_path=embedding_path,
        scored_pool=scored_pool
    )

    return {
        "variant": variant_name,
        "output_dir": output_dir
    }
