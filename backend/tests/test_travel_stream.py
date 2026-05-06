from app.api.routers.travel import (
    AGENT_META,
    _agent_start_key,
    _build_node_completion_payloads,
    _extract_counts,
    _iter_new_update_lines,
    _next_agent_start_key,
    _resolve_next_agent_starts,
)
import pytest


def test_iter_new_update_lines_extracts_incremental_lines():
    emitted = {"开始规划", "景点完成: 4个"}
    current = "开始规划\n景点完成: 4个\n酒店完成: 2个\n天气完成: 3天"

    assert _iter_new_update_lines(emitted, current) == ["酒店完成: 2个", "天气完成: 3天"]
    assert emitted == {"开始规划", "景点完成: 4个", "酒店完成: 2个", "天气完成: 3天"}


def test_iter_new_update_lines_does_not_slice_parallel_branch_fragments():
    emitted = {"已接收需求: 杭州, 1天, 1人", "天气完成: 1天"}
    current = "已接收需求: 杭州, 1天, 1人\n酒店关键词: 舒适型酒店\n酒店候选完成: 5家(目标5)"

    assert _iter_new_update_lines(emitted, current) == [
        "酒店关键词: 舒适型酒店",
        "酒店候选完成: 5家(目标5)",
    ]


def test_resolve_next_agent_starts_for_parallel_and_serial_nodes():
    assert _resolve_next_agent_starts(
        "orchestrator",
        {
            "orchestration_action": "worker_batch",
            "next_workers": ["strategy_agent", "weather_agent"],
        },
    ) == ["strategy_agent", "weather_agent"]
    assert _resolve_next_agent_starts("strategy_agent", {}) == []
    assert _resolve_next_agent_starts("anchor_resolver_agent", {}) == []
    assert _resolve_next_agent_starts("nearby_poi_agent", {}) == []
    assert _resolve_next_agent_starts("route_matrix_agent", {}) == []
    assert _resolve_next_agent_starts("itinerary_composer_agent", {}) == []
    assert _resolve_next_agent_starts("fan_in", {}) == ["orchestrator"]
    assert _resolve_next_agent_starts(
        "plan_evaluator_agent",
        {
            "planning_iteration": 0,
            "max_planning_iterations": 3,
            "evaluation": {
                "passed": False,
                "score": 0.7,
                "repair_tasks": [{"agent": "route_matrix_agent"}],
            },
        },
    ) == ["orchestrator"]
    assert _resolve_next_agent_starts(
        "orchestrator",
        {"orchestration_action": "evaluate"},
    ) == ["plan_evaluator_agent"]
    assert _resolve_next_agent_starts(
        "orchestrator",
        {"orchestration_action": "final"},
    ) == ["final_planning"]
    assert _resolve_next_agent_starts(
        "orchestrator",
        {"orchestration_action": "final_with_warnings"},
    ) == ["final_planning"]
    assert _resolve_next_agent_starts("weather_agent", {}) == []


def test_resolve_next_agent_starts_skips_to_final_planning_on_fatal_fan_in():
    state = {"status": "error", "errors": "未找到任何可用景点"}

    with pytest.raises(RuntimeError, match="fatal phase-1 issue"):
        _resolve_next_agent_starts("fan_in", state)


def test_extract_counts_returns_node_specific_numbers():
    nearby_state = {
        "attractions": [{"name": "故宫"}, {"name": "景山"}],
        "hotels": [{"name": "王府井酒店"}],
        "restaurants": [{"name": "杭帮菜"}],
    }
    assert _extract_counts("nearby_poi_agent", nearby_state) == {
        "attractions": 2,
        "hotels": 1,
        "restaurants": 1,
    }

    weather_state = {"weather": [{"date": "2026-03-10"}, {"date": "2026-03-11"}]}
    assert _extract_counts("weather_agent", weather_state) == {"days": 2}

    final_state = {
        "itinerary_draft": {
            "days": [{"day_index": 1}, {"day_index": 2}],
            "statistics": {"attraction_count": 5},
        }
    }
    assert _extract_counts("final_planning", final_state) == {"days": 2, "attractions": 5}

    evaluator_state = {
        "evaluation": {
            "passed": False,
            "score": 0.72,
            "blocking_issues": ["路线跨度过大", "餐饮重复"],
            "repair_tasks": [{"agent": "route_matrix_agent"}, {"agent": "nearby_poi_agent"}],
        }
    }
    assert _extract_counts("plan_evaluator_agent", evaluator_state) == {
        "score": 72,
        "issues": 2,
        "repairs": 2,
    }


def test_agent_meta_includes_evaluator_and_excludes_repair_router():
    assert AGENT_META["plan_evaluator_agent"]["label"] == "方案审核"
    assert AGENT_META["weather_agent"]["phase"] == "parallel"
    assert AGENT_META["strategy_agent"]["label"] == "策略规划"
    assert "repair_router" not in AGENT_META


def test_agent_start_key_allows_same_agent_in_different_iterations():
    first = _agent_start_key("route_matrix_agent", {"planning_iteration": 0})
    second = _agent_start_key("route_matrix_agent", {"planning_iteration": 1})

    assert first != second
    assert first == "route_matrix_agent:0"
    assert second == "route_matrix_agent:1"


def test_next_agent_start_key_advances_orchestrator_loop_step():
    state = {"orchestration_step": 1, "planning_iteration": 0}

    assert _next_agent_start_key("orchestrator", state) == "orchestrator:2"
    assert _next_agent_start_key("route_matrix_agent", state) == "route_matrix_agent:0"


def test_final_planning_emits_itinerary_before_agent_done():
    state = {
        "itinerary_draft": {
            "city": "大理",
            "start_date": "2026-03-10",
            "end_date": "2026-03-11",
            "total_days": 2,
            "days": [
                {
                    "date": "2026-03-10",
                    "day_index": 1,
                    "attractions": [],
                    "meals": [],
                    "route_segments": [],
                }
            ],
            "weather_info": [],
            "narrative_plan": "先到古城，再去洱海。",
            "statistics": {"attraction_count": 0},
        }
    }

    payloads = _build_node_completion_payloads("final_planning", state)
    event_types = [payload["type"] for payload in payloads]

    assert event_types == ["agent_result", "narrative", "itinerary", "agent_done"]
    assert payloads[2]["data"]["city"] == "大理"


def test_final_planning_without_itinerary_is_not_marked_done():
    with pytest.raises(RuntimeError, match="itinerary_draft"):
        _build_node_completion_payloads("final_planning", {"itinerary_draft": None})
