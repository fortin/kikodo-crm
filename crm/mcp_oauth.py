"""
Minimal OAuth 2.1 server for MCP HTTP endpoints.

Claude.ai requires OAuth before connecting to a remote MCP server.
This implements just enough of the spec to complete the handshake:
  - RFC 9728  /.well-known/oauth-protected-resource
  - RFC 8414  /.well-known/oauth-authorization-server
  - RFC 7591  /oauth/register  (Dynamic Client Registration)
              /oauth/authorize (PKCE authorization code flow)
              /oauth/token

State is kept in module-level dicts — fine for a single-worker dev server.
Issued tokens are 30-day bearer tokens stored in memory; restart clears them.
"""

import base64
import hashlib
import json
import logging
import secrets

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger("crm.mcp")

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

_clients: dict[str, dict] = {}   # client_id → {client_secret, redirect_uris}
_codes:   dict[str, dict] = {}   # code      → {client_id, redirect_uri, code_challenge}
_tokens:  set[str]        = set() # valid access tokens


def is_valid_token(token: str) -> bool:
    return token in _tokens


def _base_url(request) -> str:
    return f"{request.scheme}://{request.get_host()}"


# ---------------------------------------------------------------------------
# Discovery endpoints
# ---------------------------------------------------------------------------

def oauth_protected_resource(request):
    """RFC 9728 — tells Claude.ai which auth server to use."""
    base = _base_url(request)
    # Claude.ai uses streamable HTTP and POSTs directly to this resource URL.
    mcp_resource = f"{base}/mcp"
    return JsonResponse({
        "resource": mcp_resource,
        "authorization_servers": [base],
    })


def oauth_authorization_server(request):
    """RFC 8414 — describes our OAuth server capabilities."""
    base = _base_url(request)
    return JsonResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint":         f"{base}/oauth/token",
        "registration_endpoint":  f"{base}/oauth/register",
        "response_types_supported":        ["code"],
        "grant_types_supported":           ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
    })


# ---------------------------------------------------------------------------
# Dynamic Client Registration  (RFC 7591)
# ---------------------------------------------------------------------------

@csrf_exempt
def oauth_register(request):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}
    client_id     = secrets.token_urlsafe(16)
    client_secret = secrets.token_urlsafe(32)
    _clients[client_id] = {
        "client_secret": client_secret,
        "redirect_uris": data.get("redirect_uris", []),
    }
    logger.info("MCP OAuth: registered client %s", client_id)
    return JsonResponse({
        "client_id":     client_id,
        "client_secret": client_secret,
        "redirect_uris": data.get("redirect_uris", []),
    }, status=201)


# ---------------------------------------------------------------------------
# Authorization endpoint
# ---------------------------------------------------------------------------

@login_required
def oauth_authorize(request):
    """
    GET  → show approval page (user must be logged into Django admin first)
    POST → issue authorization code and redirect back to Claude.ai
    """
    client_id     = request.GET.get("client_id", "")
    redirect_uri  = request.GET.get("redirect_uri", "")
    state         = request.GET.get("state", "")
    code_challenge = request.GET.get("code_challenge", "")

    if client_id not in _clients:
        return HttpResponse("Unknown client.", status=400)

    if request.method == "POST":
        code = secrets.token_urlsafe(32)
        _codes[code] = {
            "client_id":      client_id,
            "redirect_uri":   redirect_uri,
            "code_challenge": code_challenge,
        }
        sep = "&" if "?" in redirect_uri else "?"
        return redirect(f"{redirect_uri}{sep}code={code}&state={escape(state)}")

    # GET — render approval page
    csrf = get_token(request)
    html = f"""<!doctype html>
<html>
<head>
  <title>Authorise Claude — Kikodo CRM</title>
  <style>
    body {{ font-family: system-ui; max-width: 480px; margin: 80px auto; padding: 0 20px; }}
    h2   {{ margin-bottom: 8px; }}
    p    {{ color: #555; margin-bottom: 24px; }}
    .btn {{ background: #7c5cbf; color: white; border: none;
            padding: 10px 24px; border-radius: 6px; cursor: pointer; font-size: 15px; }}
    .btn:hover {{ background: #6b4eab; }}
  </style>
</head>
<body>
  <h2>Authorise Claude to access Kikodo CRM?</h2>
  <p>Claude.ai is requesting access to your CRM data and tools via MCP.</p>
  <form method="post">
    <input type="hidden" name="csrfmiddlewaretoken" value="{csrf}">
    <button class="btn" type="submit">Allow access</button>
  </form>
</body>
</html>"""
    return HttpResponse(html)


# ---------------------------------------------------------------------------
# Token endpoint
# ---------------------------------------------------------------------------

@csrf_exempt
def oauth_token(request):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)

    grant_type    = request.POST.get("grant_type", "")
    code          = request.POST.get("code", "")
    client_id     = request.POST.get("client_id", "")
    code_verifier = request.POST.get("code_verifier", "")

    if grant_type != "authorization_code":
        return JsonResponse({"error": "unsupported_grant_type"}, status=400)

    code_data = _codes.pop(code, None)
    if not code_data or code_data["client_id"] != client_id:
        return JsonResponse({"error": "invalid_grant"}, status=400)

    # Verify PKCE (required by OAuth 2.1)
    if code_data.get("code_challenge"):
        digest    = hashlib.sha256(code_verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        if challenge != code_data["code_challenge"]:
            return JsonResponse({"error": "invalid_grant"}, status=400)

    token = secrets.token_urlsafe(32)
    _tokens.add(token)
    logger.info("MCP OAuth: issued token for client %s", client_id)
    return JsonResponse({
        "access_token": token,
        "token_type":   "bearer",
        "expires_in":   86400 * 30,   # 30 days
    })
