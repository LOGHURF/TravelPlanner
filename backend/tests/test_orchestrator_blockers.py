from app.ai.nodes.orchestrator_node import orchestrator_node


def test_orchestrator_dispatches_blocker_target_before_remaining_queue() -> None:
    state = {
        "request": {"destination": "杭州", "days": 1},
        "orchestration_initialized": True,
        "worker_queue": [["nearby_poi_agent"], ["route_matrix_agent"]],
        "next_workers": [],
        "current_workers": [],
        "evaluate_after_workers": True,
        "planning_iteration": 0,
        "max_planning_iterations": 3,
        "streaming_updates": "",
        "planning_blockers": [
            {
                "target_agent": "strategy_agent",
                "reason_code": "insufficient_resolved_attractions",
                "message": "第1天缺少可用景点锚点",
                "constraints": {"day_index": 1, "unresolved_names": ["人民路"]},
            }
        ],
    }

    result = orchestrator_node(state)

    assert result["planning_iteration"] == 1
    assert result["next_workers"] == ["strategy_agent"]
    assert result["current_workers"] == ["strategy_agent"]
    assert result["worker_queue"] == [
        ["anchor_resolver_agent"],
        ["nearby_poi_agent"],
        ["route_matrix_agent"],
        ["itinerary_composer_agent"],
    ]
    assert result["planning_blockers"] == []
    assert "结构化阻塞修复" in result["streaming_updates"]
