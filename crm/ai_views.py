"""
AI action endpoints for the CRM front-end.

  POST /ai/contact/<pk>/enrich/   — enrich a contact (AJAX)
  POST /ai/company/<pk>/brief/    — AI brief for a company (AJAX)
  POST /ai/chat/                  — agentic chat (AJAX, JSON body)
"""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .ai_chat import run_chat
from .ai_connector import get_ai_backend
from .enrichment import enrich_contact_from_llm
from .models import Company, Contact
from .mcp_app import _dispatch


# ---------------------------------------------------------------------------
# Contact enrichment
# ---------------------------------------------------------------------------

@login_required
@require_POST
def enrich_contact_ajax(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    try:
        result = enrich_contact_from_llm(contact)
        if result.get("error"):
            return JsonResponse({"ok": False, "error": result["error"]})
        if not result.get("updated"):
            return JsonResponse({"ok": True, "updated": False,
                                 "message": "Nothing to enrich — fields already filled."})
        parts = []
        if result.get("job_title"):
            parts.append(f"Job title: <strong>{result['job_title']}</strong>")
        if result.get("company"):
            parts.append(f"Company: <strong>{result['company'].name}</strong>")
        return JsonResponse({
            "ok": True,
            "updated": True,
            "message": "Updated " + " · ".join(parts),
            "reload": True,
        })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Company AI brief
# ---------------------------------------------------------------------------

@login_required
@require_POST
def company_brief_ajax(request, pk):
    company = get_object_or_404(Company, pk=pk)
    messages = [
        {
            "role": "user",
            "content": (
                f"Generate a concise AI brief for company '{company.name}' (ID {company.pk}). "
                "Use the get_company tool to fetch the full record first. "
                "The brief should cover: who they are, their pain points, open deals, "
                "key contacts, and the recommended next action. Use markdown."
            ),
        }
    ]
    result = run_chat(messages)
    if result.get("error"):
        return JsonResponse({"ok": False, "error": result["error"]})
    return JsonResponse({"ok": True, "brief": result["response"]})


# ---------------------------------------------------------------------------
# Agentic chat
# ---------------------------------------------------------------------------

@login_required
@require_POST
def chat_ajax(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    messages = data.get("messages", [])
    user_message = data.get("message", "").strip()
    if not user_message:
        return JsonResponse({"ok": False, "error": "Empty message"}, status=400)

    messages = messages + [{"role": "user", "content": user_message}]
    result = run_chat(messages)

    return JsonResponse({
        "ok": not bool(result.get("error")),
        "response": result.get("response", ""),
        "messages": result.get("messages", messages),
        "error": result.get("error"),
        "backend": get_ai_backend(),
    })
