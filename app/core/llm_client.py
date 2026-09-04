# app/core/llm_client.py
#
# Provider selection via env vars:
#   LLM_PROVIDER  = anthropic (default) | openai | ollama
#   LLM_MODEL     = model name for the selected provider
#
# anthropic  — uses anthropic SDK; needs ANTHROPIC_API_KEY
# openai     — OpenAI-compatible HTTP; needs OPENAI_API_KEY + optional OPENAI_BASE_URL
#              Works with: OpenAI, OpenRouter, Groq, Together, Mistral, Anyscale, etc.
#              Set OPENAI_BASE_URL=https://openrouter.ai/api/v1 for OpenRouter, etc.
# ollama     — local Ollama instance; no key needed; needs OLLAMA_BASE_URL

import os
import requests

LLM_PROVIDER    = os.getenv("LLM_PROVIDER",    "anthropic")
LLM_MODEL       = os.getenv("LLM_MODEL",       "claude-haiku-4-5-20251001")
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_KEY      = os.getenv("OPENAI_API_KEY",   "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL",  "https://api.openai.com/v1")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL",  "http://localhost:11434")


def generate_completion(
    prompt: str,
    system: str = "",
    provider: str = None,
    model: str = None,
    max_tokens: int = 400
) -> str:
    """
    provider/model default to the global LLM_PROVIDER/LLM_MODEL env vars when
    not passed — existing callers (e.g. the rewrite pipeline) are unaffected.
    Callers that need a different provider/model/budget (e.g. cover letters)
    can override per-call without changing global config.
    """
    provider = provider or LLM_PROVIDER
    model    = model or LLM_MODEL

    if provider == "anthropic":
        return _anthropic(prompt, system, model, max_tokens)
    if provider == "openai":
        return _openai_compat(prompt, system, model, max_tokens)
    if provider == "ollama":
        return _ollama(prompt, model)
    raise ValueError(f"Unknown provider: {provider!r} — set to anthropic, openai, or ollama")


def _anthropic(prompt: str, system: str, model: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    if system:
        kwargs["system"] = system
    return client.messages.create(**kwargs).content[0].text.strip()


def _openai_compat(prompt: str, system: str, model: str, max_tokens: int) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = requests.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens
        },
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _ollama(prompt: str, model: str) -> str:
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3}
        },
        timeout=120
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()
