"""天气 Agent 流程。

负责查询目的地天气预报：
1. 从请求提取目的地和日期参数
2. 调用地图天气工具
3. 确定性转换为 WeatherInfo 列表

图结构位置：
- 与策略、POI、路线组合流程并行/顺序协作
- 输出 weather 到状态
- 连接到 final_planning
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from app.config import get_logger
from app.ai.models.graph_models import TripState
from app.ai.models import WeatherInfo
from app.ai.utils import parse_int
from app.services.amap import WeatherResponse
from app.ai.mcp.client import get_tool, invoke_tool_with_debug

logger = get_logger("WeatherService")
WEATHER_TOOL_NAME = "maps_weather"
MAX_WEATHER_TOTAL = 10


def _trip_days(request: dict[str, Any]) -> int:
    """计算出行天数"""
    days = int(request.get("days", 0) or 0)
    if days > 0:
        return days

    start_date = request.get("start_date")
    end_date = request.get("end_date")
    try:
        start = datetime.strptime(str(start_date), "%Y-%m-%d").date()
        end = datetime.strptime(str(end_date), "%Y-%m-%d").date()
        return max(1, (end - start).days + 1)
    except (TypeError, ValueError):
        return 1


async def _collect_mcp_result(
    *,
    tool_name: str,
    request: dict[str, Any],
) -> WeatherResponse:
    """调用天气 MCP 工具，返回结构化响应."""
    tool = get_tool(tool_name)
    if tool is None:
        raise RuntimeError(f"未找到天气工具: {tool_name}")

    destination = str(request.get("destination", "")).strip()
    tool_args = {
        "city": destination,
        "extensions": "all",
    }
    logger.info("开始调用天气工具，工具=%s，参数=%s", tool_name, tool_args)

    # 统一走 MCP 结果解包逻辑，兼容 ToolResult content blocks。
    result = await invoke_tool_with_debug(
        tool_name=tool_name,
        tool_args=tool_args,
        log=logger,
        context=f"weather:{destination}",
    )
    if isinstance(result, WeatherResponse):
        return result
    if isinstance(result, dict):
        return WeatherResponse.model_validate(result)
    raise RuntimeError(f"天气工具返回类型错误: {type(result)}")


def _build_weather_suggestion(day_weather: str, night_weather: str, day_temp: int, night_temp: int) -> str:
    """根据天气状况生成出行建议"""
    weather_text = f"{day_weather} {night_weather}"
    notes: list[str] = []
    if any(token in weather_text for token in ["雨", "雪", "雷"]):
        notes.append("建议携带雨具")
    if any(token in weather_text for token in ["晴", "多云"]):
        notes.append("适合安排户外行程")
    if day_temp >= 30:
        notes.append("注意防晒补水")
    elif night_temp <= 8:
        notes.append("早晚温差较大，注意保暖")
    return "，".join(notes[:2])


def _format_weather_response(weather: WeatherResponse, *, limit: int) -> list[dict[str, Any]]:
    """将 WeatherResponse 稳定转换为标准 WeatherInfo 列表。"""
    items: list[dict[str, Any]] = []

    for forecast in weather.forecasts[:limit]:
        day_temp = parse_int(forecast.day_temp)
        night_temp = parse_int(forecast.night_temp)
        item = WeatherInfo(
            date=forecast.date or weather.reporttime.split(" ")[0] if weather.reporttime else "",
            day_weather=forecast.day_weather or weather.weather or "未知",
            night_weather=forecast.night_weather or forecast.day_weather or weather.weather or "未知",
            day_temp=day_temp,
            night_temp=night_temp,
            wind_direction=forecast.wind_direction or weather.winddirection or "",
            wind_power=forecast.wind_power or weather.windpower or "",
            suggestion=_build_weather_suggestion(
                forecast.day_weather or weather.weather or "",
                forecast.night_weather or forecast.day_weather or weather.weather or "",
                day_temp,
                night_temp,
            ),
        )
        items.append(item.model_dump())

    if items:
        return items[:limit]

    current_temp = parse_int(weather.temperature)
    fallback = WeatherInfo(
        date=weather.reporttime.split(" ")[0] if weather.reporttime else "",
        day_weather=weather.weather or "未知",
        night_weather=weather.weather or "未知",
        day_temp=current_temp,
        night_temp=current_temp,
        wind_direction=weather.winddirection or "",
        wind_power=weather.windpower or "",
        suggestion=_build_weather_suggestion(weather.weather or "", weather.weather or "", current_temp, current_temp),
    )
    return [fallback.model_dump()] if limit > 0 else []


async def weather_node(state: TripState) -> Dict[str, Any]:
    """天气 Agent 主流程."""
    request = state["request"]
    days = _trip_days(request)
    select_limit = min(MAX_WEATHER_TOTAL, days)

    logger.info(
        "开始获取天气，目的地=%s，需要天数=%s，工具=%s",
        request.get("destination", ""),
        days,
        WEATHER_TOOL_NAME,
    )

    # 1) 调用天气 MCP 工具，获取结构化响应
    weather_response = await _collect_mcp_result(
        tool_name=WEATHER_TOOL_NAME,
        request=request,
    )
    logger.info("天气工具调用完成，forecasts=%s", len(weather_response.forecasts))

    # 2) 直接将结构化天气结果转换为标准 WeatherInfo 列表
    weather = _format_weather_response(weather_response, limit=select_limit)

    logger.info(
        "天气处理完成，最终数量=%s",
        len(weather),
    )

    return {
        "weather": weather,
        "streaming_updates": f"\n天气完成: {len(weather)}天",
        "completed_agents": ["weather"],
    }
