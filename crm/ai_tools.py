"""Shared CRM tool execution for the AI chat loop and MCP server."""


def execute_tool(name: str, arguments: dict | None = None) -> str:
    """Run a named CRM tool and return the JSON result text."""
    from crm.mcp_app import _dispatch

    result = _dispatch(name, arguments or {})
    return result[0].text if result else "{}"
