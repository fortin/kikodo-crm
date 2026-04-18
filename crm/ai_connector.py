"""
Unified LLM connector for Kikodo CRM.

Supports these backends, selected via the AI_BACKEND setting (or env var):
  - "claude"  → Anthropic Claude API, single-shot (requires ANTHROPIC_API_KEY)
  - "ollama"  → Local Ollama (requires Ollama running at OLLAMA_BASE_URL)
  - "mcp"     → Agentic loop via run_chat(): Claude + full MCP tool access
                 (requires ANTHROPIC_API_KEY; Claude can call fetch_url,
                  create_signal, search_contacts, etc. while answering)
  - "auto"    → Claude if ANTHROPIC_API_KEY is set, otherwise Ollama (default)

All callers use call_llm(prompt, model=None).
  - For Claude/MCP, model defaults to ANTHROPIC_MODEL.
  - For Ollama, model defaults to OLLAMA_MODEL (default: qwen3-coder:30b).
  - Pass an explicit model name to override (use the right name for the active backend).
"""

import logging
import os
from pathlib import Path

from django.conf import settings

logger = logging.getLogger("crm")

# Project root — the directory containing manage.py and .env
_BASE_DIR = Path(__file__).resolve().parent.parent


def _read_env_var(key: str) -> str:
    """
    Read a variable from multiple sources in priority order:
      1. OS environment (export VAR=value before starting the server)
      2. Django settings (populated by python-decouple at startup)
      3. .env file read directly (fallback if settings were cached before .env was set)
    """
    # 1. OS env
    val = os.environ.get(key, "")
    if val:
        return val
    # 2. Django settings
    val = getattr(settings, key, "") or ""
    if val:
        return val
    # 3. Direct .env parse (most resilient — works even if decouple cached stale values)
    env_path = _BASE_DIR / ".env"
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                continue
            lkey, _, lval = stripped.partition("=")
            if lkey.strip() == key:
                return lval.strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def get_ai_backend() -> str:
    """Return the active backend: 'claude', 'ollama', or 'mcp'."""
    backend = _read_env_var("AI_BACKEND") or "auto"
    backend = backend.lower().strip()
    if backend == "auto":
        return "claude" if _read_env_var("ANTHROPIC_API_KEY") else "ollama"
    if backend not in ("claude", "ollama", "mcp"):
        raise ValueError(f"AI_BACKEND must be 'claude', 'ollama', 'mcp', or 'auto'; got '{backend}'")
    return backend


# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------

def _get_ollama_base_url() -> str:
    return _read_env_var("OLLAMA_BASE_URL") or "http://localhost:11434"


def _get_ollama_model() -> str:
    return _read_env_var("OLLAMA_MODEL") or "mistral-nemo:latest"


def _call_ollama(prompt: str, model: str | None = None, base_url: str | None = None) -> str:
    """POST to Ollama /api/generate. Retries with 127.0.0.1 if localhost returns 404."""
    import requests

    base_url = (base_url or _get_ollama_base_url()).rstrip("/")
    model = model or _get_ollama_model()
    url = f"{base_url}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}

    def _post(u: str):
        return requests.post(u, json=payload, timeout=120)

    resp = _post(url)
    if resp.status_code == 404 and "localhost" in url:
        resp = _post(url.replace("localhost", "127.0.0.1", 1))
    resp.raise_for_status()
    return resp.json().get("response", "")


# ---------------------------------------------------------------------------
# Claude helpers
# ---------------------------------------------------------------------------

def _get_anthropic_api_key() -> str:
    return _read_env_var("ANTHROPIC_API_KEY")


def _get_anthropic_model() -> str:
    return _read_env_var("ANTHROPIC_MODEL") or "claude-sonnet-4-6"


def _is_model_not_found_error(exc: Exception) -> bool:
    """Best-effort detection for Anthropic unknown model errors."""
    msg = str(exc).lower()
    return "not_found_error" in msg or ("model" in msg and "not found" in msg)


def _call_claude(prompt: str, model: str | None = None) -> str:
    """Call Anthropic Messages API. Returns assistant text content."""
    import anthropic

    api_key = _get_anthropic_api_key()
    if not api_key:
        raise RuntimeError(
            "AI_BACKEND is 'claude' but ANTHROPIC_API_KEY is not set. "
            "Add it to your .env or set AI_BACKEND=ollama."
        )

    model = model or _get_anthropic_model()
    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        fallback_model = "claude-sonnet-4-6"
        if model != fallback_model and _is_model_not_found_error(exc):
            logger.warning(
                "Configured Anthropic model '%s' not found; retrying with '%s'.",
                model,
                fallback_model,
            )
            message = client.messages.create(
                model=fallback_model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
        else:
            raise
    return message.content[0].text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_llm(prompt: str, model: str | None = None) -> str:
    """
    Call the configured LLM backend with a prompt. Returns the response text.

    Args:
        prompt: The full prompt string.
        model:  Optional model override. For Claude, use a Claude model ID
                (e.g. 'claude-opus-4-6'). For Ollama, use an Ollama model
                name (e.g. 'mistral-nemo:latest'). If None, the backend
                default is used.

    Raises:
        RuntimeError: If Claude/MCP is selected but ANTHROPIC_API_KEY is missing.
        requests.HTTPError: If Ollama returns a non-2xx response.
        anthropic.APIError: If the Anthropic API returns an error.
    """
    backend = get_ai_backend()
    logger.debug("call_llm: backend=%s model=%s prompt_len=%d", backend, model, len(prompt))

    if backend == "mcp":
        # Run through the full agentic loop so Claude has access to all CRM
        # tools (fetch_url, create_signal, search_contacts, etc.).
        # Lazy import avoids circular dependency (ai_chat imports ai_connector).
        from .ai_chat import run_chat  # noqa: PLC0415
        result = run_chat([{"role": "user", "content": prompt}])
        if result.get("error"):
            raise RuntimeError(result["error"])
        return result.get("response", "")

    if backend == "claude":
        return _call_claude(prompt, model=model)
    return _call_ollama(prompt, model=model)


def backend_info() -> dict:
    """Return a dict describing the currently active backend (useful for admin/debug views)."""
    backend = get_ai_backend()
    if backend in ("claude", "mcp"):
        return {
            "backend": backend,
            "model": _get_anthropic_model(),
            "api_key_set": bool(_get_anthropic_api_key()),
        }
    return {
        "backend": "ollama",
        "model": _get_ollama_model(),
        "base_url": _get_ollama_base_url(),
    }
