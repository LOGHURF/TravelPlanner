"""
Graph Builder 测试 - 验证并行 Fan-out 图结构
"""

from app.ai.graph_builder import (
    build_travel_graph,
    route_after_orchestrator,
    route_after_fan_in,
    get_travel_graph,
    reset_travel_graph,
)
from app.ai.models.graph_models import TripState


def create_test_state(
    attractions=None,
    hotels=None,
    weather=None,
    completed_agents=None,
    status="in_progress",
    errors="",
) -> TripState:
    """创建测试状态"""
    return {
        "request": {"destination": "北京", "days": 3},
        "attractions": attractions or [],
        "hotels": hotels or [],
        "restaurants": [],
        "weather": weather or [],
        "status": status,
        "errors": errors,
        "streaming_updates": "",
        "completed_agents": completed_agents or [],
    }


def test_route_after_orchestrator():
    """测试 Supervisor 后的并行路由"""
    state = create_test_state()
    routes = route_after_orchestrator(state)

    # 验证返回 3 个 Send：景点、酒店、天气都只依赖目的地/日期，可并行召回
    assert len(routes) == 3

    # 验证目标节点
    targets = [r.node for r in routes]
    assert "attraction_agent" in targets
    assert "hotel_agent" in targets
    assert "weather_agent" in targets

    print("✅ Supervisor 并行路由测试通过")
    print(f"   目标节点: {targets}")


def test_route_after_fan_in_success():
    """测试 Fan-in 后路由（成功）"""
    state = create_test_state(
        attractions=[{"name": "故宫"}],
        hotels=[{"name": "北京饭店"}],
        completed_agents=["attraction", "hotel"],
    )

    result = route_after_fan_in(state)
    assert result == "reviewer_agent"
    print("✅ Fan-in 成功路由测试通过")


def test_route_after_fan_in_error():
    """测试 Fan-in 后路由（错误）"""
    state = create_test_state(
        status="error",
        errors="未找到任何景点",
    )

    result = route_after_fan_in(state)
    # 有严重错误时直接进入 final planning 输出精简结果
    assert result == "final_planning"
    print("✅ Fan-in 错误路由测试通过")


def test_build_sequential_graph():
    """测试构建顺序模式图"""
    reset_travel_graph()
    graph = build_travel_graph(mode="sequential")

    assert graph is not None
    print("✅ 顺序模式图构建成功")


def test_build_parallel_graph():
    """测试构建并行模式图"""
    reset_travel_graph()
    graph = build_travel_graph(mode="parallel")

    assert graph is not None
    print("✅ 并行模式图构建成功")


def test_get_travel_graph_singleton():
    """测试图单例模式"""
    reset_travel_graph()

    # 第一次获取
    graph1 = get_travel_graph(mode="parallel")
    # 第二次获取（应该返回同一个实例）
    graph2 = get_travel_graph(mode="parallel")

    assert graph1 is graph2
    print("✅ 图单例模式测试通过")


def test_graph_nodes_exist():
    """测试图中节点存在"""
    reset_travel_graph()
    graph = build_travel_graph(mode="parallel")

    # 获取图中的节点
    nodes = graph.get_graph().nodes

    required_nodes = [
        "orchestrator",
        "attraction_agent",
        "hotel_agent",
        "reviewer_agent",
        "weather_agent",
        "restaurant_agent",
        "transport_agent",
        "final_planning",
        "fan_in",
    ]

    for node in required_nodes:
        assert node in nodes, f"节点 {node} 不存在"

    print(f"✅ 所有必需节点存在: {required_nodes}")


def test_graph_structure():
    """测试图结构"""
    from langgraph.graph import StateGraph

    reset_travel_graph()
    graph = build_travel_graph(mode="parallel")

    # 获取图的边
    graph_structure = graph.get_graph()

    print("✅ 图结构信息:")
    print(f"   节点数: {len(graph_structure.nodes)}")
    print(f"   边数: {len(graph_structure.edges)}")
    print(f"   节点列表: {list(graph_structure.nodes)}")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🧪 开始测试 Graph Builder")
    print("=" * 60)

    test_route_after_orchestrator()
    test_route_after_fan_in_success()
    test_route_after_fan_in_error()
    test_build_sequential_graph()
    test_build_parallel_graph()
    test_get_travel_graph_singleton()
    test_graph_nodes_exist()
    test_graph_structure()

    print("=" * 60)
    print("🎉 所有 Graph Builder 测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
