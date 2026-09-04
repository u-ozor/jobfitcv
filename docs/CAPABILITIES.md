# jobfitcv — Capabilities

## Job Capture
- Captures any job posting via Chrome extension side panel
- **URL-based capture** — paste a LinkedIn or Indeed URL directly into the panel URL field (below the Capture button). Background service worker opens a silent background tab (`active: false`), waits for the page to fully load, delays 2 s for SPA rendering, extracts via the pre-injected content script, closes the tab, and returns data to the panel preview. No new extension permissions required — `content_scripts: [{matches: ["<all_urls>"]}]` pre-injects `content.js` into all tabs so messaging works without the `tabs` permission. Manual on-page capture remains the fallback.
- Auto-clicks LinkedIn "See more" before extracting text
- Editable preview before saving — trim noise, correct title
- **Category select** — Step 2 preview includes a category picker (`Main | PT | Bridge | Other`). Set before confirming ingest; changeable later via tracker or API.
- Duplicate detection: same URL (query params stripped) returns existing record instead of creating a new one
- Secondary dedup: SHA256 text fingerprint catches same job posted on multiple boards
- Auto-cleans captured text: strips LinkedIn nav noise, language selector footer, similar-jobs section
- Company name extracted from page title and og:site_name (Greenhouse, LinkedIn, Indeed, Glassdoor patterns)
- **Role match badge** — at ingest time, the job title is embedded and compared against `data/job_targets.json` (currently 24 target role phrases). Best cosine similarity across all phrases determines the badge: **Strong match** (sim ≥ 0.70, teal), **Possible match** (0.58 ≤ sim < 0.70, amber), **Outside target** (sim < 0.58, rose). Shown as a chip next to the track label in the panel and every job card. Has no effect on generation — candidate-intent signal only. Target phrases are editable in `data/job_targets.json`; module-level cache is re-computed on next ingest after server restart. **Known noise**: long or noisy job titles (e.g. `AI Engineer, Agent Product (Full-time/Part-time) (Canada)`) produce unreliable scores because employment-type and location boilerplate shift the embedding. The job title is stored as submitted; no secondary cleaning is applied before scoring.
- **Company required at ingest** — Step 2 preview includes a required company field, pre-populated from auto-detection (og:site_name → title parsing). Confirm is blocked if empty. Company is always user-confirmed before save.
- **Job title cleaned before preview** — `cleanTitle()` strips `| <anything>` suffix generically before showing the title in Step 2. Handles any job board using `Title | Platform` convention. User sees and can correct the result before saving.
- **Job description trim guide** — label on the description field in Step 2 reads "trim everything above 'About the role', 'Responsibilities', or similar" — prompts user to remove platform boilerplate before the role content begins.

## Resume Generation
- Scores resume chunks against job embedding (cosine similarity + keyword overlap + priority weight)
- Track detection: classifies job as `sysadmin`, `soc`, `backend`, `cloud`, `it_support`, or `ai` via taxonomy embeddings in `data/taxonomy/*.npy` (short names derived from the `.npy` filename — see Known Limitations below)
- Track-stable summaries: each track has a dedicated summary chunk; universal (`track=null`) summary is fallback
- One variant per job — new job always generates fresh; same job re-triggered returns existing output
- Output: `resume.md`, `resume.html`, `resume.pdf` in `outputs/resumes/{job_id}/generated/`
- **Force regenerate** ("↺ Re-generate" in the scoped view, or "Re-gen" on the job card): calls `?force=true`, deletes the existing output directory + DB row, then runs a full fresh generation at the same path.

**Scoring weights** (`app/core/config.py`):
| Component | Weight | Source |
|-----------|--------|--------|
| Embedding similarity | 0.72 | Cosine between job vec and chunk vec |
| Keyword overlap | 0.13 | Tag + keywords field intersection with JD tokens |
| Priority | 0.15 | `chunk.priority / 10` (1–10 scale) |

**Thresholds and quotas** (`app/core/config.py`, `app/generation/matcher.py`):
| Name | Value | Meaning |
|------|-------|---------|
| `MIN_SCORE` | 0.50 | Final score floor for general chunk types |
| `SKILL_MIN_SCORE` | 0.43 | Score floor for skill chunks (short text, lower signal) |
| `EDUCATION_MIN_SCORE` | 0.44 | Score floor for education chunks — clears threshold on tech JDs (~0.47–0.49) but gets cut naturally on unrelated JDs, handling overqualification without special-casing |
| `POOL_FLOOR` | 0.35 | Minimum score to appear in the chunk review scored pool at all |
| `GROUP_CAP` | 3 | Max bullets selected from any single `group_key` within experience or project pools |
| Quota: experience | 5 | Max experience bullets per generated resume |
| Quota: project | 5 | Max project bullets per generated resume |
| Quota: skill | 20 | Max skill entries per generated resume |
| Quota: summary | 1 | Always exactly one summary |
| Quota: education | 2 | Max education entries |

**Chunk review inline flags** (`extension/chunk_review.js`):
| Flag | Condition |
|------|-----------|
| `✓ strong signal` | `similarity ≥ 0.70` |
| `⚠ marginal fit` | `similarity < 0.56` |
| `⚠ no keyword overlap` | `keyword_score == 0` |
| `⚠ low keyword overlap` | `0 < keyword_score < 0.25` |
| `⚠ priority carried` | `priority ≥ 0.8` and `similarity < 0.60` |

## Default Resume
- Always-on panel section — "Default CV" shown at the top of the panel at all times, independent of job capture
- Includes ALL active chunks — no quotas, no group cap, no scoring. Summary capped at 1: highest-priority `track=null` summary is selected; track-specific summaries land in the Candidates tier of chunk review so the user can swap if needed
- Regenerate button in panel; chunk review accessible via chunk_review.html?variant=default
- DB rows (`default-cv` Job + `default` Variant) seeded at server startup via `lifespan` — idempotent
- Output: `outputs/resumes/default/`
- Endpoints: `GET /default-cv/status`, `POST /default-cv/generate`

## Chunk Wizard
- Browser UI at `http://localhost:8000/wizard`
- Converts plain-language descriptions into structured resume chunks via the configured LLM (Anthropic Haiku by default, provider-agnostic via `WIZARD_PROVIDER`/`WIZARD_MODEL`)
- Types: experience, project, summary, skills
- Preview → approve → commit flow; IDs assigned sequentially at commit, not preview
- Theme-aware via the shared 5-theme system (`jaa-theme` localStorage key)
- **Edit Existing mode** — left pane lists all chunks grouped by type (filterable by search); click any row to open edit form on the right. Right pane is always in focus (independent scroll). Inactive chunks shown with strikethrough title and `off` badge.
- **Active toggle** — each chunk has an Active/Inactive toggle in the edit form header. Saving with Inactive sets `active: false` in `resume_chunks.json`, excluding the chunk from all future matching and generation without deleting it.
- **Keywords field hidden for non-skill types** — keywords on non-skill chunks are auto-generated by the configured LLM at creation; the wizard edit form deliberately hides that field for experience/project/summary/education to prevent drift. Only skill chunks expose the keywords field.
- **Content field** — single `<textarea>` (each chunk stores exactly one bullet string). Editing updates `resume_chunks.json` and triggers a full re-embed automatically on save.
- **Deeplink** — `http://localhost:8000/wizard?edit=<chunk_id>` opens the wizard directly into Edit Existing mode with that chunk's form pre-populated.

## Resume Editing
- In-browser markdown editor (`Edit Resume` link opens `edit.html` as a Chrome extension tab)
- Edits saved to `resume.edited.md` in `outputs/resumes/{variant}/edited/`
- Save & Regenerate: re-renders HTML + PDF from edited markdown without re-scoring chunks
- Original generated markdown preserved — regen from edit does not overwrite it

## Rewrite Review
- Manual, on-demand only — generation does NOT auto-rewrite
- **Merged into Chunk Review** — "Rewrite" button in the chunk review header fires `POST /variants/{id}/rewrite/preview`, populates inline diff panels on selected cards. No separate page needed for the standard flow.
- Standalone `rewrite.html` page still available (history dropdown, side-by-side iframe) via "✎ Rewrite Review ↗" in panel for advanced use
- Each selected chunk card with a pending rewrite shows a collapsible `↻ rewrite available` panel — expand to see before/after, click Accept or leave it
- Accepted rewrites are bundled into Apply Selection as `rewrite_overrides {chunk_id: after_content}` — applied before rendering, `resume_chunks.json` untouched
- Stale guard: if chunk content changed since rewrite was generated (`before` ≠ current content), panel shows "stale — re-run Rewrite" instead of diff
- `rewrite_diff.py` includes `chunk_id` on every diff item (resolved from `resume_data` at generation time) — required for inline merge; old diffs without `chunk_id` still load in standalone rewrite.html
- History: up to 10 saved diff snapshots in `outputs/resumes/{variant}/rewrites/`; applying from history validates `before` text still matches current resume and returns mismatch list

## Chunk Review
- Full-tab review page (`chunk_review.html`) opened via "⊞ Chunk Review ↗" button in the panel links section (visible after generation)
- Shows four tiers: **Selected** (chunks in the generated resume), **Candidates** (near-misses cut by threshold or quota), **Dropped** (score below pool floor), **Disabled** (`active:false` chunks — excluded before scoring, shown for visibility only)
- Each card shows: title, type, content preview, stacked score bar (Similarity / Keywords / Priority), raw values (sim, kw count, priority), inline flags, and an **↗ edit** link (opens wizard edit deeplink in new tab)
- **Stacked score bar** — three segments proportional to scoring weight: Similarity (72%), Keywords (13%), Priority (15%). Each segment color-coded independently: teal (strong), amber (passing), rose (weak). Priority is always slate. Colors are theme-aware — adjust automatically when switching dark ↔ warm.
- **Inline flags** — `✓ strong signal` (sim ≥ 0.70), `⚠ marginal fit` (sim < 0.56), `⚠ no keyword overlap`, `⚠ low keyword overlap`, `⚠ priority carried` (high priority compensating for low similarity)
- **Toggle** — click any card header (not the drag handle or ↗ edit link) to move a chunk between Selected ↔ Candidates. Apply button enables only when selection differs from the original generation.
- **Drag-and-drop reorder** — selected tier cards have a ⠿ drag handle. Dragging reorders `workingSelected`, which controls the bullet order in the resume output. Marks dirty; takes effect on Apply Selection or Preview.
- **View toggle** — "Tier view" (default) shows Selected / Candidates / Dropped / Disabled tiers. "Category view" groups all chunks by type (summary → experience → project → skill → education) with collapsible sub-sections per tier within each type. Useful for auditing a specific type without scrolling through the full list.
- **Quota row** — shows `type used/limit` for all chunk types, updated live as the selection changes.
- **Preview** — POST current selection → renders HTML in right pane without writing any artifacts
- **Assess Fit** — runs Ollama `mistral:latest` (fallback: `qwen2.5-coder:7b`) on all selected + candidate chunks. Strict prompt includes an explicit RULE: if the skill/tool is not explicitly named in the JD excerpt, the model MUST start with "Weak:" — no inference, no extrapolation from vague phrases. Passes chunk tags alongside content. Verdicts cached in `metadata.json` under `ollama_assessments`. Job context textarea shows the full `job_raw_text` from DB (not the 800-char `job_preview` truncation) — what you see is what Ollama receives. Editing the textarea and re-running Assess busts the cache and forces re-evaluation against the new text.
- **Synthesize Summary** — POST selected chunk IDs to the configured LLM (Anthropic Haiku by default, provider-agnostic via `SUMMARY_SYNTH_PROVIDER`/`SUMMARY_SYNTH_MODEL`); returns a proposed 3-sentence summary alongside the current one in a two-column modal. Approve → commits with the proposed text replacing the summary chunk. Proposed text lives only in `resume_data.json` for that variant; `resume_chunks.json` is untouched
- **Apply Selection** — commits the working selection: re-runs `build_resume_data → render_html → write_resume_bundle → write_edited_markdown`, updates `metadata.json` chunk_ids. Does not change the stored `scored_pool` (that reflects the original generation). Accepts optional `rewrite_overrides {chunk_id: after_content}` — accepted inline rewrites are substituted before rendering; `resume_chunks.json` is never modified
- Sticky legend at top of left pane (score bar segments + colors). Collapsible flag legend explaining all flag types.

## DOM Form Fill
- **Clean fill** (Greenhouse, Lever detected by URL): uses known, tested field selectors — reliable
- **Attempt fill** (any other site): scans all input/textarea elements, classifies fields by label/placeholder/name/id keywords, fills what it can
- Fills: first name, last name, email, phone, LinkedIn URL, GitHub URL, location, cover letter
- React/Vue compatible: fires native setter + input/change events so framework state updates
- EEO / demographic fields excluded (ethnicity, race, gender, veteran, disability)
- Profile data source: `data/user_profile.json`

## Cover Letter Generation
- Generates tailored cover letters via the configured LLM (Anthropic claude-sonnet-4-6 by default; provider-agnostic via `CL_PROVIDER`/`CL_MODEL`)
- 3 tones: Professional, Direct, Warm
- Opens company mission, specific requirements, and named tools from the JD — uses that exact language
- Saved to `outputs/cover_letters/{job_id}/cover_letter_{tone}.txt` and `.md`
- Panel UI: tone picker, generate, inline textarea, "Open full ↗" HTML view
- Tone switch re-loads any saved letter for that tone without regenerating
- **Bio/constraints field** — `data/user_profile.json` → `cover_letter` key is passed to the model as ground truth before the JD. Use it to state hard facts the model must not contradict: languages spoken, work authorization, availability, things the candidate does NOT have (clearance, license) that a JD might imply. The model treats this as fact — it overrides JD implications. Update this field whenever a new constraint is discovered (e.g. a cover letter fabricated a claim from the JD).

## Application Tracking
- Full-tab tracking page (`Tracking ↗` in panel header)
- **Week-based batch grouping** — jobs are grouped by the calendar week they were ingested (Monday–Sunday). Week header row shows the date range (e.g. "Aug 25 – Aug 31, 2026") and job count. Click the header to collapse/expand (session-only, not persisted). A "batch" = one week of ingestions — no manual batch creation or drag-reorder needed.
- **`week_label` field** — stored on the Job row as the Monday of ingestion week (`YYYY-MM-DD`). Derived server-side at ingest; changeable via `PATCH /jobs/{id}` with `{week_label: "YYYY-MM-DD"}` if needed.
- **`job_category` field** — `Main | PT | Bridge | Other`. Colored badge next to job title (PT = purple, Bridge = blue, Other = grey; Main = no badge). Set at ingest via panel category select; editable via detail row select or PATCH.
- Status per job: `Applied | Screening | Interviewing | Offer | Rejected | Withdrawn | Archived | Parked`
  - **Parked** — resume ready but posting is "no longer accepting." Keeps the output available to reuse if the role reopens. Delete button stays muted (Parked is not in HOT_STATUSES).
- **Search bar** — real-time filter across title, company, track, focus, app_status, category, and week label. Searching un-collapses matching week groups automatically.
- Each row expands to a two-column detail panel: **Notes (left)** and **Assessment (right)**
- **Assessment field** — free-text verdict slot; first word is parsed into a color-coded chip: `Submit` (green), `Caveat` (yellow), `Skip` (red), or pending if blank. Auto-saves on blur.
- **Notes field** — free-text scratchpad, auto-saves on blur
- Delete button highlights red when status is Rejected, Withdrawn, or Archived
- Delete permanently removes DB record + all output files; shows error alert if the server-side delete fails so the user knows the row will reappear on reload

## Panel — Recent Jobs
- All ingested jobs shown in a scrollable list at the bottom of the panel
- Jobs without output: Generate button
- Jobs with output: View HTML, Edit, Re-generate (with confirm), Rewrite
- Re-generate with `force=true`: wipes output dir + DB row, then runs fresh
- Scoped job view has its own "↺ Re-generate" button in the output links area
- Delete from panel: confirm dialog required
- Search filter: title, company, track — filters the full list in real time
- **× clear button** — small button in the job-title row (no box) resets the panel from job-scope back to the capture state without reopening the extension
- Auto-scope on tab switch: navigating to a job's URL auto-scopes the panel to that job
- **Five themes** (dark / warm / orange / blue / pink) shown as colored circle swatches — each circle is a conic-gradient split of that theme's background and accent colors. Clicking a circle applies the theme instantly across all extension pages. Persisted via `jaa-theme` localStorage key shared by all pages.

## Resume Preview
- "▶ Preview in panel" toggle renders the generated HTML in an inline iframe
- Lazy loads on first open; resets when job scope changes
- Refreshes automatically after applying rewrites

## Logging
- Rotating file log at `logs/app.log` (1MB max, 5 backups)
- Logs: job ingest, generation start/done/error, rewrite preview/apply
- Silent under normal operation — only meaningful on errors

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | /jobs/ingest | Capture + clean + classify job text |
| GET | /jobs/ | List all jobs (includes app_status, notes, url) |
| GET | /jobs/{id} | Get single job with raw_text |
| PATCH | /jobs/{id} | Update app_status, notes, figurative_assessment, job_category, week_label |
| DELETE | /jobs/{id} | Delete job + variant + output files |
| POST | /jobs/{id}/generate | Generate resume (force=true to overwrite) |
| POST | /jobs/{id}/cover_letter | Generate cover letter (tone param) |
| GET | /jobs/{id}/cover_letter | Load saved cover letter for tone |
| GET | /jobs/{id}/cover_letter/html | Render cover letter as HTML |
| GET | /variants/ | List all variants |
| GET | /variants/{id}/html | Serve resume HTML |
| GET | /variants/{id}/pdf | Download resume PDF (local only) |
| GET | /variants/{id}/markdown | Get editable markdown |
| POST | /variants/{id}/regenerate | Re-render HTML+PDF from edited markdown |
| POST | /variants/{id}/rewrite/preview | Run rewrites, save diff snapshot, return before/after items |
| GET | /variants/{id}/rewrite/pending | Return current pending diff or 404 |
| GET | /variants/{id}/rewrite/diffs | List saved diff snapshots newest-first with metadata |
| GET | /variants/{id}/rewrite/diffs/{filename} | Load a specific saved diff by filename |
| POST | /variants/{id}/rewrite/apply | Apply approved indices; returns applied count + mismatches list |
| DELETE | /variants/{id}/rewrite/pending | Discard pending rewrite |
| GET | /variants/{id}/chunk-review | Scored pool enriched with chunk content, flags, assessments — three tiers |
| POST | /variants/{id}/chunk-review/preview | Render HTML for a custom chunk_ids list (no artifact write) |
| POST | /variants/{id}/chunk-review/apply | Commit selection, regen artifacts; accepts optional summary_override |
| POST | /variants/{id}/chunk-review/assess | Ollama fit assessment per chunk; cached in metadata |
| POST | /variants/{id}/summary/synthesize | Configured-LLM summary from selected chunks; returns proposed + current |
| GET | /profile | Return user_profile.json |
| GET | /experience | Return experience.json |
| GET | /wizard | Chunk wizard UI (add `?edit=<id>` to deeplink into Edit Existing) |
| POST | /wizard/preview | Preview chunk generation (no commit) |
| POST | /wizard/commit | Commit approved chunks to resume_chunks.json |
| GET | /wizard/status | Chunk counts and next IDs by type |
| GET | /wizard/chunks | List all chunks including inactive |
| PUT | /wizard/chunks/{id} | Update chunk fields; auto re-embeds on save |
| POST | /jobs/clean_preview | Return backend-cleaned job text (strips nav noise) |

## Extension Pages and Theme System
| File | Opens via | Purpose |
|------|-----------|---------|
| panel.html | Chrome side panel | Main capture + generate + cover letter flow |
| edit.html | "Edit Resume" link in panel | Markdown resume editor |
| tracking.html | "Tracking ↗" in panel header | Full application tracker with search and expandable rows |
| rewrite.html | "✎ Rewrite Review ↗" in panel | Full-tab rewrite review with history dropdown |
| chunk_review.html | "⊞ Chunk Review ↗" in panel | Full-tab chunk selection review with score bars, flags, assess, synthesize |
| `app/static/wizard.html` | `http://localhost:8000/wizard` | Chunk wizard — add/edit resume chunks (served by FastAPI, not extension) |

**Shared theme infrastructure (extension pages only):**
- `extension/themes.css` — CSS custom property definitions for all 5 themes; linked by every extension HTML page
- `extension/theme-picker.js` — renders circle swatches into `[data-theme-picker]` elements; manages `jaa-theme` localStorage key
- Wizard (`app/static/wizard.html`) inlines equivalent theme CSS and picker JS since it is served over HTTP from the local API, not packaged as a Chrome extension file

## API Endpoints (additions)
| Method | Path | Description |
|--------|------|-------------|
| GET | /wizard/chunks | List all chunks (including inactive) |
| PUT | /wizard/chunks/{id} | Update chunk fields; triggers re-embed synchronously |
| POST | /jobs/clean_preview | Returns backend-cleaned version of raw job text |

## Known Limitations / Quirks
- PDF generation uses Playwright (Chromium) — not suitable for cloud/Docker on low-RAM instances; local only
- LinkedIn "See more" auto-click uses `.jobs-description__footer-button` selector — may break on LinkedIn DOM changes
- Footer cleaning is heuristic — some similar-jobs noise may survive if LinkedIn omits standard heading text
- DOM fill on company-custom forms is best-effort only — field identification via text heuristics
- Rewrite quality depends on the configured model — validator rejects slop but results vary
- Track field on non-summary chunks is stored but inert — only summary selection is track-filtered
- Moving or renaming the project directory after running `install.sh` breaks venv script shebangs (all `kratos/bin/` wrappers have absolute paths baked in at install time); fix by deleting `kratos/` and re-running `install.sh`. `start.sh` uses `python -m uvicorn` to avoid this for the server itself
- **Ollama assess cache persists across prompt changes** — if Assess was run before the strict prompt was deployed, old "rubber stamp" Relevant: verdicts are cached. Paste updated job text into the Job context textarea and re-run Assess to bust the cache for that variant.
- **Assess Fit always uses full raw JD** — the assess endpoint fetches `raw_text` directly from the DB for the job linked to each variant. The Job context textarea override is still available to test a different context or for edge cases where the job record no longer exists (fallback: stored `job_preview`).
- **Taxonomy track short names** — classifier returns `soc`, `sysadmin`, `cloud`, `ai`, `backend`, `it` (derived from `.npy` filename split on first `_`). Summary chunk `track` field must use these short names — not `cloud_devops`, `ai_ml`, etc.
- **Server reload kills background tasks** — uvicorn `--reload` kills in-progress generation tasks on any file change. Jobs can get stuck at "generating". Fix: `UPDATE jobs SET status='ingested' WHERE id='...'` in SQLite.
- **Drag-and-drop reorder is working-state only** — reordering workingSelected marks the Apply button dirty but doesn't persist until Apply Selection is clicked. Preview renders the working order immediately.
- **Active toggle saves on Save, not immediately** — flipping a chunk to Inactive in the wizard edit form takes effect when Save is clicked (triggers re-embed). Chunk review needs to be re-opened to reflect the change in the Disabled tier.
- **Score bar JS colors are computed at card render time** — switching themes after the page loads does not recolor already-rendered cards. Reload the page after a theme switch to see correct score bar colors.

## Future Features

### Analysis & Intelligence

- **Chunk score trend tracking** — Per chunk, maintain a time-series of (timestamp, score, variant_id) across all generated variants sorted by `created_at`. Exposed via a `--trend` flag on `chunk_stats.py`: shows whether each chunk's average score is rising (priority tuning working) or falling (chunk becoming less relevant to the roles you're targeting). Implementation: `chunk_stats.py` already reads all scored_pools — adding variant timestamp ordering and per-chunk score history requires no new data collection, only sorting and slope computation. Useful signal for knowing when a priority boost actually changed selection outcomes.

- **Chunk duplicate / overlap detection** — Load `resume_embeddings.npy` and compute pairwise cosine similarity between chunks of the same type. Flag pairs with similarity >0.82 as potential duplicates or overlaps. Output: "exp_001 and exp_003 are 87% similar — same role, consider merging or differentiating the angle." Implementation: add `--audit` flag to `chunk_stats.py` or a dedicated `scripts/chunk_audit.py`. Confirmed planned.

- **Application outcome → chunk correlation** — After enough applications with tracked outcomes (Screening / Interviewing / Offer vs Rejected / Archived), correlate which chunks were selected in variants that reached interview stage vs those that didn't. Identifies which bullets actually land. Requires meaningful sample size (15–20 applications with outcomes). Backend: join `jobs.app_status` with `variants.id` and cross-reference `metadata.chunk_ids`.

- **Interview notes via recording / transcript** — Capture post-interview notes from an audio recording or transcript rather than manual text entry. Flow: record on phone → upload or paste transcript → Claude extracts: questions asked, what seemed to land, what was weak, follow-up actions. Output populates the job's `notes` field in tracking and optionally creates a structured debrief note. Implementation: transcript → Haiku extraction endpoint → PATCH job notes. Recording capture requires either mobile integration or a local whisper transcription step.

### Application Workflow

- **Cover letter briefing suggestion (Haiku)** — The briefing textarea currently accepts free-text from the user or from Claude during a review session. A future "Suggest" button would fire a Claude Haiku call with the JD + selected chunk summaries and return 3–4 bullet briefing points (angles to emphasise, company language to lift, what to front-load). Build this after the cover letter flow has been used enough across multiple applications to know what kinds of briefing notes actually change the output meaningfully — premature automation here just shifts the generic problem from the letter to the brief.

- **Assess Fit streaming / per-chunk refresh** — Currently Assess Fit sends all chunk IDs to Ollama in one batch and the UI only updates when the entire batch completes. With many chunks this means a long blank wait. Fix: SSE stream so each card updates as its assessment finishes, or incremental cache polling so completed verdicts appear immediately without waiting for the tail end of the queue.

- **Rewrite auto-run toggle** — The "Rewrite" button in chunk review always fires a fresh preview run. A toggle to reload an existing pending diff without a new API call saves time when you want to review what was already generated. Separate toggle for auto-firing rewrite on chunk review open (current pain point: unexpected API call on every open).

- **Partial rewrite recovery** — When applying a rewrite with some items approved and some skipped, the entire `pending_rewrite.json` is deleted — skipped items are unrecoverable from pending (they still exist in the historical `rewrites/diff_*.json`). Fix: instead of deleting pending on apply, mark each item with `applied: true / skipped: true` and keep the file until explicitly cleared. Allows coming back to apply remaining items later.

### Infrastructure & Storage

- **Old variant artifact rotation** — After a job reaches `Rejected` or `Archived` status, offer to trim its variant directory: delete PDFs and HTML (regeneratable) while keeping `metadata.json` and `resume_data.json` (needed for chunk correlation). Triggered manually from tracking UI or via a `scripts/rotate_artifacts.py` script. Prevents `outputs/` from growing unboundedly over a long job search.

- **Periodic data backup script** — `scripts/backup.sh`: copies `data/` and `outputs/` to a timestamped folder outside the repo (e.g. `~/job-assist-backups/YYYYMMDD/`). The only recovery path for `resume_chunks.json`, embeddings, and generated artifacts if the repo directory is accidentally deleted — these are all gitignored and exist only on disk. Run before any major feature session or bulk chunk editing.

- **Server control from extension panel** — Start/stop the local API server directly from the Chrome side panel without opening a terminal. Implementation requires a native messaging host (`chrome.runtime.connectNative`) to exec `./start.sh` / `./stop.sh`. Alternative: lightweight tray/menubar app exposing a local control socket. Decided against building in current phase.

- **Registry rebuild trigger in panel** — Button in panel settings to POST `/jobs/registry/rebuild` and show the returned variant count. Currently rebuild only fires on server startup.

## Data Locations
| Path | Contents |
|------|----------|
| data/jobs.db | SQLite — jobs + variants |
| data/resume_chunks.json | Source of truth for resume content |
| data/experience.json | Structured work history for DOM fill |
| data/user_profile.json | Contact info for DOM fill |
| data/resume_embeddings.npy | Chunk embeddings (re-run embed_resume.py after chunk changes) |
| data/resume_embedding_ids.json | Ordered chunk IDs matching embeddings array |
| data/taxonomy/*.npy | Track classification embeddings |
| data/job_targets.json | Target role phrases for role match badge (editable, re-cached on next ingest) |
| outputs/resumes/ | One subdirectory per variant |
| outputs/cover_letters/ | One subdirectory per job |
| logs/app.log | Rotating application log |
