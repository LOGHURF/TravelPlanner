"""
Pydantic 模型测试 - 验证优化后的 travel_models
"""

from datetime import date
from pydantic import ValidationError

from app.ai.models.travel_models import (
    TripRequest, Location, Attraction, Hotel, Restaurant,
    WeatherInfo, RouteSegment, TransportPlan, DailyPlan, TripPlan
)


def test_trip_request_with_preferences():
    """测试 TripRequest 新增偏好字段"""
    req = TripRequest(
        destination="北京",
        start_date=date(2025, 6, 1),
        end_date=date(2025, 6, 5),
        num_people=2,
        budget_per_person=5000,
        # 新增偏好字段
        companions="家庭出行",
        style_preferences=["文化体验", "历史古迹"],
        pace="适中",
        hotel_level="舒适型",
    )

    assert req.destination == "北京"
    assert req.days == 5
    assert req.total_budget == 10000.0
    # 验证新增字段
    assert req.companions == "家庭出行"
    assert "文化体验" in req.style_preferences
    assert req.pace == "适中"
    assert req.hotel_level == "舒适型"

    # 测试 to_state_dict
    state_dict = req.to_state_dict()
    assert state_dict["companions"] == "家庭出行"
    assert "search_keywords" not in state_dict  # 由 Supervisor 生成
    print("✅ TripRequest 测试通过")


def test_trip_request_uses_duration_when_dates_missing():
    req = TripRequest(destination="成都", duration=4)

    assert req.days == 4


def test_trip_request_rejects_duration_mismatch_with_dates():
    try:
        TripRequest(
            destination="杭州",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 5),
            duration=3,
        )
    except ValidationError as exc:
        assert "duration must match start_date/end_date" in str(exc)
    else:
        raise AssertionError("TripRequest accepted inconsistent duration")


def test_trip_request_rejects_external_days_field():
    try:
        TripRequest(destination="北京", days=7)
    except ValidationError as exc:
        assert "Extra inputs are not permitted" in str(exc)
    else:
        raise AssertionError("TripRequest accepted external days field")


def test_location():
    """测试 Location 模型"""
    loc = Location(lat=39.9042, lng=116.4074)
    assert loc.lat == 39.9042
    assert loc.lng == 116.4074
    assert loc.to_str() == "116.4074,39.9042"  # 高德格式：lng,lat
    print("✅ Location 测试通过")


def test_attraction_enhanced():
    """测试增强的 Attraction 模型"""
    attr = Attraction(
        name="故宫",
        address="北京市东城区景山前街4号",
        location=Location(lat=39.9163, lng=116.3972),
        rating=4.9,
        category="历史古迹",
        tags=["世界遗产", "5A景区", "博物馆"],
        visit_duration="4小时",
        indoor=True,
        ticket_price=60.0,
        open_hours="08:30-17:00",
        description="中国明清两代的皇家宫殿",
    )

    assert attr.name == "故宫"
    assert attr.ticket_price == 60.0
    assert attr.open_hours == "08:30-17:00"
    assert len(attr.tags) == 3
    print("✅ Attraction 测试通过")


def test_hotel_enhanced():
    """测试增强的 Hotel 模型"""
    hotel = Hotel(
        name="北京饭店",
        address="北京市东城区东长安街33号",
        location=Location(lat=39.9097, lng=116.4117),
        rating=4.8,
        hotel_level="高档型",
        star_rating=5,
        price_per_night=800.0,
        total_price=3200.0,
        amenities=["WiFi", "停车场", "健身房", "游泳池"],
    )

    assert hotel.name == "北京饭店"
    assert hotel.price_per_night == 800.0
    assert hotel.star_rating == 5
    assert "游泳池" in hotel.amenities
    print("✅ Hotel 测试通过")


def test_restaurant_enhanced():
    """测试增强的 Restaurant 模型"""
    restaurant = Restaurant(
        name="全聚德",
        type="dinner",
        address="北京市东城区前门大街30号",
        location=Location(lat=39.8998, lng=116.3974),
        rating=4.5,
        estimated_cost=300,
        price_per_person=150,
        cuisine_type="北京菜",
        is_recommended=True,
        description="正宗北京烤鸭",
    )

    assert restaurant.name == "全聚德"
    assert restaurant.rating == 4.5
    assert restaurant.cuisine_type == "北京菜"
    assert restaurant.is_recommended is True
    print("✅ Restaurant 测试通过")


def test_weather_info_enhanced():
    """测试增强的 WeatherInfo 模型"""
    weather = WeatherInfo(
        date="2025-06-01",
        day_weather="晴",
        night_weather="多云",
        day_temp=28,
        night_temp=18,
        wind_direction="东南",
        wind_power="3级",
        suggestion="适合户外活动，注意防晒",
        uv_index="强",
        comfort_index="舒适",
    )

    assert weather.date == "2025-06-01"
    assert weather.suggestion == "适合户外活动，注意防晒"
    assert weather.uv_index == "强"
    print("✅ WeatherInfo 测试通过")


def test_weather_temperature_validator():
    """测试 WeatherInfo 温度解析器"""
    # 测试字符串温度解析
    weather = WeatherInfo(
        date="2025-06-01",
        day_weather="晴",
        night_weather="多云",
        day_temp="26°C",  # 字符串格式
        night_temp="18℃",
        wind_direction="南",
        wind_power="2级",
    )

    assert weather.day_temp == 26
    assert weather.night_temp == 18
    print("✅ WeatherInfo 温度解析器测试通过")


def test_route_segment():
    """测试 RouteSegment 模型（新增）"""
    segment = RouteSegment(
        from_name="故宫",
        to_name="天安门",
        from_location=Location(lat=39.9163, lng=116.3972),
        to_location=Location(lat=39.9055, lng=116.3976),
        mode="walking",
        distance=1.2,
        duration=15,
        cost=0,
        instruction="从故宫步行至天安门约15分钟",
    )

    assert segment.from_name == "故宫"
    assert segment.distance == 1.2
    assert segment.duration == 15
    print("✅ RouteSegment 测试通过")


def test_transport_plan():
    """测试 TransportPlan 模型（新增）"""
    transport = TransportPlan(
        inter_city={
            "mode": "train",
            "from": "上海",
            "to": "北京",
            "departure": "2025-06-01 08:00",
            "arrival": "2025-06-01 12:30",
        },
        daily_routes=[
            [  # 第1天的路线
                RouteSegment(
                    from_name="酒店",
                    to_name="故宫",
                    from_location=Location(lat=39.9, lng=116.4),
                    to_location=Location(lat=39.9163, lng=116.3972),
                    mode="driving",
                    distance=5.0,
                    duration=20,
                    cost=25.0,
                ),
            ]
        ],
        suggested_mode="mixed",
        estimated_transport_cost=500.0,
    )

    assert transport.suggested_mode == "mixed"
    assert transport.estimated_transport_cost == 500.0
    assert len(transport.daily_routes) == 1
    print("✅ TransportPlan 测试通过")


def test_daily_plan_enhanced():
    """测试增强的 DailyPlan 模型"""
    daily = DailyPlan(
        date="2025-06-01",
        day_index=1,
        day_of_week="周一",
        description="历史文化之旅",
        weather=WeatherInfo(
            date="2025-06-01",
            day_weather="晴",
            night_weather="多云",
            day_temp=28,
            night_temp=18,
            wind_direction="南",
            wind_power="2级",
        ),
        weather_note="天气晴好，适合户外活动",
        hotel=Hotel(
            name="北京饭店",
            address="东长安街33号",
            location=Location(lat=39.9, lng=116.4),
        ),
        attractions=[
            Attraction(
                name="故宫",
                address="景山前街4号",
                location=Location(lat=39.9163, lng=116.3972),
            ),
        ],
        meals=[
            Restaurant(name="全聚德", type="lunch", estimated_cost=200),
        ],
        estimated_cost={
            "attractions": 60,
            "meals": 200,
            "transport": 50,
            "hotel": 800,
        },
        timeline=[
            {"time": "09:00", "activity": "参观故宫", "type": "attraction"},
            {"time": "12:00", "activity": "午餐", "type": "meal"},
        ],
    )

    assert daily.day_index == 1
    assert daily.day_of_week == "周一"
    assert daily.total_cost == 1110.0  # 60+200+50+800
    assert daily.attraction_count == 1
    assert len(daily.timeline) == 2
    print("✅ DailyPlan 测试通过")


def test_trip_plan_enhanced():
    """测试增强的 TripPlan 模型"""
    plan = TripPlan(
        city="北京",
        start_date="2025-06-01",
        end_date="2025-06-05",
        total_days=5,
        days=[
            DailyPlan(
                date="2025-06-01",
                day_index=1,
                attractions=[
                    Attraction(name="故宫", address="景山前街", location=Location(lat=39.9, lng=116.4)),
                    Attraction(name="天安门", address="天安门广场", location=Location(lat=39.9, lng=116.4)),
                ],
            ),
            DailyPlan(
                date="2025-06-02",
                day_index=2,
                attractions=[
                    Attraction(name="长城", address="八达岭", location=Location(lat=40.4, lng=116.0)),
                ],
            ),
        ],
        budget_breakdown={
            "hotel": 4000,
            "attractions": 500,
            "meals": 1500,
            "transport": 1000,
        },
        total_budget=10000,
        estimated_total_cost=7000,
        overall_suggestions="建议提前预订景点门票",
        packing_tips=["防晒霜", "舒适的鞋子"],
        important_notes=["故宫周一闭馆"],
        statistics={
            "attraction_count": 3,
            "restaurant_count": 6,
            "hotel_count": 1,
        },
    )

    assert plan.city == "北京"
    assert plan.total_days == 5
    assert plan.total_attractions == 3  # 2 + 1
    assert plan.budget_status == "ok"  # 7000/10000 = 0.7 < 0.9
    assert len(plan.packing_tips) == 2
    print("✅ TripPlan 测试通过")


def test_trip_plan_budget_status():
    """测试 TripPlan 预算状态判断"""
    # 预算紧张
    plan_tight = TripPlan(
        city="上海",
        start_date="2025-06-01",
        end_date="2025-06-03",
        total_budget=5000,
        estimated_total_cost=4600,  # 92%
    )
    assert plan_tight.budget_status == "tight"

    # 超预算
    plan_over = TripPlan(
        city="上海",
        start_date="2025-06-01",
        end_date="2025-06-03",
        total_budget=5000,
        estimated_total_cost=5500,  # 110%
    )
    assert plan_over.budget_status == "over"

    # 无预算
    plan_unknown = TripPlan(
        city="上海",
        start_date="2025-06-01",
        end_date="2025-06-03",
    )
    assert plan_unknown.budget_status == "unknown"
    print("✅ TripPlan 预算状态测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🧪 开始测试 Pydantic 模型")
    print("=" * 60)

    test_trip_request_with_preferences()
    test_location()
    test_attraction_enhanced()
    test_hotel_enhanced()
    test_restaurant_enhanced()
    test_weather_info_enhanced()
    test_weather_temperature_validator()
    test_route_segment()
    test_transport_plan()
    test_daily_plan_enhanced()
    test_trip_plan_enhanced()
    test_trip_plan_budget_status()

    print("=" * 60)
    print("🎉 所有 Pydantic 模型测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
