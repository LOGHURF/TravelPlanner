import asyncio

from app.ai.nodes.anchor_resolver_node import anchor_resolver_node
from app.services.amap import POISearchResponse


def _empty_response() -> POISearchResponse:
    return POISearchResponse(status="1", info="OK", infocode="10000", count=0, pois=[])


def test_anchor_resolver_returns_unresolved_area_without_raising(monkeypatch) -> None:
    async def fake_search(**kwargs):
        return _empty_response()

    monkeypatch.setattr("app.ai.nodes.anchor_resolver_node.search_pois_by_text", fake_search)

    state = {
        "request": {"destination": "杭州", "days": 1},
        "strategy_plan": {
            "daily_area_plan": [
                {
                    "day_index": 1,
                    "area_name": "市中心",
                    "required_anchors": [
                        {"name": "人民路", "kind": "area", "required": False}
                    ],
                }
            ],
            "hotel_area_keywords": [],
        },
    }

    result = asyncio.run(anchor_resolver_node(state))

    assert result["resolved_anchors"] == []
    assert result["anchor_resolution_results"][0]["query"] == "人民路"
    assert result["anchor_resolution_results"][0]["status"] == "unresolved"
    assert result["planning_blockers"] == []


def test_anchor_resolver_blocks_required_attraction_when_unresolved(monkeypatch) -> None:
    async def fake_search(**kwargs):
        return _empty_response()

    monkeypatch.setattr("app.ai.nodes.anchor_resolver_node.search_pois_by_text", fake_search)

    state = {
        "request": {"destination": "杭州", "days": 1},
        "strategy_plan": {
            "daily_area_plan": [
                {
                    "day_index": 1,
                    "area_name": "西湖",
                    "required_anchors": [
                        {"name": "不存在景点", "kind": "attraction", "required": True}
                    ],
                }
            ],
            "hotel_area_keywords": [],
        },
    }

    result = asyncio.run(anchor_resolver_node(state))

    assert result["resolved_anchors"] == []
    assert result["anchor_resolution_results"][0]["status"] == "unresolved"
    assert result["planning_blockers"][0]["target_agent"] == "strategy_agent"
    assert result["planning_blockers"][0]["reason_code"] == "insufficient_resolved_attractions"
