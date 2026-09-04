"""
scripts/review_variant.py
Usage: kratos/bin/python -m scripts.review_variant [variant_id]
       kratos/bin/python -m scripts.review_variant --list

Prints a structured review report of a variant — job context, selected chunks
with scores and Ollama verdicts, top swap candidates, and rewrite/cover letter
status. Intended for quick AI-readable analysis without needing to read many
files in sequence.
"""

import os, sys, json, sqlite3, textwrap
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

RESUMES_DIR   = "outputs/resumes"
COVERS_DIR    = "outputs/cover_letters"
CHUNKS_PATH   = "data/resume_chunks.json"
DB_PATH       = "data/jobs.db"
CANDIDATE_FLOOR = 0.42


def load_chunks_map():
    with open(CHUNKS_PATH) as f:
        return {c["id"]: c for c in json.load(f)}


def get_job(job_id):
    if not os.path.exists(DB_PATH):
        return None
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def find_cover_letter(job_id):
    cl_dir = os.path.join(COVERS_DIR, job_id)
    if os.path.isdir(cl_dir):
        for fname in sorted(os.listdir(cl_dir)):
            if fname.endswith(".md"):
                with open(os.path.join(cl_dir, fname)) as f:
                    return fname, f.read()
    return None, None


def score_bar(score, width=20):
    filled = round(score * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score:.3f}"


def wrap(text, indent=4, width=100):
    prefix = " " * indent
    return textwrap.fill(text, width=width, initial_indent=prefix, subsequent_indent=prefix)


def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_chunk(chunk, entry, ollama_cache, prefix=""):
    cid   = chunk["id"]
    score = entry["score"]
    sim   = entry["similarity"]
    kw    = entry["keyword_score"]
    pri   = entry["priority_score"]
    flags = []
    if sim >= 0.70: flags.append("STRONG")
    if sim < 0.56: flags.append("marginal")
    if kw == 0.0: flags.append("no-kw")
    verdict = ollama_cache.get(cid, "")
    verdict_tag = ""
    if verdict.startswith("Relevant:"): verdict_tag = " [✓ Relevant]"
    elif verdict.startswith("Weak:"): verdict_tag = " [✗ Weak]"
    flag_str = "  " + " ".join(flags) if flags else ""
    print(f"\n{prefix}[{cid}] score={score:.3f}  sim={sim:.3f}  kw={kw:.3f}  pri={pri:.3f}{flag_str}{verdict_tag}")
    title = chunk.get("title") or chunk.get("group_key") or ""
    if title: print(f"{prefix}  title: {title}")
    content = chunk.get("content", "")
    print(wrap(content, indent=4+len(prefix)))
    if verdict:
        print(wrap(verdict, indent=4+len(prefix)))


def review(variant_id):
    variant_dir = os.path.join(RESUMES_DIR, variant_id)
    meta_path   = os.path.join(variant_dir, "metadata.json")
    if not os.path.exists(meta_path):
        print(f"No metadata.json for variant '{variant_id}' — generate first.")
        return

    with open(meta_path) as f:
        meta = json.load(f)

    chunk_map      = load_chunks_map()
    scored_pool    = meta.get("scored_pool", [])
    selected_ids   = set(meta.get("chunk_ids", []))
    ollama_cache   = meta.get("ollama_assessments", {})
    job_id         = meta.get("variant", variant_id)  # fallback
    track          = meta.get("track") or "—"
    focus          = meta.get("focus") or "—"
    created_at     = meta.get("created_at", "—")

    # resolve job from DB
    # job_id is not directly in metadata; find via variant DB row
    job  = None
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        var_row = con.execute("SELECT job_id, reused FROM variants WHERE id=?", (variant_id,)).fetchone()
        if var_row:
            job = con.execute("SELECT * FROM jobs WHERE id=?", (var_row["job_id"],)).fetchone()
            if job: job = dict(job)
        con.close()
    except Exception:
        pass

    print_section(f"VARIANT REVIEW: {variant_id}")
    print(f"  Created : {created_at}")
    print(f"  Track   : {track}   Focus: {focus}")
    if var_row and var_row["reused"]:
        print(f"  ⚠  REUSED variant — artifacts shared with another job")

    if job:
        print(f"\n  JOB     : {job['title']} @ {job['company']}")
        print(f"  Track   : {job.get('track', '—')}   Status: {job.get('status', '—')}")
        raw = (job.get("raw_text") or "").strip()
        if raw:
            print(f"\n  --- JD ({len(raw)} chars) ---")
            preview = raw[:2000]
            for line in preview.splitlines():
                print(f"  {line}")
            if len(raw) > 2000:
                print(f"  ... [{len(raw)-2000} more chars]")

    # group scored_pool by selected / candidate / dropped
    by_id = {e["id"]: e for e in scored_pool}
    selected_entries   = [e for e in scored_pool if e["id"] in selected_ids]
    candidate_entries  = [e for e in scored_pool if e["id"] not in selected_ids and e["score"] >= CANDIDATE_FLOOR]
    dropped_entries    = [e for e in scored_pool if e["id"] not in selected_ids and e["score"] < CANDIDATE_FLOOR]

    # ── Selected ──────────────────────────────────────────────
    # group by type
    by_type = {}
    for e in selected_entries:
        chunk = chunk_map.get(e["id"], {})
        t = chunk.get("type", "unknown")
        by_type.setdefault(t, []).append((chunk, e))

    print_section(f"SELECTED ({len(selected_entries)} chunks)")

    relevant_count = sum(1 for cid in selected_ids if ollama_cache.get(cid, "").startswith("Relevant:"))
    weak_count     = sum(1 for cid in selected_ids if ollama_cache.get(cid, "").startswith("Weak:"))
    assessed_count = sum(1 for cid in selected_ids if cid in ollama_cache)
    print(f"  Assess coverage: {assessed_count}/{len(selected_ids)} assessed  |  {relevant_count} Relevant  {weak_count} Weak")

    for section_type in ("summary", "experience", "project", "skill", "education"):
        items = by_type.get(section_type, [])
        if not items: continue
        items_sorted = sorted(items, key=lambda x: x[1]["score"], reverse=True)
        print(f"\n  ── {section_type.upper()} ({len(items)}) ──")
        for chunk, entry in items_sorted:
            print_chunk(chunk, entry, ollama_cache, prefix="  ")

    # ── Candidates worth considering ──────────────────────────
    print_section(f"CANDIDATES — worth swapping in ({len(candidate_entries)} total, showing top 10 by score)")
    top_candidates = sorted(candidate_entries, key=lambda e: e["score"], reverse=True)[:10]
    if not top_candidates:
        print("  None above floor.")
    for e in top_candidates:
        chunk = chunk_map.get(e["id"], {})
        cut = e.get("cut_reason") or "below-threshold"
        print_chunk(chunk, e, ollama_cache, prefix="  ")
        print(f"    cut_reason: {cut}")

    # ── Weak verdicts in selected (highest risk) ───────────────
    weak_selected = [
        (chunk_map.get(cid, {}), by_id[cid])
        for cid in selected_ids
        if cid in by_id and ollama_cache.get(cid, "").startswith("Weak:")
    ]
    if weak_selected:
        print_section(f"WEAK ASSESSMENTS IN SELECTED ({len(weak_selected)}) — consider swapping or rewriting")
        for chunk, entry in sorted(weak_selected, key=lambda x: x[1]["score"]):
            print_chunk(chunk, entry, ollama_cache, prefix="  ")

    # ── Rewrite status ────────────────────────────────────────
    rw_path = os.path.join(variant_dir, "pending_rewrite.json")
    if os.path.exists(rw_path):
        with open(rw_path) as f:
            rw = json.load(f)
        print_section(f"PENDING REWRITE ({rw.get('item_count', 0)} bullets, created {rw.get('created_at','?')})")
        for item in rw.get("items", []):
            rec = "✓ recommended" if item.get("recommend") == "recommended" else "– skip"
            print(f"\n  [{item['section']}] {item.get('label','')} ({rec})")
            print(f"    BEFORE: {item['before'][:120]}")
            print(f"    AFTER : {item['after'][:120]}")

    # ── Rewrite diffs ─────────────────────────────────────────
    rw_dir = os.path.join(variant_dir, "rewrites")
    if os.path.isdir(rw_dir):
        diffs = sorted(os.listdir(rw_dir))
        if diffs:
            print_section(f"APPLIED REWRITES ({len(diffs)} diff files)")
            for fname in diffs[-3:]:  # show last 3
                print(f"  {fname}")

    # ── Cover letter ──────────────────────────────────────────
    if job:
        cl_fname, cl_text = find_cover_letter(job["id"])
        if cl_text:
            print_section(f"COVER LETTER: {cl_fname}")
            for line in cl_text[:3000].splitlines():
                print(f"  {line}")
            if len(cl_text) > 3000:
                print(f"  ... [{len(cl_text)-3000} more chars]")
        else:
            print_section("COVER LETTER")
            print("  None generated yet.")

    print(f"\n{'='*70}\n")


def list_variants():
    print("Variants on disk:\n")
    for name in sorted(os.listdir(RESUMES_DIR)):
        path = os.path.join(RESUMES_DIR, name, "metadata.json")
        if not os.path.exists(path): continue
        with open(path) as f:
            m = json.load(f)
        n = len(m.get("chunk_ids", []))
        ts = m.get("created_at", "?")[:19]
        track = m.get("track") or "—"
        print(f"  {name:<30} {n:>3} chunks  track={track:<12}  {ts}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or "--list" in args:
        list_variants()
    else:
        review(args[0])
