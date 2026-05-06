"""
集成测试 - 验证完整数据流

测试流程：
Strategy-first artifacts → FanIn → Itinerary composition data → Weather → FinalPlanning
"""

import asyncio
from datetime import date, timedelta
import pytest

import app.ai.nodes.final_planning_node as final_planning_module
from app.ai.models.graph_models import TripState
from app.ai.nodes.orchestrator_node import orchestrator_node
from app.ai.nodes.fan_in_node import fan_in_node
from app.ai.nodes.final_planning_node import _build_summary_prompt_variables, final_planning_node
from app.ai.models import TripRequest
from app.api.routers.travel import plan_travel_sync

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def stub_final_summary_llm():
    return None


def create_initial_state() -> TripState:
    """创建初始测试状态"""
    today = date.today()
    return {
        "request": {
            "destination": "北京",
            "start_date": today.strftime("%Y-%m-%d"),
            "end_date": (today + timedelta(days=2)).strftime("%Y-%m-%d"),
            "days": 3,
            "num_people": 2,
            "budget_per_person": 3000,
            "preferences": ["文化", "美食"],
        },
        "companions": "家庭",
        "style_preferences": ["文化体验", "历史古迹"],
        "pace": "适中",
        "hotel_level": "舒适型",
    }


def seed_attractions(state: TripState) -> TripState:
    """写入已验证景点数据"""
    state["attractions"] = [
        {
            "name": "故宫",
            "address": "北京市东城区景山前街4号",
            "location": {"lat": 39.9163, "lng": 116.3972},
            "rating": 4.9,
            "visit_duration": "4小时",
            "category": "历史古迹",
            "description": "明清皇宫",
        },
        {
            "name": "天安门",
            "address": "北京市东城区天安门广场",
            "location": {"lat": 39.9055, "lng": 116.3976},
            "rating": 4.8,
            "visit_duration": "1小时",
            "category": "历史古迹",
        },
        {
            "name": "颐和园",
            "address": "北京市海淀区新建宫门路19号",
            "location": {"lat": 39.9999, "lng": 116.2755},
            "rating": 4.8,
            "visit_duration": "3小时",
            "category": "自然风光",
        },
    ]
    completed = state.get("completed_agents", [])
    if "attraction" not in completed:
        completed.append("attraction")
    state["completed_agents"] = completed
    state["streaming_updates"] = state.get("streaming_updates", "") + "\n✅ 找到3个景点"
    return state


def seed_hotels(state: TripState) -> TripState:
    """写入已验证酒店数据"""
    state["hotels"] = [
        {
            "name": "北京饭店",
            "address": "北京市东城区东长安街33号",
            "location": {"lat": 39.9097, "lng": 116.4117},
            "rating": 4.8,
            "price_per_night": 600,
            "hotel_level": "高档型",
        },
        {
            "name": "如家酒店",
            "address": "北京市东城区王府井大街",
            "location": {"lat": 39.911, "lng": 116.41},
            "rating": 4.2,
            "price_per_night": 350,
            "hotel_level": "舒适型",
        },
    ]
    completed = state.get("completed_agents", [])
    if "hotel" not in completed:
        completed.append("hotel")
    state["completed_agents"] = completed
    state["streaming_updates"] = state.get("streaming_updates", "") + "\n✅ 找到2家酒店"
    return state


def mock_weather_agent(state: TripState) -> TripState:
    """模拟天气 Agent"""
    today = date.today()
    state["weather"] = [
        {
            "date": (today + timedelta(days=i)).strftime("%Y-%m-%d"),
            "day_weather": "晴" if i % 2 == 0 else "多云",
            "night_weather": "多云",
            "day_temp": 26 - i,
            "night_temp": 18 - i,
            "wind_direction": "南",
            "wind_power": "2级",
        }
        for i in range(3)
    ]
    completed = state.get("completed_agents", [])
    if "weather" not in completed:
        completed.append("weather")
    state["completed_agents"] = completed
    state["streaming_updates"] = state.get("streaming_updates", "") + "\n✅ 获取3天天气"
    return state


def seed_restaurants(state: TripState) -> TripState:
    """写入已验证餐饮数据"""
    state["restaurants"] = [
        {
            "name": "全聚德",
            "type": "dinner",
            "estimated_cost": 150,
            "cuisine_type": "北京菜",
        },
        {
            "name": "护国寺小吃",
            "type": "lunch",
            "estimated_cost": 50,
            "cuisine_type": "小吃",
        },
    ]
    state["streaming_updates"] = state.get("streaming_updates", "") + "\n✅ 找到2家餐厅"
    return state


def seed_transport(state: TripState) -> TripState:
    """写入已组合交通数据"""
    state["transport"] = {
        "suggested_mode": "mixed",
        "estimated_transport_cost": 300,
        "daily_routes": [],
    }
    state["streaming_updates"] = state.get("streaming_updates", "") + "\n✅ 交通规划完成"
    return state


def test_supervisor():
    """测试 Supervisor 节点"""
    print("\n[1/7] 测试 Supervisor...")
    state = create_initial_state()
    result = orchestrator_node(state)
    
    assert result["search_keywords"] is not None
    assert result["hotel_price_range"] is not None
    assert result["max_attractions_per_day"] in (1, 2)  # LLM可动态决策，系统约束范围1~2
    assert result["companions"] == "家庭"
    assert "文化体验" in result["style_preferences"]
    print("   ✅ Supervisor 生成搜索参数正确")


def test_parallel_agents():
    """测试并行 Agent"""
    print("\n[2/7] 测试并行 Agents...")
    state = create_initial_state()
    
    # 模拟并行执行
    seed_attractions(state)
    seed_hotels(state)
    
    assert len(state["attractions"]) == 3
    assert len(state["hotels"]) == 2
    assert set(state["completed_agents"]) == {"attraction", "hotel"}
    print("   ✅ 并行 Agents 完成，数据正确")


def test_fan_in():
    """测试 Fan-in 节点"""
    print("\n[3/7] 测试 Fan-in...")
    state = create_initial_state()
    
    # 先执行并行 Agent
    seed_attractions(state)
    seed_hotels(state)
    
    # 执行 Fan-in
    result = asyncio.run(fan_in_node(state))
    
    assert result["worker_batch_completed"] is True
    assert result["completed_workers_in_batch"] == []
    assert "Worker批次完成" in result["streaming_updates"]
    print("   ✅ Fan-in 汇聚成功")


def test_sequential_agents():
    """测试顺序 Agents"""
    print("\n[4/7] 测试顺序 Agents...")
    state = create_initial_state()
    
    seed_attractions(state)
    seed_hotels(state)
    asyncio.run(fan_in_node(state))
    
    # 顺序执行
    seed_restaurants(state)
    seed_transport(state)
    mock_weather_agent(state)
    
    assert len(state["restaurants"]) == 2
    assert state["transport"] is not None
    print("   ✅ 顺序 Agents 完成")


def test_final_planning():
    """测试 Final Planning 节点"""
    print("\n[5/7] 测试 Final Planning...")
    state = create_initial_state()
    
    # 执行所有前置 Agent
    seed_attractions(state)
    seed_hotels(state)
    asyncio.run(fan_in_node(state))
    seed_restaurants(state)
    seed_transport(state)
    mock_weather_agent(state)
    
    # 执行 Final Planning
    result = asyncio.run(final_planning_node(state))
    
    itinerary = result["itinerary_draft"]
    assert itinerary is not None
    assert itinerary["city"] == "北京"
    assert itinerary["total_days"] == 3
    assert len(itinerary["days"]) == 3
    assert isinstance(itinerary.get("narrative_plan", ""), str)
    assert itinerary.get("narrative_plan", "") != ""
    assert itinerary["statistics"]["attraction_count"] == 3
    assert itinerary["days"][0]["hotel"]["name"] == "北京饭店"
    assert itinerary["days"][1]["hotel"]["name"] == "北京饭店"
    assert itinerary["days"][2]["hotel"]["name"] == "如家酒店"
    assert result["status"] == "completed"
    print(f"   ✅ 行程生成成功：{itinerary['total_days']}天，{itinerary['statistics']['attraction_count']}个景点")
    print(f"   💰 预估费用: {itinerary['estimated_total_cost']}元")


def test_final_planning_uses_days_without_dates():
    """测试只有天数时依然按多天生成行程"""
    state = create_initial_state()
    state["request"] = {
        "destination": "北京",
        "duration": 3,
        "days": 3,
        "num_people": 2,
    }

    seed_attractions(state)
    seed_hotels(state)
    asyncio.run(fan_in_node(state))
    seed_restaurants(state)
    seed_transport(state)
    mock_weather_agent(state)

    result = asyncio.run(final_planning_node(state))
    itinerary = result["itinerary_draft"]

    assert itinerary is not None
    assert itinerary["total_days"] == 3
    assert len(itinerary["days"]) == 3
    assert itinerary["start_date"] != ""
    assert itinerary["end_date"] != ""


def test_final_summary_prompt_variables_include_evaluation_context():
    variables = _build_summary_prompt_variables(
        request={"destination": "杭州", "days": 2},
        attractions=[{"name": "西湖"}],
        hotels=[{"name": "湖滨酒店"}],
        restaurants=[{"name": "杭帮菜"}],
        weather=[],
        days=2,
        evaluation={
            "passed": True,
            "score": 0.88,
            "residual_risks": ["热门景点仍需预约"],
        },
    )

    assert "evaluation" in variables["context_json"]
    assert "热门景点仍需预约" in variables["context_json"]


def test_final_planning_marks_max_repair_exhaustion_as_important_note():
    """审核未通过但修复轮耗尽时，最终行程必须显式暴露风险。"""
    state = create_initial_state()
    seed_attractions(state)
    seed_hotels(state)
    asyncio.run(fan_in_node(state))
    seed_restaurants(state)
    seed_transport(state)
    mock_weather_agent(state)
    state["final_with_warnings"] = True
    state["evaluation_failed_after_max_iterations"] = True
    state["evaluation"] = {
        "passed": False,
        "score": 0.66,
        "blocking_issues": ["第1天交通跨度过大"],
        "residual_risks": ["热门景点仍需预约"],
    }

    result = asyncio.run(final_planning_node(state))
    notes = result["itinerary_draft"]["important_notes"]

    assert any("最大修复轮" in note for note in notes)
    assert any("第1天交通跨度过大" in note for note in notes)
    assert any("热门景点仍需预约" in note for note in notes)


def test_final_planning_does_not_depend_on_summary_llm():
    """最终行程不应因为总结文案 LLM 输出过长而失败。"""
    state = create_initial_state()
    seed_attractions(state)
    seed_hotels(state)
    asyncio.run(fan_in_node(state))
    seed_restaurants(state)
    seed_transport(state)
    mock_weather_agent(state)

    result = asyncio.run(final_planning_node(state))
    itinerary = result["itinerary_draft"]

    assert not hasattr(final_planning_module, "invoke_prompt_json_async")
    assert result["status"] == "completed"
    assert itinerary["overall_suggestions"]
    assert itinerary["narrative_plan"]
    assert itinerary["important_notes"]
    assert itinerary["packing_tips"]


def test_final_planning_preserves_meal_anchor_metadata():
    state = create_initial_state()
    state["request"]["days"] = 1
    state["request"]["end_date"] = state["request"]["start_date"]
    attraction = {
        "name": "上午景点",
        "address": "上午路",
        "location": {"lat": 30.0, "lng": 120.0},
        "rating": 4.8,
        "category": "风景名胜",
    }
    hotel = {
        "name": "湖滨酒店",
        "address": "湖滨路",
        "location": {"lat": 30.0, "lng": 120.0},
        "price_per_night": 500,
    }
    meal = {
        "name": "锚点午餐",
        "meal_type": "lunch",
        "location": {"lat": 30.001, "lng": 120.0},
        "meal_anchor_name": "上午景点",
        "meal_anchor_role": "first_attraction",
        "distance_to_anchor_km": 0.1,
    }
    state["attractions"] = [attraction]
    state["hotels"] = [hotel]
    state["restaurants"] = [meal]
    state["weather"] = []
    state["transport"] = {
        "suggested_mode": "walking",
        "estimated_transport_cost": 0,
        "daily_routes": [[]],
        "daily_plan": [
            {
                "day_index": 1,
                "hotel": hotel,
                "attractions": [attraction],
                "meals": [meal],
            }
        ],
    }

    result = asyncio.run(final_planning_node(state))

    output_meal = result["itinerary_draft"]["days"][0]["meals"][0]
    assert output_meal["meal_anchor_name"] == "上午景点"
    assert output_meal["meal_anchor_role"] == "first_attraction"
    assert output_meal["distance_to_anchor_km"] == 0.1


def test_plan_travel_sync_serializes_validated_hotel_model():
    class FakeGraph:
        async def ainvoke(self, initial_state, config):
            return {
                "status": "completed",
                "streaming_updates": "行程完成",
                "itinerary_draft": {
                    "city": "杭州",
                    "start_date": "2026-05-05",
                    "end_date": "2026-05-05",
                    "total_days": 1,
                    "days": [
                        {
                            "date": "2026-05-05",
                            "day_index": 1,
                            "hotel": {"name": "湖滨酒店", "address": "湖滨"},
                            "attractions": [],
                            "meals": [],
                            "route_segments": [],
                        }
                    ],
                    "narrative_plan": "杭州一日行程。",
                    "statistics": {"attraction_count": 0, "restaurant_count": 0},
                },
            }

    result = asyncio.run(
        plan_travel_sync(
            TripRequest(destination="杭州", duration=1),
            graph=FakeGraph(),
        )
    )

    assert result.success is True
    assert result.itinerary is not None
    assert isinstance(result.itinerary.hotel, dict)
    assert result.itinerary.hotel["name"] == "湖滨酒店"
    assert result.itinerary.hotel["address"] == "湖滨"


def test_full_flow():
    """测试完整流程"""
    print("\n[6/7] 测试完整数据流...")
    
    # 1. Supervisor
    state = create_initial_state()
    state = orchestrator_node(state)
    
    # 2. 并行 Phase 1
    state = seed_attractions(state)
    state = seed_hotels(state)
    
    # 3. Fan-in
    state = asyncio.run(fan_in_node(state))
    
    # 4. 顺序 Phase 2
    state = seed_restaurants(state)
    state = seed_transport(state)
    state = mock_weather_agent(state)
    
    # 5. Final Planning
    state = asyncio.run(final_planning_node(state))
    
    # 验证最终结果
    assert state["status"] == "completed"
    assert "itinerary_draft" in state
    assert state["worker_batch_completed"] is True
    
    print("   ✅ 完整数据流测试通过")
    print(f"\n📊 最终统计:")
    print(f"   景点: {len(state['attractions'])}个")
    print(f"   酒店: {len(state['hotels'])}家")
    print(f"   餐厅: {len(state['restaurants'])}家")
    print(f"   天气: {len(state['weather'])}天")


def test_trip_plan_structure():
    """测试 TripPlan 结构"""
    print("\n[7/7] 测试 TripPlan 结构...")
    
    from app.ai.models.travel_models import TripPlan, DailyPlan
    
    plan = TripPlan(
        city="上海",
        start_date="2025-06-01",
        end_date="2025-06-03",
        total_days=3,
        days=[
            DailyPlan(
                date="2025-06-01",
                day_index=1,
                description="第一天",
            ),
        ],
        budget_breakdown={
            "hotel": 2000,
            "attractions": 500,
            "meals": 800,
            "transport": 300,
        },
        total_budget=5000,
        estimated_total_cost=3600,
    )
    
    assert plan.city == "上海"
    assert plan.total_days == 3
    assert plan.budget_status == "ok"  # 3600/5000 < 0.9
    print("   ✅ TripPlan 结构正确")


def run_all_tests():
    """运行所有集成测试"""
    print("=" * 60)
    print("🧪 集成测试 - 完整数据流")
    print("=" * 60)
    
    test_supervisor()
    test_parallel_agents()
    test_fan_in()
    test_sequential_agents()
    test_final_planning()
    test_full_flow()
    test_trip_plan_structure()
    
    print("\n" + "=" * 60)
    print("🎉 所有集成测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
