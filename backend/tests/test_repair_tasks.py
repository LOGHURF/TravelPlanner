from app.ai.repair_tasks import (
    agent_repair_tasks,
    repair_keywords_for_agent,
)


def test_agent_repair_tasks_filters_by_agent():
    state = {
        "active_repair_tasks": [
            {
                "agent": "nearby_poi_agent",
                "task": "search_by_day_area",
                "reason": "餐饮离行程太远",
                "constraints": {"areas": ["湖滨", "武林"]},
            },
            {
                "agent": "route_matrix_agent",
                "task": "rebalance_daily_density",
                "reason": "路线太赶",
                "constraints": {"pace": "宽松"},
            },
        ]
    }

    result = agent_repair_tasks(state, "nearby_poi_agent")

    assert result == [state["active_repair_tasks"][0]]


def test_agent_repair_tasks_rejects_malformed_task():
    state = {"active_repair_tasks": [{"task": "missing_agent"}]}

    try:
        agent_repair_tasks(state, "nearby_poi_agent")
    except ValueError as exc:
        assert "repair task agent is required" in str(exc)
    else:
        raise AssertionError("expected malformed repair task to fail")


def test_repair_keywords_for_agent_extracts_area_and_include_terms():
    state = {
        "active_repair_tasks": [
            {
                "agent": "nearby_poi_agent",
                "task": "search_by_day_area",
                "reason": "餐饮离行程太远",
                "constraints": {
                    "areas": ["湖滨", "武林"],
                    "include": ["杭帮菜", "茶点"],
                },
            }
        ]
    }

    result = repair_keywords_for_agent(state, "nearby_poi_agent")

    assert result == ["湖滨", "武林", "杭帮菜", "茶点"]
