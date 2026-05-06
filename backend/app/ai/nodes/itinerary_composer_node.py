"""行程拼装节点：用已验证数据组合可执行每日行程。"""

from __future__ import annotations

from typing import Any

from app.ai.models.graph_models import TripState
from app.ai.nodes.plan_data_utils import straight_line_distance_km
from app.ai.utils import build_day_stops, distribute_hotels, distribute_restaurants, parse_location
from app.config import get_logger

logger = get_logger("ItineraryComposer")
WALKABLE_LEG_MAX_KM = 2.0
WALKING_SPEED_KMH = 4.2
TRANSIT_LEG_MAX_KM = 8.0
TRANSIT_SPEED_KMH = 18.0
DRIVING_SPEED_KMH = 25.0


def _request_days(state: TripState) -> int:
    request = state.get("request", {})
    return int(request.get("days", request.get("duration", 1)) or 1)


def _items_by_day(items: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in items:
        day_index = int(item.get("day_index", 0) or 0)
        if day_index > 0:
            grouped.setdefault(day_index, []).append(item)
    return grouped


def _estimated_segment(start: dict[str, Any], end: dict[str, Any]) -> dict[str, Any]:
    start_loc = parse_location(start.get("location"))
    end_loc = parse_location(end.get("location"))
    if not start_loc or not end_loc:
        raise RuntimeError(f"route stop missing location from={start.get('name', '')} to={end.get('name', '')}")

    distance = straight_line_distance_km(start_loc, end_loc)
    if distance <= WALKABLE_LEG_MAX_KM:
        mode = "walking"
        duration = max(5, int(round((distance / WALKING_SPEED_KMH) * 60)))
        cost = 0
        instruction = "两点距离很近，建议步行串联。"
    elif distance <= TRANSIT_LEG_MAX_KM:
        mode = "transit"
        duration = max(12, int(round((distance / TRANSIT_SPEED_KMH) * 60)) + 8)
        cost = 3
        instruction = "基于 POI 坐标估算公共交通接驳，出发前用实时地图确认班次。"
    else:
        mode = "driving"
        duration = max(15, int(round((distance / DRIVING_SPEED_KMH) * 60)))
        cost = round(distance * 2.2, 2)
        instruction = "基于 POI 坐标估算驾车接驳，出发前用实时地图确认路况。"

    return {
        "from_name": start.get("name", ""),
        "to_name": end.get("name", ""),
        "from_location": start_loc,
        "to_location": end_loc,
        "mode": mode,
        "distance": distance,
        "duration": duration,
        "cost": cost,
        "instruction": instruction,
    }


async def _build_day_routes(
    *,
    day_index: int,
    hotel: dict[str, Any] | None,
    attractions: list[dict[str, Any]],
    meals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    stops = build_day_stops(hotel, attractions, meals)
    routes: list[dict[str, Any]] = []
    for leg_index in range(len(stops) - 1):
        routes.append(_estimated_segment(stops[leg_index], stops[leg_index + 1]))
    return routes


def _estimate_arrival_plan(request: dict[str, Any]) -> dict[str, Any] | None:
    origin = str(request.get("origin", "") or "").strip()
    destination = str(request.get("destination", "") or "").strip()
    if not origin or not destination or origin == destination:
        return None
    mode = "高铁"
    if any(keyword in origin + destination for keyword in ("香港", "澳门", "乌鲁木齐", "拉萨", "三亚")):
        mode = "航班"
    return {
        "from_city": origin,
        "to_city": destination,
        "mode": mode,
        "summary": f"从{origin}前往{destination}，建议优先查询{mode}班次，抵达后再开始第1天行程。",
    }


async def itinerary_composer_node(state: TripState) -> dict[str, Any]:
    """Compose a transport object consumed by final_planning_node."""
    request = state.get("request", {})
    days = _request_days(state)
    attractions_by_day = _items_by_day(list(state.get("attractions") or []))
    hotels = list(state.get("hotels") or [])
    route_matrix = state.get("route_matrix") or {}
    daily_routes = list(route_matrix.get("daily_routes") or [])
    route_issues = list(route_matrix.get("issues") or [])
    per_day_hotels = distribute_hotels(
        hotels,
        days,
        stay_span=2,
        day_attractions=[attractions_by_day.get(day_index, []) for day_index in range(1, days + 1)],
    )
    per_day_meals = distribute_restaurants(
        list(state.get("restaurants") or []),
        days,
        day_attractions=[attractions_by_day.get(day_index, []) for day_index in range(1, days + 1)],
        day_hotels=per_day_hotels,
    )

    daily_plan: list[dict[str, Any]] = []
    for day_index in range(1, days + 1):
        hotel = per_day_hotels[day_index - 1] if day_index - 1 < len(per_day_hotels) else (hotels[0] if hotels else None)
        daily_plan.append(
            {
                "day_index": day_index,
                "hotel": hotel,
                "hotel_index": 0 if hotel else None,
                "attractions": attractions_by_day.get(day_index, []),
                "meals": per_day_meals[day_index - 1] if day_index - 1 < len(per_day_meals) else [],
                "reason": "基于策略锚点、周边POI和路线矩阵组合。",
            }
        )

    combined_daily_routes: list[list[dict[str, Any]]] = []
    for day in daily_plan:
        day_index = int(day.get("day_index", 0) or 0)
        day_routes = await _build_day_routes(
            day_index=day_index,
            hotel=day.get("hotel") if isinstance(day.get("hotel"), dict) else None,
            attractions=list(day.get("attractions") or []),
            meals=list(day.get("meals") or []),
        )
        combined_daily_routes.append(day_routes)

    transport_cost = round(
        sum(
            float(segment.get("cost", 0) or 0)
            for route in combined_daily_routes or daily_routes
            for segment in route
        ),
        2,
    )
    if transport_cost <= 0:
        transport_cost = round(18.0 * max(1, days), 2)

    transport = {
        "inter_city": _estimate_arrival_plan(request),
        "suggested_mode": "驾车",
        "estimated_transport_cost": transport_cost,
        "daily_routes": combined_daily_routes or daily_routes,
        "daily_plan": daily_plan,
        "route_issues": route_issues,
        "planning_reason": "先生成每日片区和锚点，再用POI与路线矩阵验证后组合行程。",
    }
    logger.info("itinerary composed days=%s route_issues=%s", days, len(route_issues))
    return {
        "transport": transport,
        "streaming_updates": f"\n行程组合完成: {days}天, 路线风险{len(route_issues)}项",
        "completed_agents": ["itinerary_composer"],
    }
