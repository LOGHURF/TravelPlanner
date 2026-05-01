"""Transport node: let LLM decide the multi-day plan, then call MCP for each day's stop route.

负责多日行程的交通规划：
1. LLM 生成每日景点/餐厅分配
2. 调用地图公交 API 查询路线
3. 计算交通费用

图结构位置：
- 接收 reviewer_agent 和 restaurant_agent 的输出
- 输出 transport 到状态
- 连接到 weather 和 final_planning
"""

from __future__ import annotations

from datetime import datetime
from itertools import combinations
from math import asin, cos, radians, sin, sqrt
from typing import Any

from app.config import get_logger
from app.ai.models.graph_models import TripState
from app.ai.utils import (
    distribute_attractions,
    distribute_hotels,
    distribute_restaurants,
    invoke_llm_json_async,
    parse_float,
    parse_int,
    parse_location,
)
from app.ai.mcp.client import invoke_tool_with_debug

logger = get_logger("TransportService")
TRANSIT_TOOL_NAME = "maps_transit_integrated"


def _trip_days(request: dict[str, Any]) -> int:
    """计算出行天数"""
    try:
        start = datetime.strptime(str(request.get("start_date", "")), "%Y-%m-%d").date()
        end = datetime.strptime(str(request.get("end_date", "")), "%Y-%m-%d").date()
        return max(1, (end - start).days + 1)
    except (TypeError, ValueError):
        return max(1, int(request.get("days", 1) or 1))


def _haversine_km(start: dict[str, float], end: dict[str, float]) -> float:
    """计算两点之间的球面距离（公里）"""
    lon1, lat1 = radians(start["lng"]), radians(start["lat"])
    lon2, lat2 = radians(end["lng"]), radians(end["lat"])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    arc = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(arc))


def _is_valid_location(location: dict[str, float] | None) -> bool:
    """判断是否为有效坐标"""
    return bool(location and location.get("lat") and location.get("lng"))


def _location_text(location: dict[str, float]) -> str:
    """将坐标转换为字符串格式"""
    return f"{location['lng']:.6f},{location['lat']:.6f}"


def _coerce_transits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """从 API 响应中提取 transits 列表"""
    route = payload.get("route")
    if not isinstance(route, dict):
        return []
    transits = route.get("transits", [])
    if isinstance(transits, list):
        return [item for item in transits if isinstance(item, dict)]
    if isinstance(transits, dict):
        return [transits]
    return []


def _first_segment_instruction(transit: dict[str, Any]) -> str:
    """从 transit 中提取第一条换乘指令"""
    segments = transit.get("segments", [])
    if isinstance(segments, dict):
        segments = [segments]
    if not isinstance(segments, list):
        return ""

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        bus = segment.get("bus")
        if isinstance(bus, dict):
            buslines = bus.get("buslines") or bus.get("bus_line") or []
            if isinstance(buslines, dict):
                buslines = [buslines]
            if isinstance(buslines, list) and buslines:
                first = buslines[0]
                if isinstance(first, dict):
                    name = str(first.get("name", "") or first.get("buslinename", "")).strip()
                    if name:
                        return f"公交 {name}"
        railway = segment.get("railway")
        if isinstance(railway, dict):
            name = str(railway.get("name", "") or railway.get("trip", "")).strip()
            if name:
                return f"轨道交通 {name}"
        walking = segment.get("walking")
        if isinstance(walking, dict):
            distance = parse_int(walking.get("distance"))
            if distance > 0:
                return f"步行约{distance}米"
    return "公共交通换乘"


def _transit_segment_between_points(
    start: dict[str, Any],
    end: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """根据 API 响应构建两点间的交通段落"""
    start_loc = parse_location(start.get("location"))
    end_loc = parse_location(end.get("location"))
    if not _is_valid_location(start_loc) or not _is_valid_location(end_loc):
        return []

    transits = _coerce_transits(payload)
    if not transits:
        return []

    transit = transits[0]
    cost_info = transit.get("cost", {}) if isinstance(transit.get("cost"), dict) else {}
    distance_km = round(parse_float(transit.get("distance")) / 1000, 2)
    duration = max(1, round(parse_float(cost_info.get("duration")) / 60))
    transit_fee = parse_float(cost_info.get("transit_fee"))
    taxi_fee = parse_float(cost_info.get("taxi_fee"))
    cost = round(transit_fee or taxi_fee, 2)
    return [
        {
            "from_name": start.get("name", ""),
            "to_name": end.get("name", ""),
            "from_location": start_loc,
            "to_location": end_loc,
            "mode": "transit",
            "distance": distance_km,
            "duration": duration,
            "cost": cost,
            "instruction": _first_segment_instruction(transit),
        }
    ]


def _transit_segment_from_payload(
    attractions: list[dict[str, Any]],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """从 payload 提取景点间的交通段落"""
    if len(attractions) < 2:
        return []
    return _transit_segment_between_points(attractions[0], attractions[1], payload)


def _estimate_segment_between(start: dict[str, Any], end: dict[str, Any]) -> list[dict[str, Any]]:
    """无 API 数据时估算两点间交通（直线距离 × 系数）"""
    start_loc = parse_location(start.get("location"))
    end_loc = parse_location(end.get("location"))
    if not _is_valid_location(start_loc) or not _is_valid_location(end_loc):
        return []

    distance_km = round(_haversine_km(start_loc, end_loc), 2)
    duration = max(8, round(distance_km / 28 * 60))
    cost = round(max(12.0, distance_km * 2.8), 2)
    return [
        {
            "from_name": start.get("name", ""),
            "to_name": end.get("name", ""),
            "from_location": start_loc,
            "to_location": end_loc,
            "mode": "driving",
            "distance": distance_km,
            "duration": duration,
            "cost": cost,
            "instruction": "",
        }
    ]


def _item_key(item: dict[str, Any]) -> tuple[str, str]:
    """生成景点/餐厅的唯一标识键"""
    return (
        str(item.get("name", "")).strip(),
        str(item.get("address", "")).strip(),
    )


def _match_indexes(
    source: list[dict[str, Any]],
    selected: list[dict[str, Any]],
) -> list[int]:
    """在源列表中匹配已选项的索引"""
    result: list[int] = []
    used: set[int] = set()
    for item in selected:
        key = _item_key(item)
        for idx, candidate in enumerate(source):
            if idx in used:
                continue
            if _item_key(candidate) == key:
                result.append(idx)
                used.add(idx)
                break
    return result


def _distance_to_hotel(item: dict[str, Any], hotel: dict[str, Any] | None) -> float:
    """计算景点到酒店的距离"""
    hotel_loc = parse_location((hotel or {}).get("location"))
    item_loc = parse_location(item.get("location"))
    if not _is_valid_location(hotel_loc) or not _is_valid_location(item_loc):
        return 999.0
    return round(_haversine_km(hotel_loc, item_loc), 2)


def _distance_between_items(start: dict[str, Any], end: dict[str, Any]) -> float:
    """计算两个景点之间的距离"""
    start_loc = parse_location(start.get("location"))
    end_loc = parse_location(end.get("location"))
    if not _is_valid_location(start_loc) or not _is_valid_location(end_loc):
        return 999.0
    return round(_haversine_km(start_loc, end_loc), 2)


def _target_attractions_per_day(days: int, max_per_day: int, attractions: list[dict[str, Any]]) -> int:
    """计算每日目标景点数量"""
    if days <= 0:
        return 0
    limit = max(1, min(2, int(max_per_day or 2)))
    if len(attractions) >= days * limit:
        return limit
    return max(1, min(limit, len(attractions) // days if days else 0))


def _build_default_daily_plan(
    *,
    attractions: list[dict[str, Any]],
    restaurants: list[dict[str, Any]],
    hotels: list[dict[str, Any]],
    days: int,
    max_per_day: int,
) -> list[dict[str, Any]]:
    """基于规则构建默认每日计划（景点/餐厅/酒店分配）"""
    attractions_by_day = distribute_attractions(attractions, days, max_per_day)
    hotels_by_day = distribute_hotels(
        hotels,
        days,
        stay_span=2,
        day_attractions=attractions_by_day,
    )
    meals_by_day = distribute_restaurants(
        restaurants,
        days,
        day_attractions=attractions_by_day,
        day_hotels=hotels_by_day,
    )

    plan: list[dict[str, Any]] = []
    for idx in range(days):
        day_attractions = attractions_by_day[idx] if idx < len(attractions_by_day) else []
        day_meals = meals_by_day[idx] if idx < len(meals_by_day) else []
        day_hotel = hotels_by_day[idx] if idx < len(hotels_by_day) else None
        plan.append(
            {
                "day_index": idx + 1,
                "hotel": day_hotel,
                "hotel_index": _match_indexes(hotels, [day_hotel])[0] if day_hotel else None,
                "attractions": day_attractions,
                "attraction_indexes": _match_indexes(attractions, day_attractions),
                "meals": day_meals,
                "meal_indexes": _match_indexes(restaurants, day_meals),
                "reason": "规则兜底分配",
            }
        )
    return plan


def _compact_trip_context(
    *,
    attractions: list[dict[str, Any]],
    restaurants: list[dict[str, Any]],
    hotels: list[dict[str, Any]],
    default_plan: list[dict[str, Any]],
) -> dict[str, Any]:
    """压缩行程上下文供 LLM 使用"""
    hotel_brief = [
        {
            "index": idx,
            "name": item.get("name", ""),
            "rating": item.get("rating", 0),
            "location": item.get("location"),
            "description": item.get("description", ""),
        }
        for idx, item in enumerate(hotels)
    ]
    attraction_brief = [
        {
            "index": idx,
            "name": item.get("name", ""),
            "rating": item.get("rating", 0),
            "location": item.get("location"),
            "category": item.get("category", "") or item.get("type", ""),
            "description": item.get("description", ""),
        }
        for idx, item in enumerate(attractions)
    ]
    meal_brief = [
        {
            "index": idx,
            "name": item.get("name", ""),
            "meal_type": item.get("meal_type", ""),
            "rating": item.get("rating", 0),
            "location": item.get("location"),
            "description": item.get("description", ""),
        }
        for idx, item in enumerate(restaurants)
    ]
    day_hotel_brief = [
        {
            "day_index": day["day_index"],
            "hotel_index": day["hotel_index"],
            "hotel_name": (day.get("hotel") or {}).get("name", ""),
            "hotel_location": (day.get("hotel") or {}).get("location"),
            "default_attraction_indexes": day.get("attraction_indexes", []),
            "default_meal_indexes": day.get("meal_indexes", []),
        }
        for day in default_plan
    ]
    return {
        "hotels": hotel_brief,
        "attractions": attraction_brief,
        "restaurants": meal_brief,
        "days": day_hotel_brief,
    }


def _trip_plan_default_payload(default_plan: list[dict[str, Any]]) -> dict[str, Any]:
    """生成默认行程计划 payload"""
    return {
        "days": [
            {
                "day_index": day["day_index"],
                "attraction_indexes": day.get("attraction_indexes", []),
                "meal_indexes": day.get("meal_indexes", []),
                "reason": "规则兜底分配",
            }
            for day in default_plan
        ],
        "overall_reason": "已先按全程顺路性做整体分配，再结合酒店两天一换规则拆到每天",
    }


def _day_entry(raw_days: Any, day_index: int) -> dict[str, Any]:
    """从 LLM 返回的 days 列表中提取指定 day_index 的条目"""
    if isinstance(raw_days, list):
        for item in raw_days:
            if not isinstance(item, dict):
                continue
            try:
                if int(item.get("day_index", 0) or 0) == day_index:
                    return item
            except (TypeError, ValueError):
                continue
        if day_index - 1 < len(raw_days) and isinstance(raw_days[day_index - 1], dict):
            return raw_days[day_index - 1]
    return {}


def _pick_unique_indexes(
    raw_indexes: Any,
    items: list[dict[str, Any]],
    *,
    used: set[int],
    limit: int,
) -> list[int]:
    """从 raw_indexes 中提取不重复的索引"""
    result: list[int] = []
    if not isinstance(raw_indexes, list):
        return result
    for raw in raw_indexes:
        try:
            idx = int(raw)
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(items) or idx in used:
            continue
        used.add(idx)
        result.append(idx)
        if len(result) >= limit:
            break
    return result


def _top_up_indexes(
    current: list[int],
    *,
    fallback_indexes: list[int],
    items: list[dict[str, Any]],
    used: set[int],
    limit: int,
    hotel: dict[str, Any] | None,
) -> list[int]:
    """用兜底列表补足索引数量"""
    result = list(current)
    for idx in fallback_indexes:
        if idx in used or idx < 0 or idx >= len(items):
            continue
        used.add(idx)
        result.append(idx)
        if len(result) >= limit:
            return result[:limit]

    remaining = [
        idx for idx in range(len(items))
        if idx not in used
    ]
    remaining.sort(key=lambda idx: (_distance_to_hotel(items[idx], hotel), -float(items[idx].get("rating", 0) or 0)))
    for idx in remaining:
        used.add(idx)
        result.append(idx)
        if len(result) >= limit:
            break
    return result[:limit]


def _normalize_trip_plan(
    *,
    llm_data: dict[str, Any],
    attractions: list[dict[str, Any]],
    restaurants: list[dict[str, Any]],
    default_plan: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """将 LLM 返回的行程数据标准化并与默认值合并"""
    used_attractions: set[int] = set()
    used_meals: set[int] = set()
    normalized: list[dict[str, Any]] = []

    for default_day in default_plan:
        day_index = int(default_day["day_index"])
        hotel = default_day.get("hotel")
        entry = _day_entry(llm_data.get("days"), day_index)

        attraction_limit = len(default_day.get("attractions", []))
        meal_limit = len(default_day.get("meals", []))

        day_attraction_indexes = _pick_unique_indexes(
            entry.get("attraction_indexes"),
            attractions,
            used=used_attractions,
            limit=attraction_limit,
        )
        day_meal_indexes = _pick_unique_indexes(
            entry.get("meal_indexes"),
            restaurants,
            used=used_meals,
            limit=meal_limit,
        )

        day_attraction_indexes = _top_up_indexes(
            day_attraction_indexes,
            fallback_indexes=default_day.get("attraction_indexes", []),
            items=attractions,
            used=used_attractions,
            limit=attraction_limit,
            hotel=hotel,
        )
        day_meal_indexes = _top_up_indexes(
            day_meal_indexes,
            fallback_indexes=default_day.get("meal_indexes", []),
            items=restaurants,
            used=used_meals,
            limit=meal_limit,
            hotel=hotel,
        )

        normalized.append(
            {
                "day_index": day_index,
                "hotel": hotel,
                "hotel_index": default_day.get("hotel_index"),
                "attractions": [attractions[idx] for idx in day_attraction_indexes],
                "attraction_indexes": day_attraction_indexes,
                "meals": [restaurants[idx] for idx in day_meal_indexes],
                "meal_indexes": day_meal_indexes,
                "reason": str(entry.get("reason", "")).strip() or "规则兜底分配",
            }
        )

    return normalized


def _rebalance_daily_plan_attractions(
    *,
    daily_plan: list[dict[str, Any]],
    attractions: list[dict[str, Any]],
    target_per_day: int,
) -> list[dict[str, Any]]:
    """重新平衡每日计划的景点数量"""
    if target_per_day <= 0 or not daily_plan:
        return daily_plan
    if len(attractions) < len(daily_plan) * target_per_day:
        return daily_plan

    used_indexes: set[int] = set()
    for day in daily_plan:
        for idx in day.get("attraction_indexes", []):
            if isinstance(idx, int) and 0 <= idx < len(attractions):
                used_indexes.add(idx)

    for day in daily_plan:
        hotel = day.get("hotel")
        current_indexes = [
            idx for idx in day.get("attraction_indexes", [])
            if isinstance(idx, int) and 0 <= idx < len(attractions)
        ][:target_per_day]
        current_items = [attractions[idx] for idx in current_indexes]
        if len(current_indexes) >= target_per_day:
            day["attraction_indexes"] = current_indexes[:target_per_day]
            day["attractions"] = current_items[:target_per_day]
            continue

        remaining = [
            idx for idx in range(len(attractions))
            if idx not in used_indexes and idx not in current_indexes
        ]
        remaining.sort(
            key=lambda idx: (
                _distance_to_hotel(attractions[idx], hotel),
                -float(attractions[idx].get("rating", 0) or 0),
            )
        )
        for idx in remaining:
            current_indexes.append(idx)
            current_items.append(attractions[idx])
            used_indexes.add(idx)
            if len(current_indexes) >= target_per_day:
                break

        day["attraction_indexes"] = current_indexes[:target_per_day]
        day["attractions"] = current_items[:target_per_day]

    return daily_plan


def _recluster_daily_plan_attractions(
    *,
    daily_plan: list[dict[str, Any]],
    attractions: list[dict[str, Any]],
    target_per_day: int,
    hotels: list[dict[str, Any]],
    stay_span: int = 2,
) -> list[dict[str, Any]]:
    """重新聚类每日计划的景点（基于路线顺路性优化）"""
    if target_per_day <= 0 or not daily_plan:
        return daily_plan

    selected_indexes: list[int] = []
    used_indexes: set[int] = set()
    for day in daily_plan:
        for idx in day.get("attraction_indexes", []):
            if not isinstance(idx, int) or idx < 0 or idx >= len(attractions) or idx in used_indexes:
                continue
            selected_indexes.append(idx)
            used_indexes.add(idx)

    regrouped_indexes: list[list[int]] | None = None
    total_selected = len(selected_indexes)
    if total_selected == len(daily_plan) * target_per_day and target_per_day <= 2 and total_selected <= 10:
        best_score = float("inf")
        best_groups: list[list[int]] | None = None

        def score_day(day_items: list[dict[str, Any]], hotel: dict[str, Any] | None) -> tuple[float, list[dict[str, Any]]]:
            if len(day_items) < 2:
                return (_distance_to_hotel(day_items[0], hotel) * 2 if day_items and hotel else 0.0), day_items

            candidate_orders = [day_items, list(reversed(day_items))]
            best_day_score = float("inf")
            best_order = day_items
            for ordered_items in candidate_orders:
                score = _distance_to_hotel(ordered_items[0], hotel) if hotel else 0.0
                score += _distance_between_items(ordered_items[0], ordered_items[1])
                score += _distance_to_hotel(ordered_items[-1], hotel) if hotel else 0.0
                if score < best_day_score:
                    best_day_score = score
                    best_order = ordered_items
            return best_day_score, best_order

        def search(remaining: list[int], grouped: list[list[int]]) -> None:
            nonlocal best_score, best_groups
            if len(grouped) == len(daily_plan) - 1:
                candidate_groups = grouped + [list(remaining)]
                candidate_days = [[attractions[idx] for idx in group] for group in candidate_groups]
                hotels_by_day = distribute_hotels(
                    hotels,
                    len(candidate_days),
                    stay_span=stay_span,
                    day_attractions=candidate_days,
                )
                total_score = 0.0
                ordered_groups: list[list[int]] = []
                for day_index, group in enumerate(candidate_groups):
                    ordered_items = [attractions[idx] for idx in group]
                    day_score, optimized_order = score_day(
                        ordered_items,
                        hotels_by_day[day_index] if day_index < len(hotels_by_day) else None,
                    )
                    total_score += day_score
                    ordered_groups.append(_match_indexes(attractions, optimized_order))
                if total_score < best_score:
                    best_score = total_score
                    best_groups = ordered_groups
                return

            first = remaining[0]
            for combo in combinations(remaining[1:], target_per_day - 1):
                group = [first, *combo]
                next_remaining = [idx for idx in remaining if idx not in group]
                search(next_remaining, grouped + [group])

        search(selected_indexes, [])
        regrouped_indexes = best_groups

    if regrouped_indexes is None:
        regrouped = distribute_attractions([attractions[idx] for idx in selected_indexes], len(daily_plan), target_per_day)
        regrouped_indexes = [_match_indexes(attractions, day_items) for day_items in regrouped]

    for idx, day in enumerate(daily_plan):
        day_indexes = regrouped_indexes[idx] if idx < len(regrouped_indexes) else []
        day_attractions = [attractions[item_index] for item_index in day_indexes]
        day["attractions"] = day_attractions
        day["attraction_indexes"] = day_indexes

    return daily_plan


def _realign_daily_plan_supporting_stops(
    *,
    daily_plan: list[dict[str, Any]],
    restaurants: list[dict[str, Any]],
    hotels: list[dict[str, Any]],
    stay_span: int = 2,
) -> list[dict[str, Any]]:
    """重新对齐每日计划的配套餐饮和酒店"""
    if not daily_plan:
        return daily_plan

    day_attractions = [list(day.get("attractions") or []) for day in daily_plan]
    hotels_by_day = distribute_hotels(
        hotels,
        len(daily_plan),
        stay_span=stay_span,
        day_attractions=day_attractions,
    )
    meals_by_day = distribute_restaurants(
        restaurants,
        len(daily_plan),
        day_attractions=day_attractions,
        day_hotels=hotels_by_day,
    )

    for idx, day in enumerate(daily_plan):
        hotel = hotels_by_day[idx] if idx < len(hotels_by_day) else day.get("hotel")
        meals = meals_by_day[idx] if idx < len(meals_by_day) else list(day.get("meals") or [])
        day["hotel"] = hotel
        day["hotel_index"] = _match_indexes(hotels, [hotel])[0] if hotel else None
        day["meals"] = meals
        day["meal_indexes"] = _match_indexes(restaurants, meals)

    return daily_plan


async def _plan_trip_with_llm(
    *,
    request: dict[str, Any],
    attractions: list[dict[str, Any]],
    restaurants: list[dict[str, Any]],
    hotels: list[dict[str, Any]],
    days: int,
    max_per_day: int,
) -> tuple[list[dict[str, Any]], str, bool]:
    """LLM 生成多日行程计划"""
    default_plan = _build_default_daily_plan(
        attractions=attractions,
        restaurants=restaurants,
        hotels=hotels,
        days=days,
        max_per_day=max_per_day,
    )
    default_payload = _trip_plan_default_payload(default_plan)
    target_per_day = _target_attractions_per_day(days, max_per_day, attractions)
    context = _compact_trip_context(
        attractions=attractions,
        restaurants=restaurants,
        hotels=hotels,
        default_plan=default_plan,
    )
    prompt = (
        "你是多日旅行排期助手。请先从整个行程的顺路性出发，整体考虑这几天的游玩顺序，再拆解成每天分别去哪些景点和搭配哪些餐厅。"
        "请根据酒店位置、景点距离、餐厅搭配、游玩便利性做全局规划后，再输出每日分配。"
        "酒店已经按约两天一换固定，不要改酒店，只需要分配每天的景点和餐厅。"
        "不要发明新地点，不要重复使用同一景点或餐厅。"
        "景点顺序就是当天游玩的先后顺序。"
        f"如果景点总数足够支撑每天 {target_per_day} 个景点，那么每天都必须安排 {target_per_day} 个景点，最后一天也一样，不能减少。"
        "只返回 JSON 对象，字段：days: [{day_index, attraction_indexes, meal_indexes, reason}], overall_reason: string。\n\n"
        f"用户上下文: destination={request.get('destination', '')}, companions={request.get('companions', '')}, style_preferences={request.get('style_preferences', [])}\n"
        f"候选上下文: {context}"
    )
    llm_data = await invoke_llm_json_async(
        prompt=prompt,
        temperature=0.2,
    )
    normalized = _normalize_trip_plan(
        llm_data=llm_data,
        attractions=attractions,
        restaurants=restaurants,
        default_plan=default_plan,
    )
    normalized = _rebalance_daily_plan_attractions(
        daily_plan=normalized,
        attractions=attractions,
        target_per_day=target_per_day,
    )
    normalized = _recluster_daily_plan_attractions(
        daily_plan=normalized,
        attractions=attractions,
        target_per_day=target_per_day,
        hotels=hotels,
        stay_span=2,
    )
    normalized = _realign_daily_plan_supporting_stops(
        daily_plan=normalized,
        restaurants=restaurants,
        hotels=hotels,
        stay_span=2,
    )
    reason = str(llm_data.get("overall_reason", "")).strip() or default_payload["overall_reason"]
    return normalized, reason, True


async def _build_segment_with_mcp(
    start: dict[str, Any],
    end: dict[str, Any],
    request: dict[str, Any],
    *,
    day_index: int,
    leg_index: int,
) -> list[dict[str, Any]]:
    """调用 MCP 地图工具查询两点间交通路线"""
    start_loc = parse_location(start.get("location"))
    end_loc = parse_location(end.get("location"))
    if not _is_valid_location(start_loc) or not _is_valid_location(end_loc):
        return []

    tool_args = {
        "origin": _location_text(start_loc),
        "destination": _location_text(end_loc),
        "strategy": "0",
        "AlternativeRoute": 1,
        "max_trans": 3,
        "nightflag": 0,
        "city1": str(request.get("destination", "") or "").strip(),
        "city2": str(request.get("destination", "") or "").strip(),
    }
    result = await invoke_tool_with_debug(
        tool_name=TRANSIT_TOOL_NAME,
        tool_args=tool_args,
        log=logger,
        context=f"transport:day{day_index}:leg{leg_index}",
    )
    if not isinstance(result, dict):
        return []
    segment = _transit_segment_between_points(start, end, result)
    if segment:
        logger.info(
            "transport mcp route parsed day=%s leg=%s mode=%s distance=%s duration=%s cost=%s",
            day_index,
            leg_index,
            segment[0].get("mode", ""),
            segment[0].get("distance", 0),
            segment[0].get("duration", 0),
            segment[0].get("cost", 0),
        )
    return segment


async def _build_route_segments_for_day(
    *,
    day_index: int,
    stops: list[dict[str, Any]],
    request: dict[str, Any],
) -> list[dict[str, Any]]:
    """为一天中的所有停留点构建交通段落"""
    if len(stops) < 2:
        return []

    segments: list[dict[str, Any]] = []
    for leg_index in range(len(stops) - 1):
        start = stops[leg_index]
        end = stops[leg_index + 1]
        try:
            route = await _build_segment_with_mcp(
                start,
                end,
                request,
                day_index=day_index,
                leg_index=leg_index + 1,
            )
        except Exception as exc:
            logger.warning(
                "transport mcp route failed day=%s leg=%s error=%s",
                day_index,
                leg_index + 1,
                exc,
            )
            route = []
        if not route:
            route = _estimate_segment_between(start, end)
        segments.extend(route)
    return segments


def _estimate_arrival_plan(request: dict[str, Any]) -> dict[str, Any] | None:
    """估算出发地到目的地的城际交通方案"""
    origin = str(request.get("origin", "") or "").strip()
    destination = str(request.get("destination", "") or "").strip()
    if not origin or not destination or origin == destination:
        return None

    mode = "高铁"
    if any(keyword in origin + destination for keyword in ("香港", "澳门", "乌鲁木齐", "拉萨", "三亚")):
        mode = "航班"

    summary = f"从{origin}前往{destination}，建议优先查询{mode}班次，抵达后再开始第1天行程。"
    return {
        "from_city": origin,
        "to_city": destination,
        "mode": mode,
        "summary": summary,
    }


def _route_stops_for_day(day: dict[str, Any]) -> list[dict[str, Any]]:
    """从每日计划中提取景点停留点"""
    stops: list[dict[str, Any]] = []
    for attraction in list(day.get("attractions") or []):
        location = parse_location(attraction.get("location"))
        name = str(attraction.get("name", "")).strip()
        if not name or not _is_valid_location(location):
            continue
        if stops and stops[-1]["name"] == name and stops[-1]["location"] == location:
            continue
        stops.append(
            {
                "name": name,
                "location": location,
                "kind": "attraction",
            }
        )
    return stops


async def transport_node(state: TripState) -> TripState:
    """Transport Agent 主流程"""
    request = state.get("request", {})
    days = _trip_days(request)
    attractions = list(state.get("attractions") or [])
    restaurants = list(state.get("restaurants") or [])
    hotels = list(state.get("hotels") or [])
    max_per_day = max(1, min(2, int(state.get("max_attractions_per_day", 2) or 2)))

    daily_plan, plan_reason, used_llm = await _plan_trip_with_llm(
        request=request,
        attractions=attractions,
        restaurants=restaurants,
        hotels=hotels,
        days=days,
        max_per_day=max_per_day,
    )

    daily_routes: list[list[dict[str, Any]]] = []
    for day in daily_plan:
        day_stops = _route_stops_for_day(day)
        route = await _build_route_segments_for_day(
            day_index=int(day.get("day_index", 0) or 0),
            stops=day_stops,
            request=request,
        )
        daily_routes.append(route)

    route_segment_count = sum(len(route) for route in daily_routes)
    transport_cost = round(
        sum(
            float(segment.get("cost", 0) or 0)
            for route in daily_routes
            for segment in route
        ),
        2,
    )
    if transport_cost <= 0:
        transport_cost = round(18.0 * max(1, days), 2)

    arrival_plan = _estimate_arrival_plan(request)
    suggested_mode = "公交" if any(
        segment.get("mode") == "transit"
        for route in daily_routes
        for segment in route
    ) else "驾车"
    state["transport"] = {
        "inter_city": arrival_plan,
        "suggested_mode": suggested_mode,
        "estimated_transport_cost": transport_cost,
        "daily_routes": daily_routes,
        "daily_plan": daily_plan,
        "planning_reason": plan_reason,
    }

    arrival_message = f"\n到达建议: {arrival_plan['summary']}" if arrival_plan else ""
    state["streaming_updates"] = (
        state.get("streaming_updates", "")
        + f"\n交通完成: 已按全程顺序完成{days}天规划，并为{route_segment_count}段景点间路径生成地图数据"
        + arrival_message
    )
    state["completed_agents"] = state.get("completed_agents", []) + ["transport"]
    logger.info(
        "transport summary ready days=%s route_segments=%s cost=%s arrival=%s used_llm=%s reason=%s",
        days,
        route_segment_count,
        transport_cost,
        bool(arrival_plan),
        used_llm,
        plan_reason,
    )
    return state
