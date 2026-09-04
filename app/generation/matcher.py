# app/generation/matcher.py

import json
import numpy as np

from collections import defaultdict

from app.generation.extract_keywords import extract_keywords
from app.core.config import (
    MIN_SCORE,
    SKILL_MIN_SCORE,
    EDUCATION_MIN_SCORE,
    WEIGHTS,
    QUOTAS,
    GROUP_CAP,
)

from app.core.similarity import cosine_similarity


# =========================================================
# Keyword overlap
# =========================================================

def compute_keyword_score(job_keywords, chunk_terms):
    """
    Lexical overlap score.

    Purpose:
    - reinforce exact terminology
    - improve ATS-style alignment
    """

    if not chunk_terms:
        return 0.0

    matches = len(
        job_keywords.intersection(set(chunk_terms))
    )

    return min(matches / 8, 1.0)


# =========================================================
# Chunk scoring
# =========================================================

def score_chunk(
    job_vec,
    job_keywords,
    chunk,
    embeddings,
    id_to_index
):
    idx = id_to_index.get(chunk["id"])

    if idx is None:
        return None

    chunk_vec = embeddings[idx]

    similarity = cosine_similarity(
        job_vec,
        chunk_vec
    )

    tag_text = " ".join(t.replace("-", " ") for t in chunk.get("tags", []))
    kw_text  = " ".join(chunk.get("keywords", []))
    chunk_terms = extract_keywords(f"{tag_text} {kw_text}")

    keyword_score = compute_keyword_score(
        job_keywords,
        chunk_terms
    )

    priority = (
        chunk.get("priority", 5) / 10
    )

    keyword_weight = WEIGHTS["tag"]

    final_score = (
        WEIGHTS["similarity"] * similarity
        + keyword_weight * keyword_score
        + WEIGHTS["priority"] * priority
    )

    return {
        **chunk,
        "score": final_score,
        "similarity": similarity,
        "keyword_score": keyword_score,
        "priority_score": priority
    }


# =========================================================
# Data loading
# =========================================================

def load_data():
    with open("data/resume_chunks.json", "r") as f:
        chunks = json.load(f)

    with open("data/resume_embedding_ids.json", "r") as f:
        ids = json.load(f)

    embeddings = np.load(
        "data/resume_embeddings.npy"
    )

    id_to_index = {
        cid: i
        for i, cid in enumerate(ids)
    }

    return chunks, embeddings, id_to_index


# =========================================================
# Per-type score threshold
# =========================================================

def _threshold(chunk_type):
    if chunk_type == "skill":
        return SKILL_MIN_SCORE
    if chunk_type == "education":
        return EDUCATION_MIN_SCORE
    return MIN_SCORE


# =========================================================
# Filtering
# =========================================================

def filter_active(chunks):
    return [
        c for c in chunks
        if c.get("active", True)
    ]


def filter_summaries_by_track(chunks, track):
    """
    For summary chunks: keep only those whose track matches
    the current generation track, or whose track is null (universal).
    All non-summary chunks pass through unchanged.
    """
    result = []
    for chunk in chunks:
        if chunk["type"] != "summary":
            result.append(chunk)
            continue
        chunk_track = chunk.get("track")
        if chunk_track is None or chunk_track == track:
            result.append(chunk)
    return result


# =========================================================
# Ranking
# =========================================================

def rank_chunks(
    job_vec,
    job_keywords,
    chunks,
    embeddings,
    id_to_index
):
    scored = []

    for chunk in chunks:
        result = score_chunk(
            job_vec,
            job_keywords,
            chunk,
            embeddings,
            id_to_index
        )

        if result:
            scored.append(result)

    filtered = [
        s for s in scored
        if s["score"] >= _threshold(s["type"])
    ]

    if not filtered:
        filtered = sorted(
            scored,
            key=lambda x: x["score"],
            reverse=True
        )[:2]
        # fallback

    return sorted(
        filtered,
        key=lambda x: x["score"],
        reverse=True
    )


# =========================================================
# Pool splitting
# =========================================================

def split_by_type(scored_chunks):
    pools = defaultdict(list)

    for chunk in scored_chunks:
        pools[chunk["type"]].append(chunk)

    return pools


# =========================================================
# Quotas
# =========================================================

GROUP_CAPPED_TYPES = {"project", "experience"}


def apply_quotas(pools):
    selected = []

    for chunk_type, limit in QUOTAS.items():
        bucket = pools.get(chunk_type, [])
        if chunk_type in GROUP_CAPPED_TYPES:
            group_counts = defaultdict(int)
            type_selected = []
            for chunk in bucket:
                if len(type_selected) >= limit:
                    break
                gk = chunk.get("group_key") or chunk["id"]
                if group_counts[gk] >= GROUP_CAP:
                    continue
                type_selected.append(chunk)
                group_counts[gk] += 1
            selected.extend(type_selected)
        else:
            selected.extend(bucket[:limit])

    return selected


# =========================================================
# Scored pool (pre-quota, pre-threshold, for chunk review)
# =========================================================

POOL_FLOOR = 0.35  # minimum score to appear in the review pool at all


def build_scored_pool(all_scored, selected_ids, pools):
    """
    Builds the full scored pool for chunk review storage.

    Each entry records score components + why it was or wasn't selected.
    """
    selected_set = set(selected_ids)

    # Build a map of type → how many slots were filled by quota
    quota_filled = {t: 0 for t in QUOTAS}
    for chunk in all_scored:
        ctype = chunk["type"]
        threshold = _threshold(ctype)
        if chunk["score"] >= threshold and chunk["id"] in selected_set:
            quota_filled[ctype] = quota_filled.get(ctype, 0) + 1

    pool = []
    for chunk in all_scored:
        if chunk["score"] < POOL_FLOOR:
            continue
        ctype = chunk["type"]
        threshold = _threshold(ctype)
        selected = chunk["id"] in selected_set

        if selected:
            cut_reason = None
        elif chunk["score"] < threshold:
            cut_reason = "threshold"
        else:
            cut_reason = "quota"

        pool.append({
            "id":             chunk["id"],
            "score":          round(chunk["score"], 4),
            "similarity":     round(chunk["similarity"], 4),
            "keyword_score":  round(chunk["keyword_score"], 4),
            "priority_score": round(chunk["priority_score"], 4),
            "selected":       selected,
            "cut_reason":     cut_reason,
        })

    return pool


# =========================================================
# Main matcher
# =========================================================

def match(job_vec, job_text, track=None):
    chunks, embeddings, id_to_index = load_data()

    chunks = filter_active(chunks)

    if track:
        chunks = filter_summaries_by_track(chunks, track)

    job_keywords = extract_keywords(job_text)

    ranked = rank_chunks(
        job_vec,
        job_keywords,
        chunks,
        embeddings,
        id_to_index
    )

    pools = split_by_type(ranked)

    if track and "summary" in pools:
        pools["summary"].sort(
            key=lambda c: (c.get("track") == track, c["score"]),
            reverse=True
        )

    final = apply_quotas(pools)

    return final


def match_with_pool(job_vec, job_text, track=None):
    """
    Same as match() but also returns the full scored pool for chunk review.
    Returns: (matched_chunks, scored_pool)
    """
    chunks, embeddings, id_to_index = load_data()

    chunks = filter_active(chunks)

    if track:
        chunks = filter_summaries_by_track(chunks, track)

    job_keywords = extract_keywords(job_text)

    # Score everything (no threshold yet)
    all_scored = []
    for chunk in chunks:
        result = score_chunk(job_vec, job_keywords, chunk, embeddings, id_to_index)
        if result:
            all_scored.append(result)
    all_scored.sort(key=lambda x: x["score"], reverse=True)

    # Apply threshold for selection
    filtered = [
        s for s in all_scored
        if s["score"] >= _threshold(s["type"])
    ]
    if not filtered:
        filtered = all_scored[:2]

    pools = split_by_type(filtered)

    if track and "summary" in pools:
        pools["summary"].sort(
            key=lambda c: (c.get("track") == track, c["score"]),
            reverse=True
        )

    final = apply_quotas(pools)
    selected_ids = {c["id"] for c in final}
    scored_pool = build_scored_pool(all_scored, selected_ids, pools)

    return final, scored_pool