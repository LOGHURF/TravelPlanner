from app.api.routers.travel import (
    _build_node_completion_payloads,
    _extract_counts,
    _iter_new_update_lines,
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
    assert _resolve_next_agent_starts("orchestrator", {}) == [
        "attraction_agent",
        "hotel_agent",
        "weather_agent",
    ]
    assert _resolve_next_agent_starts("reviewer_agent", {}) == ["restaurant_agent"]
    assert _resolve_next_agent_starts("restaurant_agent", {}) == ["transport_agent"]
    assert _resolve_next_agent_starts("transport_agent", {}) == ["final_planning"]
    assert _resolve_next_agent_starts("weather_agent", {}) == []


def test_resolve_next_agent_starts_skips_to_final_planning_on_fatal_fan_in():
    state = {"status": "error", "errors": "未找到任何可用景点"}

    assert _resolve_next_agent_starts("fan_in", state) == ["final_planning"]


def test_extract_counts_returns_node_specific_numbers():
    reviewer_state = {
        "attractions": [{"name": "故宫"}, {"name": "景山"}],
        "hotels": [{"name": "王府井酒店"}],
    }
    assert _extract_counts("reviewer_agent", reviewer_state) == {"attractions": 2, "hotels": 1}

    weather_state = {"weather": [{"date": "2026-03-10"}, {"date": "2026-03-11"}]}
    assert _extract_counts("weather_agent", weather_state) == {"days": 2}

    final_state = {
        "itinerary_draft": {
            "days": [{"day_index": 1}, {"day_index": 2}],
            "statistics": {"attraction_count": 5},
        }
    }
    assert _extract_counts("final_planning", final_state) == {"days": 2, "attractions": 5}


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
