# scripts/

Standalone CLI tooling — everything here runs outside the API, for setup, maintenance, and debugging. None of these are called by the live app; the panel/extension always goes through the API. Run with `kratos/bin/python -m scripts.<name>` from the project root (or `kratos/bin/python scripts/<name>.py` directly).

| Script | What it does |
|--------|---------------|
| `setup_wizard.py` | Interactive first-time setup — `.env` (API key + per-feature LLM providers), `data/user_profile.json`, `data/resume_chunks.json`, `data/experience.json`, then runs the embed step. Safe to re-run. |
| `embed_resume.py` | Recomputes `data/resume_embeddings.npy` + `data/resume_embedding_ids.json` from `data/resume_chunks.json`. Run after any manual edit to chunks (the wizard does this automatically; this is for manual edits). |
| `build_taxonomy_embeddings.py` | Rebuilds `data/taxonomy/*.npy` from the hardcoded `TAXONOMIES` dict in this file. The 6 shipped tracks (soc, backend, it_support, cloud, sysadmin, ai) are hand-written keyword blobs specific to security/IT roles. |
| `taxonomy_builder.py` | Interactive alternative to editing `build_taxonomy_embeddings.py` directly — for targeting a field outside security/IT. Prompts for track name + description (offers an AI-prompt template to help draft it), embeds and saves. Opt-in; the default tracks work fine without ever touching this. |
| `preprocess_resume_data.py` | Thin wrapper around `app/pipelines/preprocessing_pipeline.py` — one-time resume data normalization. |
| `chunk_stats.py` | Cross-variant analytics — which chunks get selected most/least across every generated variant, priority-vs-selection-rate, Ollama verdict ratios. `--full` prints full content for never-selected chunks. |
| `review_variant.py` | Full dump for one variant — JD text, selected chunks with scores/verdicts, swap candidates, pending rewrites, cover letter — in one call instead of reading multiple files. `--list` shows all variant IDs. |
| `run_generation.py` | Manually re-run the generation pipeline for one already-ingested job. `kratos/bin/python scripts/run_generation.py <job_id>` — find IDs via `review_variant.py --list`. |
| `regen.sh` | Convenience wrapper: re-embeds chunks, then calls `run_generation.py` for one job. **Requires a `job_id` argument — does not auto-detect or fetch one.** `./scripts/regen.sh <job_id>`, run from project root. Find a job_id with `kratos/bin/python -m scripts.review_variant --list`; running with no argument prints this same usage message and exits. |
| `regenerate_resume.py` | CLI wrapper around `app/services/markdown_rebuild_service.py` — re-renders HTML/PDF from a hand-edited `resume.edited.md`. `--output-dir <variant_dir>`. |
| `generate_icons.py` | One-time: produces `extension/icon{16,32,48,128}.png` from a bundled font. Needs a bold TTF at `app/static/fonts/icon_font.ttf` (falls back to system fonts if absent). Re-run only if the icon design changes; output PNGs are committed. |

## If a script won't run

A `ModuleNotFoundError` on import usually means the script is calling something that was refactored or removed elsewhere in the codebase and never updated to match — check whether the module it's importing still exists before assuming the script itself is broken.
