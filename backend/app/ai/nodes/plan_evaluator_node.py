"""Plan evaluator node: review the complete trip draft and request targeted repairs."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.ai.models.graph_models import TripState
from app.ai.demo_data import evaluation as demo_evaluation
from app.ai.nodes.plan_data_utils import straight_line_distance_km
from app.ai.utils import invoke_prompt_json_async, parse_location
from app.config import get_logger, settings

logger = get_logger("PlanEvaluator")

EVALUATION_PASS_THRESHOLD = 0.85
MEAL_ANCHOR_MAX_KM = 3.0
ALLOWED_REPAIR_AGENTS = {
    "strategy_agent",
    "anchor_resolver_agent",
    "nearby_poi_agent",
    "route_matrix_agent",
    "itinerary_composer_agent",
    "weather_agent",
}
ALLOWED_REPAIR_TASKS = {
    "strategy_agent": {
        "regenerate_area_strategy",
        "restore_required_preferences",
    },
    "anchor_resolver_agent": {
        "resolve_missing_anchors",
        "disambiguate_bad_poi_types",
    },
    "weather_agent": {
        "refresh_weather_risk",
    },
    "nearby_poi_agent": {
        "search_hotels_near_strategy_area",
        "search_restaurants_near_day_anchors",
    },
    "route_matrix_agent": {
        "rebuild_route_matrix",
        "replace_blocked_legs",
    },
    "itinerary_composer_agent": {
        "recompose_daily_plan",
    },
}


class RepairTaskOutput(BaseModel):
    agent: str
    task: str
    reason: str
    constraints: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_task_for_agent(self) -> "RepairTaskOutput":
        if self.agent not in ALLOWED_REPAIR_AGENTS:
            raise ValueError(f"unknown repair agent: {self.agent}")
        allowed_tasks = ALLOWED_REPAIR_TASKS[self.agent]
        if self.task not in allowed_tasks:
            raise ValueError(f"unknown repair task for {self.agent}: {self.task}")
        if not self.reason.strip():
            raise ValueError("repair task reason is required")
        return self


class PlanEvaluationOutput(BaseModel):
    passed: bool
    score: float = Field(ge=0, le=1)
    dimensions: dict[str, float] = Field(default_factory=dict)
    blocking_issues: list[str] = Field(default_factory=list)
    repair_tasks: list[RepairTaskOutput] = Field(default_factory=list)
    residual_risks: list[str] = Field(default_factory=list)

    @field_validator("dimensions")
    @classmethod
    def validate_dimension_scores(cls, value: dict[str, float]) -> dict[str, float]:
        for name, score in value.items():
            if float(score) < 0 or float(score) > 1:
                raise ValueError(f"dimension score out of range: {name}")
        return value

    @model_validator(mode="after")
    def validate_pass_contract(self) -> "PlanEvaluationOutput":
        if self.passed and self.blocking_issues:
            raise ValueError("passed evaluation cannot contain blocking issues")
        if self.passed and self.score < EVALUATION_PASS_THRESHOLD:
            raise ValueError("passed evaluation score is below threshold")
        if not self.passed and not self.repair_tasks:
            raise ValueError("failed evaluation requires repair tasks")
        return self


def _compact_items(items: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    return [
        {
            "name": item.get("name", ""),
            "address": item.get("address", ""),
            "location": item.get("location"),
            "rating": item.get("rating", 0),
            "category": item.get("category", "") or item.get("type", ""),
            "price": item.get("price_per_night", item.get("price_per_person", item.get("ticket_price", 0))),
            "meal_type": item.get("meal_type", ""),
        }
        for item in items[:limit]
    ]


def _build_plan_context(state: TripState) -> dict[str, Any]:
    request = state.get("request", {})
    transport = state.get("transport") or {}
    return {
        "request": {
            "destination": request.get("destination", ""),
            "origin": request.get("origin", ""),
            "days": request.get("days", request.get("duration", 0)),
            "companions": request.get("companions", state.get("companions", "")),
            "pace": request.get("pace", state.get("pace", "")),
            "style_preferences": request.get("style_preferences", state.get("style_preferences", [])),
            "hotel_level": request.get("hotel_level", state.get("hotel_level", "")),
            "budget_per_person": request.get("budget_per_person", 0),
            "num_people": request.get("num_people", 1),
            "special_requirements": request.get("special_requirements", ""),
        },
        "attractions": _compact_items(list(state.get("attractions") or [])),
        "hotels": _compact_items(list(state.get("hotels") or [])),
        "restaurants": _compact_items(list(state.get("restaurants") or [])),
        "weather": list(state.get("weather") or [])[:10],
        "strategy_plan": state.get("strategy_plan") or {},
        "resolved_anchors": state.get("resolved_anchors") or [],
        "hotel_area_anchors": state.get("hotel_area_anchors") or [],
        "route_matrix": state.get("route_matrix") or {},
        "transport": {
            "estimated_transport_cost": transport.get("estimated_transport_cost", 0),
            "suggested_mode": transport.get("suggested_mode", ""),
            "planning_reason": transport.get("planning_reason", ""),
            "daily_plan": transport.get("daily_plan", []),
            "daily_routes": transport.get("daily_routes", []),
            "route_issues": transport.get("route_issues", []),
        },
    }


def _task(agent: str, task: str, reason: str, constraints: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "agent": agent,
        "task": task,
        "reason": reason,
        "constraints": constraints or {},
    }


def _located_attractions(day: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in day.get("attractions") or [] if parse_location(item.get("location"))]


def _meal_anchor_for_day(day: dict[str, Any], meal_type: str) -> dict[str, Any] | None:
    attractions = _located_attractions(day)
    if not attractions:
        return None
    if meal_type == "lunch":
        return attractions[0]
    if meal_type == "dinner":
        return attractions[-1]
    return None


def _distance_between_meal_and_anchor(meal: dict[str, Any], anchor: dict[str, Any]) -> float | None:
    meal_location = parse_location(meal.get("location"))
    anchor_location = parse_location(anchor.get("location"))
    if not meal_location or not anchor_location:
        return None
    return straight_line_distance_km(anchor_location, meal_location)


def _meal_distance_issues(transport: dict[str, Any]) -> list[str]:
    daily_plan = transport.get("daily_plan") if isinstance(transport, dict) else []
    if not isinstance(daily_plan, list):
        return []

    labels = {"lunch": "午餐", "dinner": "晚餐"}
    issues: list[str] = []
    for day in daily_plan:
        if not isinstance(day, dict):
            continue
        day_index = int(day.get("day_index", 0) or 0)
        for meal in day.get("meals") or []:
            if not isinstance(meal, dict):
                continue
            meal_type = str(meal.get("meal_type", meal.get("type", ""))).strip().lower()
            if meal_type not in labels:
                continue
            anchor = _meal_anchor_for_day(day, meal_type)
            if not anchor:
                continue
            distance = _distance_between_meal_and_anchor(meal, anchor)
            if distance is None or distance <= MEAL_ANCHOR_MAX_KM:
                continue
            issues.append(
                f"第{day_index}天{labels[meal_type]}{meal.get('name', '')}"
                f"距离{anchor.get('name', '')}{distance:.1f}km，超过{MEAL_ANCHOR_MAX_KM:.1f}km"
            )
    return issues


def _hard_gate_evaluation(state: TripState) -> PlanEvaluationOutput | None:
    strategy = state.get("strategy_plan") if isinstance(state.get("strategy_plan"), dict) else {}
    route_matrix = state.get("route_matrix") if isinstance(state.get("route_matrix"), dict) else {}
    transport = state.get("transport") if isinstance(state.get("transport"), dict) else {}
    issues: list[str] = []
    tasks: list[dict[str, Any]] = []

    daily_area_plan = strategy.get("daily_area_plan") if isinstance(strategy, dict) else None
    if not isinstance(daily_area_plan, list) or not daily_area_plan:
        issues.append("缺少每日片区策略")
        tasks.append(_task("strategy_agent", "regenerate_area_strategy", "必须先生成每日片区和锚点策略"))

    resolved_queries = {
        str(anchor.get("query", "") or "").strip()
        for anchor in state.get("resolved_anchors") or []
        if isinstance(anchor, dict)
    }
    missing_anchors: list[str] = []
    if isinstance(daily_area_plan, list):
        for day in daily_area_plan:
            if not isinstance(day, dict):
                continue
            for anchor in day.get("required_anchors") or []:
                text = str(anchor).strip()
                if text and text not in resolved_queries:
                    missing_anchors.append(text)
    if missing_anchors:
        issues.append(f"策略锚点未被 POI 验证: {', '.join(missing_anchors[:5])}")
        tasks.append(
            _task(
                "anchor_resolver_agent",
                "resolve_missing_anchors",
                "所有策略锚点必须先解析到 POI",
                {"missing_anchors": missing_anchors},
            )
        )

    if not state.get("hotels"):
        issues.append("缺少可用酒店 POI")
        tasks.append(_task("nearby_poi_agent", "search_hotels_near_strategy_area", "住宿必须围绕策略片区召回"))
    if not state.get("restaurants"):
        issues.append("缺少可用餐饮 POI")
        tasks.append(_task("nearby_poi_agent", "search_restaurants_near_day_anchors", "餐饮必须围绕每日锚点召回"))

    meal_distance_issues = _meal_distance_issues(transport)
    if meal_distance_issues:
        issues.append("餐厅距离日内锚点过远")
        tasks.append(
            _task(
                "nearby_poi_agent",
                "search_restaurants_near_day_anchors",
                "午餐必须靠近日内第一锚点，晚餐必须靠近日内最后锚点",
                {
                    "max_distance_km": MEAL_ANCHOR_MAX_KM,
                    "meal_distance_issues": meal_distance_issues,
                },
            )
        )

    matrix_issues = route_matrix.get("issues", []) if isinstance(route_matrix, dict) else []
    transport_issues = transport.get("route_issues", []) if isinstance(transport, dict) else []
    if matrix_issues or transport_issues:
        issues.append("存在未通过路线验证的日内交通段")
        tasks.append(
            _task(
                "route_matrix_agent",
                "rebuild_route_matrix",
                "路线矩阵中的 blocked/unavailable 路段必须修复",
                {"route_issues": matrix_issues or transport_issues},
            )
        )

    if not transport.get("daily_plan") if isinstance(transport, dict) else True:
        issues.append("缺少已组合的每日行程")
        tasks.append(_task("itinerary_composer_agent", "recompose_daily_plan", "必须基于已验证 POI 组合每日行程"))

    if not issues:
        return None

    unique_tasks: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in tasks:
        key = (item["agent"], item["task"])
        if key in seen:
            continue
        seen.add(key)
        unique_tasks.append(item)

    return PlanEvaluationOutput.model_validate(
        {
            "passed": False,
            "score": 0.35,
            "dimensions": {
                "completeness": 0.2,
                "preference_fit": 0.5,
                "route_efficiency": 0.2,
                "poi_confidence": 0.4,
            },
            "blocking_issues": issues,
            "repair_tasks": unique_tasks,
            "residual_risks": [],
        }
    )


def _repair_targets(tasks: list[RepairTaskOutput]) -> list[str]:
    targets: list[str] = []
    for task in tasks:
        if task.agent not in ALLOWED_REPAIR_AGENTS:
            raise ValueError(f"unknown repair agent: {task.agent}")
        if task.agent not in targets:
            targets.append(task.agent)
    return targets


def _repair_task_from_blocker(blocker: dict[str, Any]) -> dict[str, Any] | None:
    agent = str(blocker.get("target_agent", "") or "").strip()
    reason_code = str(blocker.get("reason_code", "") or "").strip()
    message = str(blocker.get("message", "") or "").strip()
    constraints = blocker.get("constraints", {})
    if not isinstance(constraints, dict):
        constraints = {}

    task_map = {
        ("strategy_agent", "insufficient_resolved_attractions"): "regenerate_area_strategy",
        ("strategy_agent", "invalid_strategy_contract"): "regenerate_area_strategy",
        ("anchor_resolver_agent", "missing_resolved_anchor_center"): "resolve_missing_anchors",
        ("anchor_resolver_agent", "insufficient_resolved_attractions"): "resolve_missing_anchors",
        ("anchor_resolver_agent", "no_poi_match"): "resolve_missing_anchors",
        ("anchor_resolver_agent", "invalid_anchor_contract"): "disambiguate_bad_poi_types",
        ("nearby_poi_agent", "missing_usable_hotels"): "search_hotels_near_strategy_area",
        ("nearby_poi_agent", "missing_usable_restaurants"): "search_restaurants_near_day_anchors",
        ("route_matrix_agent", "route_issues"): "rebuild_route_matrix",
        ("itinerary_composer_agent", "transport_gap"): "recompose_daily_plan",
        ("weather_agent", "weather_gap"): "refresh_weather_risk",
    }

    task = task_map.get((agent, reason_code))
    if not task:
        return None

    return _task(agent, task, message or reason_code or "planning blocker", constraints)


def _blocker_evaluation(state: TripState) -> PlanEvaluationOutput | None:
    blockers = [item for item in state.get("planning_blockers") or [] if isinstance(item, dict)]
    if not blockers:
        return None

    repair_tasks = [task for blocker in blockers if (task := _repair_task_from_blocker(blocker))]
    blocking_issues = [str(blocker.get("message", "") or blocker.get("reason_code", "")).strip() for blocker in blockers]
    return PlanEvaluationOutput.model_validate(
        {
            "passed": False,
            "score": 0.25,
            "dimensions": {
                "completeness": 0.1,
                "preference_fit": 0.6,
                "route_efficiency": 0.5,
                "poi_confidence": 0.2,
            },
            "blocking_issues": blocking_issues,
            "repair_tasks": repair_tasks
            or [
                _task(
                    "strategy_agent",
                    "regenerate_area_strategy",
                    "规划阻塞缺少可映射修复任务，重新生成策略",
                    {"blockers": blockers},
                )
            ],
            "residual_risks": [],
        }
    )


def _text_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _advisory_pass_from_llm(data: dict[str, Any]) -> PlanEvaluationOutput:
    """Convert the LLM judge into advisory risks after deterministic gates pass."""
    residual_risks = _text_items(data.get("residual_risks"))
    for issue in _text_items(data.get("blocking_issues")):
        if issue not in residual_risks:
            residual_risks.append(issue)

    repair_tasks = data.get("repair_tasks")
    if isinstance(repair_tasks, list):
        for task in repair_tasks:
            if not isinstance(task, dict):
                continue
            reason = str(task.get("reason", "") or "").strip()
            if reason and reason not in residual_risks:
                residual_risks.append(reason)

    raw_score = float(data.get("score", EVALUATION_PASS_THRESHOLD) or EVALUATION_PASS_THRESHOLD)
    dimensions = data.get("dimensions") if isinstance(data.get("dimensions"), dict) else {}
    return PlanEvaluationOutput.model_validate(
        {
            "passed": True,
            "score": max(raw_score, EVALUATION_PASS_THRESHOLD),
            "dimensions": dimensions,
            "blocking_issues": [],
            "repair_tasks": [],
            "residual_risks": residual_risks[:8],
        }
    )


async def plan_evaluator_node(state: TripState) -> dict[str, Any]:
    """Evaluate the full plan and produce targeted repair tasks."""
    planning_iteration = int(state.get("planning_iteration", 0) or 0)
    max_iterations = int(state.get("max_planning_iterations", 3) or 3)
    if settings.DEMO_MODE:
        evaluation_payload = demo_evaluation()
        history = list(state.get("evaluation_history") or [])
        history.append(evaluation_payload)
        logger.info("demo plan evaluation passed score=%.2f", evaluation_payload["score"])
        return {
            "evaluation": evaluation_payload,
            "evaluation_history": history,
            "active_repair_tasks": [],
            "repair_targets": [],
            "streaming_updates": f"\n演示方案审核通过: score={evaluation_payload['score']:.2f}",
            "completed_agents": ["plan_evaluator"],
        }

    context = _build_plan_context(state)
    evaluation = _blocker_evaluation(state)
    if evaluation is None:
        evaluation = _hard_gate_evaluation(state)
    if evaluation is None:
        data = await invoke_prompt_json_async(
            prompt_id="plan_evaluator",
            variables={
                "pass_threshold": EVALUATION_PASS_THRESHOLD,
                "planning_iteration": planning_iteration,
                "max_planning_iterations": max_iterations,
                "plan_context_json": json.dumps(context, ensure_ascii=False),
            },
            temperature=0.2,
            max_tokens=1200,
        )
        evaluation = _advisory_pass_from_llm(data)
    evaluation_payload = evaluation.model_dump()
    targets = _repair_targets(evaluation.repair_tasks)
    history = list(state.get("evaluation_history") or [])
    history.append(evaluation_payload)

    status_text = "通过" if evaluation.passed else "需要修复"
    logger.info(
        "plan evaluation %s score=%.2f targets=%s iteration=%s/%s",
        status_text,
        evaluation.score,
        targets,
        planning_iteration,
        max_iterations,
    )

    return {
        "evaluation": evaluation_payload,
        "evaluation_history": history,
        "active_repair_tasks": evaluation_payload["repair_tasks"],
        "repair_targets": targets,
        "streaming_updates": f"\n方案审核{status_text}: score={evaluation.score:.2f}",
        "completed_agents": ["plan_evaluator"],
    }
