"""
TripState 模型测试

验证优化后的 TripState 结构正确性
"""

import pytest
from datetime import date
from typing import get_type_hints

from app.ai.models.graph_models import TripState


class TestTripState:
    """TripState 测试类"""

    def test_tripstate_basic_creation(self):
        """测试基本 TripState 创建"""
        state: TripState = {
            "request": {"destination": "上海", "days": 3},
            "attractions": [],
            "hotels": [],
            "restaurants": [],
            "weather": [],
            "status": "in_progress",
            "itinerary_draft": None,
            "messages": [],
        }

        assert state["request"]["destination"] == "上海"
        assert state["status"] == "in_progress"
        assert state["attractions"] == []

    def test_tripstate_with_preferences(self):
        """测试带有用户偏好的 TripState"""
        state: TripState = {
            "request": {"destination": "北京", "days": 5},
            # 新增偏好字段
            "companions": "家庭出行",
            "style_preferences": ["文化体验", "历史古迹"],
            "pace": "适中",
            "hotel_level": "舒适型",
            # Agent输出
            "attractions": [],
            "hotels": [],
            "restaurants": [],
            "weather": [],
            "status": "in_progress",
            "messages": [],
        }

        assert state["companions"] == "家庭出行"
        assert "文化体验" in state["style_preferences"]
        assert state["pace"] == "适中"
        assert state["hotel_level"] == "舒适型"

    def test_tripstate_with_search_params(self):
        """测试带有搜索参数的 TripState"""
        state: TripState = {
            "request": {"destination": "成都", "days": 4},
            # Supervisor生成的搜索参数
            "search_keywords": "成都,美食,文化,博物馆",
            "hotel_price_range": "300,600",
            "max_attractions_per_day": 3,
            "needed_attractions": 12,
            "total_budget": 8000.0,
            # Agent输出
            "attractions": [{"name": "宽窄巷子", "rating": 4.5}],
            "hotels": [{"name": "锦江宾馆", "rating": 4.8}],
            "restaurants": [],
            "weather": [],
            "status": "in_progress",
            "messages": [],
        }

        assert state["search_keywords"] == "成都,美食,文化,博物馆"
        assert state["hotel_price_range"] == "300,600"
        assert state["max_attractions_per_day"] == 3
        assert state["needed_attractions"] == 12
        assert state["total_budget"] == 8000.0
        assert len(state["attractions"]) == 1

    def test_tripstate_with_streaming(self):
        """测试带有流式更新字段的 TripState"""
        state: TripState = {
            "request": {"destination": "杭州"},
            "attractions": [],
            "hotels": [],
            "restaurants": [],
            "weather": [],
            "status": "in_progress",
            # 新增流式字段
            "streaming_updates": "✅ 已了解您的旅行需求\n📍 目的地: 杭州\n🚀 开始搜索...",
            "completed_agents": ["attraction", "hotel"],
            "messages": [],
        }

        assert "杭州" in state["streaming_updates"]
        assert "attraction" in state["completed_agents"]

    def test_tripstate_completed_state(self):
        """测试完成状态的 TripState"""
        state: TripState = {
            "request": {"destination": "西安", "days": 3},
            "companions": "情侣出行",
            "style_preferences": ["历史古迹", "文化体验"],
            "pace": "宽松",
            "hotel_level": "高档型",
            "search_keywords": "西安,历史,文化,古迹",
            "hotel_price_range": "500,1000",
            "max_attractions_per_day": 2,
            "needed_attractions": 6,
            "total_budget": 6000.0,
            # Agent输出
            "attractions": [
                {"name": "兵马俑", "rating": 4.9},
                {"name": "大雁塔", "rating": 4.7},
            ],
            "hotels": [{"name": "西安喜来登", "rating": 4.8}],
            "restaurants": [{"name": "回民街小吃", "type": "local"}],
            "weather": [{"date": "2025-06-01", "condition": "晴"}],
            "transport": {"mode": "mixed", "estimated_cost": 500},
            # 最终结果
            "itinerary_draft": {
                "city": "西安",
                "days": [
                    {"day_index": 1, "date": "2025-06-01", "attractions": ["兵马俑"]},
                ],
            },
            # 流程控制
            "status": "completed",
            "errors": "",
            "streaming_updates": "✅ 行程规划完成！",
            "completed_agents": ["attraction", "hotel", "restaurant", "weather", "transport"],
            "messages": [],
        }

        assert state["status"] == "completed"
        assert len(state["attractions"]) == 2
        assert state["itinerary_draft"]["city"] == "西安"
        assert len(state["completed_agents"]) == 5

    def test_tripstate_error_state(self):
        """测试错误状态的 TripState"""
        state: TripState = {
            "request": {"destination": "未知城市"},
            "attractions": [],
            "hotels": [],
            "restaurants": [],
            "weather": [],
            "status": "error",
            "errors": "无法识别目的地: 未知城市",
            "streaming_updates": "❌ 规划失败: 无法识别目的地",
            "messages": [],
        }

        assert state["status"] == "error"
        assert "无法识别" in state["errors"]

    def test_tripstate_field_types(self):
        """测试 TripState 字段类型"""
        # 验证类型注解存在
        hints = get_type_hints(TripState)

        assert "request" in hints
        assert "attractions" in hints
        assert "companions" in hints  # 新增字段
        assert "streaming_updates" in hints  # 新增字段
        assert "completed_agents" in hints  # 新增字段

    def test_tripstate_partial_fields(self):
        """测试部分字段的 TripState（模拟执行中间状态）"""
        # 模拟 Supervisor 执行后的状态
        state_after_supervisor: TripState = {
            "request": {"destination": "上海", "days": 3},
            "companions": "朋友出行",
            "style_preferences": ["美食", "购物"],
            "pace": "紧凑",
            "hotel_level": "舒适型",
            "search_keywords": "上海,美食,购物,外滩",
            "hotel_price_range": "300,600",
            "max_attractions_per_day": 4,
            "needed_attractions": 12,
            "total_budget": 5000.0,
            "attractions": [],  # 尚未填充
            "hotels": [],
            "restaurants": [],
            "weather": [],
            "status": "in_progress",
            "streaming_updates": "🚀 开始搜索景点、餐厅、酒店和天气...",
            "completed_agents": [],
            "messages": [],
        }

        assert state_after_supervisor["search_keywords"] is not None
        assert len(state_after_supervisor["completed_agents"]) == 0

        # 模拟 Attraction Agent 完成后的状态
        state_after_attraction = dict(state_after_supervisor)
        state_after_attraction["attractions"] = [
            {"name": "外滩", "rating": 4.8},
            {"name": "东方明珠", "rating": 4.6},
        ]
        state_after_attraction["completed_agents"] = ["attraction"]
        state_after_attraction["streaming_updates"] += "\n✅ 找到 2 个推荐景点"

        assert "attraction" in state_after_attraction["completed_agents"]
        assert len(state_after_attraction["attractions"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
