"""锚点验真节点：用高德 POI 验证策略锚点。"""

from __future__ import annotations

from typing import Any

from app.ai.models.graph_models import TripState
from app.ai.models.planning_contracts import AnchorResolution, PlanningBlocker, StrategyAnchor, strategy_anchor_from_value
from app.ai.nodes.plan_data_utils import anchor_from_poi
from app.ai.poi_types import ATTRACTION_TYPE_CODES
from app.config import get_logger, settings
from app.ai.demo_data import resolved_anchors as demo_resolved_anchors
from app.services.amap import POI, search_pois_by_text

logger = get_logger("AnchorResolver")

BLOCKED_ATTRACTION_TYPE_PREFIXES = ("05", "10", "12", "13", "15", "16", "17", "19")
AREA_ANCHOR_SUFFIXES = ("村", "街", "街区", "片区", "商圈", "古镇")


def _is_area_anchor(query: str) -> bool:
    text = str(query or "").strip()
    return any(text.endswith(suffix) for suffix in AREA_ANCHOR_SUFFIXES)


def _is_valid_attraction_poi(poi: POI, *, query: str) -> bool:
    code = str(poi.typecode or "")
    return not code.startswith(BLOCKED_ATTRACTION_TYPE_PREFIXES)


def _display_name(anchor: StrategyAnchor, poi: POI) -> str:
    if anchor.kind != "attraction" and not str(poi.typecode or "").startswith(BLOCKED_ATTRACTION_TYPE_PREFIXES):
        return anchor.name
    if _is_area_anchor(anchor.name) and not str(poi.typecode or "").startswith(BLOCKED_ATTRACTION_TYPE_PREFIXES):
        return anchor.name
    return poi.name


def _query_variants(query: str, destination: str) -> list[str]:
    base = [query]
    if destination and destination not in query:
        base.append(f"{destination}{query}")
    if query.endswith("村"):
        base.extend([f"{query}景区", f"{query}茶园"])
    result: list[str] = []
    for item in base:
        text = item.strip()
        if text and text not in result:
            result.append(text)
    return result


def _search_types_for_anchor(anchor: StrategyAnchor) -> str:
    if anchor.kind == "attraction":
        return ATTRACTION_TYPE_CODES
    return ""


async def _resolve_one_anchor(
    *,
    anchor: StrategyAnchor,
    destination: str,
    day_index: int | None,
    role: str,
) -> AnchorResolution:
    for search_query in _query_variants(anchor.name, destination):
        response = await search_pois_by_text(
            keywords=search_query,
            types=_search_types_for_anchor(anchor),
            region=destination,
            citylimit=True,
            offset=8,
        )
        for rank, poi in enumerate(response.pois or []):
            confidence = max(0.55, 0.98 - rank * 0.08)
            if anchor.kind == "attraction" and not _is_valid_attraction_poi(poi, query=anchor.name):
                continue
            resolved_anchor = anchor_from_poi(
                query=anchor.name,
                day_index=day_index,
                role=role,
                poi=poi,
                confidence=confidence,
                display_name=_display_name(anchor, poi),
            )
            return AnchorResolution(
                query=anchor.name,
                kind=anchor.kind,
                status="resolved",
                required=anchor.required,
                day_index=day_index,
                resolved_anchor=resolved_anchor,
            )
    return AnchorResolution(
        query=anchor.name,
        kind=anchor.kind,
        status="unresolved",
        required=anchor.required,
        day_index=day_index,
        reason_code="no_poi_match",
        message=f"未能解析到可用 POI: {anchor.name}",
    )


def _invalid_anchor_resolution(*, value: Any, day_index: int | None, message: str) -> AnchorResolution:
    return AnchorResolution(
        query=str(value or "").strip() or "invalid_anchor",
        kind="attraction",
        status="unresolved",
        required=True,
        day_index=day_index,
        reason_code="invalid_anchor_contract",
        message=message,
    )


def _blockers_for_resolutions(resolutions: list[AnchorResolution]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    unresolved_required = [
        item
        for item in resolutions
        if item.kind == "attraction" and item.required and item.status != "resolved"
    ]
    by_day: dict[int, list[str]] = {}
    for item in unresolved_required:
        day_index = int(item.day_index or 0)
        if day_index > 0:
            by_day.setdefault(day_index, []).append(item.query)

    for day_index, names in sorted(by_day.items()):
        blockers.append(
            PlanningBlocker(
                target_agent="strategy_agent",
                reason_code="insufficient_resolved_attractions",
                message=f"第{day_index}天缺少可用景点锚点",
                constraints={
                    "day_index": day_index,
                    "unresolved_names": names,
                    "required_kind": "attraction",
                },
            ).model_dump()
        )
    return blockers


async def anchor_resolver_node(state: TripState) -> dict[str, Any]:
    """Resolve strategy anchor names to concrete POI-backed anchors."""
    request = state.get("request", {})
    destination = str(request.get("destination", "") or "").strip()
    strategy = state.get("strategy_plan") or {}
    daily_area_plan = strategy.get("daily_area_plan") if isinstance(strategy, dict) else None
    if not isinstance(daily_area_plan, list) or not daily_area_plan:
        raise ValueError("anchor resolver requires strategy_plan.daily_area_plan")

    if settings.DEMO_MODE:
        resolved, hotel_areas, results = demo_resolved_anchors(request, strategy)
        logger.info("demo anchors resolved attractions=%s hotel_areas=%s", len(resolved), len(hotel_areas))
        return {
            "resolved_anchors": resolved,
            "hotel_area_anchors": hotel_areas,
            "anchor_resolution_results": results,
            "planning_blockers": [],
            "streaming_updates": f"\n演示锚点验证完成: {len(resolved)}个景点锚点, {len(hotel_areas)}个住宿片区",
            "completed_agents": ["anchor_resolver"],
        }

    resolved_anchors: list[dict[str, Any]] = []
    resolution_results: list[AnchorResolution] = []
    for day in daily_area_plan:
        if not isinstance(day, dict):
            raise ValueError("daily area plan entry must be an object")
        day_index = int(day.get("day_index", 0) or 0)
        for value in day.get("required_anchors") or []:
            try:
                strategy_anchor = strategy_anchor_from_value(value)
            except ValueError as exc:
                resolution_results.append(
                    _invalid_anchor_resolution(value=value, day_index=day_index, message=str(exc))
                )
                continue
            resolution = await _resolve_one_anchor(
                anchor=strategy_anchor,
                destination=destination,
                day_index=day_index,
                role="attraction",
            )
            resolution_results.append(resolution)
            if resolution.status == "resolved" and resolution.resolved_anchor:
                resolved_anchors.append(resolution.resolved_anchor)

    hotel_area_anchors: list[dict[str, Any]] = []
    for value in strategy.get("hotel_area_keywords") or []:
        try:
            hotel_anchor = strategy_anchor_from_value(value)
            hotel_anchor = StrategyAnchor(
                name=hotel_anchor.name,
                kind="hotel_area",
                required=False,
                reason=hotel_anchor.reason,
            )
        except ValueError as exc:
            resolution_results.append(_invalid_anchor_resolution(value=value, day_index=None, message=str(exc)))
            continue
        resolution = await _resolve_one_anchor(
            anchor=hotel_anchor,
            destination=destination,
            day_index=None,
            role="hotel_area",
        )
        resolution_results.append(resolution)
        if resolution.status == "resolved" and resolution.resolved_anchor:
            hotel_area_anchors.append(resolution.resolved_anchor)

    blockers = _blockers_for_resolutions(resolution_results)
    unresolved_count = len([item for item in resolution_results if item.status != "resolved"])
    logger.info(
        "anchors resolved attractions=%s hotel_areas=%s unresolved=%s blockers=%s",
        len(resolved_anchors),
        len(hotel_area_anchors),
        unresolved_count,
        len(blockers),
    )
    return {
        "resolved_anchors": resolved_anchors,
        "hotel_area_anchors": hotel_area_anchors,
        "anchor_resolution_results": [item.model_dump() for item in resolution_results],
        "planning_blockers": blockers,
        "streaming_updates": (
            f"\n锚点验证完成: {len(resolved_anchors)}个景点锚点, "
            f"{len(hotel_area_anchors)}个住宿片区, {unresolved_count}个未命中"
        ),
        "completed_agents": ["anchor_resolver"],
    }
