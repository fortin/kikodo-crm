"""
Kikodo CRM — MCP application (shared between stdio and HTTP transports).

Tools exposed:
  search_contacts, get_contact, update_contact
  search_companies, get_company, update_company
  fetch_url
  create_signal, update_signal, get_signals
  get_pain_signals, create_pain_signal
  get_deals
  get_activities, create_activity

Transport wiring:
  - stdio  → crm_mcp_server.py (for Claude Code / CLI)
  - HTTP   → kikodo_crm/asgi.py mounts build_starlette_app() at /mcp/
              - SSE endpoint:         /mcp/sse
              - Streamable POST URL:  /mcp
"""

import json
import logging
from datetime import date, datetime
from typing import Any

import mcp.types as types
from asgiref.sync import sync_to_async
from mcp.server import Server

logger = logging.getLogger("crm.mcp")

mcp_server = Server("kikodo-crm")


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _s(obj: Any) -> Any:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _s(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_s(i) for i in obj]
    return obj


def _ok(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(_s(data), indent=2))]


def _err(msg: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps({"error": msg}))]


def _contact_dict(c) -> dict:
    return {
        "id": c.pk,
        "name": f"{c.first_name} {c.last_name}".strip(),
        "first_name": c.first_name,
        "last_name": c.last_name,
        "email": c.email or "",
        "phone": c.phone or "",
        "job_title": c.job_title or "",
        "company_id": c.company_id,
        "company_name": c.company.name if c.company_id else "",
        "headline": c.headline or "",
        "bio": c.bio or "",
        "notes": c.notes or "",
        "linkedin_url": c.linkedin_url or c.linkedin or "",
        "status": c.status or "",
        "is_active": c.is_active,
        "created_at": c.created_at,
    }


def _company_dict(co) -> dict:
    return {
        "id": co.pk,
        "name": co.name,
        "website": co.website or "",
        "industry": co.industry or "",
        "employee_count": co.employee_count,
        "annual_revenue": str(co.annual_revenue) if co.annual_revenue else "",
        "size_category": co.size_category or "",
        "icp_fit_score": co.icp_fit_score,
        "icp_fit_tier": co.icp_fit_tier or "",
        "description": co.description or "",
        "linkedin_url": co.linkedin_url or "",
        "notes": co.notes or "",
        "city": co.city or "",
        "state": co.state or "",
        "country": co.country or "",
        "is_active": co.is_active,
    }


def _signal_dict(s) -> dict:
    return {
        "id": s.pk,
        "source_url": s.source_url or "",
        "headline": s.headline or "",
        "source_type": s.source_type or "",
        "relevance": s.relevance or "",
        "summary": s.summary or "",
        "potential_action": s.potential_action or "",
        "competitors": s.competitors or "",
        "status": s.status or "",
        "date_logged": s.date_logged,
        "week": s.week or "",
    }


def _deal_dict(d) -> dict:
    return {
        "id": d.pk,
        "name": d.name,
        "stage": d.stage or "",
        "amount": str(d.amount) if d.amount else "",
        "probability": d.probability,
        "priority": d.priority or "",
        "expected_close_date": d.expected_close_date,
        "contact_name": f"{d.contact.first_name} {d.contact.last_name}".strip() if d.contact_id else "",
        "company_name": d.company.name if d.company_id else "",
        "notes": d.notes or "",
    }


# ---------------------------------------------------------------------------
# Tool dispatch (synchronous — called via sync_to_async)
# ---------------------------------------------------------------------------

def _dispatch(name: str, arguments: dict) -> list[types.TextContent]:
    from crm.models import Activity, Company, Contact, Deal, PainSignal, Signal

    # ------------------------------------------------------------------ contacts
    if name == "search_contacts":
        from django.db.models import Q
        q = arguments.get("query", "")
        qs = Contact.objects.filter(is_active=True).filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
            | Q(email__icontains=q) | Q(company__name__icontains=q)
        ).select_related("company")[: int(arguments.get("limit", 20))]
        return _ok([_contact_dict(c) for c in qs])

    if name == "get_contact":
        try:
            c = Contact.objects.select_related("company").get(pk=arguments["contact_id"])
        except Contact.DoesNotExist:
            return _err("Contact not found")
        data = _contact_dict(c)
        data["recent_activities"] = [
            {"id": a.pk, "type": a.activity_type, "subject": a.subject or "",
             "status": a.status or "", "created_at": a.created_at}
            for a in Activity.objects.filter(contact=c).order_by("-created_at")[:10]
        ]
        data["deals"] = [
            {"id": d.pk, "name": d.name, "stage": d.stage or "", "amount": str(d.amount or "")}
            for d in Deal.objects.filter(contact=c, is_active=True)
        ]
        data["pain_signals"] = [
            {"id": p.pk, "description": p.description or "", "source": p.source or ""}
            for p in PainSignal.objects.filter(contact=c).order_by("-created_at")[:5]
        ]
        return _ok(data)

    if name == "update_contact":
        try:
            c = Contact.objects.select_related("company").get(pk=arguments["contact_id"])
        except Contact.DoesNotExist:
            return _err("Contact not found")
        updated = ["updated_at"]
        for field in ("job_title", "headline", "bio", "notes", "linkedin_url", "status"):
            if arguments.get(field):
                setattr(c, field, arguments[field])
                updated.append(field)
        if arguments.get("company_name"):
            val = arguments["company_name"].strip()
            if len(val) >= 2 and not val.startswith("http") and "linkedin.com" not in val.lower():
                co, _ = Company.objects.get_or_create(name=val, defaults={"owner": c.owner})
                c.company = co
                updated.append("company")
        c.save(update_fields=updated)
        return _ok({"updated": True, "contact_id": c.pk, "fields": updated})

    # ---------------------------------------------------------------- companies
    if name == "search_companies":
        from django.db.models import Q
        q = arguments.get("query", "")
        qs = Company.objects.filter(is_active=True).filter(
            Q(name__icontains=q) | Q(industry__icontains=q)
        )[: int(arguments.get("limit", 20))]
        return _ok([_company_dict(co) for co in qs])

    if name == "get_company":
        try:
            co = Company.objects.get(pk=arguments["company_id"])
        except Company.DoesNotExist:
            return _err("Company not found")
        data = _company_dict(co)
        data["contacts"] = [
            {"id": c.pk, "name": f"{c.first_name} {c.last_name}".strip(), "job_title": c.job_title or ""}
            for c in Contact.objects.filter(company=co, is_active=True)[:20]
        ]
        data["deals"] = [_deal_dict(d) for d in Deal.objects.filter(company=co, is_active=True)[:10]]
        data["pain_signals"] = [
            {"id": p.pk, "description": p.description or "", "source": p.source or ""}
            for p in PainSignal.objects.filter(company=co).order_by("-created_at")[:10]
        ]
        data["signals"] = [
            {"id": s.pk, "headline": s.headline or "", "relevance": s.relevance or ""}
            for s in Signal.objects.filter(companies=co).order_by("-date_logged")[:5]
        ]
        return _ok(data)

    if name == "update_company":
        try:
            co = Company.objects.get(pk=arguments["company_id"])
        except Company.DoesNotExist:
            return _err("Company not found")
        updated = ["updated_at"]
        for field in ("description", "industry", "website", "employee_count",
                      "icp_fit_score", "icp_fit_tier", "notes"):
            if field in arguments and arguments[field] is not None:
                setattr(co, field, arguments[field])
                updated.append(field)
        co.save(update_fields=updated)
        return _ok({"updated": True, "company_id": co.pk, "fields": updated})

    # ------------------------------------------------------------------- signals
    if name == "fetch_url":
        from crm.signals_llm import fetch_url_text
        try:
            text = fetch_url_text(arguments["url"], max_chars=int(arguments.get("max_chars", 25000)))
            return _ok({"url": arguments["url"], "content": text, "length": len(text)})
        except Exception as e:
            return _err(f"Could not fetch URL: {e}")

    if name == "create_signal":
        today = date.today()
        iso = today.isocalendar()
        s = Signal(
            source_url=arguments.get("source_url", ""),
            headline=arguments.get("headline", "")[:200],
            source_type=arguments.get("source_type", "other"),
            relevance=arguments.get("relevance", "medium"),
            summary=arguments.get("summary", ""),
            potential_action=arguments.get("potential_action", ""),
            competitors=arguments.get("competitors", ""),
            competitors_notes=arguments.get("competitors_notes", ""),
            date_logged=today,
            week=f"{iso.year}-W{iso.week:02d}",
            status="logged",
        )
        s.save()
        for cname in arguments.get("mentioned_company_names", []):
            cname = cname.strip()
            if cname:
                co, _ = Company.objects.get_or_create(name=cname, defaults={})
                s.companies.add(co)
        return _ok({"created": True, "signal_id": s.pk})

    if name == "update_signal":
        try:
            s = Signal.objects.get(pk=arguments["signal_id"])
        except Signal.DoesNotExist:
            return _err("Signal not found")
        updated = ["updated_at"]
        for field in ("headline", "summary", "relevance", "potential_action",
                      "status", "competitors", "competitors_notes"):
            if field in arguments and arguments[field] is not None:
                setattr(s, field, arguments[field])
                updated.append(field)
        s.save(update_fields=updated)
        return _ok({"updated": True, "signal_id": s.pk})

    if name == "get_signals":
        qs = Signal.objects.all()
        if "relevance" in arguments:
            qs = qs.filter(relevance=arguments["relevance"])
        if "status" in arguments:
            qs = qs.filter(status=arguments["status"])
        qs = qs.order_by("-date_logged")[: int(arguments.get("limit", 20))]
        return _ok([_signal_dict(s) for s in qs])

    # --------------------------------------------------------------- pain signals
    if name == "get_pain_signals":
        qs = PainSignal.objects.select_related("company", "contact").order_by("-created_at")
        if "company_id" in arguments:
            qs = qs.filter(company_id=arguments["company_id"])
        qs = qs[: int(arguments.get("limit", 30))]
        return _ok([
            {
                "id": p.pk, "description": p.description or "", "source": p.source or "",
                "company": p.company.name if p.company_id else "",
                "contact": f"{p.contact.first_name} {p.contact.last_name}".strip() if p.contact_id else "",
                "created_at": p.created_at,
            }
            for p in qs
        ])

    if name == "create_pain_signal":
        ps = PainSignal(
            description=arguments.get("description", ""),
            source=arguments.get("source", ""),
        )
        if "company_id" in arguments:
            ps.company_id = arguments["company_id"]
        if "contact_id" in arguments:
            ps.contact_id = arguments["contact_id"]
        ps.save()
        return _ok({"created": True, "pain_signal_id": ps.pk})

    # --------------------------------------------------------------------- deals
    if name == "get_deals":
        qs = Deal.objects.filter(is_active=True).select_related("contact", "company")
        if "stage" in arguments:
            qs = qs.filter(stage=arguments["stage"])
        if "company_id" in arguments:
            qs = qs.filter(company_id=arguments["company_id"])
        if "contact_id" in arguments:
            qs = qs.filter(contact_id=arguments["contact_id"])
        qs = qs.order_by("-created_at")[: int(arguments.get("limit", 20))]
        return _ok([_deal_dict(d) for d in qs])

    # ----------------------------------------------------------------- activities
    if name == "get_activities":
        qs = Activity.objects.select_related("contact", "company").order_by("-created_at")
        if "contact_id" in arguments:
            qs = qs.filter(contact_id=arguments["contact_id"])
        if "company_id" in arguments:
            qs = qs.filter(company_id=arguments["company_id"])
        if "deal_id" in arguments:
            qs = qs.filter(deal_id=arguments["deal_id"])
        qs = qs[: int(arguments.get("limit", 20))]
        return _ok([
            {
                "id": a.pk, "type": a.activity_type, "subject": a.subject or "",
                "body": (a.body or "")[:500], "status": a.status or "",
                "direction": a.direction or "", "created_at": a.created_at,
                "contact": f"{a.contact.first_name} {a.contact.last_name}".strip() if a.contact_id else "",
            }
            for a in qs
        ])

    if name == "create_activity":
        a = Activity(
            activity_type=arguments.get("activity_type", "note"),
            subject=arguments.get("subject", ""),
            body=arguments.get("body", ""),
            status=arguments.get("status", "completed"),
            direction=arguments.get("direction", "outbound"),
        )
        if "contact_id" in arguments:
            a.contact_id = arguments["contact_id"]
        if "company_id" in arguments:
            a.company_id = arguments["company_id"]
        if "deal_id" in arguments:
            a.deal_id = arguments["deal_id"]
        a.save()
        return _ok({"created": True, "activity_id": a.pk})

    return _err(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# MCP server — tool registration
# ---------------------------------------------------------------------------

@mcp_server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_contacts",
            description="Search CRM contacts by name, email, or company.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_contact",
            description="Full contact record with recent activities, deals, and pain signals.",
            inputSchema={
                "type": "object",
                "properties": {"contact_id": {"type": "integer"}},
                "required": ["contact_id"],
            },
        ),
        types.Tool(
            name="update_contact",
            description="Save enriched fields (job_title, company, bio, notes, status) back to the CRM.",
            inputSchema={
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
        ),
        types.Tool(
            name="search_companies",
            description="Search CRM companies by name or industry.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_company",
            description="Full company record with contacts, deals, pain signals, and linked signals.",
            inputSchema={
                "type": "object",
                "properties": {"company_id": {"type": "integer"}},
                "required": ["company_id"],
            },
        ),
        types.Tool(
            name="update_company",
            description="Update company fields: description, industry, ICP score/tier, notes.",
            inputSchema={
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
        ),
        types.Tool(
            name="fetch_url",
            description="Fetch a web page and return plain text (HTML stripped). Use to read a signal URL or LinkedIn profile before analysing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "max_chars": {"type": "integer", "default": 25000},
                },
                "required": ["url"],
            },
        ),
        types.Tool(
            name="create_signal",
            description="Save a new market signal after you have analysed a URL or article.",
            inputSchema={
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
        ),
        types.Tool(
            name="update_signal",
            description="Update an existing signal's fields or status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "signal_id": {"type": "integer"},
                    "headline": {"type": "string"},
                    "summary": {"type": "string"},
                    "relevance": {"type": "string", "enum": ["high", "medium", "low"]},
                    "potential_action": {"type": "string"},
                    "status": {"type": "string", "enum": ["logged", "actioned", "archived"]},
                    "competitors": {"type": "string"},
                    "competitors_notes": {"type": "string"},
                },
                "required": ["signal_id"],
            },
        ),
        types.Tool(
            name="get_signals",
            description="List recent signals, optionally filtered by relevance or status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "relevance": {"type": "string"},
                    "status": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        ),
        types.Tool(
            name="get_pain_signals",
            description="Get pain signals for a company or across the whole CRM.",
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {"type": "integer"},
                    "limit": {"type": "integer", "default": 30},
                },
            },
        ),
        types.Tool(
            name="create_pain_signal",
            description="Log a new pain signal for a company or contact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {"type": "integer"},
                    "contact_id": {"type": "integer"},
                    "description": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["description"],
            },
        ),
        types.Tool(
            name="get_deals",
            description="List deals filtered by stage, company, or contact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "stage": {"type": "string"},
                    "company_id": {"type": "integer"},
                    "contact_id": {"type": "integer"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        ),
        types.Tool(
            name="get_activities",
            description="List activities for a contact, company, or deal.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "integer"},
                    "company_id": {"type": "integer"},
                    "deal_id": {"type": "integer"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        ),
        types.Tool(
            name="create_activity",
            description="Log a new activity (call, email, meeting, note, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "integer"},
                    "company_id": {"type": "integer"},
                    "deal_id": {"type": "integer"},
                    "activity_type": {"type": "string",
                                      "enum": ["call", "email", "meeting", "task",
                                               "linkedin", "note", "demo", "proposal"]},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "completed"], "default": "completed"},
                    "direction": {"type": "string", "enum": ["inbound", "outbound"], "default": "outbound"},
                },
                "required": ["activity_type", "subject"],
            },
        ),
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    return await sync_to_async(_dispatch)(name, arguments)


# ---------------------------------------------------------------------------
# Starlette HTTP app (SSE + streamable POST endpoint)
# ---------------------------------------------------------------------------

def build_starlette_app():
    """
    Returns a Starlette ASGI app that serves the MCP server over HTTP.
    Mount this at /mcp/ in kikodo_crm/asgi.py.

    Clients may use:
      - /mcp/sse  — legacy SSE transport (Claude Desktop, Claude Code)
      - /mcp      — Streamable HTTP transport (Claude.ai remote MCP connector)
    """
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse as StarletteJSON
    from starlette.routing import Mount, Route

    sse = SseServerTransport("/mcp/messages/")

    def _bearer_token(headers_list):
        """Extract Bearer token from ASGI headers list, or None."""
        for key, value in headers_list:
            if key == b"authorization":
                auth = value.decode("latin1")
                if auth.lower().startswith("bearer "):
                    return auth[7:].strip()
        return None

    def _validate_bearer(request):
        from .mcp_oauth import is_valid_token
        token = _bearer_token(list(request.headers.raw))
        if token and not is_valid_token(token):
            return StarletteJSON({"error": "unauthorized"}, status_code=401)
        return None

    async def handle_sse(request):
        auth_error = _validate_bearer(request)
        if auth_error:
            return auth_error
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0], streams[1], mcp_server.create_initialization_options()
            )

    async def handle_streamable(scope, receive, send):
        """Streamable HTTP transport — used by Claude.ai remote MCP connector.

        Creates a per-request task group and transport rather than relying on
        a shared session manager whose lifespan is tied to the ASGI startup
        event (which Django may consume before requests arrive).
        """
        import anyio
        from mcp.server.streamable_http import StreamableHTTPServerTransport

        from .mcp_oauth import is_valid_token
        token = _bearer_token(scope.get("headers", []))
        if token and not is_valid_token(token):
            await StarletteJSON({"error": "unauthorized"}, status_code=401)(scope, receive, send)
            return

        transport = StreamableHTTPServerTransport(
            mcp_session_id=None, is_json_response_enabled=False
        )

        async def _run_server(*, task_status=anyio.TASK_STATUS_IGNORED):
            async with transport.connect() as (read_stream, write_stream):
                task_status.started()
                await mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server.create_initialization_options(),
                    stateless=True,
                )

        async with anyio.create_task_group() as tg:
            await tg.start(_run_server)
            await transport.handle_request(scope, receive, send)
            await transport.terminate()
            tg.cancel_scope.cancel()

    return Starlette(routes=[
        Route("/mcp/sse", endpoint=handle_sse),
        Mount("/mcp/messages/", app=sse.handle_post_message),
        Mount("/mcp", app=handle_streamable),
    ])
