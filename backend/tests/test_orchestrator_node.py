from app.ai.nodes.orchestrator_node import orchestrator_node


def test_orchestrator_initializes_and_dispatches_foundation_batch() -> None:
    state = {
        "request": {"destination": "大理", "days": 2, "num_people": 2},
        "next_workers": [],
        "worker_queue": [],
        "evaluate_after_workers": False,
    }

    result = orchestrator_node(state)

    assert result["orchestration_initialized"] is True
    assert result["orchestration_action"] == "worker_batch"
    assert result["next_workers"] == ["strategy_agent", "weather_agent"]
    assert result["current_workers"] == ["strategy_agent", "weather_agent"]
    assert result["completed_workers_in_batch"] == []
    assert result["worker_queue"] == [
        ["anchor_resolver_agent"],
        ["nearby_poi_agent"],
        ["route_matrix_agent"],
        ["itinerary_composer_agent"],
    ]


def test_orchestrator_consumes_failed_evaluation_into_repair_queue() -> None:
    state = {
        "request": {"destination": "大理", "days": 2},
        "orchestration_initialized": True,
        "worker_queue": [],
        "next_workers": [],
        "evaluate_after_workers": False,
        "planning_iteration": 0,
        "max_planning_iterations": 3,
        "streaming_updates": "",
        "evaluation": {
            "passed": False,
            "score": 0.72,
            "repair_tasks": [
                {
                    "agent": "route_matrix_agent",
                    "task": "rebuild_route_matrix",
                    "reason": "公交路线不可用",
                    "constraints": {},
                }
            ],
        },
    }

    result = orchestrator_node(state)

    assert result["planning_iteration"] == 1
    assert result["active_repair_tasks"][0]["agent"] == "route_matrix_agent"
    assert result["repair_targets"] == ["route_matrix_agent"]
    assert result["orchestration_action"] == "worker_batch"
    assert result["next_workers"] == ["route_matrix_agent"]
    assert result["current_workers"] == ["route_matrix_agent"]
    assert result["worker_queue"] == [["itinerary_composer_agent"]]
    assert result["evaluate_after_workers"] is True


def test_orchestrator_marks_final_with_warnings_when_max_repairs_are_exhausted() -> None:
    state = {
        "request": {"destination": "大理", "days": 2},
        "orchestration_initialized": True,
        "worker_queue": [],
        "next_workers": [],
        "evaluate_after_workers": False,
        "planning_iteration": 3,
        "max_planning_iterations": 3,
        "streaming_updates": "",
        "evaluation": {
            "passed": False,
            "score": 0.62,
            "blocking_issues": ["Day 2 路线跨度过大"],
            "repair_tasks": [
                {
                    "agent": "route_matrix_agent",
                    "task": "rebuild_route_matrix",
                    "reason": "仍有长距离动线",
                    "constraints": {},
                }
            ],
        },
    }

    result = orchestrator_node(state)

    assert result["orchestration_action"] == "final_with_warnings"
    assert result["final_with_warnings"] is True
    assert result["evaluation_failed_after_max_iterations"] is True
    assert "最大修复轮" in result["streaming_updates"]
