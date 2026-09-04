"""
scripts/chunk_stats.py
Usage: kratos/bin/python -m scripts.chunk_stats [--full]

Cross-variant chunk analytics — answers "which chunks are working?" across
all generated variants. Shows selection frequency, score trends, Ollama verdict
ratios, and never-selected active chunks.

--full  : also print each never-selected chunk's content (not just IDs)
"""

import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

RESUMES_DIR = "outputs/resumes"
CHUNKS_PATH = "data/resume_chunks.json"


def load_chunks_map():
    with open(CHUNKS_PATH) as f:
        return {c["id"]: c for c in json.load(f)}


def load_all_variants():
    """Returns list of (variant_name, metadata_dict) for all generated variants."""
    variants = []
    for name in sorted(os.listdir(RESUMES_DIR)):
        if name == "default":
            continue
        path = os.path.join(RESUMES_DIR, name, "metadata.json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            meta = json.load(f)
        variants.append((name, meta))
    return variants


def main():
    full = "--full" in sys.argv
    chunk_map = load_chunks_map()
    variants  = load_all_variants()

    if not variants:
        print("No generated variants found.")
        return

    # ── Aggregate stats per chunk ──────────────────────────────────────────
    stats = {}   # chunk_id → {times_selected, times_in_pool, scores, relevant, weak, variant_names}

    for name, meta in variants:
        selected_ids = set(meta.get("chunk_ids", []))
        pool         = meta.get("scored_pool", [])
        assessments  = meta.get("ollama_assessments", {})

        for entry in pool:
            cid = entry["id"]
            if cid not in stats:
                stats[cid] = {
                    "times_selected": 0,
                    "times_in_pool":  0,
                    "scores":         [],
                    "relevant":       0,
                    "weak":           0,
                    "variants":       [],
                }
            s = stats[cid]
            s["times_in_pool"] += 1
            s["scores"].append(entry["score"])
            if cid in selected_ids:
                s["times_selected"] += 1
                s["variants"].append(name)
            verdict = assessments.get(cid, "")
            if verdict.startswith("Relevant:"): s["relevant"] += 1
            elif verdict.startswith("Weak:"):   s["weak"]     += 1

    # ── Section 1: Most consistently selected ─────────────────────────────
    print(f"\n{'='*70}")
    print(f"  CHUNK STATS ACROSS {len(variants)} VARIANT(S)")
    print(f"  Variants: {', '.join(n for n, _ in variants)}")
    print(f"{'='*70}")

    selected_any = {cid: s for cid, s in stats.items() if s["times_selected"] > 0}
    by_freq = sorted(selected_any.items(), key=lambda x: x[1]["times_selected"], reverse=True)

    print(f"\n── TOP PERFORMERS (selected in most variants) ──")
    for cid, s in by_freq[:15]:
        chunk    = chunk_map.get(cid, {})
        avg_score = sum(s["scores"]) / len(s["scores"]) if s["scores"] else 0
        rv_str   = f"  ✓{s['relevant']}" if s["relevant"] else ""
        wk_str   = f"  ✗{s['weak']}"    if s["weak"]     else ""
        sel_str  = f"{s['times_selected']}/{s['times_in_pool']}"
        print(f"  [{cid}] sel={sel_str}  avg={avg_score:.3f}{rv_str}{wk_str}  {chunk.get('type','')}")
        print(f"    {(chunk.get('content') or '')[:100]}")

    # ── Section 2: Selected but consistently Weak ──────────────────────────
    weak_selected = [
        (cid, s) for cid, s in selected_any.items()
        if s["weak"] > 0 and s["relevant"] == 0
    ]
    weak_selected.sort(key=lambda x: x[1]["weak"], reverse=True)

    if weak_selected:
        print(f"\n── SELECTED BUT ALL ASSESSMENTS WEAK ({len(weak_selected)}) — rewrite or cut ──")
        for cid, s in weak_selected:
            chunk    = chunk_map.get(cid, {})
            avg_score = sum(s["scores"]) / len(s["scores"]) if s["scores"] else 0
            print(f"  [{cid}] weak={s['weak']}  avg={avg_score:.3f}  pri={chunk.get('priority','?')}  {chunk.get('type','')}")
            print(f"    {(chunk.get('content') or '')[:100]}")

    # ── Section 3: Never selected (but active and in pool) ────────────────
    never_selected_pool = [
        (cid, s) for cid, s in stats.items()
        if s["times_selected"] == 0 and s["times_in_pool"] > 0
    ]
    never_selected_pool.sort(key=lambda x: max(x[1]["scores"]) if x[1]["scores"] else 0, reverse=True)

    print(f"\n── NEVER SELECTED (reached pool but always cut, {len(never_selected_pool)}) ──")
    for cid, s in never_selected_pool[:20]:
        chunk     = chunk_map.get(cid, {})
        max_score = max(s["scores"]) if s["scores"] else 0
        avg_score = sum(s["scores"]) / len(s["scores"]) if s["scores"] else 0
        print(f"  [{cid}] max={max_score:.3f}  avg={avg_score:.3f}  pri={chunk.get('priority','?')}  {chunk.get('type','')}  {chunk.get('title','')[:40]}")
        if full:
            print(f"    {(chunk.get('content') or '')[:120]}")

    # ── Section 4: Active chunks never appearing in any pool ──────────────
    all_pooled_ids = set(stats.keys())
    active_chunks  = [c for c in chunk_map.values() if c.get("active", True)]
    never_pooled   = [c for c in active_chunks if c["id"] not in all_pooled_ids]

    if never_pooled:
        print(f"\n── NEVER REACHED POOL (active but scored below floor in all variants, {len(never_pooled)}) ──")
        by_type = {}
        for c in never_pooled:
            by_type.setdefault(c.get("type","?"), []).append(c)
        for t, chunks in sorted(by_type.items()):
            ids = ", ".join(c["id"] for c in chunks)
            print(f"  {t}: {ids}")

    # ── Section 5: Priority vs selection rate ─────────────────────────────
    print(f"\n── PRIORITY vs SELECTION RATE ──")
    buckets = {
        "high (8-10)":   [],
        "mid  (5-7)":    [],
        "low  (1-4)":    [],
    }
    for cid, s in stats.items():
        chunk = chunk_map.get(cid, {})
        pri   = chunk.get("priority", 5)
        rate  = s["times_selected"] / s["times_in_pool"] if s["times_in_pool"] else 0
        if pri >= 8:   buckets["high (8-10)"].append(rate)
        elif pri >= 5: buckets["mid  (5-7)"].append(rate)
        else:          buckets["low  (1-4)"].append(rate)

    for label, rates in buckets.items():
        if rates:
            avg = sum(rates) / len(rates)
            print(f"  {label}: {len(rates)} chunks  avg selection rate {avg:.0%}")

    # ── Section 6: Per-variant summary ────────────────────────────────────
    print(f"\n── PER-VARIANT SUMMARY ──")
    for name, meta in variants:
        n_sel    = len(meta.get("chunk_ids", []))
        n_pool   = len(meta.get("scored_pool", []))
        n_assess = len(meta.get("ollama_assessments", {}))
        track    = meta.get("track") or "—"
        ts       = (meta.get("created_at") or "")[:16]
        print(f"  {name:<28}  {n_sel:>3} selected / {n_pool:>3} in pool  assessed={n_assess}  track={track}  {ts}")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
