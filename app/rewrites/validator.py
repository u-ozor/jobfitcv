#app/validators/rewrite_validator

import re


BAD_PATTERNS = [
    r"responsibilities:",
    r"requirements:",
    r"nice to have:",
    r"preferred qualifications:",
    r"objective:",
    r"project description:",
    r"key responsibilities:",
    r"demonstrated proficiency",
    r"excellent written and verbal communication",
    r"\bthis role\b",
    r"\bcandidate will\b",
    r"\byou will\b",
    r"\byou'll\b",
    r"\bwe are looking\b",
    r"\bthe ideal candidate\b",
]

WEAK_OPENERS = {
    "participated", "assisted", "helped", "supported",
    "worked", "contributed", "involved", "engaged",
    "utilized", "leveraged", "facilitated"
}

MAX_BULLET_WORDS = 38
MAX_PROJECT_WORDS = 45
MAX_WORD_GROWTH = 12


def validate_rewrite_text(text, max_words=MAX_BULLET_WORDS):

    issues = []

    lowered = text.lower()

    for pattern in BAD_PATTERNS:
        if re.search(pattern, lowered):
            issues.append(f"AI sludge pattern: {pattern}")

    word_count = len(text.split())

    if word_count > max_words:
        issues.append(f"Too long: {word_count} words")

    if "\n" in text:
        issues.append("Contains newline")

    return issues


def is_rewrite_acceptable(original: str, rewritten: str, max_words=MAX_BULLET_WORDS) -> bool:
    """
    Returns True if the rewrite should replace the original.

    Rejects if:
    - rewrite has known bad patterns or is too long
    - rewrite grew more than MAX_WORD_GROWTH words vs original
    - rewrite opens with a weak verb
    - rewrite is empty
    """
    if not rewritten or not rewritten.strip():
        return False

    if validate_rewrite_text(rewritten, max_words=max_words):
        return False

    original_wc = len(original.split())
    rewritten_wc = len(rewritten.split())

    if rewritten_wc - original_wc > MAX_WORD_GROWTH:
        return False

    first_word = rewritten.strip().split()[0].lower().rstrip(",.")
    if first_word in WEAK_OPENERS:
        return False

    return True