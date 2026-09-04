# app/jobs/cleaner.py
# Strips nav noise from raw job text captured via browser innerText.
# Works on LinkedIn and degrades gracefully on other boards.

import re

# Lines matching these patterns are nav/UI noise — drop unconditionally
_NAV_PATTERNS = [
    r"^skip to",
    r"^(home|jobs|messaging|notifications|me|for business)$",
    r"^\d+\s*(notifications?)?$",
    r"^try premium",
    r"^(save|apply|share|report|dismiss)$",
    r"^promoted by",
    r"^responses managed",
    r"^over \d+ people",
    r"^reposted? \d",
    r"^show (all|more|match details|less)",
    r"^tailor my resume",
    r"^help me stand out",
    r"^use ai to",
    r"^people you (can|might)",
    r"^school alumni",
    r"^(on-site|remote|hybrid|full-time|part-time|contract|internship)$",
    r"^get ai-powered",
    r"^linkedin corporation",
    r"^(accessibility|privacy policy|user agreement|cookie policy)$",
    r"^©\s*\d{4}",
]

_NAV_RE = re.compile("|".join(_NAV_PATTERNS), re.IGNORECASE)

# Lines that signal the language-selector footer — everything from here down is noise
_FOOTER_SIGNALS = re.compile(
    r"\(Hebrew\)|\(Japanese\)|\(Korean\)|\(Marathi\)|\(Dutch\)|"
    r"select language|show more languages|"
    r"more jobs for you|people also viewed|"
    r"see more jobs like this|looking for talent\?|"
    r"recommendation transparency|"
    r"^post a job$|^about$",
    re.IGNORECASE,
)

# Common content-start markers (case-insensitive, checked as line prefix)
_CONTENT_MARKERS = [
    "about the job",
    "job description",
    "about this role",
    "about the role",
    "about the position",
    "about us",
    "the opportunity",
    "what you'll do",
    "what you will do",
    "responsibilities",
    "the role",
    "role overview",
    "position overview",
    "full job description",
]


def clean_job_text(raw: str) -> str:
    """
    Strips LinkedIn (and generic) nav noise from raw innerText.

    Strategy:
    1. Cut footer at first language-selector line
    2. Find content-start marker; extract from there if found
    3. Strip known nav lines from whatever remains
    4. Collapse excessive blank lines
    """

    lines = raw.splitlines()

    # ── 1. Drop language-selector footer ──────────────────────────────────────
    cutoff = len(lines)
    for i, line in enumerate(lines):
        if _FOOTER_SIGNALS.search(line):
            cutoff = i
            break
    lines = lines[:cutoff]

    # ── 2. Find content start marker ──────────────────────────────────────────
    start_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        for marker in _CONTENT_MARKERS:
            if stripped == marker or stripped.startswith(marker):
                start_idx = i
                break
        if start_idx is not None:
            break

    if start_idx is not None:
        lines = lines[start_idx:]
    else:
        # No marker found — strip nav lines from the top until we hit real content
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not _NAV_RE.match(stripped) and len(stripped.split()) > 4:
                lines = lines[i:]
                break

    # ── 3. Strip remaining nav lines ──────────────────────────────────────────
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if _NAV_RE.match(stripped):
            continue
        cleaned.append(line)

    # ── 4. Collapse runs of blank lines to a single blank ─────────────────────
    result = []
    prev_blank = False
    for line in cleaned:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank

    return "\n".join(result).strip()
