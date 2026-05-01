import asyncio

from app.services.amap import POI, POISearchResponse
from app.ai.nodes.hotel_node import (
    _clean_poi_to_hotel,
    _default_hotel_types,
    _default_keywords_for_types,
    _hotel_target_counts,
    _normalize_hotel_types,
    hotel_node,
)
from app.ai.nodes.restaurant_node import (
    _clean_poi_to_restaurant,
    _default_keywords_for_types as _default_restaurant_keywords_for_types,
    _default_restaurant_types,
    _normalize_restaurant_types,
    _restaurant_target_counts,
    restaurant_node,
)


def test_hotel_target_counts_follow_two_day_rotation() -> None:
    assert _hotel_target_counts(2) == (1, 5)
    assert _hotel_target_counts(4) == (2, 6)


def test_normalize_hotel_types_accepts_valid_codes_and_aliases() -> None:
    result = _normalize_hotel_types(
        ["100102", "豪华酒店", "青旅", "无效类型"],
        keywords=["四星酒店"],
    )

    assert result == ["100102", "100101", "100201", "100103"]


def test_normalize_hotel_types_respects_allowed_types() -> None:
    result = _normalize_hotel_types(
        ["100102", "豪华酒店", "青旅"],
        allowed_types=["100101", "100201"],
    )

    assert result == ["100101", "100201"]


def test_default_hotel_types_match_high_end_family_context() -> None:
    result = _default_hotel_types(
        hotel_level="高档型",
        companions="家庭",
        special_requirements="希望安静一点，最好有景观，适合亲子",
    )

    assert result[:4] == ["100100", "100103", "100102", "100101"]


def test_default_keywords_for_hotel_types_returns_catalog_labels() -> None:
    assert _default_keywords_for_types(["100101", "100102", "100105"]) == [
        "奢华酒店",
        "五星级宾馆",
        "经济型连锁酒店",
    ]


def test_clean_poi_to_hotel_builds_display_description() -> None:
    poi = POI(
        id="hotel-1",
        name="大理山海观景酒店",
        address="大理古城东门",
        type="住宿服务;宾馆酒店;高档型宾馆",
        typecode="100105",
        location="100.170,25.692",
        business={"rating": "4.6", "cost": "488", "business_area": "大理古城"},
        photos=[{"url": "https://example.com/hotel.jpg"}],
    )

    hotel = _clean_poi_to_hotel(
        poi,
        hotel_level="高档型",
        days=4,
        keyword="观景酒店",
    )

    assert hotel is not None
    assert hotel["image_url"] == "https://example.com/hotel.jpg"
    assert "高档型" in hotel["description"]
    assert "评分4.6" in hotel["description"]


def test_clean_poi_to_hotel_rejects_guesthouse_for_high_end_level() -> None:
    poi = POI(
        id="hotel-2",
        name="大理古城精品旅馆",
        address="大理古城",
        type="住宿服务;宾馆酒店;旅馆招待所",
        typecode="100102",
        location="100.170,25.692",
        business={"rating": "4.8", "cost": "220", "business_area": "大理古城"},
    )

    hotel = _clean_poi_to_hotel(
        poi,
        hotel_level="高档型",
        days=2,
        keyword="高档酒店",
    )

    assert hotel is None


def test_clean_poi_to_hotel_rejects_non_hotel_poi() -> None:
    poi = POI(
        id="attraction-1",
        name="大理古城",
        address="大理古城",
        type="风景名胜;风景名胜相关;旅游景点",
        typecode="110202",
        location="100.170,25.692",
        business={"rating": "4.8"},
    )

    hotel = _clean_poi_to_hotel(
        poi,
        hotel_level="舒适型",
        days=2,
        keyword="古城酒店",
    )

    assert hotel is None


def test_hotel_node_does_not_apply_default_type_filters(monkeypatch) -> None:
    captured_args: list[dict] = []

    async def fake_invoke_tool_with_debug(*, tool_name, tool_args, log, context):
        captured_args.append(tool_args)
        return POISearchResponse(
            status="1",
            count=1,
            pois=[
                POI(
                    id="hotel-1",
                    name="大理山海观景酒店",
                    address="大理古城东门",
                    type="住宿服务;宾馆酒店;高档型宾馆",
                    typecode="100100",
                    location="100.170,25.692",
                    business={"rating": "4.6", "cost": "488", "business_area": "大理古城"},
                )
            ],
        )

    async def fake_select(*, request, candidates, final_needed, candidate_target, price_range):
        return candidates[:candidate_target], "test"

    monkeypatch.setattr("app.ai.nodes.hotel_node.get_tool", lambda tool_name: object())
    monkeypatch.setattr("app.ai.nodes.hotel_node.invoke_tool_with_debug", fake_invoke_tool_with_debug)
    monkeypatch.setattr("app.ai.nodes.hotel_node._select_hotel_candidates_with_llm", fake_select)

    asyncio.run(
        hotel_node(
            {
                "request": {
                    "destination": "大理",
                    "duration": 2,
                    "companions": "朋友",
                    "hotel_level": "高档型",
                },
                "hotel_price_range": "600,1200",
            }
        )
    )

    assert captured_args
    assert all("types" not in args for args in captured_args)


def test_restaurant_target_counts_follow_two_per_day_rule() -> None:
    assert _restaurant_target_counts(1) == (2, 4)
    assert _restaurant_target_counts(3) == (6, 8)


def test_normalize_restaurant_types_accepts_valid_codes_and_aliases() -> None:
    result = _normalize_restaurant_types(
        ["050117", "咖啡馆", "粤菜", "无效类型"],
        keywords=["甜品"],
    )

    assert result == ["050117", "050500", "050103", "050900"]


def test_normalize_restaurant_types_respects_allowed_types() -> None:
    result = _normalize_restaurant_types(
        ["050117", "咖啡馆", "粤菜"],
        allowed_types=["050500", "050103"],
    )

    assert result == ["050500", "050103"]


def test_default_restaurant_types_match_foodie_friends_context() -> None:
    result = _default_restaurant_types(
        preferences=["美食"],
        companions="朋友",
        special_requirements="晚上想吃火锅，也想找本地特色",
    )

    assert result[:6] == ["050118", "050116", "050117", "050123", "050102", "050108"]


def test_default_keywords_for_restaurant_types_returns_catalog_labels() -> None:
    assert _default_restaurant_keywords_for_types(["050117", "050500", "050103"]) == [
        "火锅店",
        "咖啡厅",
        "广东菜(粤菜)",
    ]


def test_clean_poi_to_restaurant_builds_display_description() -> None:
    poi = POI(
        id="food-1",
        name="喜洲破酥粑粑",
        address="大理喜洲古镇",
        type="餐饮服务;中餐厅;云南菜",
        typecode="050100",
        location="100.229,25.877",
        business={"rating": "4.5", "cost": "32", "business_area": "喜洲古镇"},
        photos=[{"url": "https://example.com/food.jpg"}],
    )

    restaurant = _clean_poi_to_restaurant(poi, keyword="大理特色菜")

    assert restaurant is not None
    assert restaurant["photo"] == "https://example.com/food.jpg"
    assert "云南菜" in restaurant["description"]
    assert "评分4.5" in restaurant["description"]
    assert restaurant["cuisine_type"] == "云南菜"


def test_clean_poi_to_restaurant_rejects_non_restaurant_poi() -> None:
    poi = POI(
        id="hotel-1",
        name="大理山海观景酒店",
        address="大理古城东门",
        type="住宿服务;宾馆酒店;高档型宾馆",
        typecode="100100",
        location="100.170,25.692",
        business={"rating": "4.6", "cost": "488"},
    )

    restaurant = _clean_poi_to_restaurant(poi, keyword="本地菜")

    assert restaurant is None


def test_restaurant_node_does_not_apply_default_type_filters(monkeypatch) -> None:
    captured_args: list[dict] = []

    async def fake_invoke_tool_with_debug(*, tool_name, tool_args, log, context):
        captured_args.append(tool_args)
        return POISearchResponse(
            status="1",
            count=1,
            pois=[
                POI(
                    id="food-1",
                    name="大理白族私房菜",
                    address="大理古城",
                    type="餐饮服务;中餐厅;云南菜",
                    typecode="050100",
                    location="100.170,25.692",
                    business={"rating": "4.5", "cost": "68"},
                )
            ],
        )

    async def fake_select(*, request, candidates, final_needed, candidate_target):
        return candidates[:final_needed], "test"

    monkeypatch.setattr("app.ai.nodes.restaurant_node.get_tool", lambda tool_name: object())
    monkeypatch.setattr("app.ai.nodes.restaurant_node.invoke_tool_with_debug", fake_invoke_tool_with_debug)
    monkeypatch.setattr("app.ai.nodes.restaurant_node._select_restaurants_with_llm", fake_select)

    asyncio.run(
        restaurant_node(
            {
                "request": {
                    "destination": "大理",
                    "duration": 1,
                    "companions": "朋友",
                    "style_preferences": ["美食"],
                }
            }
        )
    )

    assert captured_args
    assert all("types" not in args for args in captured_args)
