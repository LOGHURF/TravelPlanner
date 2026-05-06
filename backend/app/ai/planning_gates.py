"""Deterministic gates for deciding whether planning can continue."""

from __future__ import annotations

from typing import Any

from app.ai.models.graph_models import TripState
from app.ai.models.planning_contracts import PlanningBlocker


def _request_days(state: TripState) -> int:
    request = state.get("request", {})
    return max(1, int(request.get("days", request.get("duration", 1)) or 1))


def _strategy_day_indexes(state: TripState) -> list[int]:
    strategy = state.get("strategy_plan") if isinstance(state.get("strategy_plan"), dict) else {}
    daily_area_plan = strategy.get("daily_area_plan") if isinstance(strategy, dict) else []
    indexes: list[int] = []
    for day in daily_area_plan or []:
        if not isinstance(day, dict):
            continue
        day_index = int(day.get("day_index", 0) or 0)
        if day_index > 0 and day_index not in indexes:
            indexes.append(day_index)
    return indexes or list(range(1, _request_days(state) + 1))


def _resolved_attraction_days(state: TripState) -> set[int]:
    days: set[int] = set()
    for anchor in state.get("resolved_anchors") or []:
        if not isinstance(anchor, dict):
            continue
        day_index = int(anchor.get("day_index", 0) or 0)
        if day_index > 0:
            days.add(day_index)
    return days


def _unresolved_required_names_by_day(state: TripState) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for item in state.get("anchor_resolution_results") or []:
        if not isinstance(item, dict):
            continue
        if item.get("status") != "unresolved":
            continue
        if item.get("kind") != "attraction" or item.get("required") is False:
            continue
        day_index = int(item.get("day_index", 0) or 0)
        if day_index <= 0:
            continue
        query = str(item.get("query", "") or "").strip()
        if query:
            result.setdefault(day_index, []).append(query)
    return result


def evaluate_anchor_gate(state: TripState) -> list[dict[str, Any]]:
    """Return blockers when verified attraction anchors are insufficient."""
    resolved_days = _resolved_attraction_days(state)
    unresolved_by_day = _unresolved_required_names_by_day(state)
    blockers: list[dict[str, Any]] = []
    for day_index in _strategy_day_indexes(state):
        if day_index in resolved_days:
            continue
        blockers.append(
            PlanningBlocker(
                target_agent="strategy_agent",
                reason_code="insufficient_resolved_attractions",
                message=f"第{day_index}天缺少可用景点锚点",
                constraints={
                    "day_index": day_index,
                    "unresolved_names": unresolved_by_day.get(day_index, []),
                    "required_kind": "attraction",
                },
            ).model_dump()
        )
    return blockers


def evaluate_resource_gate(state: TripState) -> list[dict[str, Any]]:
    """Return blockers for missing resource prerequisites before downstream planning."""
    if not state.get("resolved_anchors"):
        return [
            PlanningBlocker(
                target_agent="anchor_resolver_agent",
                reason_code="missing_resolved_anchor_center",
                message="缺少可用于周边 POI 搜索的已验证锚点",
                constraints={},
            ).model_dump()
        ]
    return []
