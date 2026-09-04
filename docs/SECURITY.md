# Security Considerations

jobfitcv is a local-first personal tool. This document covers what the extension can and cannot do, where your data goes, and the rationale behind every permission the extension holds. It is intended for users evaluating the tool, security-conscious reviewers, and Chrome Web Store review.

---

## Data Storage

All sensitive data lives on the local filesystem under `data/` and `outputs/`. Every path below is gitignored — none of it is tracked in version control.

| Path | Contents | Leaves machine? |
|------|----------|----------------|
| `data/jobs.db` | Job text, URLs, tracking status, notes, embeddings metadata | No |
| `data/resume_chunks.json` | Resume content in scored chunks | Only on opt-in API call during setup |
| `data/user_profile.json` | Name, email, phone, LinkedIn, GitHub, cover letter default | No |
| `data/experience.json` | Work history, education, certifications | Only on opt-in API call during setup |
| `data/resume_embeddings.npy` | Vector embeddings (no PII — derived mathematical representation) | No |
| `outputs/resumes/` | Generated HTML/PDF resumes | No |
| `outputs/cover_letters/` | Generated cover letters | No |
| `.env` | API key(s) | No |

---

## Network Calls Inventory

| Call | Source | Destination | When | Content |
|------|--------|-------------|------|---------|
| `fetch http://localhost:8000/*` | Extension panel/background | Local FastAPI server | All operations | Job data, profile, experience — stays on machine |
| Configured LLM (Anthropic by default) | FastAPI server (`app/api/routers/wizard.py`) | Anthropic / OpenAI-compatible / Ollama, per `WIZARD_PROVIDER` | On "Generate" in chunk wizard, user-initiated | Resume chunk descriptions for structured chunk creation |
| Configured LLM (Anthropic by default) | FastAPI server (`app/api/routers/cover_letters.py`) | Anthropic / OpenAI-compatible / Ollama, per `CL_PROVIDER` | On "Generate Cover Letter" in panel, user-initiated | Job text + resume highlights for cover letter generation |
| Configured LLM (Anthropic by default) | FastAPI server (`app/api/routers/chunk_review.py`) | Anthropic / OpenAI-compatible / Ollama, per `SUMMARY_SYNTH_PROVIDER` | On "Synthesize Summary" in chunk review, user-initiated | Selected chunk contents + job text for summary proposal |
| Job page load | Browser (user navigation) | Job site | Normal browsing | Standard HTTP — not extension-initiated |

**The extension itself makes no outbound internet requests.** All extension fetches go to `localhost` only (port configurable, `8000` by default), enforced by `host_permissions: ["http://localhost:*/*"]` in the manifest.

LLM calls are made by the FastAPI server process (not the browser extension) when the user explicitly triggers the chunk wizard, cover letter generation, or summary synthesis. Each of these three features defaults to Anthropic but is independently configurable — for example, setting `WIZARD_PROVIDER=ollama` routes chunk-wizard calls to a local Ollama instance instead, and no data leaves the machine for that feature. Whichever provider is active, the server reads the matching credential (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`, or no key at all for Ollama) from `.env` at runtime. These calls send resume content and/or job text — data leaves the machine only when a cloud provider (Anthropic or an OpenAI-compatible endpoint) is configured for that feature; that provider's own data-handling terms then apply.

---

## Extension Permissions

### Declared

| Permission | Purpose | Scope |
|-----------|---------|-------|
| `activeTab` | Inject/message content script on the current tab when user acts | Only the tab the user is on at action time; grant expires on navigation |
| `scripting` | MV3 requirement for tab-level script injection | Used as fallback when declarative injection missed a page open before extension loaded |
| `sidePanel` | Open the side panel UI | UI rendering only, no data access |
| `windows` | Open a popup window for URL-based capture (LinkedIn/Indeed) — a background tab gets `visibilityState: 'hidden'` and the page defers rendering the job description, so a visible-but-unfocused popup window is used instead, then closed automatically | Only opened during an explicit user-initiated URL capture; closes itself within ~5–10s |
| `host_permissions: http://localhost:*/*` | Allow extension pages to fetch from local API, any port | Localhost only — not reachable from external network |

### Deliberately Not Requested

| Permission | Why excluded |
|-----------|-------------|
| `tabs` | Would allow reading URL/title of all open tabs. Tab-switch URL detection is handled by `visibilitychange` in content.js instead |
| `history` | No access to browsing history needed or used |
| `cookies` | No session or cookie access needed |
| `storage` | Persistent data lives on filesystem via API, not in browser storage |
| `webRequest` | No network interception |
| `<all_urls>` in `host_permissions` | Programmatic script injection on any site not needed — declarative `content_scripts` handles injection; `activeTab` covers the fallback |

---

## Content Script Scope

`content.js` is declared with `matches: ["<all_urls>"]`. This is required because job postings appear on any domain — restricting to specific job boards would break capture on company career pages, which is a primary use case.

**What content.js does:**

- Listens for messages from the extension's own service worker
- On `extract`: reads `document.body.innerText` and `document.title`, clicks "See more" if present, returns text to the panel for user review before saving
- On `fill_form`: fills form fields with data the extension provides (profile + experience), dispatches native input events for React/Vue compatibility
- On `visibilitychange` to visible: sends current `window.location.href` to the panel so the panel can auto-scope the matching saved job

**What content.js cannot do:**

- Initiate any action on its own — it is entirely passive until a message arrives from the service worker
- Send data to any external server — `chrome.runtime.sendMessage` routes only within the extension
- Access `chrome.tabs`, `chrome.history`, `chrome.cookies`, `chrome.storage` — content scripts do not have access to privileged extension APIs
- Run on `chrome://` pages, extension pages, or PDFs — Chrome blocks content script injection on these by design

**A page cannot trigger content.js.** Messages flow only from the extension service worker to the content script, not from the page to the extension.

---

## EEO / Demographic Field Handling

The generic form fill intentionally skips fields whose labels, names, placeholders, or aria-labels contain any of: `ethnicity`, `race`, `gender`, `veteran`, `disability`, `hispanic`, `latino`, `eeo`, `equal opportunity`, `demographic`. These fields require deliberate user input and are excluded from automated fill to avoid misclassification.

Greenhouse and Lever clean-mode fill targets only explicitly-known selectors for contact and work history fields. EEO sections on Greenhouse are separate form blocks that our selectors do not target.

---

## Threat Model

### Addressed

**Accidental data exposure** — all sensitive files gitignored, never committed. `.env` excluded. `outputs/` excluded.

**Extension over-reach** — minimum viable permissions. No `tabs`, no `history`, no `<all_urls>` in `host_permissions` (content script injection is a separate, narrower mechanism — see Content Script Scope above).

**Credential exposure** — API key read from env at runtime, never logged, never transmitted by the extension, never written to DB.

**Wrong-field fills** — EEO/demographic field exclusion list in content.js. Generic fill only targets fields with clearly matching labels.

**Duplicate job capture** — URL dedup (query-param-stripped) + text fingerprint (sha256 of first 2000 chars) prevent re-ingesting the same job from different boards or sessions.

### Out of Scope

**Local machine compromise** — if the OS is compromised, no local tool is safe. Mitigate with standard OS security hygiene.

**Malicious job posting tricking the user into capturing false data** — the user must explicitly review and confirm the captured text before it is saved. The edit field in the capture preview allows trimming before confirmation.

**Man-in-the-middle on localhost** — localhost traffic is unencrypted. Acceptable because it never leaves the machine and is only reachable from local processes.

**Extension update injection** — when sideloaded (unpacked developer mode), updates require manual reload from `chrome://extensions`. No silent auto-updates. Chrome Web Store distribution auto-updates within the same permission set; any permission expansion triggers re-review.

**Compromised developer account pushing a malicious Web Store update** — only relevant if/when this extension is ever published to the Web Store (not the case today). A compromised publisher account could push an update that silently gains malicious behavior within the already-granted permission set, auto-distributed to every installed user. Mitigation at that point would be standard account hardening (2FA, unique credentials) on whatever account publishes it — no code-level mitigation prevents this, it's an account-security concern, not an application one.

---

## Chrome Web Store Review Reference

| Review point | Justification |
|-------------|--------------|
| `content_scripts: matches: ["<all_urls>"]` | Job postings appear on any domain. Content is read only when user clicks Capture. Script is dormant otherwise. |
| `activeTab` | Required for form fill and job text extraction. Only active when user initiates an action from the panel. |
| `scripting` | MV3 requirement. Used as fallback injection when a page was open before the extension loaded. |
| No remote code execution | No `eval()`, no dynamic script fetches, no CDN dependencies. All JS is bundled in the extension package. |
| No data exfiltration | `host_permissions` restricts extension fetches to `localhost` only (any port). Verified by manifest. |

---

## What This Tool Is Not

- Not a password manager or autofill for credentials
- Not a web scraper that runs without user action
- Not a data broker — captured job text stays local
- Not a tracking tool — no analytics, no telemetry, no usage reporting
- Not a cloud service — no accounts, no servers, no third-party data storage
