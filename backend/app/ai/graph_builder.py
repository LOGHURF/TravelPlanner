"""
LangGraph 图构建 - Orchestrator 主控循环模式

图结构：
```
START → orchestrator → worker batch → fan_in → orchestrator
                              ↑                     │
                              └──── evaluator ←─────┘
orchestrator 根据审核结果继续派发 worker batch，或进入 final_planning。
```

mode 参数保留给测试和未来执行策略扩展，当前图只注册 strategy-first worker。
"""
from copy import deepcopy
from inspect import isawaitable
from typing import TYPE_CHECKING, Any, Callable, List, Literal

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from app.config import get_logger
from app.ai.models.graph_models import TripState

logger = get_logger("GraphBuilder")

ExecutionMode = Literal["parallel", "sequential"]
NodeFn = Callable[[TripState], Any]

if TYPE_CHECKING:
    from app.ai.nodes.anchor_resolver_node import anchor_resolver_node as _anchor_resolver_node
    from app.ai.nodes.fan_in_node import fan_in_node as _fan_in_node
    from app.ai.nodes.final_planning_node import final_planning_node as _final_planning_node
    from app.ai.nodes.itinerary_composer_node import itinerary_composer_node as _itinerary_composer_node
    from app.ai.nodes.nearby_poi_node import nearby_poi_node as _nearby_poi_node
    from app.ai.nodes.orchestrator_node import orchestrator_node as _orchestrator_node
    from app.ai.nodes.plan_evaluator_node import plan_evaluator_node as _plan_evaluator_node
    from app.ai.nodes.route_matrix_node import route_matrix_node as _route_matrix_node
    from app.ai.nodes.strategy_node import strategy_node as _strategy_node
    from app.ai.nodes.weather_node import weather_node as _weather_node


def route_after_orchestrator(state: TripState) -> List[Send] | str:
    """Route according to the orchestrator's explicit next action."""
    action = str(state.get("orchestration_action", "") or "").strip()
    if action == "evaluate":
        logger.info("route: orchestrator -> plan_evaluator_agent")
        return "plan_evaluator_agent"
    if action in {"final", "final_with_warnings"}:
        logger.info("route: orchestrator -> final_planning")
        return "final_planning"
    if action == "error":
        logger.error("route: orchestrator -> END status=error errors=%s", state.get("errors", ""))
        return END
    if action != "worker_batch":
        raise ValueError(f"unknown orchestration action: {action}")

    workers = [str(item).strip() for item in state.get("next_workers", []) if str(item).strip()]
    if not workers:
        raise ValueError("worker_batch action requires next_workers")
    logger.info("route: orchestrator -> worker batch %s", workers)
    return [Send(worker, state) for worker in workers]


def route_after_fan_in(state: TripState) -> str:
    """
    Fan-in 后的路由。

    如果 Phase 1 数据出现致命缺口，直接失败，避免输出掩盖问题的精简结果。
    """
    errors = state.get("errors", "")
    status = state.get("status", "")

    if status == "error" and "未找到任何" in errors:
        logger.error("route: fan_in detected fatal issue: %s", errors)
        raise ValueError(f"fatal phase-1 issue: {errors}")

    logger.info("route: fan_in -> orchestrator")
    return "orchestrator"


def route_after_plan_evaluator(state: TripState) -> str:
    """Evaluation always returns control to the orchestrator."""
    evaluation = state.get("evaluation")
    if not isinstance(evaluation, dict):
        raise ValueError("plan evaluator route requires evaluation")

    logger.info("route: plan_evaluator -> orchestrator")
    return "orchestrator"


def _streaming_delta(before: str, after: str) -> str:
    if after.startswith(before):
        return after[len(before) :]
    return after


def _completed_agents_delta(before: list[str], after: list[str]) -> list[str]:
    return [name for name in after if name and name not in before]


def _state_delta(before: TripState, after: TripState) -> TripState:
    delta: TripState = {}
    for key, value in after.items():
        if before.get(key) == value:
            continue
        if key == "streaming_updates":
            update = _streaming_delta(str(before.get(key, "") or ""), str(value or ""))
            if update:
                delta[key] = update
            continue
        if key == "completed_agents" and isinstance(value, list):
            added = _completed_agents_delta(list(before.get(key, []) or []), value)
            if added:
                delta[key] = added
            continue
        delta[key] = value
    return delta


def _worker_delta_node(node_fn: NodeFn) -> NodeFn:
    async def wrapped(state: TripState) -> TripState:
        before = deepcopy(dict(state))
        working_state = deepcopy(dict(state))
        result = node_fn(working_state)
        if isawaitable(result):
            result = await result
        return _state_delta(before, result or working_state)

    return wrapped


def build_travel_graph(mode: ExecutionMode = "parallel"):
    """构建旅行规划图。"""
    from app.ai.nodes.anchor_resolver_node import anchor_resolver_node
    from app.ai.nodes.fan_in_node import fan_in_node
    from app.ai.nodes.final_planning_node import final_planning_node
    from app.ai.nodes.itinerary_composer_node import itinerary_composer_node
    from app.ai.nodes.nearby_poi_node import nearby_poi_node
    from app.ai.nodes.orchestrator_node import orchestrator_node
    from app.ai.nodes.plan_evaluator_node import plan_evaluator_node
    from app.ai.nodes.route_matrix_node import route_matrix_node
    from app.ai.nodes.strategy_node import strategy_node
    from app.ai.nodes.weather_node import weather_node

    logger.info("build graph mode=%s", mode.upper())

    graph = StateGraph(TripState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("strategy_agent", _worker_delta_node(strategy_node))
    graph.add_node("anchor_resolver_agent", _worker_delta_node(anchor_resolver_node))
    graph.add_node("nearby_poi_agent", _worker_delta_node(nearby_poi_node))
    graph.add_node("route_matrix_agent", _worker_delta_node(route_matrix_node))
    graph.add_node("itinerary_composer_agent", _worker_delta_node(itinerary_composer_node))
    graph.add_node("fan_in", fan_in_node)
    graph.add_node("weather_agent", _worker_delta_node(weather_node))
    graph.add_node("plan_evaluator_agent", plan_evaluator_node)
    graph.add_node("final_planning", final_planning_node)

    graph.set_entry_point("orchestrator")

    _build_orchestrator_loop_edges(graph)

    logger.info("graph build done")
    # Note: LangGraph API handles persistence automatically, don't pass checkpointer here
    return graph.compile()


def _build_orchestrator_loop_edges(graph: StateGraph):
    logger.info("build edges: orchestrator loop")

    graph.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        path_map={
            "weather_agent": "weather_agent",
            "strategy_agent": "strategy_agent",
            "anchor_resolver_agent": "anchor_resolver_agent",
            "nearby_poi_agent": "nearby_poi_agent",
            "route_matrix_agent": "route_matrix_agent",
            "itinerary_composer_agent": "itinerary_composer_agent",
            "plan_evaluator_agent": "plan_evaluator_agent",
            "final_planning": "final_planning",
            END: END,
        },
    )

    graph.add_edge("weather_agent", "fan_in")
    graph.add_edge("strategy_agent", "fan_in")
    graph.add_edge("anchor_resolver_agent", "fan_in")
    graph.add_edge("nearby_poi_agent", "fan_in")
    graph.add_edge("route_matrix_agent", "fan_in")
    graph.add_edge("itinerary_composer_agent", "fan_in")
    graph.add_conditional_edges(
        "fan_in",
        route_after_fan_in,
        path_map={
            "orchestrator": "orchestrator",
        },
    )
    graph.add_conditional_edges(
        "plan_evaluator_agent",
        route_after_plan_evaluator,
        path_map={
            "orchestrator": "orchestrator",
        },
    )
    graph.add_edge("final_planning", END)


_travel_graph = None


def get_travel_graph(mode: ExecutionMode = "parallel"):
    """获取旅行规划图实例（单例）。"""
    global _travel_graph
    if _travel_graph is None:
        _travel_graph = build_travel_graph(mode=mode)
    return _travel_graph


def reset_travel_graph():
    """重置图实例（用于测试）。"""
    global _travel_graph
    _travel_graph = None
    logger.info("graph instance reset")


# 导出图实例供 LangGraph 使用
travel = build_travel_graph()
