"""Local MCP server smoke tests."""

from __future__ import annotations

import asyncio

from app.ai.mcp.amap_stdio_server import mcp


def test_local_mcp_tools_are_available() -> None:
    async def _run() -> set[str]:
        tools = await mcp.list_tools()
        return {tool.name for tool in tools}

    tool_names = asyncio.run(_run())
    assert "maps_nearby_search" in tool_names
    assert "maps_text_search" in tool_names
    assert "maps_weather" in tool_names
    assert "maps_transit_integrated" in tool_names
