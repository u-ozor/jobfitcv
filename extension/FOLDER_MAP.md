# extension/FOLDER_MAP.md

Chrome MV3 extension — one HTML page per feature, each with its own JS file. No build step, no bundler, no npm dependencies; every file here is loaded directly by the browser as-is.

| File | What it is |
|------|------------|
| `config.js` | Single source of truth for `BASE_URL` (the API's host:port). Loaded before every other script — the one place to edit if the server runs on a non-default port. |
| `background.js` | MV3 service worker — side panel registration, tab tracking, URL-based capture (opens a popup window, polls for content, closes it). Loads `config.js` via `importScripts` since it has no HTML wrapper. |
| `content.js` | Injected into every page (`<all_urls>` — see `docs/SECURITY.md` for the rationale and threat model). Dormant until it receives a message from the extension's own trusted contexts; cannot be triggered by the page itself. Scrapes job text, fills application forms. |
| `panel.html` / `panel.js` | The side panel — capture, ingest, generate, cover letter, recent jobs list. |
| `tracking.html` / `tracking.js` | Full-tab job application tracker. |
| `chunk_review.html` / `chunk_review.js` | Full-tab chunk review UI — tier/category views, drag reorder, Assess Fit, Apply Selection. |
| `rewrite.html` / `rewrite.js` | Full-tab rewrite review UI — before/after diffs, accept/reject, history. |
| `edit.html` / `edit.js` | Full-tab raw markdown editor for manual resume edits. |
| `theme-picker.js` / `theme.js` | Shared theme-switcher UI + `themes.css` custom-property definitions, used by every page above. |

**Why no `js/`, `html/`, `css/` subfolders**: Chrome resolves `manifest.json` paths and `<script src>` relative to the extension root — nesting would just add path prefixes for no organizational win at this file count. Grouping by feature (one HTML + one JS per page, named identically) already shows what touches what at a glance; grouping by file type would scatter each feature across three folders instead.
