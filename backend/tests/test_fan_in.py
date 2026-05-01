"""
Fan-in 汇聚节点测试
"""

import asyncio

from app.ai.models.graph_models import TripState
from app.ai.nodes.fan_in_node import check_phase1_complete, fan_in_node, get_phase1_progress


def create_test_state(
    attractions=None,
    hotels=None,
    weather=None,
    completed_agents=None,
    days=3,
) -> TripState:
    """创建测试状态"""
    return {
        "request": {"destination": "北京", "days": days},
        "attractions": attractions or [],
        "hotels": hotels or [],
        "restaurants": [],
        "weather": weather or [],
        "status": "in_progress",
        "streaming_updates": "",
        "completed_agents": completed_agents or [],
    }


def create_sample_attractions(count=3):
    """创建示例景点"""
    return [
        {
            "name": f"景点{i}",
            "rating": 4.5 + i * 0.1,
            "address": f"地址{i}",
            "location": {"lat": 39.9 + i * 0.01, "lng": 116.4 + i * 0.01},
        }
        for i in range(1, count + 1)
    ]


def create_sample_hotels(count=2):
    """创建示例酒店"""
    return [
        {
            "name": f"酒店{i}",
            "rating": 4.6 + i * 0.1,
            "address": f"酒店地址{i}",
            "location": {"lat": 39.91, "lng": 116.41},
        }
        for i in range(1, count + 1)
    ]


def create_sample_weather(days=3):
    """创建示例天气"""
    return [
        {
            "date": f"2025-06-0{i}",
            "day_weather": "晴",
            "night_weather": "多云",
            "day_temp": 25 + i,
            "night_temp": 18,
            "wind_direction": "南",
            "wind_power": "2级",
        }
        for i in range(1, days + 1)
    ]


def test_fan_in_complete_data():
    """测试完整数据的 Fan-in"""
    state = create_test_state(
        attractions=create_sample_attractions(5),
        hotels=create_sample_hotels(3),
        completed_agents=["attraction", "hotel"],
        days=3,
    )

    result = asyncio.run(fan_in_node(state))

    assert result["phase_1_completed"] is True
    assert "基础数据采集完成" in result["streaming_updates"]
    assert "5个" in result["streaming_updates"]
    assert "3家" in result["streaming_updates"]
    assert result["status"] == "in_progress"  # 没有错误
    print("✅ 完整数据 Fan-in 测试通过")


def test_fan_in_empty_data():
    """测试空数据的 Fan-in"""
    state = create_test_state(
        attractions=[],
        hotels=[],
        weather=[],
        completed_agents=[],
    )

    result = asyncio.run(fan_in_node(state))

    assert "未找到任何景点" in result["errors"]
    assert "未找到任何酒店" in result["errors"]
    assert result["status"] == "error"
    print("✅ 空数据 Fan-in 测试通过")


def test_fan_in_partial_data():
    """测试部分数据的 Fan-in"""
    state = create_test_state(
        attractions=create_sample_attractions(2),  # 只有2个景点
        hotels=create_sample_hotels(1),  # 只有1家酒店
        completed_agents=["attraction", "hotel"],
    )

    result = asyncio.run(fan_in_node(state))

    assert result["errors"] == ""
    # 有警告但状态仍然是 in_progress
    assert result["status"] == "in_progress"
    print("✅ 部分数据 Fan-in 测试通过")


def test_fan_in_missing_weather():
    """测试缺少天气数据的 Fan-in"""
    state = create_test_state(
        attractions=create_sample_attractions(5),
        hotels=create_sample_hotels(3),
        weather=[],  # 缺少天气
        completed_agents=["attraction", "hotel"],
        days=5,
    )

    result = asyncio.run(fan_in_node(state))

    assert result["status"] == "in_progress"
    print("✅ 缺少天气数据 Fan-in 测试通过")


def test_check_phase1_complete():
    """测试 Phase 1 完成检查"""
    # 全部完成
    state_complete = create_test_state(
        attractions=create_sample_attractions(3),
        hotels=create_sample_hotels(2),
        completed_agents=["attraction", "hotel"],
    )
    assert check_phase1_complete(state_complete) is True

    # 缺少 attraction
    state_no_attr = create_test_state(
        attractions=[],
        hotels=create_sample_hotels(2),
        completed_agents=["hotel"],
    )
    assert check_phase1_complete(state_no_attr) is False

    # 缺少 hotel
    state_no_hotel = create_test_state(
        attractions=create_sample_attractions(3),
        hotels=[],
        completed_agents=["attraction"],
    )
    assert check_phase1_complete(state_no_hotel) is False

    # 数据为空但标记完成
    state_empty_but_marked = create_test_state(
        attractions=[],
        hotels=[],
        weather=[],
        completed_agents=["attraction", "hotel"],
    )
    assert check_phase1_complete(state_empty_but_marked) is False

    print("✅ Phase 1 完成检查测试通过")


def test_get_phase1_progress():
    """测试 Phase 1 进度获取"""
    # 初始状态
    state_initial = create_test_state(completed_agents=[])
    progress = get_phase1_progress(state_initial)
    assert progress["progress_percent"] == 0
    assert progress["current_step"] == "搜索景点"
    assert progress["is_complete"] is False

    # 完成 attraction
    state_attr = create_test_state(completed_agents=["attraction"])
    progress = get_phase1_progress(state_attr)
    assert progress["progress_percent"] == 50
    assert progress["current_step"] == "筛选酒店"

    # 完成 attraction + hotel
    state_attr_hotel = create_test_state(completed_agents=["attraction", "hotel"])
    progress = get_phase1_progress(state_attr_hotel)
    assert progress["progress_percent"] == 100  # 2/2 = 100%
    assert progress["current_step"] == "数据汇聚"

    # 全部完成
    state_all = create_test_state(completed_agents=["attraction", "hotel"])
    progress = get_phase1_progress(state_all)
    assert progress["progress_percent"] == 100
    assert progress["current_step"] == "数据汇聚"
    assert progress["is_complete"] is True

    print("✅ Phase 1 进度获取测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🧪 开始测试 Fan-in 节点")
    print("=" * 60)

    test_fan_in_complete_data()
    test_fan_in_empty_data()
    test_fan_in_partial_data()
    test_fan_in_missing_weather()
    test_check_phase1_complete()
    test_get_phase1_progress()

    print("=" * 60)
    print("🎉 所有 Fan-in 节点测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
