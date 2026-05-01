"""FinalPlanning 节点：生成精简后的最终行程结构。

负责生成最终 TripPlan 结构：
1. 分配每日景点/餐厅/酒店到具体日期
2. 生成每日时间线和费用估算
3. LLM 生成行程总结和建议

图结构位置：
- 接收 transport_node 的输出
- 输出完整 TripPlan 到状态
- 连接到最终输出/前端展示
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.config import get_logger
from app.ai.models.graph_models import TripState
from app.ai.utils import (
    build_daily_timeline,
    distribute_attractions,
    distribute_hotels,
    distribute_restaurants,
    invoke_llm_json_async,
    sum_route_segment_cost,
)

logger = get_logger("FinalPlanning")


def parse_date(date_str: str) -> datetime:
    """解析日期字符串"""
    if isinstance(date_str, datetime):
        return date_str
    try:
        return datetime.strptime(str(date_str), "%Y-%m-%d")
    except (TypeError, ValueError):
        return datetime.now()


def format_date(dt: datetime) -> str:
    """格式化日期为字符串"""
    return dt.strftime("%Y-%m-%d")


def get_day_of_week(dt: datetime) -> str:
    """获取星期几的中文表示"""
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return weekdays[dt.weekday()]


def estimate_daily_meal_cost(restaurants: List[Dict[str, Any]]) -> float:
    """估算每日餐饮费用"""
    if not restaurants:
        return 180.0
    avg = sum(float(item.get("estimated_cost", 0) or 0) for item in restaurants) / max(len(restaurants), 1)
    if avg <= 0:
        avg = 80.0
    return round(avg * 2 + 30.0, 2)


def _normalize_attraction(item: dict[str, Any]) -> dict[str, Any]:
    """标准化景点数据"""
    return {
        "name": item.get("name", ""),
        "address": item.get("address", ""),
        "location": item.get("location"),
        "keytag": item.get("keytag", ""),
        "type": item.get("type", ""),
        "photos": item.get("photos", []),
        "tel": item.get("tel", ""),
        "open_time2": item.get("open_time2", ""),
        "rating": item.get("rating", 0),
        "visit_duration": item.get("visit_duration", "2小时"),
        "category": item.get("category", "") or item.get("type", ""),
        "description": item.get("description", ""),
        "ticket_price": item.get("ticket_price", 0),
        "photo": item.get("photo", "") or ((item.get("photos") or [""])[0]),
    }


def _normalize_hotel(item: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """标准化酒店数据"""
    if not item:
        return None
    return {
        "name": item.get("name", ""),
        "address": item.get("address", ""),
        "location": item.get("location"),
        "keytag": item.get("keytag", ""),
        "type": item.get("type", ""),
        "photos": item.get("photos", []),
        "tel": item.get("tel", ""),
        "open_time2": item.get("open_time2", ""),
        "rating": item.get("rating", 0),
        "hotel_level": item.get("hotel_level", ""),
        "price_per_night": item.get("price_per_night", 0),
        "photo": item.get("photo", "") or ((item.get("photos") or [""])[0]),
        "image_url": item.get("image_url", "") or item.get("photo", ""),
        "description": item.get("description", ""),
    }


def _normalize_meal(item: dict[str, Any]) -> dict[str, Any]:
    """标准化餐饮数据"""
    return {
        "name": item.get("name", ""),
        "type": item.get("meal_type", item.get("type", "lunch")),
        "meal_type": item.get("meal_type", item.get("type", "lunch")),
        "poi_type": item.get("type", ""),
        "address": item.get("address"),
        "location": item.get("location"),
        "description": item.get("description"),
        "keytag": item.get("keytag", ""),
        "photos": item.get("photos", []),
        "tel": item.get("tel", ""),
        "open_time2": item.get("open_time2", ""),
        "rating": item.get("rating", 0),
        "estimated_cost": item.get("estimated_cost", 0),
        "price_per_person": item.get("price_per_person", 0),
        "cuisine_type": item.get("cuisine_type", ""),
        "is_recommended": item.get("is_recommended", False),
        "photo": item.get("photo", "") or ((item.get("photos") or [""])[0]),
    }


def create_daily_plan(
    *,
    date: datetime,
    day_index: int,
    attractions: List[Dict[str, Any]],
    meals: List[Dict[str, Any]],
    route_segments: List[Dict[str, Any]],
    hotel: Optional[Dict[str, Any]],
    weather: Optional[Dict[str, Any]],
    meal_cost: float,
    transport_cost: float,
    transport_mode: str,
    arrival_transport: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建单日行程计划"""
    weather_info = None
    if weather:
        weather_info = {
            "date": weather.get("date", format_date(date)),
            "day_weather": weather.get("day_weather", "晴"),
            "night_weather": weather.get("night_weather", "多云"),
            "day_temp": weather.get("day_temp", 25),
            "night_temp": weather.get("night_temp", 18),
            "wind_direction": weather.get("wind_direction", "东北"),
            "wind_power": weather.get("wind_power", "2级"),
            "suggestion": weather.get("suggestion", ""),
        }

    day_attractions = [_normalize_attraction(item) for item in attractions[:2]]
    day_meals = [_normalize_meal(item) for item in meals]
    hotel_info = _normalize_hotel(hotel)
    timeline = build_daily_timeline(hotel_info, day_attractions, day_meals)
    meal_budget = sum(float(item.get("estimated_cost", 0) or 0) for item in day_meals)
    if meal_budget <= 0:
        meal_budget = float(meal_cost)

    title = " / ".join(item.get("name", "") for item in day_attractions if item.get("name")) or f"第{day_index}天行程"

    return {
        "date": format_date(date),
        "day_index": day_index,
        "day_of_week": get_day_of_week(date),
        "description": title,
        "weather": weather_info,
        "weather_note": weather.get("suggestion", "") if weather else "",
        "accommodation": hotel_info.get("name", "") if hotel_info else "",
        "hotel": hotel_info,
        "arrival_transport": arrival_transport,
        "attractions": day_attractions,
        "meals": day_meals,
        "route_segments": route_segments,
        "transportation": arrival_transport.get("summary", "") if arrival_transport else "",
        "transport_mode": transport_mode,
        "estimated_cost": {
            "attractions": sum(float(a.get("ticket_price", 0) or 0) for a in day_attractions),
            "meals": meal_budget,
            "transport": float(transport_cost),
            "hotel": float((hotel_info or {}).get("price_per_night", 0) or 0),
        },
        "timeline": timeline,
    }


def _build_summary_prompt(
    *,
    request: dict[str, Any],
    attractions: list[dict[str, Any]],
    hotels: list[dict[str, Any]],
    restaurants: list[dict[str, Any]],
    weather: list[dict[str, Any]],
    days: int,
) -> str:
    """构造行程总结提示词"""
    context = {
        "destination": request.get("destination", ""),
        "days": days,
        "companions": request.get("companions", "朋友"),
        "style_preferences": request.get("style_preferences", []),
        "hotel_level": request.get("hotel_level", "舒适型"),
        "selected_attractions": [a.get("name", "") for a in attractions[: days * 2]],
        "selected_hotels": [h.get("name", "") for h in hotels[: min(3, len(hotels))]],
        "restaurant_recommendations": [r.get("name", "") for r in restaurants[: min(days * 2, len(restaurants))]],
        "weather_brief": weather[: min(3, len(weather))],
    }
    return (
        "你是旅行行程总结智能体。请给出简洁、可执行、不过度铺陈的结果。"
        "只返回JSON对象，字段：\n"
        "1) overall_suggestions: string\n"
        "2) important_notes: string[]\n"
        "3) packing_tips: string[]\n"
        "4) narrative_plan: string\n"
        "   用2到4个自然段写简洁说明，不要写成长篇攻略。\n\n"
        f"上下文:\n{context}"
    )


def _build_fallback_narrative(*, destination: str, daily_plans: list[dict[str, Any]]) -> str:
    """无 LLM 时生成备选行程叙述"""
    lines: list[str] = [f"{destination}行程概览"]
    for daily in daily_plans:
        spots = [item.get("name", "") for item in (daily.get("attractions") or []) if item.get("name")]
        hotel_name = ((daily.get("hotel") or {}).get("name") or "").strip()
        summary = "、".join(spots[:2]) if spots else "自由安排"
        line = f"Day {daily.get('day_index', 1)}：{summary}"
        if hotel_name:
            line += f"，入住 {hotel_name}"
        lines.append(line)
    return "\n".join(lines).strip()


def resolve_trip_window(request: dict[str, Any]) -> tuple[datetime, datetime, int]:
    """解析行程日期窗口"""
    start_date_raw = request.get("start_date")
    end_date_raw = request.get("end_date")
    duration_raw = request.get("days", request.get("duration", 0))

    try:
        duration = max(1, int(duration_raw or 0))
    except (TypeError, ValueError):
        duration = 0

    start_date = None
    end_date = None

    if start_date_raw:
        try:
            start_date = datetime.strptime(str(start_date_raw), "%Y-%m-%d")
        except (TypeError, ValueError):
            start_date = None

    if end_date_raw:
        try:
            end_date = datetime.strptime(str(end_date_raw), "%Y-%m-%d")
        except (TypeError, ValueError):
            end_date = None

    if start_date and end_date:
        days = max(1, (end_date - start_date).days + 1)
        return start_date, end_date, days

    if duration <= 0:
        duration = 1

    if start_date and not end_date:
        end_date = start_date + timedelta(days=duration - 1)
        return start_date, end_date, duration

    base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = base_date + timedelta(days=duration - 1)
    return base_date, end_date, duration


async def final_planning_node(state: TripState) -> TripState:
    """FinalPlanning Agent 主流程"""
    request = state.get("request", {})
    destination = str(request.get("destination", ""))

    attractions = state.get("attractions", [])
    hotels = state.get("hotels", [])
    restaurants = state.get("restaurants", [])
    weather_list = state.get("weather", [])
    transport = state.get("transport") or {}

    start_date, end_date, days = resolve_trip_window(request)
    start_date_str = format_date(start_date)
    end_date_str = format_date(end_date)

    max_per_day = max(1, min(2, int(state.get("max_attractions_per_day", 2) or 2)))
    per_day_hotels = distribute_hotels(hotels, days, stay_span=2)
    weather_by_date = {str(item.get("date", "")): item for item in weather_list}
    per_day_attractions = distribute_attractions(attractions, days, max_per_day)
    per_day_meals = distribute_restaurants(restaurants, days)
    per_day_meal_cost = estimate_daily_meal_cost(restaurants)
    daily_routes = transport.get("daily_routes") or []
    transport_daily_plan = transport.get("daily_plan") or []
    total_transport_cost = float(transport.get("estimated_transport_cost", 0) or 0)
    transport_mode = str(transport.get("suggested_mode", "驾车"))
    arrival_transport = transport.get("inter_city")

    daily_plans: List[Dict[str, Any]] = []
    budget = {"hotel": 0.0, "attractions": 0.0, "meals": 0.0, "transport": 0.0}

    for idx in range(days):
        current_date = start_date + timedelta(days=idx)
        date_key = format_date(current_date)
        day_weather = weather_by_date.get(date_key)
        if day_weather is None and idx < len(weather_list):
            day_weather = weather_list[idx]

        transport_day = transport_daily_plan[idx] if idx < len(transport_daily_plan) else {}
        if isinstance(transport_day, dict):
            day_attractions = list(transport_day.get("attractions") or [])
            day_meals = list(transport_day.get("meals") or [])
            day_hotel = transport_day.get("hotel")
        else:
            day_attractions = []
            day_meals = []
            day_hotel = None
        if not day_attractions:
            day_attractions = per_day_attractions[idx] if idx < len(per_day_attractions) else []
        if not day_meals:
            day_meals = per_day_meals[idx] if idx < len(per_day_meals) else []
        route_segments = daily_routes[idx] if idx < len(daily_routes) else []
        if not day_hotel:
            day_hotel = per_day_hotels[idx] if idx < len(per_day_hotels) else None
        day_transport_cost = sum_route_segment_cost(route_segments)
        if day_transport_cost <= 0:
            day_transport_cost = total_transport_cost / days if days else 0.0

        daily = create_daily_plan(
            date=current_date,
            day_index=idx + 1,
            attractions=day_attractions,
            meals=day_meals,
            route_segments=route_segments,
            hotel=day_hotel,
            weather=day_weather,
            meal_cost=per_day_meal_cost,
            transport_cost=day_transport_cost,
            transport_mode=transport_mode,
            arrival_transport=arrival_transport if idx == 0 else None,
        )
        daily_plans.append(daily)

        costs = daily["estimated_cost"]
        budget["hotel"] += float(costs.get("hotel", 0) or 0)
        budget["attractions"] += float(costs.get("attractions", 0) or 0)
        budget["meals"] += float(costs.get("meals", 0) or 0)
        budget["transport"] += float(costs.get("transport", 0) or 0)

    estimated_total = sum(budget.values())
    total_budget = float(state.get("total_budget", 0) or 0)
    budget_range = {
        "low": round(estimated_total * 0.85, 2),
        "high": round(estimated_total * 1.15, 2),
    }
    used_hotels: list[dict[str, Any]] = []
    used_hotel_keys: set[tuple[str, str]] = set()
    for daily in daily_plans:
        hotel = daily.get("hotel")
        if not isinstance(hotel, dict):
            continue
        key = (str(hotel.get("name", "")).strip(), str(hotel.get("address", "")).strip())
        if key == ("", "") or key in used_hotel_keys:
            continue
        used_hotel_keys.add(key)
        used_hotels.append(hotel)

    llm_default = {
        "overall_suggestions": f"行程已压缩为每日核心双景点结构，建议结合实时天气灵活微调。",
        "important_notes": ["热门景点建议提前预约。", "实际价格以下单时为准。"],
        "packing_tips": ["身份证", "充电器", "舒适鞋子"],
        "narrative_plan": "",
    }
    summary_prompt = _build_summary_prompt(
        request=request,
        attractions=attractions,
        hotels=used_hotels,
        restaurants=restaurants,
        weather=weather_list,
        days=days,
    )
    llm_data = await invoke_llm_json_async(
        prompt=summary_prompt,
        temperature=0.35,
    )

    notes_raw = llm_data.get("important_notes")
    important_notes = [str(x).strip() for x in notes_raw] if isinstance(notes_raw, list) else []
    important_notes = [x for x in important_notes if x][:5] or llm_default["important_notes"]

    tips_raw = llm_data.get("packing_tips")
    packing_tips = [str(x).strip() for x in tips_raw] if isinstance(tips_raw, list) else []
    packing_tips = [x for x in packing_tips if x][:6] or llm_default["packing_tips"]

    overall_suggestions = str(llm_data.get("overall_suggestions", "")).strip() or llm_default["overall_suggestions"]
    narrative_plan = str(llm_data.get("narrative_plan", "")).strip()
    if not narrative_plan:
        narrative_plan = _build_fallback_narrative(destination=destination, daily_plans=daily_plans)
    overall_suggestions = f"{overall_suggestions}（已结合候选结果做精简整理）"

    trip_plan = {
        "city": destination,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "total_days": days,
        "days": daily_plans,
        "narrative_plan": narrative_plan,
        "weather_info": weather_list,
        "restaurant_recommendations": restaurants,
        "budget_breakdown": budget,
        "total_budget": total_budget,
        "estimated_total_cost": estimated_total,
        "budget_estimate_range": budget_range,
        "transport": transport,
        "overall_suggestions": overall_suggestions,
        "packing_tips": packing_tips,
        "important_notes": important_notes,
        "statistics": {
            "attraction_count": len(attractions),
            "restaurant_count": len(restaurants),
            "hotel_count": len(used_hotels),
        },
    }

    state["itinerary_draft"] = trip_plan
    state["status"] = "completed"
    state["streaming_updates"] = (
        state.get("streaming_updates", "")
        + f"\n行程完成: {days}天, 已按每天景点/美食与两天一换酒店生成路径数据"
    )

    logger.info(
        "final_planning done city=%s days=%s attractions=%s hotels=%s total=%.2f used_llm=%s",
        destination,
        days,
        len(attractions),
        len(hotels),
        estimated_total,
        True,
    )
    return state
