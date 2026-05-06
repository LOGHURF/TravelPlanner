"""策略规划节点：在 POI 查询前生成城市片区和锚点骨架。"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.ai.models.graph_models import TripState
from app.ai.models.planning_contracts import PlanningBlocker, StrategyAnchor
from app.ai.utils import invoke_prompt_json_async
from app.config import get_logger

logger = get_logger("StrategyPlanner")


class DailyAreaPlanOutput(BaseModel):
    day_index: int = Field(ge=1)
    area_name: str
    required_anchors: list[StrategyAnchor] = Field(min_length=1)
    restaurant_area_keywords: list[str] = Field(default_factory=list)
    reason: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_required_anchors(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("daily area plan entry must be an object")
        anchors = data.get("required_anchors")
        if not isinstance(anchors, list) or not anchors:
            raise ValueError("each daily area must contain at least one anchor")

        normalized: list[dict[str, Any]] = []
        for anchor in anchors:
            if isinstance(anchor, str):
                raise ValueError("daily required anchors must be objects")
            if not isinstance(anchor, dict):
                raise ValueError("daily required anchors must be objects")
            if str(anchor.get("kind", "attraction") or "attraction") != "attraction":
                raise ValueError("daily required anchors must use kind=attraction")
            normalized.append(
                {
                    "name": anchor.get("name", ""),
                    "kind": "attraction",
                    "required": True,
                    "reason": anchor.get("reason", data.get("reason", "")),
                }
            )
        data["required_anchors"] = normalized
        return data


class StrategyPlanOutput(BaseModel):
    trip_theme: str
    daily_area_plan: list[DailyAreaPlanOutput] = Field(min_length=1)
    hotel_area_keywords: list[StrategyAnchor] = Field(default_factory=list)
    avoid_rules: list[str] = Field(default_factory=list)
    planning_notes: list[str] = Field(default_factory=list)

    @field_validator("hotel_area_keywords", mode="before")
    @classmethod
    def normalize_hotel_area_keywords(cls, value: Any) -> list[dict[str, Any]]:
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise ValueError("hotel_area_keywords must be a list")

        normalized: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, str):
                raise ValueError("hotel area keywords must be objects")
            if not isinstance(item, dict):
                raise ValueError("hotel area keywords must be objects")
            normalized.append(
                {
                    "name": item.get("name", ""),
                    "kind": "hotel_area",
                    "required": False,
                    "reason": item.get("reason", ""),
                }
            )
        return normalized

    @model_validator(mode="after")
    def validate_anchor_contracts(self) -> "StrategyPlanOutput":
        normalized_hotels: list[StrategyAnchor] = []
        for anchor in self.hotel_area_keywords:
            if not isinstance(anchor, StrategyAnchor):
                raise ValueError("hotel area keywords must be structured anchors")
            normalized_hotels.append(
                StrategyAnchor.model_validate(
                    {
                        "name": anchor.name,
                        "kind": "hotel_area",
                        "required": False,
                        "reason": anchor.reason,
                    }
                )
            )
        self.hotel_area_keywords = normalized_hotels[:4]
        return self


def _request_context(state: TripState) -> dict[str, Any]:
    request = state.get("request", {})
    return {
        "destination": request.get("destination", ""),
        "origin": request.get("origin", ""),
        "days": request.get("days", request.get("duration", 1)),
        "companions": request.get("companions", state.get("companions", "")),
        "pace": request.get("pace", state.get("pace", "")),
        "style_preferences": request.get("style_preferences", state.get("style_preferences", [])),
        "hotel_level": request.get("hotel_level", state.get("hotel_level", "")),
        "special_requirements": request.get("special_requirements", ""),
    }


def _strategy_contract_blocker(message: str) -> dict[str, Any]:
    return PlanningBlocker(
        target_agent="strategy_agent",
        reason_code="invalid_strategy_contract",
        message="策略输出不符合可验证锚点契约",
        constraints={"validation_error": message[:500]},
    ).model_dump()


async def strategy_node(state: TripState) -> dict[str, Any]:
    """Generate a route skeleton made of daily areas and anchor names."""
    request_context = _request_context(state)
    days = int(request_context.get("days", 1) or 1)
    data = await invoke_prompt_json_async(
        prompt_id="travel_strategy",
        variables={
            "request_context_json": json.dumps(request_context, ensure_ascii=False),
            "days": days,
        },
        temperature=0.25,
        max_tokens=1400,
    )
    try:
        strategy = StrategyPlanOutput.model_validate(data).model_dump()
    except ValidationError as exc:
        logger.warning("strategy contract invalid: %s", exc)
        return {
            "strategy_plan": {},
            "planning_blockers": [_strategy_contract_blocker(str(exc))],
            "streaming_updates": "\n策略输出未通过结构化校验，等待重新生成",
            "completed_agents": ["strategy"],
        }
    if len(strategy["daily_area_plan"]) != days:
        return {
            "strategy_plan": {},
            "planning_blockers": [
                _strategy_contract_blocker(
                    f"strategy returned {len(strategy['daily_area_plan'])} days, expected {days}"
                )
            ],
            "streaming_updates": "\n策略天数未通过结构化校验，等待重新生成",
            "completed_agents": ["strategy"],
        }

    logger.info(
        "strategy ready theme=%s days=%s hotel_areas=%s",
        strategy.get("trip_theme", ""),
        days,
        strategy.get("hotel_area_keywords", []),
    )
    return {
        "strategy_plan": strategy,
        "planning_blockers": [],
        "streaming_updates": f"\n策略完成: {days}天片区骨架",
        "completed_agents": ["strategy"],
    }
