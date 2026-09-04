#app/taxonomy_classifier

import os
import numpy as np

from app.core.embedder import embed_text
from app.core.similarity import cosine_similarity


TAXONOMY_DIR = "data/taxonomy"


# =========================================================
# Load taxonomy embeddings
# =========================================================

def load_taxonomy_embeddings():

    taxonomy = {}

    for file in os.listdir(TAXONOMY_DIR):

        if not file.endswith(".npy"):
            continue

        name = file.replace(".npy", "")

        taxonomy[name] = np.load(
            os.path.join(TAXONOMY_DIR, file)
        )

    return taxonomy


# =========================================================
# Classification
# =========================================================

def classify_job(job_text):
    """
    Embedding-based track/focus classification.

    Returns:
    - track
    - focus
    - similarity score
    """

    job_vec = embed_text(job_text)

    taxonomy = load_taxonomy_embeddings()

    best_name = None
    best_score = -1

    for name, vec in taxonomy.items():

        score = cosine_similarity(
            job_vec,
            vec
        )

        if score > best_score:
            best_score = score
            best_name = name

    if not best_name:
        return {
            "track": "general",
            "focus": "general",
            "score": 0
        }

    parts = best_name.split("_", 1)

    track = parts[0]
    focus = parts[1] if len(parts) > 1 else "general"

    return {
        "track": track,
        "focus": focus,
        "score": best_score
    }



