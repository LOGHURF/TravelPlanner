"""路线体检节点：在行程拼装前验证日内移动距离和风险。"""

from __future__ import annotations

from typing import Any

from app.ai.models.graph_models import TripState
from app.ai.nodes.plan_data_utils import location_text, straight_line_distance_km
from app.ai.utils import parse_float, parse_location
from app.config import get_logger
from app.services.amap import get_driving_route

logger = get_logger("RouteMatrix")
WALKABLE_LEG_MAX_KM = 2.0
WALKING_SPEED_KMH = 4.2
MAX_REASONABLE_DRIVING_KMH = 120.0
URBAN_DRIVING_ESTIMATE_KMH = 25.0


def _group_attractions_by_day(state: TripState) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for attraction in state.get("attractions") or []:
        if not isinstance(attraction, dict):
            continue
        day_index = int(attraction.get("day_index", 0) or 0)
        if day_index > 0:
            grouped.setdefault(day_index, []).append(attraction)
    return grouped


def _walking_segment(
    *,
    start: dict[str, Any],
    end: dict[str, Any],
    start_loc: dict[str, float],
    end_loc: dict[str, float],
    distance: float,
    day_index: int,
    leg_index: int,
) -> dict[str, Any]:
    duration = max(5, int(round((distance / WALKING_SPEED_KMH) * 60)))
    return {
        "day_index": day_index,
        "leg_index": leg_index,
        "from_name": start.get("name", ""),
        "to_name": end.get("name", ""),
        "from_location": start_loc,
        "to_location": end_loc,
        "mode": "walking",
        "distance": distance,
        "duration": duration,
        "cost": 0,
        "instruction": "两点距离很近，建议步行串联。",
        "status": "ok",
        "issue": "",
    }


def _coerce_driving_paths(payload: dict[str, Any]) -> list[dict[str, Any]]:
    route = payload.get("route")
    if not isinstance(route, dict):
        return []
    paths = route.get("paths", [])
    if isinstance(paths, list):
        return [item for item in paths if isinstance(item, dict)]
    if isinstance(paths, dict):
        return [paths]
    return []


def _first_driving_instruction(path: dict[str, Any]) -> str:
    steps = path.get("steps", [])
    if isinstance(steps, dict):
        steps = [steps]
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict):
                instruction = str(step.get("instruction", "") or "").strip()
                if instruction:
                    return instruction
    return "建议驾车或打车前往"


def _sum_step_duration_seconds(path: dict[str, Any]) -> float:
    steps = path.get("steps", [])
    if isinstance(steps, dict):
        steps = [steps]
    if not isinstance(steps, list):
        return 0.0
    total = 0.0
    for step in steps:
        if not isinstance(step, dict):
            continue
        cost_info = step.get("cost", {}) if isinstance(step.get("cost"), dict) else {}
        total += parse_float(cost_info.get("duration")) or parse_float(step.get("duration"))
    return total


def _driving_segment_between_points(
    start: dict[str, Any],
    end: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    start_loc = parse_location(start.get("location"))
    end_loc = parse_location(end.get("location"))
    if not start_loc or not end_loc:
        return []

    paths = _coerce_driving_paths(payload)
    if not paths:
        return []

    path = paths[0]
    cost_info = path.get("cost", {}) if isinstance(path.get("cost"), dict) else {}
    distance_km = round(parse_float(path.get("distance")) / 1000, 2)
    duration_seconds = (
        parse_float(cost_info.get("duration"))
        or parse_float(path.get("duration"))
        or _sum_step_duration_seconds(path)
    )
    if distance_km > 0 and duration_seconds <= 0:
        duration_seconds = distance_km / URBAN_DRIVING_ESTIMATE_KMH * 3600
    if distance_km <= 0 or duration_seconds <= 0:
        return []

    speed_kmh = distance_km / (duration_seconds / 3600)
    if speed_kmh > MAX_REASONABLE_DRIVING_KMH:
        logger.warning(
            "discard unrealistic driving route from=%s to=%s distance=%s duration_seconds=%s speed=%.1f",
            start.get("name", ""),
            end.get("name", ""),
            distance_km,
            duration_seconds,
            speed_kmh,
        )
        return []

    taxi_fee = parse_float(cost_info.get("taxi_fee")) or parse_float(path.get("taxi_fee"))
    return [
        {
            "from_name": start.get("name", ""),
            "to_name": end.get("name", ""),
            "from_location": start_loc,
            "to_location": end_loc,
            "mode": "driving",
            "distance": distance_km,
            "duration": max(1, round(duration_seconds / 60)),
            "cost": round(taxi_fee, 2),
            "instruction": _first_driving_instruction(path),
        }
    ]


def _driving_segment_from_payload(
    attractions: list[dict[str, Any]],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    if len(attractions) < 2:
        return []
    return _driving_segment_between_points(attractions[0], attractions[1], payload)


async def _build_driving_leg(
    *,
    start: dict[str, Any],
    end: dict[str, Any],
    day_index: int,
    leg_index: int,
) -> dict[str, Any]:
    start_loc = parse_location(start.get("location"))
    end_loc = parse_location(end.get("location"))
    if not start_loc or not end_loc:
        return {
            "day_index": day_index,
            "leg_index": leg_index,
            "from_name": start.get("name", ""),
            "to_name": end.get("name", ""),
            "status": "unavailable",
            "issue": "missing location",
        }

    direct_distance = straight_line_distance_km(start_loc, end_loc)
    if direct_distance <= WALKABLE_LEG_MAX_KM:
        return _walking_segment(
            start=start,
            end=end,
            start_loc=start_loc,
            end_loc=end_loc,
            distance=direct_distance,
            day_index=day_index,
            leg_index=leg_index,
        )

    payload = await get_driving_route(origin=location_text(start_loc), destination=location_text(end_loc))
    segments = _driving_segment_between_points(start, end, payload)
    if not segments:
        return {
            "day_index": day_index,
            "leg_index": leg_index,
            "from_name": start.get("name", ""),
            "to_name": end.get("name", ""),
            "from_location": start_loc,
            "to_location": end_loc,
            "status": "unavailable",
            "issue": "driving route unavailable",
        }

    segment = segments[0]
    distance = float(segment.get("distance", 0) or 0)
    duration = int(segment.get("duration", 0) or 0)
    status = "ok"
    issue = ""
    if distance > 25:
        status = "blocked"
        issue = "same-day leg exceeds 25km"
    elif distance > 15:
        status = "risky"
        issue = "same-day leg exceeds 15km"

    return {
        "day_index": day_index,
        "leg_index": leg_index,
        **segment,
        "status": status,
        "issue": issue,
    }


async def route_matrix_node(state: TripState) -> dict[str, Any]:
    """Create route legs for each day's verified attractions."""
    legs: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    daily_routes: list[list[dict[str, Any]]] = []

    for day_index, attractions in sorted(_group_attractions_by_day(state).items()):
        day_legs: list[dict[str, Any]] = []
        for index in range(len(attractions) - 1):
            leg = await _build_driving_leg(
                start=attractions[index],
                end=attractions[index + 1],
                day_index=day_index,
                leg_index=index + 1,
            )
            legs.append(leg)
            if leg.get("status") in {"unavailable", "blocked"}:
                issues.append(leg)
            if leg.get("status") != "unavailable":
                day_legs.append(leg)
        daily_routes.append(day_legs)

    route_matrix = {
        "mode": "driving",
        "legs": legs,
        "issues": issues,
        "daily_routes": daily_routes,
    }
    logger.info("route matrix ready legs=%s issues=%s", len(legs), len(issues))
    return {
        "route_matrix": route_matrix,
        "streaming_updates": f"\n路线矩阵完成: {len(legs)}段, {len(issues)}段需修复",
        "completed_agents": ["route_matrix"],
    }
