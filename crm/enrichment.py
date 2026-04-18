"""
LLM-based contact enrichment: fill missing company and job_title from headline, bio, notes,
email domain, or fetched LinkedIn page.

Uses the configured AI backend (Claude or Ollama) via crm.ai_connector.call_llm.
Set AI_BACKEND, ANTHROPIC_API_KEY / OLLAMA_BASE_URL in settings or .env.
"""

import json
import re

from .ai_connector import call_llm
from .models import Company, Contact


def fetch_url_text(url: str, max_chars: int = 15000) -> str:
    """Fetch URL and return main text content (strip HTML)."""
    from urllib.parse import urlparse

    import requests
    from bs4 import BeautifulSoup

    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": origin + "/",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n\s*\n", "\n\n", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[... truncated]"
    return text


def _parse_enrichment_response(raw: str) -> dict:
    """Parse LLM response into job_title and company_name."""
    out = {"job_title": "", "company_name": ""}
    json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            out["job_title"] = str(data.get("job_title") or "").strip()[:500]
            out["company_name"] = str(data.get("company_name") or "").strip()[:255]
            return out
        except json.JSONDecodeError:
            pass
    plain_json = re.search(r"\{[\s\S]*\}", raw)
    if plain_json:
        try:
            data = json.loads(plain_json.group(0))
            out["job_title"] = str(data.get("job_title") or "").strip()[:500]
            out["company_name"] = str(data.get("company_name") or "").strip()[:255]
            return out
        except json.JSONDecodeError:
            pass
    for line in raw.splitlines():
        if line.strip().lower().startswith("job_title:"):
            out["job_title"] = line.split(":", 1)[1].strip()[:500]
        elif line.strip().lower().startswith("company_name:"):
            out["company_name"] = line.split(":", 1)[1].strip()[:255]
    return out


def enrich_contact_from_llm(
    contact: Contact,
    *,
    fetch_linkedin: bool = True,
    model: str | None = None,
) -> dict:
    """
    Enrich a contact's job_title and company using LLM. Uses headline, bio, notes,
    email domain, and optionally fetched LinkedIn page. Only fills fields that are
    currently empty.

    Returns dict with keys: updated (bool), job_title (str or None), company (Company or None),
    sources (list of str), error (str or None).
    """
    result = {"updated": False, "job_title": None, "company": None, "sources": [], "error": None}
    needs_job = not (contact.job_title or "").strip()
    needs_company = contact.company_id is None

    if not needs_job and not needs_company:
        return result

    # Build context from available fields
    parts = []
    if contact.headline:
        parts.append(f"Headline: {contact.headline}")
    if contact.bio:
        parts.append(f"Bio: {contact.bio[:2000]}")
    if contact.notes:
        parts.append(f"Notes: {contact.notes[:2000]}")
    if contact.email:
        domain = contact.email.split("@")[-1] if "@" in contact.email else ""
        parts.append(f"Email domain: {domain}")
    if contact.linkedin or contact.linkedin_url:
        parts.append(f"LinkedIn URL: {contact.linkedin or contact.linkedin_url}")

    if not parts:
        result["error"] = "No data to enrich from (need headline, bio, notes, email, or LinkedIn URL)."
        return result

    context = "\n".join(parts)
    linkedin_text = ""

    # Optionally fetch LinkedIn page
    if fetch_linkedin and (needs_job or needs_company):
        url = (contact.linkedin or contact.linkedin_url or "").strip()
        if url and url.startswith("http"):
            try:
                linkedin_text = fetch_url_text(url)
                if linkedin_text and len(linkedin_text) > 100:
                    context += f"\n\n--- Fetched LinkedIn page content ---\n{linkedin_text[:8000]}"
                    result["sources"].append("LinkedIn page")
            except Exception as e:
                result["sources"].append(f"LinkedIn fetch failed: {e}")

    if not result["sources"] and (contact.headline or contact.bio or contact.notes):
        result["sources"].append("headline/bio/notes")
    if contact.email and not any("domain" in s.lower() for s in result["sources"]):
        result["sources"].append("email domain")

    prompt = f"""You are helping enrich a CRM contact. Extract job title and company name from the context below.

Contact: {contact.first_name} {contact.last_name}

Context:
{context}

Return a JSON object with exactly these keys (use empty string if you cannot determine):
- job_title: the person's current job/role (e.g. "Senior Engineer", "VP of Sales")
- company_name: the company/organization name (e.g. "Acme Corp", "Microsoft")

Rules:
- Only extract information that is explicitly stated or strongly implied. Do NOT guess or invent.
- If the headline says "Engineer at Acme", job_title is "Engineer" and company_name is "Acme".
- For email domain (e.g. john@acme.com), company_name might be "Acme" or "Acme Inc" - use your best judgment for the domain part only.
- Return empty string for any field you cannot confidently determine.
- Company name should be a clean organization name, not a URL or "at Company".

Return only the JSON object, no other text."""

    try:
        raw = call_llm(prompt, model=model)
        parsed = _parse_enrichment_response(raw)
    except Exception as e:
        result["error"] = str(e)
        return result

    # Apply job_title if we got one and contact needs it
    if needs_job and parsed["job_title"]:
        contact.job_title = parsed["job_title"]
        result["job_title"] = parsed["job_title"]
        result["updated"] = True

    # Apply company if we got one and contact needs it
    if needs_company and parsed["company_name"]:
        company_name = parsed["company_name"]
        # Basic validation: reject URLs, very short, or garbage
        if (
            company_name
            and len(company_name) >= 2
            and not company_name.startswith(("http://", "https://", "www."))
            and "linkedin.com" not in company_name.lower()
        ):
            company, _ = Company.objects.get_or_create(
                name=company_name,
                defaults={"owner": contact.owner},
            )
            contact.company = company
            result["company"] = company
            result["updated"] = True

    if result["updated"]:
        contact.save(update_fields=["job_title", "company", "updated_at"])

    return result
