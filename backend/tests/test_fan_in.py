"""
Fan-in 汇聚节点测试
"""

import asyncio

from app.ai.models.graph_models import TripState
from app.ai.nodes.fan_in_node import fan_in_node


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
    """测试 worker 批次汇合不再输出旧 Phase-1 文案"""
    state = create_test_state(
        attractions=create_sample_attractions(5),
        hotels=create_sample_hotels(3),
        completed_agents=["strategy", "weather"],
        days=3,
    )
    state["current_workers"] = ["strategy_agent", "weather_agent"]

    result = asyncio.run(fan_in_node(state))

    assert result["worker_batch_completed"] is True
    assert result["completed_workers_in_batch"] == [
        "strategy_agent",
        "weather_agent",
    ]
    assert "Worker批次完成" in result["streaming_updates"]
    assert "基础数据采集完成" not in result["streaming_updates"]
    assert "进入评审" not in result["streaming_updates"]
    assert result["status"] == "in_progress"  # 没有错误
    print("✅ 完整数据 Fan-in 测试通过")


def test_fan_in_empty_data():
    """空数据不由 worker join 判定为 phase-1 错误"""
    state = create_test_state(
        attractions=[],
        hotels=[],
        weather=[],
        completed_agents=[],
    )

    result = asyncio.run(fan_in_node(state))

    assert "errors" not in result
    assert result["worker_batch_completed"] is True
    assert result["status"] == "in_progress"
    print("✅ 空数据 Fan-in 测试通过")


def test_fan_in_partial_data():
    """部分数据不由 worker join 添加警告"""
    state = create_test_state(
        attractions=create_sample_attractions(2),  # 只有2个景点
        hotels=create_sample_hotels(1),  # 只有1家酒店
        completed_agents=["attraction", "hotel"],
    )

    result = asyncio.run(fan_in_node(state))

    assert "errors" not in result
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


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🧪 开始测试 Fan-in 节点")
    print("=" * 60)

    test_fan_in_complete_data()
    test_fan_in_empty_data()
    test_fan_in_partial_data()
    test_fan_in_missing_weather()

    print("=" * 60)
    print("🎉 所有 Fan-in 节点测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
