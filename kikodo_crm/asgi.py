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
_static_app = None


def _get_mcp_app():
    global _mcp_app
    if _mcp_app is None:
        from crm.mcp_app import build_starlette_app
        _mcp_app = build_starlette_app()
    return _mcp_app


def _get_static_app():
    """
    Serve static files with an ASGI-native handler.

    This avoids Django/WhiteNoise returning a sync file iterator (FileResponse),
    which emits a warning when served in an async context under uvicorn.
    """
    global _static_app
    if _static_app is None:
        from django.conf import settings
        from starlette.staticfiles import StaticFiles

        static_dir = None
        static_dirs = [str(p) for p in getattr(settings, "STATICFILES_DIRS", [])]
        static_root = str(getattr(settings, "STATIC_ROOT", "") or "").strip() or None

        if static_root and os.path.isdir(static_root):
            static_dir = static_root
        else:
            for d in static_dirs:
                if d and os.path.isdir(d):
                    static_dir = d
                    break

        # If no directory exists yet (fresh repo), still initialize so we return 404s cleanly.
        _static_app = StaticFiles(directory=static_dir or ".", check_dir=False)
    return _static_app


async def application(scope, receive, send):
    if scope.get("path", "").startswith("/mcp"):
        await _get_mcp_app()(scope, receive, send)
    elif scope.get("path", "").startswith("/static/"):
        # When calling Starlette's StaticFiles directly (not inside a Starlette app),
        # exceptions like HTTPException won't be converted into responses automatically.
        try:
            # StaticFiles expects to be *mounted* at /static and receive the remaining subpath.
            # Since we're dispatching manually, adjust the scope to mimic mounting behavior.
            static_scope = dict(scope)
            path = scope.get("path", "")
            static_scope["root_path"] = (scope.get("root_path", "") or "") + "/static"
            static_scope["path"] = path[len("/static") :] or "/"
            await _get_static_app()(static_scope, receive, send)
        except Exception as e:
            from starlette.responses import PlainTextResponse

            status_code = getattr(e, "status_code", None) or 500
            if status_code == 404:
                await PlainTextResponse("Not Found", status_code=404)(scope, receive, send)
            else:
                await PlainTextResponse("Static file error", status_code=500)(scope, receive, send)
    else:
        await _django_app(scope, receive, send)
