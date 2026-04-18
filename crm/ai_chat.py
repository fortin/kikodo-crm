"""
Agentic chat loop for the CRM AI assistant.

Uses the Anthropic API with tool use. Each call to run_chat() runs the full
tool-call loop (Claude → tool → result → Claude) until Claude produces a
final text response or hits max_iterations.

Falls back gracefully when AI_BACKEND=ollama (no tool use, plain chat).
"""

import json
import logging

from .ai_connector import _get_anthropic_api_key, _get_anthropic_model, get_ai_backend
from .mcp_app import _dispatch

logger = logging.getLogger("crm")

_SYSTEM_PROMPT = """You are an AI assistant embedded in Kikodo CRM, a B2B sales CRM.

You help the user with:
- Looking up, enriching, and summarising contacts and companies
- Analysing market signals and news
- Reviewing the sales pipeline and drafting follow-ups
- Summarising pain signals and suggesting talking points
- Suggesting outreach sequences and next best actions

You have access to the CRM database through tools. Always use the tools to
fetch real data before answering questions about specific records.

Keep responses concise, structured, and actionable. Use markdown for formatting
(bullet points, bold headings). When you update data, confirm exactly what changed."""

# Tool definitions in Anthropic API format (mirrors the MCP tool schemas)
_TOOLS = [
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

    # Ollama fallback: no tool use, just a plain completion
    if backend == "ollama":
        from .ai_connector import call_llm
        history = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in messages[-6:]
        )
        prompt = (
            "You are a CRM assistant for Kikodo CRM. Answer concisely.\n\n"
            f"{history}"
        )
        try:
            response = call_llm(prompt)
            updated = messages + [{"role": "assistant", "content": response}]
            return {"response": response, "messages": updated, "error": None}
        except Exception as e:
            return {"response": "", "messages": messages, "error": str(e)}

    # Claude: full agentic loop with tool use
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
                result = _dispatch(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result[0].text if result else "{}",
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
