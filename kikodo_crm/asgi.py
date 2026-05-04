"""
ASGI config for kikodo_crm.

Routes:
  /mcp/*  → MCP Starlette app (SSE + Streamable HTTP transports)
  /*      → Django application

Run with:
  uvicorn kikodo_crm.asgi:application --reload --port 8081

Claude Desktop config (~/.claude/claude_desktop_config.json):
  {
    "mcpServers": {
      "kikodo-crm": {
        "type": "sse",
        "url": "http://localhost:8081/mcp/sse"
      }
    }
  }

Claude.ai remote MCP connector URL:
  https://<your-ngrok-host>/mcp
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kikodo_crm.settings")

_django_app = get_asgi_application()

_mcp_app = None


def _get_mcp_app():
    global _mcp_app
    if _mcp_app is None:
        from crm.mcp_app import build_starlette_app
        _mcp_app = build_starlette_app()
    return _mcp_app


async def application(scope, receive, send):
    if scope.get("path", "").startswith("/mcp"):
        await _get_mcp_app()(scope, receive, send)
    else:
        await _django_app(scope, receive, send)
