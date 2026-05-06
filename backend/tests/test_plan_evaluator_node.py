import asyncio

import pytest

from app.ai.nodes.plan_evaluator_node import (
    EVALUATION_PASS_THRESHOLD,
    PlanEvaluationOutput,
    plan_evaluator_node,
)


def _state():
    return {
        "request": {
            "destination": "杭州",
            "days": 3,
            "companions": "情侣",
            "pace": "适中",
            "style_preferences": ["自然风光", "美食"],
            "budget_per_person": 1800,
            "num_people": 2,
        },
        "attractions": [
            {"name": "西湖", "location": {"lat": 30.25, "lng": 120.15}, "rating": 4.8},
            {"name": "灵隐寺", "location": {"lat": 30.24, "lng": 120.10}, "rating": 4.7},
        ],
        "hotels": [
            {"name": "湖滨酒店", "location": {"lat": 30.25, "lng": 120.16}, "price_per_night": 500}
        ],
        "restaurants": [
            {"name": "杭帮菜", "location": {"lat": 30.25, "lng": 120.15}, "meal_type": "dinner"}
        ],
        "weather": [
            {"date": "2026-05-02", "day_weather": "小雨", "night_weather": "阴", "day_temp": 23, "night_temp": 18}
        ],
        "transport": {
            "estimated_transport_cost": 120,
            "daily_plan": [{"day_index": 1, "attractions": [], "meals": []}],
            "daily_routes": [[]],
            "route_issues": [],
        },
        "strategy_plan": {
            "daily_area_plan": [
                {"day_index": 1, "area_name": "西湖", "required_anchors": ["西湖"]},
            ],
        },
        "resolved_anchors": [{"query": "西湖", "name": "西湖", "day_index": 1}],
        "route_matrix": {"legs": [], "issues": []},
        "planning_iteration": 1,
        "max_planning_iterations": 3,
        "evaluation_history": [],
        "streaming_updates": "",
        "completed_agents": [],
    }


def test_plan_evaluation_output_rejects_unknown_repair_agent():
    with pytest.raises(ValueError, match="unknown repair agent"):
        PlanEvaluationOutput.model_validate(
            {
                "passed": False,
                "score": 0.6,
                "dimensions": {"route_efficiency": 0.4},
                "blocking_issues": ["路线不合理"],
                "repair_tasks": [
                    {
                        "agent": "unknown_agent",
                        "task": "fix_anything",
                        "reason": "bad",
                        "constraints": {},
                    }
                ],
                "residual_risks": [],
            }
        )


def test_plan_evaluator_node_converts_llm_repairs_to_advisory_risks(monkeypatch):
    async def fake_invoke_prompt_json_async(*, prompt_id, variables, temperature, max_tokens):
        assert prompt_id == "plan_evaluator"
        assert max_tokens == 1200
        assert "transport" in variables["plan_context_json"]
        assert "route_matrix" in variables["plan_context_json"]
        return {
            "passed": False,
            "score": EVALUATION_PASS_THRESHOLD - 0.1,
            "dimensions": {"route_efficiency": 0.4, "food_quality": 0.6},
            "blocking_issues": ["路线跨度过大"],
            "repair_tasks": [
                {
                    "agent": "route_matrix_agent",
                    "task": "rebuild_route_matrix",
                    "reason": "路线跨度过大",
                    "constraints": {"pace": "适中"},
                }
            ],
            "residual_risks": [],
        }

    monkeypatch.setattr(
        "app.ai.nodes.plan_evaluator_node.invoke_prompt_json_async",
        fake_invoke_prompt_json_async,
    )

    result = asyncio.run(plan_evaluator_node(_state()))

    assert result["evaluation"]["passed"] is True
    assert result["repair_targets"] == []
    assert result["active_repair_tasks"] == []
    assert result["evaluation_history"][0]["score"] == EVALUATION_PASS_THRESHOLD
    assert "路线跨度过大" in result["evaluation"]["residual_risks"]
    assert result["completed_agents"] == ["plan_evaluator"]


def test_plan_evaluator_node_records_passed_evaluation(monkeypatch):
    async def fake_invoke_prompt_json_async(*, prompt_id, variables, temperature, max_tokens):
        assert max_tokens == 1200
        return {
            "passed": True,
            "score": EVALUATION_PASS_THRESHOLD,
            "dimensions": {"route_efficiency": 0.9},
            "blocking_issues": [],
            "repair_tasks": [],
            "residual_risks": ["热门景点仍需预约"],
        }

    monkeypatch.setattr(
        "app.ai.nodes.plan_evaluator_node.invoke_prompt_json_async",
        fake_invoke_prompt_json_async,
    )

    result = asyncio.run(plan_evaluator_node(_state()))

    assert result["evaluation"]["passed"] is True
    assert result["repair_targets"] == []
    assert result["active_repair_tasks"] == []


def test_plan_evaluator_hard_gate_blocks_missing_route_matrix_without_llm(monkeypatch):
    async def should_not_call_llm(**kwargs):
        raise AssertionError("hard gate failures should not call LLM judge")

    state = _state()
    state["route_matrix"] = {"legs": [], "issues": [{"day_index": 1, "issue": "blocked"}]}
    monkeypatch.setattr(
        "app.ai.nodes.plan_evaluator_node.invoke_prompt_json_async",
        should_not_call_llm,
    )

    result = asyncio.run(plan_evaluator_node(state))

    assert result["evaluation"]["passed"] is False
    assert result["repair_targets"] == ["route_matrix_agent"]


def test_plan_evaluator_hard_gate_blocks_meals_far_from_day_anchor_without_llm(monkeypatch):
    async def should_not_call_llm(**kwargs):
        raise AssertionError("hard gate failures should not call LLM judge")

    state = _state()
    state["transport"]["daily_plan"] = [
        {
            "day_index": 1,
            "attractions": [
                {"name": "上午景点", "location": {"lat": 30.0, "lng": 120.0}},
                {"name": "下午景点", "location": {"lat": 30.1, "lng": 120.0}},
            ],
            "meals": [
                {
                    "name": "过远午餐",
                    "meal_type": "lunch",
                    "location": {"lat": 30.1, "lng": 120.0},
                }
            ],
        }
    ]
    state["restaurants"] = state["transport"]["daily_plan"][0]["meals"]
    monkeypatch.setattr(
        "app.ai.nodes.plan_evaluator_node.invoke_prompt_json_async",
        should_not_call_llm,
    )

    result = asyncio.run(plan_evaluator_node(state))

    assert result["evaluation"]["passed"] is False
    assert result["repair_targets"] == ["nearby_poi_agent"]
    assert "餐厅距离日内锚点过远" in result["evaluation"]["blocking_issues"]


def test_plan_evaluator_node_short_circuits_on_planning_blockers(monkeypatch):
    async def should_not_call_llm(**kwargs):
        raise AssertionError("planning blockers should bypass LLM judge")

    state = _state()
    state["planning_blockers"] = [
        {
            "target_agent": "strategy_agent",
            "reason_code": "insufficient_resolved_attractions",
            "message": "第1天缺少可用景点锚点",
            "constraints": {"day_index": 1, "unresolved_names": ["人民路"]},
        }
    ]
    monkeypatch.setattr(
        "app.ai.nodes.plan_evaluator_node.invoke_prompt_json_async",
        should_not_call_llm,
    )

    result = asyncio.run(plan_evaluator_node(state))

    assert result["evaluation"]["passed"] is False
    assert result["repair_targets"] == ["strategy_agent"]
    assert result["active_repair_tasks"][0]["task"] == "regenerate_area_strategy"
    assert "第1天缺少可用景点锚点" in result["evaluation"]["blocking_issues"]
