# app/job_fit_scorer.py
#
# Scores a job against the user's declared target role phrases.
# Independent from track classification — track is a resume-build concern,
# this is a candidate-intent concern: "do I actually want this job?"

import json
import numpy as np

from app.core.embedder import embed_text
from app.core.similarity import cosine_similarity

TARGETS_PATH = "data/job_targets.json"

_cached_targets = None   # list of (phrase, np.ndarray)


def _load_target_embeddings():
    global _cached_targets
    if _cached_targets is not None:
        return _cached_targets
    with open(TARGETS_PATH) as f:
        phrases = json.load(f).get("targets", [])
    _cached_targets = [(p, np.array(embed_text(p))) for p in phrases]
    return _cached_targets


def score_role_fit(job_title: str, job_text: str = "") -> dict:
    """
    Returns:
      score : float  — best cosine similarity against any target phrase (0–1)
      label : str    — "Strong match" | "Possible match" | "Outside target"
    """
    job_vec = np.array(embed_text(job_title))

    targets = _load_target_embeddings()
    if not targets:
        return {"score": None, "label": None}

    best = max(cosine_similarity(job_vec, vec) for _, vec in targets)
    best = float(best)

    if best >= 0.70:
        label = "Strong match"
    elif best >= 0.58:
        label = "Possible match"
    else:
        label = "Outside target"

    return {"score": round(best, 3), "label": label}
