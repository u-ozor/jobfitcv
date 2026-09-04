#!/usr/bin/env python3
"""
setup_wizard.py — Interactive first-time setup for jobfitcv.

Usage: PYTHONPATH=. python scripts/setup_wizard.py

Walks through:
  1. API key + model            (.env)
  2. Server port                (.env + extension/config.js)
  3. Per-feature LLM providers  (.env)
  4. Contact info               (data/user_profile.json)
  5. Resume chunks              (data/resume_chunks.json)
  6. Job targets                (data/job_targets.json — role-match badge phrases)
  7. Experience data            (data/experience.json)
  8. Runs embed_resume.py to generate embeddings from chunks

Safe to re-run: existing values shown as defaults, press Enter to keep them.
"""

import json
import os
import re
import sys
import shutil
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

PROFILE_PATH        = "data/user_profile.json"
PROFILE_TEMPLATE    = "data/templates/user_profile.template.json"
CHUNKS_PATH         = "data/resume_chunks.json"
CHUNKS_TEMPLATE     = "data/templates/resume_chunks.template.json"
EXPERIENCE_PATH     = "data/experience.json"
EXPERIENCE_TEMPLATE = "data/templates/experience.template.json"
JOB_TARGETS_PATH     = "data/job_targets.json"
JOB_TARGETS_TEMPLATE = "data/templates/job_targets.template.json"
EMBED_SCRIPT        = "scripts/embed_resume.py"
ENV_PATH            = ".env"
DEFAULT_MODEL       = "claude-opus-4-7"


def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def prompt(label, current="", required=False):
    display = f" [{current}]" if current else ""
    while True:
        val = input(f"  {label}{display}: ").strip()
        if val:
            return val
        if current:
            return current
        if not required:
            return ""
        print("  (required — please enter a value)")


def section(title):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


def load_env_file(path):
    """Read key=value pairs from .env, return as dict."""
    result = {}
    if not os.path.exists(path):
        return result
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


def save_env_file(path, data):
    """
    Merge data into existing .env IN PLACE — preserves comments, blank lines,
    and section structure. Updates a KEY= line where it already exists;
    genuinely new keys are appended under a clearly marked section at the end.
    (Previously this flattened the whole file into an unstructured KEY=VALUE
    dump, destroying every comment — fixed 2026-09-03.)
    """
    lines = []
    if os.path.exists(path):
        with open(path) as f:
            lines = f.readlines()

    remaining = dict(data)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}\n"

    if remaining:
        if lines and lines[-1].strip():
            lines.append("\n")
        lines.append("# — Added by setup_wizard.py —\n")
        for k, v in remaining.items():
            lines.append(f"{k}={v}\n")

    with open(path, "w") as f:
        f.writelines(lines)


def setup_api_config():
    section("1 / 8 — API configuration  (.env)")
    print("  Default credential for cover letters, JD summarization, wizard chunk")
    print("  creation, and chunk-review summary synthesis (step 3 can override any of")
    print("  those to OpenAI-compatible or local Ollama instead). Also used for the")
    print("  optional Claude-only experience.json auto-generate later (step 7).\n")

    env = load_env_file(ENV_PATH)

    current_key   = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    current_model = env.get("ANTHROPIC_MODEL",   os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL))

    display_key = f"...{current_key[-6:]}" if len(current_key) > 6 else ("set" if current_key else "")

    print("  Press Enter to keep existing value. Leave blank to skip.\n")
    key = input(f"  ANTHROPIC_API_KEY [{display_key}]: ").strip()
    if not key and current_key:
        key = current_key
    model = input(f"  ANTHROPIC_MODEL [{current_model}]: ").strip() or current_model

    updates = {}
    if key:
        updates["ANTHROPIC_API_KEY"] = key
        os.environ["ANTHROPIC_API_KEY"] = key
    if model:
        updates["ANTHROPIC_MODEL"] = model
        os.environ["ANTHROPIC_MODEL"] = model

    if updates:
        save_env_file(ENV_PATH, updates)
        print(f"\n  ✓ Saved to {ENV_PATH}")
    else:
        print("  Skipped (no key provided — auto-generate will prompt later if needed).")


FEATURE_PROVIDERS = [
    ("CL_PROVIDER",           "CL_MODEL",           "Cover letters"),
    ("JD_SUMMARY_PROVIDER",   "JD_SUMMARY_MODEL",   "JD summarization at ingest"),
    ("WIZARD_PROVIDER",       "WIZARD_MODEL",       "Wizard chunk creation"),
    ("SUMMARY_SYNTH_PROVIDER","SUMMARY_SYNTH_MODEL","Chunk review summary synth"),
    ("EXPERIENCE_PROVIDER",   "EXPERIENCE_MODEL",   "Experience auto-generate (step 7)"),
]


def setup_llm_providers():
    section("3 / 8 — LLM providers per feature  (.env)")
    print("  Every LLM feature defaults to Anthropic — press Enter through this whole")
    print("  section to keep that (uses the API key from step 1). Only answer if you")
    print("  want a specific feature on OpenAI-compatible or local Ollama instead.\n")

    env = load_env_file(ENV_PATH)
    updates = {}

    for provider_key, model_key, label in FEATURE_PROVIDERS:
        current_provider = env.get(provider_key, "anthropic")
        provider = input(
            f"  {label} — provider [{current_provider}] (anthropic/openai/ollama): "
        ).strip().lower() or current_provider

        if provider not in ("anthropic", "openai", "ollama"):
            print(f"    Unrecognized value, keeping '{current_provider}'.")
            provider = current_provider

        if provider != "anthropic":
            # Only prompted when switching off Anthropic — .env.example already
            # ships sensible per-feature Anthropic model defaults, so staying on
            # Anthropic needs no prompt here at all.
            fallback = {"ollama": "mistral:latest", "openai": "gpt-4o-mini"}[provider]
            current_model = env.get(model_key, fallback) if env.get(provider_key) == provider else fallback
            model = input(f"  {label} — model for {provider} [{current_model}]: ").strip() or current_model
            updates[model_key] = model

        if provider != current_provider:
            updates[provider_key] = provider

    if any(v == "ollama" for k, v in updates.items() if k.endswith("_PROVIDER")):
        current_url = env.get("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_url = input(f"\n  OLLAMA_BASE_URL [{current_url}]: ").strip() or current_url
        if ollama_url != current_url:
            updates["OLLAMA_BASE_URL"] = ollama_url
    if any(v == "openai" for k, v in updates.items() if k.endswith("_PROVIDER")):
        current_openai_key = env.get("OPENAI_API_KEY", "")
        display = f"...{current_openai_key[-6:]}" if len(current_openai_key) > 6 else ""
        openai_key = input(f"\n  OPENAI_API_KEY [{display}]: ").strip()
        if openai_key:
            updates["OPENAI_API_KEY"] = openai_key

    if updates:
        save_env_file(ENV_PATH, updates)
        for k, v in updates.items():
            os.environ[k] = v
        print(f"\n  ✓ Saved to {ENV_PATH}")
    else:
        print("\n  Keeping all defaults (Anthropic everywhere).")


EXTENSION_CONFIG_PATH = "extension/config.js"


def setup_port():
    section("2 / 8 — Server port  (.env + extension/config.js)")
    print("  Both sides must agree — this writes to both files so you don't have to.\n")

    env = load_env_file(ENV_PATH)
    current_port = env.get("PORT", "8000")

    port = input(f"  PORT [{current_port}]: ").strip() or current_port

    if not port.isdigit():
        print(f"  '{port}' isn't a valid port number, keeping {current_port}.")
        port = current_port

    save_env_file(ENV_PATH, {"PORT": port})
    os.environ["PORT"] = port

    if os.path.exists(EXTENSION_CONFIG_PATH):
        with open(EXTENSION_CONFIG_PATH) as f:
            js = f.read()
        js = re.sub(
            r'const BASE_URL = "http://localhost:\d+";',
            f'const BASE_URL = "http://localhost:{port}";',
            js
        )
        with open(EXTENSION_CONFIG_PATH, "w") as f:
            f.write(js)
        print(f"  ✓ Saved PORT={port} to {ENV_PATH} and {EXTENSION_CONFIG_PATH}")
        print("  Reload the extension in chrome://extensions for the change to take effect.")
    else:
        print(f"  ✓ Saved PORT={port} to {ENV_PATH}")
        print(f"  ⚠ {EXTENSION_CONFIG_PATH} not found — update BASE_URL there manually to match.")


def setup_profile():
    section("4 / 8 — Contact info  (data/user_profile.json)")
    print("  Used by the extension to fill application forms.\n")

    if not os.path.exists(PROFILE_PATH):
        print("  (i) Interactive prompts (recommended) — answer questions now")
        print("  (t) Copy template — fill in data/user_profile.json by hand later\n")
        choice = input("  Choice [i]: ").strip().lower() or "i"
        if choice == "t":
            if not os.path.exists(PROFILE_TEMPLATE):
                print(f"  Template not found at {PROFILE_TEMPLATE}.")
            else:
                shutil.copy(PROFILE_TEMPLATE, PROFILE_PATH)
                print(f"\n  ✓ Template copied to {PROFILE_PATH}")
                print("  Every field is a placeholder — edit it before using DOM form fill or cover letters.")
            return

    current = load_json(PROFILE_PATH)

    profile = {
        "name":     prompt("Full name",           current.get("name", "")),
        "email":    prompt("Email",               current.get("email", ""),    required=True),
        "phone":    prompt("Phone",               current.get("phone", "")),
        "linkedin": prompt("LinkedIn URL",        current.get("linkedin", "")),
        "github":   prompt("GitHub URL",          current.get("github", "")),
        "location": prompt("Location (City, Province/State)", current.get("location", "")),
        "cover_letter": prompt(
            "Default cover letter / summary (used to fill cover letter fields)",
            current.get("cover_letter", "")
        ),
    }

    save_json(PROFILE_PATH, profile)
    print(f"\n  ✓ Saved to {PROFILE_PATH}")


def setup_file(label, dest_path, template_path, step):
    section(f"{step} — {label}")

    if os.path.exists(dest_path):
        if label == "Resume chunks":
            count = len(load_json(dest_path))
            print(f"  Existing file found: {count} chunks.")
        else:
            print(f"  Existing file found: {dest_path}")
        choice = input("  (k) Keep existing  (e) Provide path  (t) Copy template to start fresh: ").strip().lower()
    else:
        print(f"  No {os.path.basename(dest_path)} found.")
        choice = input("  (t) Copy template  (e) Provide path to existing file: ").strip().lower()
        if not choice:
            choice = "t"

    if choice == "k":
        print("  Keeping existing.")
        return True

    if choice == "t":
        if not os.path.exists(template_path):
            print(f"  Template not found at {template_path}.")
            return False
        shutil.copy(template_path, dest_path)
        print(f"\n  ✓ Template copied to {dest_path}")
        print("  Open that file and replace placeholder content with your actual data.")
        return False

    if choice == "e":
        path = input(f"  Path to your {os.path.basename(dest_path)}: ").strip()
        if not os.path.exists(path):
            print(f"  File not found: {path}")
            return False
        shutil.copy(path, dest_path)
        print(f"  ✓ Copied to {dest_path}")
        return True

    return False


def setup_chunks():
    return setup_file(
        "Resume chunks  (data/resume_chunks.json)",
        CHUNKS_PATH, CHUNKS_TEMPLATE,
        "5 / 8"
    )


def setup_job_targets():
    # Read on every job ingest (role-match badge) — a fresh install with no
    # data/job_targets.json crashes the very first capture, so this isn't optional.
    setup_file(
        "Job targets  (data/job_targets.json — role-match badge phrases)",
        JOB_TARGETS_PATH, JOB_TARGETS_TEMPLATE,
        "6 / 8"
    )


def setup_experience():
    section("7 / 8 — Experience data  (data/experience.json)")
    print("  Structured work history, education, certifications.")
    print("  Used to fill ATS form fields like employer, title, dates.\n")
    print("  Options:")
    print("  (t) Copy template — fill in manually")
    print("  (a) Auto-generate from resume_chunks.json using an LLM")
    print("      (EXPERIENCE_PROVIDER from step 3 — anthropic/openai/ollama)")
    print("  (s) Skip for now\n")

    choice = input("  Choice: ").strip().lower()

    if choice == "t":
        if not os.path.exists(EXPERIENCE_TEMPLATE):
            print(f"  Template not found.")
            return
        shutil.copy(EXPERIENCE_TEMPLATE, EXPERIENCE_PATH)
        print(f"\n  ✓ Template copied to {EXPERIENCE_PATH}")
        print("  Edit it with your actual work history, then you're ready.")

    elif choice == "a":
        auto_generate_experience()

    else:
        print("  Skipped. DOM fill will cover contact fields only until experience.json exists.")


def auto_generate_experience():
    provider = os.environ.get("EXPERIENCE_PROVIDER", "anthropic")
    model    = os.environ.get("EXPERIENCE_MODEL", DEFAULT_MODEL if provider == "anthropic" else
                               {"ollama": "mistral:latest", "openai": "gpt-4o-mini"}.get(provider))

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            api_key = input("  ANTHROPIC_API_KEY: ").strip()
            if not api_key:
                print("  No key provided. Skipping.")
                return
            os.environ["ANTHROPIC_API_KEY"] = api_key
    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            api_key = input("  OPENAI_API_KEY: ").strip()
            if not api_key:
                print("  No key provided. Skipping.")
                return
            os.environ["OPENAI_API_KEY"] = api_key

    if not os.path.exists(CHUNKS_PATH):
        print(f"  {CHUNKS_PATH} not found. Set up chunks first.")
        return

    print(f"\n  Sending chunks to {provider} ({model}) for extraction...")

    with open(CHUNKS_PATH) as f:
        chunks_text = f.read()

    prompt = f"""Extract structured work experience, education, and certification data from these resume chunks.

Return ONLY valid JSON matching this exact schema — no commentary:

{{
  "experience": [
    {{
      "employer": "string",
      "title": "string",
      "location": "string",
      "start_month": "MM or null",
      "start_year": "YYYY or null",
      "end_month": "MM or null",
      "end_year": "YYYY or null",
      "current": true/false,
      "bullets": ["string", ...],
      "description": "prose version of bullets joined into sentences"
    }}
  ],
  "education": [
    {{
      "institution": "string",
      "degree": "string",
      "field": "string",
      "location": "string",
      "start_year": "YYYY or null",
      "end_year": "YYYY or null",
      "gpa": null
    }}
  ],
  "certifications": [
    {{
      "name": "string",
      "issuer": "string",
      "issued_month": "MM or null",
      "issued_year": "YYYY or null",
      "credential_id": null
    }}
  ]
}}

Resume chunks:
{chunks_text}"""

    from app.core.llm_client import generate_completion
    raw = generate_completion(prompt, provider=provider, model=model, max_tokens=2048).strip()

    # Extract the JSON object regardless of surrounding prose — smaller/
    # less-instructable models (e.g. via ollama) often add conversational
    # preamble before the fence, unlike Claude's typical direct response.
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if fence_match:
        candidate = fence_match.group(1)
    else:
        start, end = raw.find("{"), raw.rfind("}")
        candidate = raw[start:end + 1] if start != -1 and end != -1 else raw

    try:
        data = json.loads(candidate.strip())
        save_json(EXPERIENCE_PATH, data)
        exp_count = len(data.get("experience", []))
        edu_count = len(data.get("education", []))
        print(f"\n  ✓ Saved to {EXPERIENCE_PATH}")
        print(f"  {exp_count} experience entries, {edu_count} education entries")
        print("  Review the file and correct any dates or details before using fill.")
    except json.JSONDecodeError as e:
        print(f"\n  Could not parse the model's response: {e}")
        print("  Raw output saved to data/experience_raw.txt for inspection.")
        with open("data/experience_raw.txt", "w") as f:
            f.write(raw)


def run_embed():
    section("8 / 8 — Generating embeddings")
    print("  Running embed_resume.py — this may take 30-60 seconds on first run")
    print("  (downloads the embedding model ~270MB if not cached)\n")

    python = sys.executable
    result = subprocess.run(
        [python, EMBED_SCRIPT],
        env={**os.environ, "PYTHONPATH": "."}
    )

    if result.returncode == 0:
        print("\n  ✓ Embeddings generated successfully.")
    else:
        print("\n  ✗ Embedding failed. Check output above.")
        print(f"  You can re-run manually: PYTHONPATH=. python {EMBED_SCRIPT}")


def main():
    print("\n  jobfitcv setup")
    print("  Press Enter to keep existing values.\n")

    setup_api_config()
    setup_port()
    setup_llm_providers()
    setup_profile()
    chunks_ready = setup_chunks()
    setup_job_targets()
    setup_experience()

    if chunks_ready:
        run_embed()
    else:
        print("\n  Skipping embeddings — edit your chunks file first, then run:")
        print(f"    PYTHONPATH=. python {EMBED_SCRIPT}\n")

    print("\n  Setup complete. Start the API with: ./start.sh")
    print("  Then reload the extension at chrome://extensions.\n")


if __name__ == "__main__":
    main()
