# app/job_summarizer.py
#
# Produces the short, keyword-dense structured summary stored as Job.raw_text.
# This is what every downstream consumer actually uses — chunk scoring
# (embedding + keyword overlap), Ollama "Assess Fit" (looped once per chunk),
# and rewrite hooks (looped once per bullet). Keeping it short and free of
# boilerplate/benefits/legal fluff matters for both embedding signal quality
# and per-call latency in those loops.
#
# Separate from jd_actual.txt, which stores the full verbatim posting for
# human/interview reference and is never fed into scoring.

import os
from app.core.llm_client import generate_completion

JD_SUMMARY_PROVIDER = os.environ.get("JD_SUMMARY_PROVIDER", "anthropic")
JD_SUMMARY_MODEL    = os.environ.get("JD_SUMMARY_MODEL", "claude-haiku-4-5-20251001")

SYSTEM_PROMPT = """\
You compress job postings into short, structured, keyword-dense summaries for \
a resume-matching pipeline. Preserve every concrete technical term, tool, \
platform, certification, and requirement VERBATIM — do not paraphrase them \
(e.g. keep "AWS", not "cloud platform"). Strip company boilerplate, benefits/perks \
lists, EEO/legal statements, culture fluff, and how-to-apply instructions — none \
of that helps matching. Output plain text, under 900 characters, structured as \
short labeled sections (Role, Requirements, Responsibilities, Tools) only where \
the posting actually contains that content. No preamble, no commentary."""


def summarize_job_text(cleaned_text: str) -> str:
    """
    Returns a short structured summary of cleaned_text via the configured
    JD_SUMMARY_PROVIDER/JD_SUMMARY_MODEL. Raises on failure — callers should
    catch and fall back to cleaned_text so ingestion never breaks over this.
    """
    prompt = f"<job_posting>\n{cleaned_text[:6000]}\n</job_posting>\n\nSummarize per the rules above."
    return generate_completion(
        prompt,
        system=SYSTEM_PROMPT,
        provider=JD_SUMMARY_PROVIDER,
        model=JD_SUMMARY_MODEL,
        max_tokens=400
    )
