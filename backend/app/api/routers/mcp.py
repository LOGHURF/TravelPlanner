"""MCP introspection APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ai.mcp.client import get_tools, get_tool, invoke_tool_raw

router = APIRouter()


class RawToolInvokeRequest(BaseModel):
    args: dict[str, Any] = Field(default_factory=dict, description="Raw MCP tool arguments")


def _tool_to_dict(tool: Any) -> dict[str, Any]:
    schema: dict[str, Any] = {}
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is not None:
        try:
            schema = args_schema.model_json_schema()
        except Exception:
            schema = {}

    return {
        "name": getattr(tool, "name", ""),
        "description": getattr(tool, "description", "") or "",
        "input_schema": schema,
        "required": schema.get("required", []) if isinstance(schema, dict) else [],
        "properties": schema.get("properties", {}) if isinstance(schema, dict) else {},
    }


@router.get("/tools")
async def list_mcp_tools() -> dict[str, Any]:
    """Return all MCP tools and their input schemas."""
    try:
        tools = get_tools()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    data = [_tool_to_dict(tool) for tool in tools]
    return {"count": len(data), "tools": data}


@router.get("/tools/{tool_name}")
async def get_mcp_tool(tool_name: str) -> dict[str, Any]:
    """Return one MCP tool schema by tool name."""
    try:
        tool = get_tool(tool_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if tool is None:
        raise HTTPException(status_code=404, detail=f"tool not found: {tool_name}")
    return _tool_to_dict(tool)


@router.post("/tools/{tool_name}/invoke-raw")
async def invoke_mcp_tool_raw(
    tool_name: str,
    payload: RawToolInvokeRequest,
) -> dict[str, Any]:
    """Invoke an MCP tool directly and return the untouched CallToolResult payload."""
    try:
        tool = get_tool(tool_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if tool is None:
        raise HTTPException(status_code=404, detail=f"tool not found: {tool_name}")

    try:
        return await invoke_tool_raw(
            tool_name=tool_name,
            tool_args=payload.args,
            context=f"api:{tool_name}",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
