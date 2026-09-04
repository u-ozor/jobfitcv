# app/_FOLDER_MAP.md

| Package | Contains | Why grouped here |
|---------|----------|-------------------|
| `core/` | `config.py`, `embedder.py`, `similarity.py`, `pdf_export.py`, `llm_client.py`, `profile_loader.py`, `experience_loader.py`, `markdown_parser.py` | Shared infrastructure used by 2+ other packages below — not specific to any single domain. |
| `jobs/` | `cleaner.py`, `summarizer.py`, `fit_scorer.py`, `taxonomy_classifier.py` | Everything touching an incoming job posting before it's scored — text cleaning, LLM summarization, role-match badge, track classification. Only `api/routers/jobs.py` calls into this package. |
| `generation/` | `matcher.py`, `resume_builder.py`, `renderer.py`, `template_manager.py`, `extract_keywords.py`, `variant_manager.py`, `artifact_writer.py` | The core resume-generation domain — scoring, assembly, rendering, output-directory management. |
| `rewrites/` | `manager.py`, `hooks.py`, `experience_rewriter.py`, `project_rewriter.py`, `summary_rewriter.py`, `rewrite_diff.py`, `validator.py` | The AI per-bullet rewrite feature (off by default, see `ENABLE_REWRITES` in `core/config.py`). |
| `api/routers/` | One file per HTTP endpoint group | Kept as its own layer — every route is findable in one place regardless of which domain it calls into. `cover_letters.py`, `chunk_review.py`, `wizard.py` have no separate domain-logic file; all their logic lives inline in the router itself. |
| `pipelines/` | `generation_pipeline.py`, `preprocessing_pipeline.py`, `markdown_regeneration_pipeline.py` | Orchestration layer — each one calls into multiple domain packages above to run an end-to-end flow. |
| `services/` | `markdown_rebuild_service.py` | Rebuilds resume artifacts from hand-edited markdown. Distinct from the `rewrites/` package — that's AI rewriting, this is re-rendering your own manual edits. |
| `database/` | SQLAlchemy models, session, init | Standard layout. |
| `utils/` | `time_utils.py`, `atomic_io.py` | Small, generic helpers with no domain. `atomic_io.py` provides write-then-rename JSON writes — every `metadata.json` write in the codebase goes through it to guarantee a concurrent read or an interrupted write can never see a corrupted file. |
| `static/` | `fonts/` | Build input for `scripts/generate_icons.py`. |

**Adding a new file?** Check who's actually going to import it. If 2+ existing packages will need it, it belongs in `core/`. If it's specific to one feature, it either fits an existing package above or is a genuinely new domain — don't drop it loose at `app/` root.
