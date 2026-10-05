"""
Agentic chat loop for the CRM AI assistant.

Uses the Anthropic API with tool use. Each call to run_chat() runs the full
tool-call loop (Claude → tool → result → Claude) until Claude produces a
final text response or hits max_iterations.

Falls back gracefully when AI_BACKEND=ollama (uses Ollama /api/chat with tool calling).
"""

import json
import logging

from .ai_connector import (
    _get_anthropic_api_key,
    _get_anthropic_model,
    _get_ollama_base_url,
    _get_ollama_model,
    get_ai_backend,
)
from .ai_db import DB_TOOL_SCHEMAS
from .ai_tools import execute_tool

logger = logging.getLogger("crm")

_SYSTEM_PROMPT = """You are an AI assistant embedded in Kikodo CRM, a B2B sales CRM.

You help the user with:
- Looking up, enriching, and summarising contacts and companies
- Analysing market signals and news
- Reviewing the sales pipeline and drafting follow-ups
- Summarising pain signals and suggesting talking points
- Suggesting outreach sequences and next best actions

CRITICAL: You have full read access to the CRM database through your tools.
NEVER tell the user you lack access to their data. For any question about
contacts, companies, signals, deals, newsletters, or other CRM records, you
MUST call the appropriate tool before answering.

You have access to the full CRM database through tools:
- list_models / describe_model — discover models and their fields
- query_records / get_record / count_records — query any model (newsletters,
  sequences, pipelines, analytics, etc.)
- get_signals — list market signals; count_records with model Signal also works
- Specialised tools (search_contacts, create_contact, create_company, create_deal, …) for common CRM tasks

For unfamiliar data, call list_models then describe_model before querying.

Keep responses concise, structured, and actionable. Use markdown for formatting
(bullet points, bold headings). When you update data, confirm exactly what changed."""

# Generic DB tools first, then specialised CRM tools (mirrors MCP tool schemas)
_TOOLS = DB_TOOL_SCHEMAS + [
    {
        "name": "search_contacts",
        "description": "Search CRM contacts by name, email, or company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_contact",
        "description": "Full contact record with recent activities, deals, and pain signals.",
        "input_schema": {
            "type": "object",
            "properties": {"contact_id": {"type": "integer"}},
            "required": ["contact_id"],
        },
    },
    {
        "name": "create_contact",
        "description": "Create a new CRM contact. Prefer company_id if the company already exists.",
        "input_schema": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "job_title": {"type": "string"},
                "company_id": {"type": "integer"},
                "company_name": {
                    "type": "string",
                    "description": "Create or attach by company name if company_id is unknown",
                },
                "linkedin_url": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["lead", "prospect", "customer", "inactive"],
                    "default": "lead",
                },
                "headline": {"type": "string"},
                "notes": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["first_name", "last_name"],
        },
    },
    {
        "name": "update_contact",
        "description": "Save enriched fields (job_title, company, bio, notes, status) back to the CRM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "integer"},
                "job_title": {"type": "string"},
                "company_name": {"type": "string"},
                "headline": {"type": "string"},
                "bio": {"type": "string"},
                "notes": {"type": "string"},
                "linkedin_url": {"type": "string"},
                "status": {"type": "string"},
            },
            "required": ["contact_id"],
        },
    },
    {
        "name": "search_companies",
        "description": "Search CRM companies by name or industry.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_company",
        "description": "Full company record with contacts, deals, pain signals, and linked signals.",
        "input_schema": {
            "type": "object",
            "properties": {"company_id": {"type": "integer"}},
            "required": ["company_id"],
        },
    },
    {
        "name": "create_company",
        "description": "Create a new CRM company. Fails if a company with the same name already exists.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "industry": {"type": "string"},
                "website": {"type": "string"},
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "city": {"type": "string"},
                "state": {"type": "string"},
                "country": {"type": "string"},
                "description": {"type": "string"},
                "linkedin_url": {"type": "string"},
                "employee_count": {"type": "integer"},
                "icp_fit_score": {"type": "number"},
                "icp_fit_tier": {"type": "string", "enum": ["A", "B", "C", "D"]},
            },
            "required": ["name"],
        },
    },
    {
        "name": "update_company",
        "description": "Update company fields: description, industry, ICP score/tier, notes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_id": {"type": "integer"},
                "description": {"type": "string"},
                "industry": {"type": "string"},
                "website": {"type": "string"},
                "employee_count": {"type": "integer"},
                "icp_fit_score": {"type": "number"},
                "icp_fit_tier": {"type": "string", "enum": ["A", "B", "C", "D"]},
                "notes": {"type": "string"},
            },
            "required": ["company_id"],
        },
    },
    {
        "name": "fetch_url",
        "description": "Fetch a web page and return plain text. Use to read a signal URL or article.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "max_chars": {"type": "integer", "default": 25000},
            },
            "required": ["url"],
        },
    },
    {
        "name": "create_signal",
        "description": "Save a new market signal after analysing a URL or article.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_url": {"type": "string"},
                "headline": {"type": "string"},
                "source_type": {"type": "string"},
                "relevance": {"type": "string", "enum": ["high", "medium", "low"]},
                "summary": {"type": "string"},
                "potential_action": {"type": "string"},
                "competitors": {"type": "string"},
                "competitors_notes": {"type": "string"},
                "mentioned_company_names": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["source_url", "headline", "summary"],
        },
    },
    {
        "name": "update_signal",
        "description": "Update an existing signal's fields or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "signal_id": {"type": "integer"},
                "headline": {"type": "string"},
                "summary": {"type": "string"},
                "relevance": {"type": "string", "enum": ["high", "medium", "low"]},
                "potential_action": {"type": "string"},
                "status": {"type": "string", "enum": ["logged", "actioned", "archived"]},
            },
            "required": ["signal_id"],
        },
    },
    {
        "name": "get_signals",
        "description": "List recent signals, optionally filtered by relevance or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "relevance": {"type": "string"},
                "status": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "get_pain_signals",
        "description": "Get pain signals for a company or across the whole CRM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_id": {"type": "integer"},
                "limit": {"type": "integer", "default": 30},
            },
        },
    },
    {
        "name": "create_pain_signal",
        "description": "Log a new pain signal for a company or contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_id": {"type": "integer"},
                "contact_id": {"type": "integer"},
                "description": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["description"],
        },
    },
    {
        "name": "create_deal",
        "description": "Create a new deal/opportunity. Requires an existing contact. Company is taken from the contact unless company_id is set. expected_close_date defaults to 30 days from today.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "contact_id": {"type": "integer"},
                "company_id": {"type": "integer"},
                "amount": {"type": "number", "default": 0},
                "currency": {"type": "string", "default": "USD"},
                "stage": {
                    "type": "string",
                    "enum": [
                        "prospecting",
                        "qualification",
                        "proposal",
                        "negotiation",
                        "closed_won",
                        "closed_lost",
                    ],
                    "default": "prospecting",
                },
                "probability": {"type": "integer", "default": 0},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "default": "medium",
                },
                "expected_close_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD; defaults to 30 days from today",
                },
                "description": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["name", "contact_id"],
        },
    },
    {
        "name": "get_deals",
        "description": "List deals filtered by stage, company, or contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string"},
                "company_id": {"type": "integer"},
                "contact_id": {"type": "integer"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "get_activities",
        "description": "List activities for a contact, company, or deal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "integer"},
                "company_id": {"type": "integer"},
                "deal_id": {"type": "integer"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "create_activity",
        "description": "Log a new activity (call, email, meeting, note, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "integer"},
                "company_id": {"type": "integer"},
                "deal_id": {"type": "integer"},
                "activity_type": {
                    "type": "string",
                    "enum": ["call", "email", "meeting", "task", "linkedin", "note", "demo", "proposal"],
                },
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "status": {"type": "string", "enum": ["pending", "completed"], "default": "completed"},
                "direction": {"type": "string", "enum": ["inbound", "outbound"], "default": "outbound"},
            },
            "required": ["activity_type", "subject"],
        },
    },
]


def _content_to_text(content) -> str:
    """Extract text from an Anthropic content block or list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.text for block in content
            if hasattr(block, "text")
        )
    if hasattr(content, "text"):
        return content.text
    return str(content)


def _tools_for_ollama() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in _TOOLS
    ]


def _parse_tool_arguments(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return {}


def _run_ollama_chat(messages: list, max_iterations: int = 8) -> dict:
    """Agentic loop via Ollama /api/chat with native tool calling."""
    import requests

    base_url = _get_ollama_base_url().rstrip("/")
    model = _get_ollama_model()
    ollama_messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for message in messages:
        ollama_messages.append({"role": message["role"], "content": message["content"]})

    tools = _tools_for_ollama()

    for _ in range(max_iterations):
        try:
            resp = requests.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": ollama_messages,
                    "tools": tools,
                    "stream": False,
                },
                timeout=300,
            )
            if resp.status_code == 404 and "localhost" in base_url:
                resp = requests.post(
                    base_url.replace("localhost", "127.0.0.1", 1) + "/api/chat",
                    json={
                        "model": model,
                        "messages": ollama_messages,
                        "tools": tools,
                        "stream": False,
                    },
                    timeout=300,
                )
            resp.raise_for_status()
            msg = resp.json().get("message", {})
        except Exception as exc:
            return {"response": "", "messages": messages, "error": str(exc)}

        tool_calls = msg.get("tool_calls") or []
        if tool_calls:
            ollama_messages.append(msg)
            for tool_call in tool_calls:
                fn = tool_call.get("function", {})
                name = fn.get("name", "")
                args = _parse_tool_arguments(fn.get("arguments"))
                logger.debug("Ollama tool call: %s %s", name, args)
                tool_message = {
                    "role": "tool",
                    "content": execute_tool(name, args),
                    "tool_name": name,
                }
                if tool_call.get("id"):
                    tool_message["tool_call_id"] = tool_call["id"]
                ollama_messages.append(tool_message)
            continue

        text = (msg.get("content") or "").strip()
        updated = messages + [{"role": "assistant", "content": text}]
        return {"response": text, "messages": updated, "error": None}

    return {
        "response": "I reached my step limit. Please try a simpler question.",
        "messages": messages,
        "error": None,
    }


def run_chat(messages: list, max_iterations: int = 8) -> dict:
    """
    Run the agentic loop.

    Args:
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
                  The last message should be the new user message.
        max_iterations: Safety limit on tool-call rounds.

    Returns:
        {"response": str, "messages": list, "error": str|None}
    """
    backend = get_ai_backend()

    if backend == "ollama":
        return _run_ollama_chat(messages, max_iterations=max_iterations)

    # Claude / MCP: full agentic loop with tool use
    import anthropic

    api_key = _get_anthropic_api_key()
    if not api_key:
        return {
            "response": "",
            "messages": messages,
            "error": "ANTHROPIC_API_KEY is not set.",
        }

    client = anthropic.Anthropic(api_key=api_key)
    current = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
    ]

    for _ in range(max_iterations):
        try:
            resp = client.messages.create(
                model=_get_anthropic_model(),
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                tools=_TOOLS,
                messages=current,
            )
        except Exception as e:
            return {"response": "", "messages": messages, "error": str(e)}

        if resp.stop_reason == "end_turn":
            text = _content_to_text(resp.content)
            updated = messages + [{"role": "assistant", "content": text}]
            return {"response": text, "messages": updated, "error": None}

        if resp.stop_reason == "tool_use":
            tool_results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                logger.debug("AI tool call: %s %s", block.name, block.input)
                result_text = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

            current.append({"role": "assistant", "content": resp.content})
            current.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason
        break

    return {
        "response": "I reached my step limit. Please try a simpler question.",
        "messages": messages,
        "error": None,
    }
