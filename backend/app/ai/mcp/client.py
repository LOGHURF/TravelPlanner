"""Global MCP tool registry - MCP 客户端管理。

该模块负责：
1. 初始化 MCP 工具连接到高德地图 MCP 服务器
2. 维护全局工具缓存
3. 提供工具查询和调用接口

图结构位置：
- 在应用启动时初始化（lifespan 中调用）
- 被各个 Agent 节点调用以执行 MCP 工具
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import create_session
from langchain_core.tools import BaseTool

from app.config import settings, get_logger, BASE_DIR

logger = get_logger("MCPClient")

# ═══════════════════════════════════════════════════════════════════════════════
# 全局状态
# ═══════════════════════════════════════════════════════════════════════════════

_mcp_tools: List[BaseTool] = []
_tools_by_name: Dict[str, BaseTool] = {}
_initialized = False


# ═══════════════════════════════════════════════════════════════════════════════
# 连接配置
# ═══════════════════════════════════════════════════════════════════════════════


def _get_amap_connection() -> dict[str, Any]:
    """构建高德地图 MCP 服务器的连接配置。

    使用 stdio 传输模式，通过子进程启动 MCP 服务器。

    Returns:
        MCP 连接配置字典

    Raises:
        RuntimeError: 当 AMAP API Key 未设置时
    """
    if not settings.amap_key:
        raise RuntimeError("AMAP_MAPS_API_KEY 环境变量未设置")

    return {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-m", "app.ai.mcp.amap_stdio_server"],
        "cwd": str(BASE_DIR),
        "env": {
            **os.environ,
            "AMAP_MAPS_API_KEY": settings.amap_key,
            "AMAP_API_KEY": settings.amap_key,
            "FASTMCP_SHOW_SERVER_BANNER": "false",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 初始化
# ═══════════════════════════════════════════════════════════════════════════════


async def initialize_mcp_tools():
    """Initialize MCP tools once at app startup.

    该函数在应用启动时调用一次，建立与 MCP 服务器的连接并获取可用工具列表。

    Raises:
        RuntimeError: 当 MCP 服务器返回空工具列表时
    """
    global _mcp_tools, _tools_by_name, _initialized

    if _initialized:
        return

    logger.info("initializing mcp tools")

    client = MultiServerMCPClient(
        {
            "amap": _get_amap_connection()
        }
    )

    _mcp_tools = await client.get_tools()

    if not _mcp_tools:
        raise RuntimeError("MCP 服务器返回空工具列表")

    _tools_by_name = {tool.name: tool for tool in _mcp_tools}
    _initialized = True

    logger.info("mcp tools loaded count=%s", len(_mcp_tools))
    for tool in _mcp_tools:
        logger.info("tool=%s", tool.name)


# ═══════════════════════════════════════════════════════════════════════════════
# 工具查询
# ═══════════════════════════════════════════════════════════════════════════════


def get_tools() -> List[BaseTool]:
    """获取所有已注册的 MCP 工具。

    Returns:
        BaseTool 列表

    Raises:
        RuntimeError: 当 MCP 工具未初始化时
    """
    if not _initialized:
        raise RuntimeError("MCP 工具尚未初始化，请先调用 initialize_mcp_tools()")
    return _mcp_tools


def get_tool(name: str) -> Optional[BaseTool]:
    """根据名称获取指定的 MCP 工具。

    Args:
        name: 工具名称（如 "maps_text_search"、"maps_weather"）

    Returns:
        找到的 BaseTool 实例，或 None
    """
    if not _initialized:
        raise RuntimeError("MCP 工具尚未初始化")
    return _tools_by_name.get(name)


def get_tool_schema(tool: BaseTool) -> dict[str, Any]:
    """读取工具输入 schema。

    Args:
        tool: MCP 工具实例

    Returns:
        工具的 JSON schema 字典，失败时返回空字典
    """
    schema: dict[str, Any] = {}
    args_schema = getattr(tool, "args_schema", None)
    if isinstance(args_schema, dict):
        return args_schema

    if args_schema is not None:
        try:
            schema = args_schema.model_json_schema()
        except Exception:
            schema = {}

    if schema:
        return schema

    tool_call_schema = getattr(tool, "tool_call_schema", None)
    if tool_call_schema is not None:
        try:
            schema = tool_call_schema.model_json_schema()
        except Exception:
            schema = {}
    return schema


def _format_poi2_query(params: dict[str, Any]) -> str:
    """仅用于日志展示：格式化 POI 查询参数。

    Args:
        params: 查询参数字典

    Returns:
        URL 编码后的参数字符串
    """
    normalized: dict[str, str] = {}
    for key, value in params.items():
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            normalized[key] = str(value).lower()
        else:
            normalized[key] = str(value)
    return urlencode(normalized)


# ═══════════════════════════════════════════════════════════════════════════════
# 工具调用
# ═══════════════════════════════════════════════════════════════════════════════


async def invoke_tool_with_debug(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    log: Any | None = None,
    context: str = "",
) -> Any:
    """调用 MCP 工具，并输出详细的调试日志。

    该函数执行以下操作：
    1. 获取工具实例
    2. 记录调用参数和 schema 信息
    3. 调用工具
    4. 解析返回结果（处理 MCP ToolResult 格式）
    5. 记录返回结果类型和结构

    Args:
        tool_name: 工具名称
        tool_args: 工具参数字典
        log: 可选的日志记录器
        context: 调用上下文标识（用于日志）

    Returns:
        工具返回结果

    Raises:
        RuntimeError: 当未找到指定工具时
    """
    tool = get_tool(tool_name)
    if tool is None:
        raise RuntimeError(f"未找到 MCP 工具: {tool_name}")

    active_logger = log or logger
    schema = get_tool_schema(tool)
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    required = schema.get("required", []) if isinstance(schema, dict) else []

    provided_keys = list(tool_args.keys())
    schema_keys = list(properties.keys())
    unknown_keys = [key for key in provided_keys if schema_keys and key not in properties]

    active_logger.info(
        "mcp invoke context=%s tool=%s provided_keys=%s required=%s schema_keys=%s unknown_keys=%s args=%s",
        context or "-",
        tool_name,
        provided_keys,
        required,
        schema_keys,
        unknown_keys,
        tool_args,
    )

    if tool_name == "maps_text_search":
        active_logger.info(
            "mcp invoke context=%s tool=%s query_inferred=%s",
            context or "-",
            tool_name,
            _format_poi2_query(tool_args),
        )

    raw = await tool.ainvoke(tool_args)

    # 解析 MCP ToolResult 格式: [{type: "text", text: "...", id: "..."}]
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict) and "text" in first:
            text_content = first.get("text", "")
            # 尝试解析 JSON 字符串
            if isinstance(text_content, str):
                import json
                try:
                    parsed = json.loads(text_content)
                    active_logger.info(
                        "mcp result parsed JSON from text, keys=%s",
                        list(parsed.keys())[:10] if isinstance(parsed, dict) else f"list len={len(parsed)}",
                    )
                    raw = parsed
                except json.JSONDecodeError:
                    # 不是 JSON，保持原样
                    pass

    # 处理 Pydantic 模型或字典
    if hasattr(raw, "model_dump"):
        raw_result = raw.model_dump()
    else:
        raw_result = raw

    # 记录返回结果的类型信息
    if hasattr(raw, "__class__"):
        active_logger.info(
            "mcp result context=%s tool=%s result_class=%s",
            context or "-",
            tool_name,
            raw.__class__.__name__,
        )

    if isinstance(raw_result, list):
        result_type = "list"
        result_size = len(raw_result)
        result_keys: list[str] = []
    elif isinstance(raw_result, dict):
        result_type = "dict"
        result_size = len(raw_result)
        result_keys = list(raw_result.keys())[:12]
    else:
        result_type = type(raw_result).__name__
        result_size = 0
        result_keys = []

    active_logger.info(
        "mcp result context=%s tool=%s result_type=%s result_size=%s result_keys=%s",
        context or "-",
        tool_name,
        result_type,
        result_size,
        result_keys,
    )

    return raw_result


async def invoke_tool_raw(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    log: Any | None = None,
    context: str = "",
) -> dict[str, Any]:
    """Invoke MCP tool via raw session and return the full CallToolResult dump.

    与 invoke_tool_with_debug 不同，该函数返回完整的 MCP 协议原生结果。

    Args:
        tool_name: 工具名称
        tool_args: 工具参数
        log: 可选的日志记录器
        context: 调用上下文标识

    Returns:
        完整的 CallToolResult 模型 dump
    """
    active_logger = log or logger

    active_logger.info(
        "mcp raw invoke context=%s tool=%s args=%s",
        context or "-",
        tool_name,
        tool_args,
    )

    async with create_session(_get_amap_connection()) as session:
        await session.initialize()
        raw_result = await session.call_tool(tool_name, tool_args)

    dumped = (
        raw_result.model_dump(mode="json", by_alias=True, exclude_none=False)
        if hasattr(raw_result, "model_dump")
        else raw_result
    )

    active_logger.info(
        "mcp raw result context=%s tool=%s keys=%s",
        context or "-",
        tool_name,
        list(dumped.keys()) if isinstance(dumped, dict) else [],
    )

    return dumped


# ═══════════════════════════════════════════════════════════════════════════════
# 工具筛选
# ═══════════════════════════════════════════════════════════════════════════════


def get_tools_by_keywords(keywords: List[str]) -> List[BaseTool]:
    """根据关键词筛选工具。

    Args:
        keywords: 关键词列表

    Returns:
        匹配的工具列表
    """
    if not _initialized:
        raise RuntimeError("MCP 工具尚未初始化")

    matched = []
    for tool in _mcp_tools:
        for keyword in keywords:
            if keyword.lower() in tool.name.lower():
                matched.append(tool)
                break
    return matched


def get_search_tools() -> List[BaseTool]:
    """获取搜索类工具（POI 搜索、周边搜索）。"""
    return get_tools_by_keywords(["maps_text_search", "maps_nearby_search"])


def get_route_tools() -> List[BaseTool]:
    """获取路径规划工具（驾车、步行、公交）。"""
    return get_tools_by_keywords(["direction", "route", "driving", "walking", "transit"])


def get_weather_tool() -> Optional[BaseTool]:
    """获取天气查询工具。"""
    direct = get_tool("maps_weather")
    if direct:
        return direct
    weather_tools = get_tools_by_keywords(["weather", "forecast"])
    return weather_tools[0] if weather_tools else None


def get_geo_tools() -> List[BaseTool]:
    """获取地理编码工具。"""
    return get_tools_by_keywords(["geo", "regeo"])


def get_poi_detail_tools() -> List[BaseTool]:
    """获取 POI 详情工具。"""
    return get_tools_by_keywords(["detail", "poi"])