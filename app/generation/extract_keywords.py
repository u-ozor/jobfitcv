# app/generation/extract_keywords.py
# Canonical keyword extraction used by match_job.py

import re
from app.core.config import (
    STOPWORDS,
    KNOWN_TERMS,
    ALIASES,
)

def normalize_token(token: str) -> str:
    token = token.lower().strip()

    # remove punctuation around token
    token = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", token)

    # direct alias map
    token = ALIASES.get(token, token)

    return token

def extract_keywords(text: str) -> set[str]:
    """
    Returns normalized keyword set.

    Rules:
    - capture alphanumeric tokens length >=2
    - remove stopwords
    - apply aliases
    - preserve KNOWN_TERMS even if short
    - keep useful unknown tokens length >=3
    """

    raw_tokens = re.findall(r"\b[a-zA-Z0-9\.\-]{2,}\b", text.lower())

    output = set()

    for raw in raw_tokens:

        # skip tokens that lead with a digit (e.g. "0-2", "3rd")
        if raw[0].isdigit():
            continue

        token = normalize_token(raw)

        if not token:
            continue

        # preserve important terms first
        if token in KNOWN_TERMS:
            output.add(token)
            continue

        # remove filler words
        if token in STOPWORDS:
            continue

        # keep meaningful generic words only if len >=3
        if len(token) >= 3:
            output.add(token)

    return output


if __name__ == "__main__":
    sample = """
    Junior SOC Analyst with Python scripting, AWS exposure,
    SIEM monitoring, APIs, Linux systems, communication skills.
    """

    print(sorted(extract_keywords(sample)))
