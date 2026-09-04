# Chunk Review Feature — Spec

Design-intent document written before the feature was built; the feature has since shipped and is documented as-built in [`CAPABILITIES.md`](CAPABILITIES.md) and [`INTERNALS.md`](INTERNALS.md). Kept here for the reasoning behind design choices (data model, flag thresholds, prompt design) that isn't repeated elsewhere — treat those two docs as authoritative if anything here conflicts with current behavior.

Solves the core slow-state problem: after generation you have no visibility into why chunks were selected, no way to swap near-misses in, and no path to adjustment short of editing `resume_chunks.json` manually and force-regenning. This feature makes the selection auditable and adjustable in-browser with a preview loop, Ollama-powered fit assessment, and a synthesized summary (provider-agnostic LLM) from the actual selected content.

---

## Problem summary

Current flow after generation:
1. Look at resume PDF — not happy with a chunk
2. Manually edit `data/resume_chunks.json` to adjust priority
3. Re-embed if needed
4. Force-regen via API
5. Repeat blind

Target flow:
1. Open chunk review for a variant
2. See selected vs. near-miss chunks with score breakdown and fit flags
3. Toggle chunks in/out
4. Preview the re-rendered resume HTML in the right pane (local, no artifact write)
5. Run Ollama fit assessment on any chunk on-demand
6. When happy with selection, click "Apply" — commits + regens artifact
7. Click "Synthesize Summary" (always active, uses current Selected pile) → synthesized proposed summary shown alongside current — approve or discard

---

## Data changes

### Store scored pool in metadata at generation time

In `generation_pipeline.py`, after `match()` returns `matched_chunks`, also capture the pre-quota ranked list from `rank_chunks`. Store it in `metadata.json` under `scored_pool`.

Structure per entry:
```json
{
  "id": "proj_023",
  "score": 0.7341,
  "similarity": 0.6901,
  "keyword_score": 0.75,
  "priority_score": 1.0,
  "selected": true,
  "cut_reason": null
}
```

`cut_reason` values:
- `null` — selected
- `"threshold"` — scored below MIN_SCORE / SKILL_MIN_SCORE
- `"quota"` — passed threshold but type quota was already full (e.g. 5th project when limit is 4)

Floor for inclusion in pool: score ≥ 0.35 (anything below is noise, not useful to display).

Changes needed:
- `matcher.py` — `rank_chunks` returns pre-filter scored list alongside filtered list
- `variant_manager.py` — `export_metadata` accepts and stores `scored_pool`
- `generation_pipeline.py` — passes pool down the chain

---

## Backend — new endpoints

### `GET /variants/{id}/chunk-review`

Returns three tiers built from `metadata.json` scored_pool + current `resume_chunks.json` content:

```json
{
  "variant": "soc_security_v1",
  "job_preview": "...",
  "tiers": {
    "selected": [...],
    "candidates": [...],
    "dropped": [...]
  }
}
```

Each chunk entry:
```json
{
  "id": "proj_023",
  "type": "project",
  "title": "Example Project — Sample Chunk",
  "content": "...",
  "score": 0.7341,
  "similarity": 0.6901,
  "keyword_score": 0.75,
  "priority_score": 1.0,
  "selected": true,
  "cut_reason": null,
  "flags": ["strong_signal"],
  "ollama_assessment": null
}
```

Flags computed server-side:
- `"strong_signal"` — similarity ≥ 0.70
- `"marginal_fit"` — similarity < 0.56 (within 0.06 of threshold)
- `"no_keyword_overlap"` — keyword_score = 0.0
- `"low_keyword_overlap"` — keyword_score > 0 but matches < 3
- `"priority_carried"` — priority_score ≥ 0.9 but similarity < 0.60 (chunk is selected mainly by priority weight, not semantic fit)

`ollama_assessment` is `null` until the assess endpoint is called — cached in metadata after first run.

Tiers:
- `selected` — `cut_reason: null` entries
- `candidates` — `cut_reason: "threshold"` or `"quota"`, score ≥ 0.42
- `dropped` — score < 0.42, collapsed by default in UI, shown on expand

---

### `POST /variants/{id}/chunk-review/preview`

Takes a custom chunk selection, runs the full render pipeline, returns HTML string. No artifact writes, no variant changes.

Request:
```json
{ "chunk_ids": ["sum_003", "exp_001", "proj_023", "proj_018", "..."] }
```

Response:
```json
{ "html": "<html>...</html>" }
```

Uses existing `build_resume_data → render_html` path — identical to what generation uses, so preview IS the artifact.

---

### `POST /variants/{id}/chunk-review/apply`

Commits the custom selection and force-regens the artifact.

Request:
```json
{ "chunk_ids": ["sum_003", "exp_001", "proj_023", "..."] }
```

Re-runs `write_resume_bundle` + `write_edited_markdown` with the new selection. Updates `metadata.json` chunk_ids. Does NOT change scoring or the stored scored_pool (those reflect the original generation).

---

### `POST /variants/{id}/chunk-review/assess`

Runs Ollama Mistral assessment for a list of chunk IDs. Returns one-sentence verdicts, caches in `metadata.json` under `ollama_assessments: { chunk_id: "..." }`.

Request:
```json
{ "chunk_ids": ["exp_007", "proj_002"] }
```

Response:
```json
{
  "assessments": {
    "exp_007": "Weak: this bullet does not mention any skill or tool named in the job posting.",
    "proj_002": "Relevant: this bullet explicitly demonstrates a tool and skill named in the job posting."
  }
}
```

Prompt per chunk (Mistral via Ollama):
```
[INST]
Job role: {job_preview}

Resume section:
{chunk_content}

Does this section strengthen this specific job application? Reply in exactly one sentence starting with "Relevant:" or "Weak:".
[/INST]
```

Skips chunks already in cache. Runs sequentially (Ollama is single-threaded locally).

Model: `mistral:latest`. Fallback: `qwen2.5-coder:7b` if Mistral unavailable.

---

### `POST /variants/{id}/summary/synthesize`

Uses the currently-selected chunk_ids (or an override list) + job text to synthesize a new summary via the configured LLM (SUMMARY_SYNTH_PROVIDER/MODEL, provider-agnostic). Always on-demand, never auto-run.

Request:
```json
{ "chunk_ids": ["exp_001", "proj_023", "proj_018", "edu_001"] }
```

Response:
```json
{
  "proposed": "Backend engineer with three years shipping distributed systems in Python...",
  "current": "Backend engineer with three years shipping distributed systems in Python and Go..."
}
```

Prompt:
```
Job role: {job_text[:350]}

These resume sections are selected for this application:
{chunk_1_content}

{chunk_2_content}

...

Write a 3-sentence professional summary that:
- Opens with identity and the strongest credential for this specific role
- Highlights 2-3 themes visible across the sections above, without restating specific metrics or event IDs already in those sections
- Closes with what this candidate brings to this role
- No "I", no bullet points, plain paragraph
```

Token estimate: ~700 input, ~100 output. Cost: < $0.001 per call.

The proposed summary is shown alongside the current one. User approves → `POST /variants/{id}/chunk-review/apply` with the modified chunk list (summary chunk replaced with proposed text injected into the chunk entry). Or discard, no change.

Implementation note: approved summary is NOT written back to `resume_chunks.json` — it lives only in the variant's `resume_data.json` for this specific variant. Source chunks remain canonical.

---

## Frontend — `chunk_review.html`

Two-pane layout (matches `rewrite.html` pattern):
- **Left pane**: chunk tiers + controls
- **Right pane**: resume HTML preview (iframe, lazy-loaded)

### Toolbar

```
[← Back]   soc_security_v1 — Chunk Review   [Assess Fit]  [Synthesize Summary]  [Preview]  [Apply Selection]
```

- **Assess Fit** — runs Ollama assessment for all chunks in Selected + Candidates tiers. Shows spinner per chunk, populates assessment text in-place when done
- **Synthesize Summary** — always active, uses whatever is currently in the Selected pile. Opens a modal: proposed vs. current, approve or discard
- **Preview** — renders current Selected pile in the right iframe
- **Apply Selection** — commits + regens artifact, disabled until at least one chunk has been toggled from the original selection

### Chunk card

```
┌─────────────────────────────────────────────────────────────┐
│ [✓ Selected]  Example Project — Sample Chunk        project  │
│                                                             │
│ One-line description of what this chunk demonstrates...     │
│                                                             │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░  sim 0.69  ▓▓▓░░  kw 3  ●●●  p10 │
│ ████████████████████░░░░░░░░░░░░░░ [sim 72%][kw 13%][p 15%]│
│                                                             │
│ ✓ strong signal                                             │
│ Relevant: AD attack simulation directly maps to...          │
└─────────────────────────────────────────────────────────────┘
```

#### Score bar detail

Stacked horizontal bar, full width, three segments proportional to weight contribution:
- **Similarity segment** (72% of bar width): fills proportionally to sim score
  - sim ≥ 0.70: **teal** (`#14b8a6`)
  - sim 0.56–0.69: **amber** (`#f59e0b`)
  - sim ≤ 0.55: **rose** (`#f43f5e`)
- **Keyword segment** (13% of bar width): fills proportionally to keyword_score
  - ≥ 5 matches: teal
  - 2–4 matches: amber
  - 0–1 matches: rose
- **Priority segment** (15% of bar width): always slate (`#94a3b8`), fills proportionally to priority/10

Raw values shown inline: `sim 0.69  kw 3  p10`

#### Inline flags (text, below bar)

- `✓ strong signal` — sim ≥ 0.70
- `⚠ marginal fit` — sim < 0.56
- `⚠ no keyword overlap` — kw = 0
- `⚠ low keyword overlap` — kw matches 1–2
- `⚠ priority carried` — selected mainly by priority weight, low semantic fit

#### Ollama assessment (shown after Assess Fit runs)

Single line below flags, prefixed `Relevant:` or `Weak:`, dimmer text style.

#### Toggle

Click anywhere on the card header to move chunk between Selected ↔ Candidates. Cut-reason label updates to reflect manual override.

### Tiers

**Selected** — expanded by default, chunks in score order
**Candidates** — expanded by default, grouped by cut_reason: "near miss (quota)" / "near miss (threshold)"
**Dropped** — collapsed by default with count label "12 chunks below useful threshold — expand to view"

### Summary synthesis modal

Opens on "Synthesize Summary" click. Two-column text display:
- Left: **Current summary** (greyed)
- Right: **Proposed summary** (highlighted)

Buttons: `Approve — use proposed` / `Discard`

On approve: the proposed text replaces the summary chunk content for this variant only (not in resume_chunks.json). Preview re-renders automatically.

---

## Keyword overlap threshold

Change `compute_keyword_score` divisor in `matcher.py` from 4 to 8:
```python
return min(matches / 8, 1.0)
```

At divisor 4, max score reached at 4 matches — too easy to saturate. At 8, a chunk needs 8 matching job keywords to max out, making the keyword component genuinely discriminating. A strongly-relevant chunk against a well-matched JD will still hit 8+ matches easily. A weak/off-topic chunk against that same JD will score proportionally low.

---

## Color scheme and legend

### Score tier colors

| Color | Hex | Meaning |
|-------|-----|---------|
| Teal | `#14b8a6` | Strong — sim ≥ 0.70 or keyword ≥ 5 matches |
| Amber | `#f59e0b` | Passing — sim 0.56–0.69 or keyword 2–4 matches |
| Rose | `#f43f5e` | Weak/marginal — sim ≤ 0.55 or keyword 0–1 matches |
| Slate | `#94a3b8` | Priority segment (always, neutral — structural weight not semantic) |

### Stacked bar legend

Displayed as a persistent legend row above the first chunk card:

```
Score bar:  [━━━━━━━━━━━ Similarity (72%) ━━━━━━━━━━━][━━ Keywords (13%) ━━][━ Priority (15%) ━]
            ■ Teal = strong   ■ Amber = passing   ■ Rose = weak   ■ Slate = priority
```

Legend is sticky at the top of the chunk list pane so it stays visible while scrolling.

### Flag legend

Shown as a small collapsible "What do these mean?" block at the top of the left pane:

| Flag | Meaning |
|------|---------|
| `✓ strong signal` | Similarity ≥ 0.70 — chunk is semantically close to this job |
| `⚠ marginal fit` | Similarity ≤ 0.55 — squeaked past threshold, low semantic relevance |
| `⚠ no keyword overlap` | Zero matching tokens between chunk tags/keywords and job text |
| `⚠ low keyword overlap` | 1–2 matching tokens — weak terminology alignment |
| `⚠ priority carried` | High priority score is compensating for low similarity — chunk included mainly by weight, not fit |
| `cut — quota full` | Passed threshold but type limit already reached (e.g. 5th project, limit is 4) |
| `cut — below threshold` | Score did not reach MIN_SCORE (0.50) or SKILL_MIN_SCORE (0.43) |

### Ollama assessment prefix colors

- `Relevant:` — teal text
- `Weak:` — rose text

---

## Access point

Add "Chunk Review ↗" link to the panel job card (alongside "Rewrite Review ↗"), navigates to:
`/variants/{id}/chunk-review-ui` → serves `chunk_review.html`

---

## Build order

1. `matcher.py` — return scored_pool alongside final selection
2. `generation_pipeline.py` + `variant_manager.py` — store scored_pool in metadata
3. `GET /chunk-review` endpoint
4. `POST /chunk-review/preview` endpoint
5. `POST /chunk-review/assess` endpoint (Ollama)
6. `POST /summary/synthesize` endpoint (provider-agnostic)
7. `POST /chunk-review/apply` endpoint
8. `chunk_review.html` + JS
9. Panel link
