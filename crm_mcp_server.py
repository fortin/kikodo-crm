#!/usr/bin/env python
"""
Kikodo CRM — MCP stdio entry point.

Runs the MCP server over stdio for use with Claude Code or CLI clients.
For HTTP/SSE (Claude Desktop), use the ASGI app instead:
  uvicorn kikodo_crm.asgi:application --port 8081

Usage:
  python crm_mcp_server.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kikodo_crm.settings")

import django
django.setup()

from mcp.server.stdio import stdio_server
from crm.mcp_app import mcp_server


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream, write_stream, mcp_server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
