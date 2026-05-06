"""Nearby POI node: retrieve concrete hotels/restaurants around verified anchors."""

from __future__ import annotations

from typing import Any

from app.ai.models.graph_models import TripState
from app.ai.models.planning_contracts import PlanningBlocker
from app.ai.nodes.plan_data_utils import (
    anchor_to_attraction,
    location_text,
    poi_to_hotel,
    poi_rating,
    poi_to_restaurant,
    straight_line_distance_km,
)
from app.ai.poi_types import HOTEL_TYPE_CODE, HOTEL_TYPE_PREFIX, RESTAURANT_TYPE_CODE, RESTAURANT_TYPE_PREFIX, has_type_prefix
from app.ai.planning_gates import evaluate_resource_gate
from app.ai.utils import parse_location
from app.config import get_logger
from app.services.amap import search_pois_nearby

logger = get_logger("NearbyPOI")

RESTAURANTS_PER_DAY = 2


def _day_anchors(state: TripState) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for anchor in state.get("resolved_anchors") or []:
        if not isinstance(anchor, dict):
            continue
        day_index = int(anchor.get("day_index", 0) or 0)
        if day_index > 0:
            grouped.setdefault(day_index, []).append(anchor)
    return grouped


def _first_location(items: list[dict[str, Any]]) -> dict[str, float] | None:
    for item in items:
        location = parse_location(item.get("location"))
        if location:
            return location
    return None


def _rank_restaurant_pois(pois: list[Any]) -> list[Any]:
    indexed = [
        (index, poi, poi_rating(poi))
        for index, poi in enumerate(pois)
        if has_type_prefix(getattr(poi, "typecode", ""), RESTAURANT_TYPE_PREFIX)
    ]
    ranked = sorted(indexed, key=lambda item: (item[2] <= 0, -item[2], item[0]))
    return [poi for _, poi, _ in ranked]


def _unique_texts(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _daily_strategy_by_index(state: TripState) -> dict[int, dict[str, Any]]:
    strategy = state.get("strategy_plan") or {}
    daily_plan = strategy.get("daily_area_plan") if isinstance(strategy, dict) else []
    result: dict[int, dict[str, Any]] = {}
    for day in daily_plan or []:
        if not isinstance(day, dict):
            continue
        day_index = int(day.get("day_index", 0) or 0)
        if day_index > 0:
            result[day_index] = day
    return result


def _food_keyword(request: dict[str, Any]) -> str:
    destination = str(request.get("destination", ""))
    if destination == "杭州":
        return "杭帮菜"
    preferences = [str(item) for item in request.get("style_preferences", [])]
    if "美食" in preferences:
        return "本地菜"
    return "特色菜"


def _restaurant_keywords_for_day(state: TripState, day_index: int, base_keyword: str) -> list[str]:
    day_strategy = _daily_strategy_by_index(state).get(day_index, {})
    return _unique_texts(
        [
            base_keyword,
            *(day_strategy.get("restaurant_area_keywords") or []),
            day_strategy.get("area_name", ""),
            "餐厅",
            "美食",
        ]
    )


async def _search_hotels(state: TripState) -> list[dict[str, Any]]:
    request = state.get("request", {})
    hotel_level = str(request.get("hotel_level", state.get("hotel_level", "舒适型")) or "舒适型")
    destination = str(request.get("destination", "") or "")
    hotel_area_anchors = [item for item in state.get("hotel_area_anchors") or [] if isinstance(item, dict)]
    center = _first_location(hotel_area_anchors) or _first_location(list(state.get("resolved_anchors") or []))
    if not center:
        raise ValueError("nearby hotel search requires a resolved center location")

    response = await search_pois_nearby(
        location=location_text(center),
        keywords=f"{hotel_level}酒店",
        types=HOTEL_TYPE_CODE,
        region=destination,
        citylimit=True,
        radius=3000,
        offset=8,
    )
    hotels = [
        poi_to_hotel(poi, hotel_level=hotel_level)
        for poi in response.pois or []
        if has_type_prefix(poi.typecode, HOTEL_TYPE_PREFIX)
    ]
    if not hotels:
        raise ValueError("nearby hotel search returned no usable hotels")
    return hotels[:5]


async def _collect_restaurants_near_anchor(
    *,
    center_anchor: dict[str, Any],
    meal_type: str,
    meal_anchor_role: str,
    day_index: int,
    destination: str,
    keywords: list[str],
    seen: set[str],
    day_items: list[dict[str, Any]],
) -> bool:
    center = parse_location(center_anchor.get("location"))
    if not center:
        return False

    search_specs = [(keyword, 2200, 10) for keyword in keywords]
    search_specs.append(("", 3200, 16))
    for keyword, radius, offset in search_specs:
        response = await search_pois_nearby(
            location=location_text(center),
            keywords=keyword,
            types=RESTAURANT_TYPE_CODE,
            region=destination,
            citylimit=True,
            radius=radius,
            offset=offset,
        )
        ranked_pois = _rank_restaurant_pois(response.pois or [])
        logger.info(
            "restaurant recall day=%s center=%s keyword=%s radius=%s raw=%s usable=%s",
            day_index,
            center_anchor.get("name", ""),
            keyword or RESTAURANT_TYPE_CODE,
            radius,
            len(response.pois or []),
            len(ranked_pois),
        )
        for poi in ranked_pois:
            poi_key = poi.id or f"{poi.name}|{poi.address}"
            if poi_key in seen:
                continue
            item = poi_to_restaurant(
                poi,
                keyword=keyword or keywords[0],
                meal_type=meal_type,
                day_index=day_index,
            )
            item_location = parse_location(item.get("location"))
            item["meal_anchor_role"] = meal_anchor_role
            item["meal_anchor_name"] = str(center_anchor.get("name", "") or "").strip()
            if item_location:
                item["distance_to_anchor_km"] = straight_line_distance_km(center, item_location)
            seen.add(poi_key)
            day_items.append(item)
            return True
    return False


def _meal_center_plan(anchors: list[dict[str, Any]]) -> list[tuple[str, str, dict[str, Any]]]:
    if not anchors:
        return []
    if len(anchors) == 1:
        return [
            ("lunch", "first_attraction", anchors[0]),
            ("dinner", "last_attraction", anchors[0]),
        ]
    return [
        ("lunch", "first_attraction", anchors[0]),
        ("dinner", "last_attraction", anchors[-1]),
    ]


async def _search_restaurants(state: TripState) -> list[dict[str, Any]]:
    request = state.get("request", {})
    destination = str(request.get("destination", "") or "")
    base_keyword = _food_keyword(request)
    restaurants: list[dict[str, Any]] = []
    seen: set[str] = set()

    for day_index, anchors in sorted(_day_anchors(state).items()):
        day_items: list[dict[str, Any]] = []
        keywords = _restaurant_keywords_for_day(state, day_index, base_keyword)
        for meal_type, meal_anchor_role, center_anchor in _meal_center_plan(anchors):
            found = await _collect_restaurants_near_anchor(
                center_anchor=center_anchor,
                meal_type=meal_type,
                meal_anchor_role=meal_anchor_role,
                day_index=day_index,
                destination=destination,
                keywords=keywords,
                seen=seen,
                day_items=day_items,
            )
            if found and len(day_items) >= RESTAURANTS_PER_DAY:
                break
        if not day_items:
            raise ValueError(f"nearby restaurant search returned no usable restaurants for day {day_index}")
        restaurants.extend(day_items)

    return restaurants


async def nearby_poi_node(state: TripState) -> dict[str, Any]:
    """Build POI-backed attractions, hotels, and restaurants from verified anchors."""
    attractions = [anchor_to_attraction(anchor) for anchor in state.get("resolved_anchors") or []]
    blockers = evaluate_resource_gate(state)
    if blockers:
        return {
            "attractions": attractions,
            "hotels": [],
            "restaurants": [],
            "planning_blockers": blockers,
            "streaming_updates": "\n周边POI暂停: 缺少已验证锚点中心",
            "completed_agents": ["nearby_poi"],
        }

    try:
        hotels = await _search_hotels(state)
    except ValueError as exc:
        return {
            "attractions": attractions,
            "hotels": [],
            "restaurants": [],
            "planning_blockers": [
                PlanningBlocker(
                    target_agent="nearby_poi_agent",
                    reason_code="missing_usable_hotels",
                    message=str(exc),
                    constraints={},
                ).model_dump()
            ],
            "streaming_updates": f"\n周边POI暂停: {exc}",
            "completed_agents": ["nearby_poi"],
        }

    try:
        restaurants = await _search_restaurants(state)
    except ValueError as exc:
        return {
            "attractions": attractions,
            "hotels": hotels,
            "restaurants": [],
            "planning_blockers": [
                PlanningBlocker(
                    target_agent="nearby_poi_agent",
                    reason_code="missing_usable_restaurants",
                    message=str(exc),
                    constraints={},
                ).model_dump()
            ],
            "streaming_updates": f"\n周边POI暂停: {exc}",
            "completed_agents": ["nearby_poi"],
        }

    logger.info("nearby poi ready attractions=%s hotels=%s restaurants=%s", len(attractions), len(hotels), len(restaurants))
    return {
        "attractions": attractions,
        "hotels": hotels,
        "restaurants": restaurants,
        "planning_blockers": [],
        "streaming_updates": f"\n周边POI完成: 景点{len(attractions)}个, 酒店{len(hotels)}家, 餐厅{len(restaurants)}家",
        "completed_agents": ["nearby_poi"],
    }
