import asyncio

from app.ai.nodes.transport_node import (
    _build_default_daily_plan,
    _build_route_segments_for_day,
    _normalize_trip_plan,
    _realign_daily_plan_supporting_stops,
    _rebalance_daily_plan_attractions,
    _route_stops_for_day,
    _target_attractions_per_day,
    _transit_segment_from_payload,
)


def test_transit_segment_from_payload_parses_first_transit() -> None:
    attractions = [
        {"name": "大理古城", "location": {"lat": 25.694, "lng": 100.160}},
        {"name": "崇圣寺三塔", "location": {"lat": 25.705, "lng": 100.145}},
    ]
    payload = {
        "route": {
            "transits": [
                {
                    "distance": "5400",
                    "cost": {
                        "duration": "1800",
                        "transit_fee": "3",
                    },
                    "segments": [
                        {
                            "bus": {
                                "buslines": [
                                    {"name": "古城旅游专线"}
                                ]
                            }
                        }
                    ],
                }
            ]
        }
    }

    segments = _transit_segment_from_payload(attractions, payload)

    assert len(segments) == 1
    assert segments[0]["mode"] == "transit"
    assert segments[0]["distance"] == 5.4
    assert segments[0]["duration"] == 30
    assert segments[0]["cost"] == 3.0
    assert "古城旅游专线" in segments[0]["instruction"]


def test_build_default_daily_plan_uses_two_day_hotel_rule() -> None:
    attractions = [
        {"name": "A1", "address": "addr1", "location": {"lat": 25.1, "lng": 100.1}},
        {"name": "A2", "address": "addr2", "location": {"lat": 25.2, "lng": 100.2}},
        {"name": "A3", "address": "addr3", "location": {"lat": 25.3, "lng": 100.3}},
        {"name": "A4", "address": "addr4", "location": {"lat": 25.4, "lng": 100.4}},
    ]
    restaurants = [
        {"name": "R1", "address": "r1", "location": {"lat": 25.1, "lng": 100.1}, "meal_type": "lunch"},
        {"name": "R2", "address": "r2", "location": {"lat": 25.2, "lng": 100.2}, "meal_type": "dinner"},
        {"name": "R3", "address": "r3", "location": {"lat": 25.3, "lng": 100.3}, "meal_type": "lunch"},
        {"name": "R4", "address": "r4", "location": {"lat": 25.4, "lng": 100.4}, "meal_type": "dinner"},
    ]
    hotels = [
        {"name": "H1", "address": "h1", "location": {"lat": 25.0, "lng": 100.0}},
        {"name": "H2", "address": "h2", "location": {"lat": 25.5, "lng": 100.5}},
    ]

    daily_plan = _build_default_daily_plan(
        attractions=attractions,
        restaurants=restaurants,
        hotels=hotels,
        days=4,
        max_per_day=2,
    )

    assert daily_plan[0]["hotel"]["name"] == daily_plan[1]["hotel"]["name"]
    assert daily_plan[2]["hotel"]["name"] == daily_plan[3]["hotel"]["name"]
    assert daily_plan[0]["hotel"]["name"] != daily_plan[2]["hotel"]["name"]
    assert {daily_plan[0]["hotel"]["name"], daily_plan[2]["hotel"]["name"]} == {"H1", "H2"}
    assert [len(day["attractions"]) for day in daily_plan] == [1, 1, 1, 1]
    assert sorted(item["name"] for day in daily_plan for item in day["attractions"]) == ["A1", "A2", "A3", "A4"]
    assert all(len(day["meals"]) == 1 for day in daily_plan)


def test_normalize_trip_plan_keeps_unique_items_and_tops_up_missing() -> None:
    attractions = [
        {"name": "A1", "address": "addr1", "location": {"lat": 25.1, "lng": 100.1}},
        {"name": "A2", "address": "addr2", "location": {"lat": 25.2, "lng": 100.2}},
        {"name": "A3", "address": "addr3", "location": {"lat": 25.3, "lng": 100.3}},
        {"name": "A4", "address": "addr4", "location": {"lat": 25.4, "lng": 100.4}},
    ]
    restaurants = [
        {"name": "R1", "address": "r1", "location": {"lat": 25.1, "lng": 100.1}, "meal_type": "lunch"},
        {"name": "R2", "address": "r2", "location": {"lat": 25.2, "lng": 100.2}, "meal_type": "dinner"},
        {"name": "R3", "address": "r3", "location": {"lat": 25.3, "lng": 100.3}, "meal_type": "lunch"},
        {"name": "R4", "address": "r4", "location": {"lat": 25.4, "lng": 100.4}, "meal_type": "dinner"},
    ]
    hotels = [
        {"name": "H1", "address": "h1", "location": {"lat": 25.0, "lng": 100.0}},
        {"name": "H2", "address": "h2", "location": {"lat": 25.5, "lng": 100.5}},
    ]
    default_plan = _build_default_daily_plan(
        attractions=attractions,
        restaurants=restaurants,
        hotels=hotels,
        days=2,
        max_per_day=2,
    )

    normalized = _normalize_trip_plan(
        llm_data={
            "days": [
                {"day_index": 1, "attraction_indexes": [1], "meal_indexes": [1]},
                {"day_index": 2, "attraction_indexes": [1, 3], "meal_indexes": [1, 3]},
            ]
        },
        attractions=attractions,
        restaurants=restaurants,
        default_plan=default_plan,
    )

    assert len(normalized[0]["attractions"]) == 2
    assert len(normalized[1]["attractions"]) == 2
    all_attractions = [item["name"] for day in normalized for item in day["attractions"]]
    assert len(set(all_attractions)) == 4


def test_target_attractions_per_day_keeps_two_when_total_is_enough() -> None:
    attractions = [{"name": f"A{i}"} for i in range(6)]

    target = _target_attractions_per_day(3, 2, attractions)

    assert target == 2


def test_rebalance_daily_plan_attractions_fills_last_day_to_two() -> None:
    attractions = [
        {"name": "A1", "address": "addr1", "location": {"lat": 25.1, "lng": 100.1}, "rating": 4.8},
        {"name": "A2", "address": "addr2", "location": {"lat": 25.2, "lng": 100.2}, "rating": 4.7},
        {"name": "A3", "address": "addr3", "location": {"lat": 25.3, "lng": 100.3}, "rating": 4.6},
        {"name": "A4", "address": "addr4", "location": {"lat": 25.4, "lng": 100.4}, "rating": 4.5},
        {"name": "A5", "address": "addr5", "location": {"lat": 25.5, "lng": 100.5}, "rating": 4.4},
        {"name": "A6", "address": "addr6", "location": {"lat": 25.6, "lng": 100.6}, "rating": 4.3},
    ]
    daily_plan = [
        {"day_index": 1, "hotel": None, "attractions": [attractions[0], attractions[1]], "attraction_indexes": [0, 1]},
        {"day_index": 2, "hotel": None, "attractions": [attractions[2], attractions[3]], "attraction_indexes": [2, 3]},
        {"day_index": 3, "hotel": None, "attractions": [attractions[4]], "attraction_indexes": [4]},
    ]

    rebalanced = _rebalance_daily_plan_attractions(
        daily_plan=daily_plan,
        attractions=attractions,
        target_per_day=2,
    )

    assert len(rebalanced[2]["attractions"]) == 2
    assert [item["name"] for item in rebalanced[2]["attractions"]] == ["A5", "A6"]


def test_realign_daily_plan_supporting_stops_reassigns_meals_and_hotels_to_match_clusters() -> None:
    hotels = [
        {"name": "西湖酒店", "address": "west", "location": {"lat": 30.2580, "lng": 120.1450}},
        {"name": "湘湖酒店", "address": "south", "location": {"lat": 30.1330, "lng": 120.2700}},
    ]
    restaurants = [
        {
            "name": "湖滨午餐",
            "address": "west-lunch",
            "location": {"lat": 30.2580, "lng": 120.1420},
            "meal_type": "lunch",
        },
        {
            "name": "湖畔晚餐",
            "address": "west-dinner",
            "location": {"lat": 30.2550, "lng": 120.1460},
            "meal_type": "dinner",
        },
        {
            "name": "湘湖午餐",
            "address": "south-lunch",
            "location": {"lat": 30.1340, "lng": 120.2680},
            "meal_type": "lunch",
        },
        {
            "name": "湘湖晚餐",
            "address": "south-dinner",
            "location": {"lat": 30.1360, "lng": 120.2720},
            "meal_type": "dinner",
        },
    ]
    daily_plan = [
        {
            "day_index": 1,
            "hotel": hotels[1],
            "hotel_index": 1,
            "attractions": [
                {"name": "断桥", "address": "a1", "location": {"lat": 30.2570, "lng": 120.1410}},
                {"name": "孤山", "address": "a2", "location": {"lat": 30.2600, "lng": 120.1380}},
            ],
            "attraction_indexes": [0, 1],
            "meals": [restaurants[2]],
            "meal_indexes": [2],
        },
        {
            "day_index": 2,
            "hotel": hotels[0],
            "hotel_index": 0,
            "attractions": [
                {"name": "湘湖", "address": "a3", "location": {"lat": 30.1350, "lng": 120.2660}},
                {"name": "跨湖桥", "address": "a4", "location": {"lat": 30.1320, "lng": 120.2710}},
            ],
            "attraction_indexes": [2, 3],
            "meals": [restaurants[0]],
            "meal_indexes": [0],
        },
    ]

    realigned = _realign_daily_plan_supporting_stops(
        daily_plan=daily_plan,
        restaurants=restaurants,
        hotels=hotels,
        stay_span=1,
    )

    assert realigned[0]["hotel"]["name"] == "西湖酒店"
    assert [item["name"] for item in realigned[0]["meals"]] == ["湖滨午餐", "湖畔晚餐"]
    assert realigned[1]["hotel"]["name"] == "湘湖酒店"
    assert [item["name"] for item in realigned[1]["meals"]] == ["湘湖午餐", "湘湖晚餐"]


def test_route_stops_for_day_only_include_attractions() -> None:
    day = {
        "hotel": {"name": "酒店", "location": {"lat": 30.2580, "lng": 120.1450}},
        "meals": [
            {"name": "午餐", "location": {"lat": 30.2580, "lng": 120.1420}, "meal_type": "lunch"},
            {"name": "晚餐", "location": {"lat": 30.2550, "lng": 120.1460}, "meal_type": "dinner"},
        ],
        "attractions": [
            {"name": "断桥", "location": {"lat": 30.2570, "lng": 120.1410}},
            {"name": "西湖", "location": {"lat": 30.2500, "lng": 120.1500}},
        ],
    }

    stops = _route_stops_for_day(day)

    assert [(item["name"], item["kind"]) for item in stops] == [
        ("断桥", "attraction"),
        ("西湖", "attraction"),
    ]


def test_build_route_segments_for_day_connects_attractions_only(monkeypatch) -> None:
    stops = [
        {"name": "断桥", "location": {"lat": 30.2570, "lng": 120.1410}, "kind": "attraction"},
        {"name": "曲院风荷", "location": {"lat": 30.2520, "lng": 120.1340}, "kind": "attraction"},
        {"name": "灵隐寺", "location": {"lat": 30.2420, "lng": 120.1010}, "kind": "attraction"},
    ]

    async def fake_build_segment_with_mcp(start, end, request, *, day_index, leg_index):
        return [
            {
                "from_name": start["name"],
                "to_name": end["name"],
                "from_location": start["location"],
                "to_location": end["location"],
                "mode": "driving",
                "distance": float(leg_index),
                "duration": 10 * leg_index,
                "cost": 5.0,
                "instruction": "",
            }
        ]

    monkeypatch.setattr(
        "app.ai.nodes.transport_node._build_segment_with_mcp",
        fake_build_segment_with_mcp,
    )

    segments = asyncio.run(
        _build_route_segments_for_day(
            day_index=1,
            stops=stops,
            request={"destination": "杭州"},
        )
    )

    assert len(segments) == 2
    assert [(item["from_name"], item["to_name"]) for item in segments] == [
        ("断桥", "曲院风荷"),
        ("曲院风荷", "灵隐寺"),
    ]
