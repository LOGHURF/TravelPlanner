"""
LangGraph 图构建 - 采用 Fan-out/Fan-in 并行模式

图结构：
```
START → orchestrator → [并行Fan-out] → attraction ─┐
                              hotel ────────────────┼──→ fan_in → reviewer → restaurant → transport → final_planning
                              weather ──────────────┘
```

支持两种模式：
- PARALLEL: 并行执行（默认）
- SEQUENTIAL: 顺序执行（兼容旧版，避免MCP并发问题）
"""
from typing import TYPE_CHECKING, List, Literal

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from app.config import get_logger
from app.ai.models.graph_models import TripState

logger = get_logger("GraphBuilder")

ExecutionMode = Literal["parallel", "sequential"]

if TYPE_CHECKING:
    from app.ai.nodes.attraction_node import attraction_node as _attraction_node
    from app.ai.nodes.fan_in_node import fan_in_node as _fan_in_node
    from app.ai.nodes.final_planning_node import final_planning_node as _final_planning_node
    from app.ai.nodes.hotel_node import hotel_node as _hotel_node
    from app.ai.nodes.orchestrator_node import orchestrator_node as _orchestrator_node
    from app.ai.nodes.restaurant_node import restaurant_node as _restaurant_node
    from app.ai.nodes.reviewer_node import reviewer_node as _reviewer_node
    from app.ai.nodes.transport_node import transport_node as _transport_node
    from app.ai.nodes.weather_node import weather_node as _weather_node


def route_after_orchestrator(state: TripState) -> List[Send]:
    """Supervisor 后的并行路由（Fan-out）。"""
    logger.info("route: orchestrator -> fan-out(attraction, hotel, weather)")
    return [
        Send("attraction_agent", state),
        Send("hotel_agent", state),
        Send("weather_agent", state),
    ]


def route_after_fan_in(state: TripState) -> str:
    """
    Fan-in 后的路由。

    如果 Phase 1 数据不完整，直接进入 final_planning 输出精简结果，
    避免再走单独的 report 节点。
    """
    errors = state.get("errors", "")
    status = state.get("status", "")

    if status == "error" and "未找到任何" in errors:
        logger.warning(
            "route: fan_in detected fatal issue, skip reviewer and jump to final_planning"
        )
        return "final_planning"

    logger.info("route: fan_in -> reviewer_agent")
    return "reviewer_agent"


def build_travel_graph(mode: ExecutionMode = "parallel"):
    """构建旅行规划图。"""
    from app.ai.nodes.attraction_node import attraction_node
    from app.ai.nodes.fan_in_node import fan_in_node
    from app.ai.nodes.final_planning_node import final_planning_node
    from app.ai.nodes.hotel_node import hotel_node
    from app.ai.nodes.orchestrator_node import orchestrator_node
    from app.ai.nodes.restaurant_node import restaurant_node
    from app.ai.nodes.reviewer_node import reviewer_node
    from app.ai.nodes.transport_node import transport_node
    from app.ai.nodes.weather_node import weather_node

    logger.info("build graph mode=%s", mode.upper())

    graph = StateGraph(TripState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("attraction_agent", attraction_node)
    graph.add_node("hotel_agent", hotel_node)
    graph.add_node("fan_in", fan_in_node)
    graph.add_node("reviewer_agent", reviewer_node)
    graph.add_node("restaurant_agent", restaurant_node)
    graph.add_node("transport_agent", transport_node)
    graph.add_node("weather_agent", weather_node)
    graph.add_node("final_planning", final_planning_node)

    graph.set_entry_point("orchestrator")

    if mode == "parallel":
        _build_parallel_edges(graph)
    else:
        _build_sequential_edges(graph)

    logger.info("graph build done")
    # Note: LangGraph API handles persistence automatically, don't pass checkpointer here
    return graph.compile()


def _build_parallel_edges(graph: StateGraph):
    logger.info("build edges: parallel")

    # Fan-out: 并行执行 attraction、hotel、weather
    graph.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        path_map={
            "attraction_agent": "attraction_agent",
            "hotel_agent": "hotel_agent",
            "weather_agent": "weather_agent",
        },
    )

    # Fan-in: 等待三个 agent 都完成
    graph.add_edge("attraction_agent", "fan_in")
    graph.add_edge("hotel_agent", "fan_in")
    graph.add_edge("weather_agent", "fan_in")

    graph.add_conditional_edges(
        "fan_in",
        route_after_fan_in,
        path_map={
            "reviewer_agent": "reviewer_agent",
            "final_planning": "final_planning",
        },
    )
    graph.add_edge("reviewer_agent", "restaurant_agent")
    graph.add_edge("restaurant_agent", "transport_agent")
    graph.add_edge("transport_agent", "final_planning")
    graph.add_edge("final_planning", END)


def _build_sequential_edges(graph: StateGraph):
    logger.info("build edges: sequential")

    graph.add_edge("orchestrator", "attraction_agent")
    graph.add_edge("attraction_agent", "hotel_agent")
    graph.add_edge("hotel_agent", "fan_in")
    graph.add_conditional_edges(
        "fan_in",
        route_after_fan_in,
        path_map={
            "reviewer_agent": "reviewer_agent",
            "final_planning": "final_planning",
        },
    )
    graph.add_edge("reviewer_agent", "restaurant_agent")
    graph.add_edge("restaurant_agent", "transport_agent")
    graph.add_edge("transport_agent", "weather_agent")
    graph.add_edge("weather_agent", "final_planning")
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