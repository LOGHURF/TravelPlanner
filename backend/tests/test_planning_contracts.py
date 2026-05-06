import pytest
from pydantic import ValidationError

from app.ai.models.planning_contracts import AnchorResolution, StrategyAnchor, strategy_anchor_from_value


def test_strategy_anchor_rejects_road_as_attraction() -> None:
    with pytest.raises(ValidationError, match="road-like anchor cannot be an attraction"):
        StrategyAnchor(name="人民路", kind="attraction")


def test_strategy_anchor_allows_road_as_area() -> None:
    anchor = StrategyAnchor(name="人民路", kind="area", required=False)

    assert anchor.name == "人民路"
    assert anchor.kind == "area"
    assert anchor.required is False


def test_unresolved_anchor_resolution_is_structured_business_result() -> None:
    resolution = AnchorResolution(
        query="人民路",
        kind="area",
        status="unresolved",
        reason_code="no_poi_match",
    )

    assert resolution.status == "unresolved"
    assert resolution.reason_code == "no_poi_match"
    assert resolution.resolved_anchor is None


def test_strategy_anchor_from_value_rejects_legacy_string_contract() -> None:
    with pytest.raises(ValueError, match="strategy anchor must be an object"):
        strategy_anchor_from_value("西湖风景名胜区")
