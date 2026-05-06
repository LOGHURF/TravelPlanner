import pytest
from langgraph.types import Send
from pathlib import Path

from app.ai.graph_builder import (
    build_travel_graph,
    route_after_fan_in,
    route_after_orchestrator,
    route_after_plan_evaluator,
    get_travel_graph,
    reset_travel_graph,
)
from app.ai.models.graph_models import TripState


def create_test_state(**overrides) -> TripState:
    state: TripState = {
        "request": {"destination": "北京", "days": 3},
        "attractions": [],
        "hotels": [],
        "restaurants": [],
        "weather": [],
        "status": "in_progress",
        "errors": "",
        "streaming_updates": "",
        "completed_agents": [],
        "next_workers": [],
        "orchestration_action": "worker_batch",
    }
    state.update(overrides)
    return state


def _send_targets(routes: list[Send] | str) -> list[str]:
    assert isinstance(routes, list)
    return [route.node for route in routes]


def test_route_after_orchestrator_dispatches_current_worker_batch():
    state = create_test_state(next_workers=["strategy_agent", "weather_agent"])

    routes = route_after_orchestrator(state)

    assert _send_targets(routes) == ["strategy_agent", "weather_agent"]


def test_route_after_orchestrator_can_send_to_evaluator_or_final():
    assert route_after_orchestrator(create_test_state(orchestration_action="evaluate")) == "plan_evaluator_agent"
    assert route_after_orchestrator(create_test_state(orchestration_action="final")) == "final_planning"


def test_route_after_fan_in_returns_control_to_orchestrator():
    assert route_after_fan_in(create_test_state(attractions=[{"name": "故宫"}], hotels=[{"name": "北京饭店"}])) == "orchestrator"


def test_route_after_fan_in_fails_fast_on_fatal_foundation_issue():
    state = create_test_state(status="error", errors="未找到任何景点")

    try:
        route_after_fan_in(state)
    except ValueError as exc:
        assert "fatal phase-1 issue" in str(exc)
    else:
        raise AssertionError("fatal fan-in issue should fail fast")


def test_route_after_plan_evaluator_returns_to_orchestrator():
    state = create_test_state(
        evaluation={
            "passed": False,
            "score": 0.72,
            "repair_tasks": [{"agent": "route_matrix_agent"}],
        }
    )

    assert route_after_plan_evaluator(state) == "orchestrator"


def test_graph_nodes_exclude_repair_router_and_keep_orchestrator_loop():
    reset_travel_graph()
    graph = build_travel_graph(mode="parallel")

    nodes = graph.get_graph().nodes

    assert "repair_router" not in nodes
    for node in [
        "orchestrator",
        "strategy_agent",
        "anchor_resolver_agent",
        "nearby_poi_agent",
        "route_matrix_agent",
        "itinerary_composer_agent",
        "weather_agent",
        "fan_in",
        "plan_evaluator_agent",
        "final_planning",
    ]:
        assert node in nodes

def test_active_strategy_first_nodes_do_not_import_legacy_nodes():
    nodes_dir = Path(__file__).resolve().parents[1] / "app" / "ai" / "nodes"
    active_files = [
        "anchor_resolver_node.py",
        "nearby_poi_node.py",
        "route_matrix_node.py",
        "itinerary_composer_node.py",
        "plan_evaluator_node.py",
        "strategy_node.py",
        "final_planning_node.py",
    ]
    removed_stems = ["attraction", "hotel", "restaurant", "transport", "reviewer"]
    for stem in removed_stems:
        assert not (nodes_dir / f"{stem}_node.py").exists()
    for file_name in active_files:
        text = (nodes_dir / file_name).read_text(encoding="utf-8")
        assert not any(f"{stem}_node" in text for stem in removed_stems), file_name


def test_build_modes_and_singleton_compile():
    reset_travel_graph()
    parallel_graph = build_travel_graph(mode="parallel")
    sequential_graph = build_travel_graph(mode="sequential")

    assert parallel_graph is not None
    assert sequential_graph is not None

    reset_travel_graph()
    graph1 = get_travel_graph(mode="parallel")
    graph2 = get_travel_graph(mode="parallel")
    assert graph1 is graph2


@pytest.mark.anyio
async def test_parallel_graph_workers_return_only_deltas(monkeypatch):
    async def strategy(state):
        state["strategy_plan"] = {
            "trip_theme": "经典游",
            "daily_area_plan": [
                {"day_index": 1, "area_name": "古城", "required_anchors": ["大理古城"]}
            ],
            "hotel_area_keywords": ["大理古城"],
        }
        state.setdefault("completed_agents", []).append("strategy")
        state["streaming_updates"] = state.get("streaming_updates", "") + "\n策略完成"
        return state

    async def anchor(state):
        state["resolved_anchors"] = [{"query": "大理古城", "name": "大理古城", "day_index": 1}]
        state.setdefault("completed_agents", []).append("anchor_resolver")
        state["streaming_updates"] = state.get("streaming_updates", "") + "\n锚点完成"
        return state

    async def weather(state):
        state["weather"] = [{"date": "2026-01-01"}]
        state.setdefault("completed_agents", []).append("weather")
        state["streaming_updates"] = state.get("streaming_updates", "") + "\n天气完成"
        return state

    async def nearby(state):
        state["attractions"] = [{"name": "景点", "day_index": 1}]
        state["hotels"] = [{"name": "酒店"}]
        state["restaurants"] = [{"name": "餐厅"}]
        state.setdefault("completed_agents", []).append("nearby_poi")
        state["streaming_updates"] = state.get("streaming_updates", "") + "\n周边完成"
        return state

    async def route_matrix(state):
        state["route_matrix"] = {"legs": [], "issues": [], "daily_routes": [[]]}
        state.setdefault("completed_agents", []).append("route_matrix")
        state["streaming_updates"] = state.get("streaming_updates", "") + "\n路线完成"
        return state

    async def composer(state):
        state["transport"] = {"daily_plan": [{"day_index": 1}], "daily_routes": [[]]}
        state.setdefault("completed_agents", []).append("itinerary_composer")
        state["streaming_updates"] = state.get("streaming_updates", "") + "\n组合完成"
        return state

    async def evaluator(state):
        state["evaluation"] = {
            "passed": True,
            "score": 0.95,
            "blocking_issues": [],
            "repair_tasks": [],
            "residual_risks": [],
        }
        state["streaming_updates"] = state.get("streaming_updates", "") + "\n审核完成"
        return state

    async def final(state):
        state["itinerary_draft"] = {"city": "大理", "days": [], "statistics": {"attraction_count": 1}}
        state["status"] = "completed"
        return state

    monkeypatch.setattr("app.ai.nodes.strategy_node.strategy_node", strategy)
    monkeypatch.setattr("app.ai.nodes.anchor_resolver_node.anchor_resolver_node", anchor)
    monkeypatch.setattr("app.ai.nodes.nearby_poi_node.nearby_poi_node", nearby)
    monkeypatch.setattr("app.ai.nodes.route_matrix_node.route_matrix_node", route_matrix)
    monkeypatch.setattr("app.ai.nodes.itinerary_composer_node.itinerary_composer_node", composer)
    monkeypatch.setattr("app.ai.nodes.weather_node.weather_node", weather)
    monkeypatch.setattr("app.ai.nodes.plan_evaluator_node.plan_evaluator_node", evaluator)
    monkeypatch.setattr("app.ai.nodes.final_planning_node.final_planning_node", final)

    graph = build_travel_graph(mode="parallel")
    state = {
        "request": {"destination": "大理", "days": 1, "num_people": 2},
        "max_planning_iterations": 3,
    }

    events: list[str] = []
    async for event in graph.astream(state, {"configurable": {"thread_id": "delta-test"}}):
        events.extend(event.keys())

    assert "itinerary_composer_agent" in events
    assert events[-1] == "final_planning"
