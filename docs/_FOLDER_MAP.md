# docs/_FOLDER_MAP.md

Reference documentation. No build step — these are read directly on GitHub or locally.

| File | Purpose |
|------|---------|
| `DEMO.md` | Feature-by-feature walkthrough — what each part of the app does and how to use it, one numbered section per feature. |
| `CAPABILITIES.md` | Current-state reference: scoring weights, quotas, thresholds, endpoint behavior, per-feature specifics. The source of truth for "what does this actually do right now." |
| `INTERNALS.md` | Deeper pipeline reference — scoring formula details, taxonomy classification, provider routing architecture, artifact layout, known gaps. Includes Mermaid diagrams for the ingest→generate→review flow and the LLM provider routing. |
| `SECURITY.md` | Extension permission rationale, data flow inventory, threat model. Written for users evaluating the tool, security-conscious reviewers, and Chrome Web Store review. |
| `CHUNK_REVIEW_SPEC.md` | Design-intent document from before the chunk review feature was built. Kept for the reasoning behind data model and threshold choices that isn't repeated in `CAPABILITIES.md`/`INTERNALS.md` — those two are authoritative for current behavior. |
| `assets/` | Images and GIFs referenced by the docs above and the root `README.md`. |
