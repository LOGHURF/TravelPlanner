import asyncio

from app.ai.nodes.strategy_node import strategy_node


def test_strategy_node_returns_blocker_for_legacy_string_anchors(monkeypatch) -> None:
    async def fake_prompt(*, prompt_id, variables, temperature, max_tokens):
        return {
            "trip_theme": "旧格式",
            "daily_area_plan": [
                {
                    "day_index": 1,
                    "area_name": "西湖",
                    "required_anchors": ["西湖风景名胜区"],
                    "restaurant_area_keywords": ["湖滨"],
                    "reason": "旧字符串格式",
                }
            ],
            "hotel_area_keywords": [{"name": "湖滨", "kind": "hotel_area", "required": False}],
            "avoid_rules": [],
            "planning_notes": [],
        }

    monkeypatch.setattr("app.ai.nodes.strategy_node.invoke_prompt_json_async", fake_prompt)

    result = asyncio.run(strategy_node({"request": {"destination": "杭州", "days": 1}}))

    assert result["strategy_plan"] == {}
    assert result["planning_blockers"][0]["target_agent"] == "strategy_agent"
    assert result["planning_blockers"][0]["reason_code"] == "invalid_strategy_contract"
