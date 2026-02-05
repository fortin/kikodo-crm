"""
Fetch a URL, extract main text, and call Ollama to populate Signal fields (Signals-Grid style).
Uses OLLAMA_BASE_URL (default http://localhost:11434) and OLLAMA_MODEL (default mistral-nemo:latest; set to a model you have, e.g. from ollama list).
"""

import json
import re
from datetime import date

from django.conf import settings


def get_ollama_base_url():
    return getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")


def get_ollama_model():
    return getattr(settings, "OLLAMA_MODEL", "mistral-nemo:latest")


def fetch_url_text(url: str, max_chars: int = 30000) -> str:
    """Fetch URL and return main text content (strip HTML)."""
    from urllib.parse import urlparse

    import requests
    from bs4 import BeautifulSoup

    # Mimic a real browser to reduce 403 from sites that block bots
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": origin + "/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # Remove script/style
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n\s*\n", "\n\n", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[... truncated]"
    return text


def call_ollama(
    prompt: str, model: str | None = None, base_url: str | None = None
) -> str:
    """Call Ollama via HTTP using /api/generate only.
    Returns full response text (no streaming). Retries with 127.0.0.1 if localhost returns 404.
    """
    import requests

    base_url = (base_url or get_ollama_base_url()).rstrip("/")
    model = model or get_ollama_model()

    url = f"{base_url}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}

    def _post(u):
        r = requests.post(u, json=payload, timeout=120)
        return r

    resp = _post(url)
    # Some processes (e.g. Django runserver in a different context) get 404 on localhost; retry with 127.0.0.1
    if resp.status_code == 404 and "localhost" in url:
        alt_url = url.replace("localhost", "127.0.0.1", 1)
        resp = _post(alt_url)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", "")


def parse_llm_signal_response(raw: str, source_url: str) -> dict:
    """
    Parse LLM response into Signal field dict. Expects JSON block or key: value lines.
    Returns dict with keys: headline, week, source_type, relevance, summary, potential_action, competitors, competitors_notes.
    """
    out = {
        "headline": "",
        "week": "",
        "source_type": "other",
        "relevance": "medium",
        "summary": "",
        "potential_action": "",
        "competitors": "",
        "competitors_notes": "",
    }

    # Try to find JSON in the response (```json ... ``` or { ... })
    json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            for key in out:
                if key in data and data[key] is not None:
                    out[key] = str(data[key]).strip()[:5000]
            return out
        except json.JSONDecodeError:
            pass

    plain_json = re.search(r"\{[\s\S]*\}", raw)
    if plain_json:
        try:
            data = json.loads(plain_json.group(0))
            for key in out:
                if key in data and data[key] is not None:
                    out[key] = str(data[key]).strip()[:5000]
            return out
        except json.JSONDecodeError:
            pass

    # Fallback: key: value lines
    for line in raw.splitlines():
        for key in out:
            if line.strip().lower().startswith(key + ":"):
                value = line.split(":", 1)[1].strip()
                if len(value) > 5000:
                    value = value[:5000]
                out[key] = value
                break

    return out


def iso_week_string(d: date) -> str:
    """Return e.g. 2025-W40."""
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def populate_signal_from_url(source_url: str, model: str | None = None) -> dict:
    """
    Fetch URL, call Ollama to extract signal fields, return dict suitable for Signal model.
    Includes source_url, date_logged, week, and all LLM-parsed fields.
    """
    text = fetch_url_text(source_url)
    today = date.today()
    week = iso_week_string(today)

    prompt = f"""You are helping populate a "Signals" spreadsheet row from a web page. The page content is below.

Extract and return a single JSON object with exactly these keys (use empty string if not applicable):
- headline: short headline or key point (max ~200 chars)
- week: ISO week e.g. "{week}"
- source_type: one of: publisher_news, general_market, compliance_update, thought_leadership, market_forecast, regulatory, potential_lead, other
- relevance: one of: high, medium, low
- summary: 1-3 sentence summary of the content
- potential_action: suggested next step or how to use this signal (e.g. "Track as innovator; mention in outreach")
- competitors: any companies or products mentioned (comma-separated)
- competitors_notes: audience, content focus, relevance to Kikodo ICP, or positioning notes

Page URL: {source_url}

Page content:
---
{text[:25000]}
---

Return only the JSON object, no other text."""

    raw = call_ollama(prompt, model=model)
    parsed = parse_llm_signal_response(raw, source_url)
    parsed["week"] = parsed["week"] or week
    parsed["source_url"] = source_url
    parsed["date_logged"] = today
    parsed["status"] = "logged"
    return parsed


def populate_signal_from_text(
    source_url: str, text: str, model: str | None = None
) -> dict:
    """
    Use pasted page text (no fetch) and call Ollama to extract signal fields.
    Same as populate_signal_from_url but takes text directly (e.g. when URL returns 403).
    """
    today = date.today()
    week = iso_week_string(today)

    prompt = f"""You are helping populate a "Signals" spreadsheet row from a web page. The page content is below.

Extract and return a single JSON object with exactly these keys (use empty string if not applicable):
- headline: short headline or key point (max ~200 chars)
- week: ISO week e.g. "{week}"
- source_type: one of: publisher_news, general_market, compliance_update, thought_leadership, market_forecast, regulatory, potential_lead, other
- relevance: one of: high, medium, low
- summary: 1-3 sentence summary of the content
- potential_action: suggested next step or how to use this signal (e.g. "Track as innovator; mention in outreach")
- competitors: any companies or products mentioned (comma-separated)
- competitors_notes: audience, content focus, relevance to Kikodo ICP, or positioning notes

Page URL: {source_url}

Page content:
---
{text[:25000]}
---

Return only the JSON object, no other text."""

    raw = call_ollama(prompt, model=model)
    parsed = parse_llm_signal_response(raw, source_url)
    parsed["week"] = parsed["week"] or week
    parsed["source_url"] = source_url
    parsed["date_logged"] = today
    parsed["status"] = "logged"
    return parsed


def suggest_sequence_steps(
    name: str, description: str, model: str | None = None
) -> list:
    """
    Call Ollama to suggest sequence steps (order, offset_days, activity_type, subject, body)
    from sequence name and description. Uses best-practice timing in the prompt.
    Returns list of dicts with keys: order, offset_days, activity_type, subject, body, auto_execute.
    """
    prompt = f"""You are helping design an outbound sales/marketing sequence. Given the sequence name and description below, suggest 4-6 steps with optimal timing for effectiveness.

Best-practice timing: Step 1 Day 0; follow-up emails 2-4 days apart; mix in call/meeting after 1-2 emails; final touch 5-7 days after previous; total under 21 days unless long nurture.

Activity types (use exactly): email, call, meeting, task, linkedin, note, demo, proposal.

Return a JSON array of steps. Each step: order (1,2,...), offset_days (0 for first), activity_type, subject (max 100 chars), body (max 500 chars), auto_execute (true for email).

Sequence name: {name or "Outreach sequence"}
Description: {description or "General outreach"}

Return only the JSON array."""

    raw = call_ollama(prompt, model=model)
    out = []
    json_match = re.search(r"\[\s*\{[\s\S]*\}\s*\]", raw)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            for i, step in enumerate(data):
                if not isinstance(step, dict):
                    continue
                order = step.get("order", i + 1)
                offset_days = step.get("offset_days", 0)
                activity_type = (step.get("activity_type") or "email").strip().lower()
                if activity_type not in (
                    "email",
                    "call",
                    "meeting",
                    "task",
                    "linkedin",
                    "note",
                    "demo",
                    "proposal",
                    "system",
                ):
                    activity_type = "email"
                subject = (step.get("subject") or "")[:255]
                body = (step.get("body") or "")[:2000]
                auto_execute = step.get("auto_execute", activity_type == "email")
                out.append(
                    {
                        "order": order,
                        "offset_days": (
                            int(offset_days)
                            if isinstance(offset_days, (int, float))
                            else 0
                        ),
                        "activity_type": activity_type,
                        "subject": subject,
                        "body": body,
                        "auto_execute": bool(auto_execute),
                    }
                )
        except json.JSONDecodeError:
            pass
    return out
