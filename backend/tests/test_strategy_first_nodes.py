import asyncio

from app.ai.nodes.anchor_resolver_node import anchor_resolver_node
from app.ai.nodes.itinerary_composer_node import itinerary_composer_node
from app.ai.nodes.nearby_poi_node import nearby_poi_node
from app.ai.nodes.route_matrix_node import _driving_segment_from_payload, route_matrix_node
from app.ai.nodes.strategy_node import strategy_node
from app.ai.poi_types import ATTRACTION_TYPE_CODES, HOTEL_TYPE_CODE, RESTAURANT_TYPE_CODE, has_type_prefix
from app.services.amap import POI, POIBusiness, POISearchResponse


def _poi(
    *,
    name: str,
    location: str = "120.100000,30.200000",
    typecode: str = "110200",
    poi_id: str = "poi-1",
    business_area: str = "西湖",
) -> POI:
    return POI(
        id=poi_id,
        name=name,
        address=f"{name}地址",
        location=location,
        type="风景名胜",
        typecode=typecode,
        cityname="杭州市",
        adname="西湖区",
        business=POIBusiness(rating="4.8", cost="88", business_area=business_area),
        navi={"entr_location": location},
    )


def _response(*pois: POI) -> POISearchResponse:
    return POISearchResponse(status="1", info="OK", infocode="10000", count=str(len(pois)), pois=list(pois))


def test_strategy_node_returns_structured_area_plan(monkeypatch):
    async def fake_prompt(*, prompt_id, variables, temperature, max_tokens):
        assert prompt_id == "travel_strategy"
        assert max_tokens == 1400
        return {
            "trip_theme": "首次经典游",
            "daily_area_plan": [
                {
                    "day_index": 1,
                    "area_name": "西湖",
                    "required_anchors": [
                        {
                            "name": "西湖风景名胜区",
                            "kind": "attraction",
                            "required": True,
                            "reason": "经典片区",
                        }
                    ],
                    "restaurant_area_keywords": ["湖滨"],
                    "reason": "经典片区",
                }
            ],
            "hotel_area_keywords": [
                {
                    "name": "龙翔桥",
                    "kind": "hotel_area",
                    "required": False,
                    "reason": "交通便利",
                }
            ],
            "avoid_rules": ["不去远郊"],
            "planning_notes": [],
        }

    monkeypatch.setattr("app.ai.nodes.strategy_node.invoke_prompt_json_async", fake_prompt)

    result = asyncio.run(
        strategy_node(
            {
                "request": {"destination": "杭州", "days": 1, "num_people": 2},
                "companions": "朋友",
                "style_preferences": ["自然风光"],
            }
        )
    )

    assert result["strategy_plan"]["daily_area_plan"][0]["required_anchors"][0]["name"] == "西湖风景名胜区"
    assert result["strategy_plan"]["daily_area_plan"][0]["required_anchors"][0]["kind"] == "attraction"
    assert result["completed_agents"] == ["strategy"]


def test_anchor_resolver_skips_bad_type_for_attraction_but_allows_area_anchor(monkeypatch):
    calls: list[dict] = []

    async def fake_search(*, keywords, region, citylimit, offset, types=""):
        calls.append({"keywords": keywords, "types": types})
        if keywords == "西湖风景名胜区":
            return _response(
                _poi(name="西湖公交站", typecode="150700", poi_id="bus"),
                _poi(name="杭州西湖风景名胜区", typecode="110202", poi_id="westlake"),
            )
        if keywords == "龙井村":
            return _response(_poi(name="龙井村(公交站)", typecode="150700", poi_id="longjing-bus"))
        if keywords == "杭州龙井村":
            return _response()
        if keywords == "龙井村景区":
            return _response(_poi(name="龙井村茶文化景区", typecode="110200", poi_id="longjing-scenic"))
        if keywords == "龙翔桥":
            return _response(_poi(name="龙翔桥(地铁站)", typecode="150500", poi_id="hub"))
        raise AssertionError(f"unexpected query {keywords}")

    monkeypatch.setattr("app.ai.nodes.anchor_resolver_node.search_pois_by_text", fake_search)
    state = {
        "request": {"destination": "杭州", "days": 1},
        "strategy_plan": {
            "daily_area_plan": [
                {
                    "day_index": 1,
                    "area_name": "西湖",
                    "required_anchors": [
                        {"name": "西湖风景名胜区", "kind": "attraction", "required": True},
                        {"name": "龙井村", "kind": "attraction", "required": True},
                    ],
                }
            ],
            "hotel_area_keywords": [{"name": "龙翔桥", "kind": "hotel_area", "required": False}],
        },
    }

    result = asyncio.run(anchor_resolver_node(state))

    assert [item["poi_id"] for item in result["resolved_anchors"]] == ["westlake", "longjing-scenic"]
    assert result["resolved_anchors"][1]["name"] == "龙井村"
    assert result["hotel_area_anchors"][0]["poi_id"] == "hub"
    assert calls[0]["types"] == ATTRACTION_TYPE_CODES
    assert calls[-1]["keywords"] == "龙翔桥"
    assert calls[-1]["types"] == ""


def test_nearby_poi_node_searches_hotels_and_restaurants_around_verified_centers(monkeypatch):
    calls: list[dict] = []

    async def fake_nearby(**kwargs):
        calls.append(kwargs)
        if "酒店" in kwargs["keywords"]:
            return _response(_poi(name="湖滨酒店", typecode="100100", poi_id="hotel"))
        return _response(
            _poi(name="灵隐杭帮菜", typecode="050106", poi_id="r1"),
            _poi(name="龙井杭帮菜", typecode="050106", poi_id="r2"),
        )

    monkeypatch.setattr("app.ai.nodes.nearby_poi_node.search_pois_nearby", fake_nearby)
    state = {
        "request": {"destination": "杭州", "days": 1, "hotel_level": "舒适型", "style_preferences": ["美食"]},
        "hotel_level": "舒适型",
        "resolved_anchors": [
            {
                "query": "灵隐飞来峰",
                "name": "灵隐飞来峰",
                "day_index": 1,
                "address": "灵隐路",
                "location": {"lat": 30.24, "lng": 120.10},
                "type": "风景名胜",
                "typecode": "110200",
                "rating": 4.8,
                "photos": [],
                "confidence": 0.98,
            }
        ],
        "hotel_area_anchors": [{"name": "龙翔桥", "location": {"lat": 30.25, "lng": 120.16}}],
    }

    result = asyncio.run(nearby_poi_node(state))

    assert result["attractions"][0]["name"] == "灵隐飞来峰"
    assert result["hotels"][0]["name"] == "湖滨酒店"
    assert result["restaurants"][0]["day_index"] == 1
    assert calls[0]["keywords"] == "舒适型酒店"
    assert calls[0]["types"] == HOTEL_TYPE_CODE
    assert calls[1]["keywords"] == "杭帮菜"
    assert calls[1]["types"] == RESTAURANT_TYPE_CODE


def test_nearby_poi_node_separates_lunch_and_dinner_search_centers(monkeypatch):
    async def fake_nearby(**kwargs):
        if "酒店" in kwargs["keywords"]:
            return _response(_poi(name="湖滨酒店", typecode="100100", poi_id="hotel"))
        if kwargs["location"] == "120.0,30.0":
            return _response(
                _poi(name="上午餐厅", location="120.0005,30.0005", typecode="050106", poi_id="lunch")
            )
        if kwargs["location"] == "120.0,30.1":
            return _response(
                _poi(name="下午餐厅", location="120.0005,30.1005", typecode="050106", poi_id="dinner")
            )
        return _response()

    monkeypatch.setattr("app.ai.nodes.nearby_poi_node.search_pois_nearby", fake_nearby)
    state = {
        "request": {"destination": "杭州", "days": 1, "hotel_level": "舒适型", "style_preferences": ["美食"]},
        "hotel_level": "舒适型",
        "resolved_anchors": [
            {
                "query": "上午景点",
                "name": "上午景点",
                "day_index": 1,
                "address": "上午路",
                "location": {"lat": 30.0, "lng": 120.0},
                "type": "风景名胜",
                "typecode": "110200",
                "rating": 4.8,
                "photos": [],
                "confidence": 0.98,
            },
            {
                "query": "下午景点",
                "name": "下午景点",
                "day_index": 1,
                "address": "下午路",
                "location": {"lat": 30.1, "lng": 120.0},
                "type": "风景名胜",
                "typecode": "110200",
                "rating": 4.8,
                "photos": [],
                "confidence": 0.98,
            },
        ],
        "hotel_area_anchors": [{"name": "湖滨", "location": {"lat": 30.05, "lng": 120.0}}],
    }

    result = asyncio.run(nearby_poi_node(state))

    assert [(item["name"], item["meal_type"]) for item in result["restaurants"]] == [
        ("上午餐厅", "lunch"),
        ("下午餐厅", "dinner"),
    ]


def test_nearby_poi_node_uses_restaurant_type_recall_when_food_keyword_is_empty(monkeypatch):
    calls: list[dict] = []

    async def fake_nearby(**kwargs):
        calls.append(kwargs)
        if "酒店" in kwargs["keywords"]:
            return _response(_poi(name="秦淮酒店", typecode="100100", poi_id="hotel"))
        if kwargs.get("types") == "050000" and not kwargs.get("keywords"):
            return _response(_poi(name="秦淮本地餐厅", typecode="050118", poi_id="restaurant"))
        return _response(_poi(name="秦淮文创店", typecode="061400", poi_id="shop"))

    monkeypatch.setattr("app.ai.nodes.nearby_poi_node.search_pois_nearby", fake_nearby)
    state = {
        "request": {"destination": "南京", "days": 1, "hotel_level": "舒适型"},
        "hotel_level": "舒适型",
        "strategy_plan": {
            "daily_area_plan": [
                {"day_index": 1, "area_name": "秦淮河", "restaurant_area_keywords": ["夫子庙"]}
            ]
        },
        "resolved_anchors": [
            {
                "query": "夫子庙",
                "name": "夫子庙",
                "day_index": 1,
                "address": "秦淮区",
                "location": {"lat": 32.02, "lng": 118.78},
                "type": "风景名胜",
                "typecode": "110200",
                "rating": 4.8,
                "photos": [],
                "confidence": 0.98,
            }
        ],
        "hotel_area_anchors": [{"name": "夫子庙", "location": {"lat": 32.02, "lng": 118.78}}],
    }

    result = asyncio.run(nearby_poi_node(state))

    assert result["restaurants"][0]["name"] == "秦淮本地餐厅"
    assert result["restaurants"][0]["day_index"] == 1
    assert any(call.get("types") == "050000" and not call.get("keywords") for call in calls)


def test_nearby_poi_node_accepts_mixed_top_level_typecodes(monkeypatch):
    async def fake_nearby(**kwargs):
        if kwargs.get("types") == "100000":
            return _response(_poi(name="混合编码酒店", typecode="060000|100102", poi_id="hotel"))
        return _response(_poi(name="混合编码茶饮", typecode="060704|050700", poi_id="restaurant"))

    monkeypatch.setattr("app.ai.nodes.nearby_poi_node.search_pois_nearby", fake_nearby)
    state = {
        "request": {"destination": "杭州", "days": 1, "hotel_level": "舒适型"},
        "hotel_level": "舒适型",
        "resolved_anchors": [
            {
                "query": "灵隐寺",
                "name": "灵隐寺",
                "day_index": 1,
                "address": "灵隐路",
                "location": {"lat": 30.24, "lng": 120.10},
                "type": "风景名胜",
                "typecode": "110200",
                "rating": 4.8,
                "photos": [],
                "confidence": 0.98,
            }
        ],
        "hotel_area_anchors": [{"name": "灵隐寺", "location": {"lat": 30.24, "lng": 120.10}}],
    }

    result = asyncio.run(nearby_poi_node(state))

    assert result["hotels"][0]["name"] == "混合编码酒店"
    assert result["restaurants"][0]["name"] == "混合编码茶饮"
    assert has_type_prefix("060704|050700", "05")


def test_driving_segment_accepts_distance_only_path_with_estimated_duration():
    attractions = [
        {"name": "西湖", "location": {"lat": 30.224729, "lng": 120.153345}},
        {"name": "河坊街", "location": {"lat": 30.240627, "lng": 120.171566}},
    ]
    payload = {"route": {"paths": [{"distance": "5000", "steps": [{"instruction": "沿南山路行驶"}]}]}}

    segments = _driving_segment_from_payload(attractions, payload)

    assert len(segments) == 1
    assert segments[0]["distance"] == 5.0
    assert segments[0]["duration"] > 0


def test_route_matrix_node_builds_blocking_issues(monkeypatch):
    async def fake_route(*, origin, destination):
        return {"route": {"paths": [{"distance": "26000", "cost": {"duration": "3600"}}]}}

    monkeypatch.setattr("app.ai.nodes.route_matrix_node.get_driving_route", fake_route)

    result = asyncio.run(
        route_matrix_node(
            {
                "attractions": [
                    {"name": "A", "day_index": 1, "location": {"lat": 30.1, "lng": 120.1}},
                    {"name": "B", "day_index": 1, "location": {"lat": 30.2, "lng": 120.2}},
                ]
            }
        )
    )

    assert result["route_matrix"]["issues"][0]["status"] == "blocked"


def test_route_matrix_node_treats_adjacent_scenic_spots_as_walkable(monkeypatch):
    async def fake_route(*, origin, destination):
        raise AssertionError("walkable legs should not call driving route")

    monkeypatch.setattr("app.ai.nodes.route_matrix_node.get_driving_route", fake_route)

    result = asyncio.run(
        route_matrix_node(
            {
                "attractions": [
                    {
                        "name": "断桥残雪",
                        "day_index": 1,
                        "location": {"lat": 30.259343, "lng": 120.152264},
                    },
                    {
                        "name": "白堤",
                        "day_index": 1,
                        "location": {"lat": 30.259326, "lng": 120.152286},
                    },
                ]
            }
        )
    )

    leg = result["route_matrix"]["legs"][0]
    assert leg["status"] == "ok"
    assert leg["mode"] == "walking"
    assert result["route_matrix"]["issues"] == []


def test_itinerary_composer_sets_transport_daily_plan():
    result = asyncio.run(
        itinerary_composer_node(
            {
                "request": {"destination": "杭州", "origin": "上海", "days": 1},
                "attractions": [{"name": "西湖", "day_index": 1, "location": {"lat": 30.24, "lng": 120.15}}],
                "restaurants": [
                    {"name": "杭帮菜", "day_index": 1, "meal_type": "lunch", "location": {"lat": 30.25, "lng": 120.16}}
                ],
                "hotels": [{"name": "湖滨酒店", "location": {"lat": 30.26, "lng": 120.17}}],
                "route_matrix": {"daily_routes": [[{"cost": 12}]], "issues": []},
            }
        )
    )

    transport = result["transport"]
    assert transport["daily_plan"][0]["attractions"][0]["name"] == "西湖"
    assert transport["inter_city"]["mode"] == "高铁"
    assert transport["estimated_transport_cost"] > 0
    assert len(transport["daily_routes"][0]) == 3


def test_itinerary_composer_uses_walkable_segments_without_mcp():
    result = asyncio.run(
        itinerary_composer_node(
            {
                "request": {"destination": "杭州", "days": 1},
                "attractions": [
                    {"name": "断桥残雪", "day_index": 1, "location": {"lat": 30.259343, "lng": 120.152264}}
                ],
                "restaurants": [],
                "hotels": [{"name": "白堤旁酒店", "location": {"lat": 30.259326, "lng": 120.152286}}],
                "route_matrix": {"daily_routes": [[]], "issues": []},
            }
        )
    )

    routes = result["transport"]["daily_routes"][0]
    assert routes
    assert {segment["mode"] for segment in routes} == {"walking"}
