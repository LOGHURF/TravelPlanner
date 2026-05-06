"""Typed contracts passed between travel planning agents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

AnchorKind = Literal["attraction", "area", "hotel_area", "food_area", "transport"]
ResolutionStatus = Literal["resolved", "unresolved", "ambiguous"]

ROAD_LIKE_SUFFIXES = ("路", "大道", "大街", "街道", "公路", "快速路", "高架路")
TRANSPORT_LIKE_SUFFIXES = ("地铁站", "公交站", "火车站", "高铁站", "机场", "客运站", "汽车站", "码头")


def _is_road_like(text: str) -> bool:
    return any(text.endswith(suffix) for suffix in ROAD_LIKE_SUFFIXES)


def _is_transport_like(text: str) -> bool:
    return any(text.endswith(suffix) for suffix in TRANSPORT_LIKE_SUFFIXES)


class StrategyAnchor(BaseModel):
    """A strategy candidate before POI verification."""

    name: str = Field(min_length=1)
    kind: AnchorKind = "attraction"
    required: bool = True
    reason: str = ""

    @field_validator("name", "reason", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> str:
        return str(value or "").strip()

    @model_validator(mode="after")
    def validate_kind_matches_name(self) -> "StrategyAnchor":
        if self.kind == "attraction" and (_is_road_like(self.name) or _is_transport_like(self.name)):
            raise ValueError("road-like anchor cannot be an attraction")
        return self


class AnchorResolution(BaseModel):
    """POI verification result for one strategy anchor."""

    query: str = Field(min_length=1)
    kind: AnchorKind
    status: ResolutionStatus
    required: bool = True
    day_index: int | None = None
    reason_code: str = ""
    message: str = ""
    resolved_anchor: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("query", "reason_code", "message", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> str:
        return str(value or "").strip()

    @model_validator(mode="after")
    def validate_resolution_payload(self) -> "AnchorResolution":
        if self.status == "resolved" and not self.resolved_anchor:
            raise ValueError("resolved anchor requires resolved_anchor")
        if self.status != "resolved" and self.resolved_anchor is not None:
            raise ValueError("non-resolved anchor cannot include resolved_anchor")
        return self


class PlanningBlocker(BaseModel):
    """A business blocker that should be handled by orchestration, not an exception."""

    target_agent: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    constraints: dict[str, Any] = Field(default_factory=dict)

    @field_validator("target_agent", "reason_code", "message", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> str:
        return str(value or "").strip()


def strategy_anchor_from_value(value: Any) -> StrategyAnchor:
    """Normalize legacy strategy anchor values at the boundary."""
    if isinstance(value, StrategyAnchor):
        return value
    if isinstance(value, dict):
        return StrategyAnchor.model_validate(value)
    raise ValueError("strategy anchor must be an object")
