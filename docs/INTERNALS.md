# jobfitcv — System Internals

Reference doc for understanding how the pipeline actually works before making assumptions or changes.

---

## Pipeline flow (end to end)

```mermaid
flowchart TD
    A["Job posting captured\n(Chrome extension)"] --> B["POST /jobs/ingest"]
    B --> C["clean_job_text()\nstrip nav/footer noise"]
    C --> D["classify_job()\ntaxonomy embedding cosine sim\n→ track + focus"]
    C --> E["summarize_job_text()\nLLM call → short structured summary"]
    E --> F[("Job.raw_text\nstored in DB")]
    C --> G["jd_actual.txt\nfull verbatim posting, never scored"]
    D --> H
    F --> H["POST /jobs/{id}/generate"]

    H --> I["embed_text(raw_text)\nsentence-transformer → 768-dim vector"]
    I --> J["match_with_pool()\nscore every active chunk:\n0.72 sim + 0.13 keyword + 0.15 priority"]
    J --> K["threshold + quota + group-cap\n→ selected set + scored_pool"]
    K --> L["build_resume_data()\ngroups chunks into resume schema"]
    L --> M["create_variant()\ndir keyed by job_id — one job, one dir"]
    M --> N{"ENABLE_REWRITES?"}
    N -- "False (default)" --> P["render_markdown/html()"]
    N -- "True" --> O["apply_rewrite_hooks()\nper-bullet LLM rewrite for ATS alignment"]
    O --> P
    P --> Q["write_resume_bundle()\nresume.md / resume.html / resume.pdf"]
    Q --> R[("outputs/resumes/{job_id}/")]

    R --> S["Chunk Review UI\nreads scored_pool from metadata.json"]
    S --> T["toggle / reorder / Assess Fit (Ollama) / synthesize summary"]
    T --> U["Apply Selection\nrebuilds artifacts from working selection\n(scored_pool untouched)"]
    U --> R
```

---

## LLM provider architecture (`app/core/llm_client.py`)

Every LLM-touching feature routes through one function, `generate_completion()`, which is provider-agnostic and independently configurable per feature — switching one feature's provider never affects another's.

```mermaid
flowchart LR
    subgraph Features
        R["Rewrite pipeline\n(off by default)"]
        C["Cover letters"]
        J["JD summarization\n(at ingest)"]
        W["Wizard\nchunk creation"]
        S["Chunk review\nsummary synthesis"]
    end

    R -- "LLM_PROVIDER / LLM_MODEL" --> GC
    C -- "CL_PROVIDER / CL_MODEL" --> GC
    J -- "JD_SUMMARY_PROVIDER / JD_SUMMARY_MODEL" --> GC
    W -- "WIZARD_PROVIDER / WIZARD_MODEL" --> GC
    S -- "SUMMARY_SYNTH_PROVIDER / SUMMARY_SYNTH_MODEL" --> GC

    GC["generate_completion()\napp/core/llm_client.py"]

    GC --> AN["Anthropic SDK\n(default)"]
    GC --> OA["OpenAI-compatible HTTP\n(OpenAI, OpenRouter, Groq, Together, ...)"]
    GC --> OL["Ollama local HTTP\n(no API key)"]
```

Each feature's `*_PROVIDER`/`*_MODEL` pair defaults to Anthropic and its own pre-existing model choice — nothing changes behavior unless you explicitly set a variable. See `.env.example` for the full list.

**Separately, not part of this system:** the chunk-review "Assess Fit" feature calls Ollama's HTTP API directly (`_ollama_assess()` in `chunk_review.py`), not through `generate_completion()` — it has no provider option, Ollama only.

---

## Track classification (`taxonomy_classifier.py`)

- Embeds the job text, cosine-sims against every `.npy` file in `data/taxonomy/`
- Picks the highest-scoring file → splits on `_` to get `track` + `focus`
- Splits the winning filename on the first `_` to derive the short track name: `cloud_devops.npy` → `"cloud"`, `ai_ml.npy` → `"ai"`, `soc_security.npy` → `"soc"`. Summary chunks' `track` field must use these short names.
- Available tracks: `soc`, `sysadmin`, `backend`, `cloud`, `it_support`, `ai`
- Track classification affects TWO things only: (1) which summary chunks are eligible, (2) variant reuse gate (see below)

---

## Chunk scoring (`matcher.py`)

**What track affects:**
- `filter_summaries_by_track()` removes summary chunks where `chunk.track != None AND chunk.track != current_track`
- Only summary chunks are track-filtered. Experience, project, skill, education all compete regardless of track.

**Scoring formula (per chunk):**
```
final_score = 0.72 * cosine_similarity(job_vec, chunk_vec)
            + keyword_weight * keyword_overlap_score
            + 0.15 * (chunk.priority / 10)
```
- `keyword_weight` = 0.13 for all chunk types (skills included)
- `keyword_overlap_score` = min(matching_tokens / 4, 1.0)

**Keyword overlap — how tags and keywords feed in:**
```python
tag_text   = " ".join(t.replace("-", " ") for t in chunk.get("tags", []))
kw_text    = " ".join(chunk.get("keywords", []))
chunk_terms = extract_keywords(f"{tag_text} {kw_text}")
```
Hyphens in tags are split to spaces BEFORE `extract_keywords`, so `aws-security` → `aws` + `security`. Tags and keywords compete equally. Job text goes through the same `extract_keywords` normalization on its side.

**`extract_keywords` survival rules:**
- Lowercased, punctuation stripped
- Alias map applied (e.g. `ad` → `directory`, `containers` → `docker`)
- KNOWN_TERMS: always kept regardless of length (includes `iam`, `mfa`, `ai`, `ml`, `soc`, etc.)
- STOPWORDS: dropped
- Everything else: kept if `len >= 3`
- Tokens starting with a digit: dropped

**Thresholds (via `_threshold(chunk_type)` in matcher.py):**
- Skill chunks: `SKILL_MIN_SCORE = 0.43`
- Education chunks: `EDUCATION_MIN_SCORE = 0.44` — edu chunks score ~0.47–0.49 on target tech JDs (clear threshold); retail/unrelated JDs score much lower and are cut naturally, avoiding overqualification signal
- All other chunks: `MIN_SCORE = 0.50`
- Pool floor: `POOL_FLOOR = 0.35` — chunks below this don't appear in chunk review at all
- If nothing passes threshold, top 2 by score are taken as fallback

**Quotas (after threshold filter):**
```python
QUOTAS = { "experience": 5, "project": 5, "skill": 20, "summary": 1, "education": 2 }
```
Within each type, top N by score are taken. `GROUP_CAP = 3` — max bullets from any single `group_key` in experience or project pools.

**Education ordering:** sorted by `priority` descending in `build_resume_data()` — not by score. This ensures chronological (most recent / highest priority) ordering regardless of which job the resume is for.

---

## Summary chunk selection

There are 6 summary chunks:
| ID | Track | Priority | Notes |
|----|-------|----------|-------|
| sum_001 | None | 7 | Stale — "software engineer + frontend" framing, predates security focus. Consider `active:false`. |
| sum_002 | sysadmin | 10 | AD/SIEM/infra focused |
| sum_003 | soc | 10 | SOC tooling, MITRE ATT&CK, Wazuh, threat detection |
| sum_004 | None | 10 | Broad — infra + security + software + AI (current general fallback) |
| sum_005 | cloud | 10 | Cloud/DevSecOps focused |
| sum_006 | ai | 10 | AI/ML engineering focused |

**Why sum_004 wins most of the time:**
sum_004's embedding sits at the centroid of infra + security + engineering language. Generalist postings hit all three, so sum_004 consistently outscores track-specific summaries in cosine similarity (e.g. 0.7714 vs sum_003's 0.7081 against a cybersecurity engineer job).

To make a track-specific summary win: either give it a meaningfully higher priority (current max is 10, same as sum_004) or restructure the scorer to hard-prefer track-matched summaries.

---

## Variant creation (`variant_manager.py` + `generation_pipeline.py`)

**No reuse detection exists in the current code.** Earlier versions of this app compared new jobs against existing variants by cosine similarity + Jaccard keyword overlap and shared a single output directory across matching jobs (`{track}_{focus}_v{N}` naming, thin reference DB rows, a `reused` flag). That system was removed — confirmed 2026-09 by reading `variant_manager.py` and `jobs.py` directly; no cosine/Jaccard comparison exists anywhere in the codebase. It will not be coming back. The `reused` column still exists on the `Variant` table but nothing sets it to `1` anymore — vestigial.

**Current behavior, much simpler:**
- Every ingested job gets a UUID `job_id` (`uuid.uuid4()`).
- `create_variant(job_id, ...)` creates a directory keyed directly by that `job_id` — **one job, one directory, always.**
- `POST /jobs/{job_id}/generate`: if a variant already exists for that `job_id`, returns it as-is (no re-run). With `?force=true`, deletes the existing output directory + DB row, then runs the full pipeline again to produce a fresh variant at the same path.
- No shared directories between jobs, no version-number suffixes, no reference rows — each job's artifacts are fully independent.

---

## Artifact layout

```
outputs/resumes/{job_id}/
  job_embedding.npy       # job vector used for scoring + future reuse detection
  metadata.json           # track, focus, chunk_ids, job_keywords, job_preview, artifacts
  generated/
    resume.md
    resume.html
    resume_data.json      # structured resume object (the builder output)
  edited/
    resume.edited.md      # seeded from generated, user edits land here
  rewrites/
    pending_rewrite.json  # current rewrite session diff
    diff_*.json           # timestamped saved diffs (up to 10)
```

---

## Known gaps / quirks

- **sum_001 stale** — "software engineer + frontend" framing predates current security focus. Recommend setting `active:false` in wizard.
- **sum_004 dominates for generic JDs** — broad infra+security embedding sits close to the centroid of most postings. Track-specific summaries win when the JD is heavily specialized.
- **Server reload (watchfiles) kills in-progress generation** — uvicorn `--reload` restarts the process when any watched file changes mid-generation. Job status stays `"generating"` in the DB forever. Fix: `UPDATE jobs SET status='ingested' WHERE id='...'` in SQLite, then re-trigger.
- **Tag keyword overlap limited by job text** — adding tags to chunks only helps if the job posting actually uses those terms. Tags don't affect embedding similarity, only the `0.13 * keyword_score` component.
- **Near-miss chunks visible in chunk review** — pool floor 0.35 means chunks in the 0.35–0.50 range appear in the Dropped tier and can be manually toggled in.
