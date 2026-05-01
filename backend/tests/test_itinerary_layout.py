from app.ai.utils import (
    distribute_attractions,
    distribute_hotels,
    distribute_restaurants,
)


def test_distribute_attractions_groups_nearby_pois_into_same_day() -> None:
    attractions = [
        {"name": "西湖断桥", "location": {"lat": 30.2570, "lng": 120.1410}},
        {"name": "孤山公园", "location": {"lat": 30.2600, "lng": 120.1380}},
        {"name": "湘湖慢生活", "location": {"lat": 30.1350, "lng": 120.2660}},
        {"name": "跨湖桥遗址", "location": {"lat": 30.1320, "lng": 120.2710}},
    ]

    result = distribute_attractions(attractions, 2, 2)

    assert [item["name"] for item in result[0]] == ["西湖断桥", "孤山公园"]
    assert [item["name"] for item in result[1]] == ["湘湖慢生活", "跨湖桥遗址"]


def test_distribute_hotels_assigns_same_hotel_for_two_days() -> None:
    hotels = [
        {"name": "酒店A"},
        {"name": "酒店B"},
    ]

    result = distribute_hotels(hotels, 4, stay_span=2)

    assert [item["name"] for item in result] == ["酒店A", "酒店A", "酒店B", "酒店B"]


def test_distribute_hotels_reuses_last_hotel_when_days_exceed_count() -> None:
    hotels = [
        {"name": "酒店A"},
        {"name": "酒店B"},
    ]

    result = distribute_hotels(hotels, 5, stay_span=2)

    assert [item["name"] for item in result] == ["酒店A", "酒店A", "酒店B", "酒店B", "酒店B"]


def test_distribute_hotels_chooses_hotels_near_each_two_day_cluster() -> None:
    hotels = [
        {"name": "西湖酒店", "location": {"lat": 30.2580, "lng": 120.1450}},
        {"name": "湘湖酒店", "location": {"lat": 30.1330, "lng": 120.2700}},
    ]
    day_attractions = [
        [
            {"name": "断桥", "location": {"lat": 30.2570, "lng": 120.1410}},
            {"name": "孤山", "location": {"lat": 30.2600, "lng": 120.1380}},
        ],
        [
            {"name": "曲院风荷", "location": {"lat": 30.2520, "lng": 120.1330}},
            {"name": "苏堤", "location": {"lat": 30.2470, "lng": 120.1380}},
        ],
        [
            {"name": "湘湖", "location": {"lat": 30.1350, "lng": 120.2660}},
            {"name": "跨湖桥", "location": {"lat": 30.1320, "lng": 120.2710}},
        ],
        [
            {"name": "极地海洋公园", "location": {"lat": 30.1420, "lng": 120.2780}},
            {"name": "闻堰老街", "location": {"lat": 30.1410, "lng": 120.2830}},
        ],
    ]

    result = distribute_hotels(hotels, 4, stay_span=2, day_attractions=day_attractions)

    assert [item["name"] for item in result] == ["西湖酒店", "西湖酒店", "湘湖酒店", "湘湖酒店"]


def test_distribute_restaurants_assigns_nearby_meals_for_each_day() -> None:
    restaurants = [
        {
            "name": "湖滨午餐",
            "meal_type": "lunch",
            "location": {"lat": 30.2580, "lng": 120.1420},
            "rating": 4.8,
        },
        {
            "name": "湖畔晚餐",
            "meal_type": "dinner",
            "location": {"lat": 30.2550, "lng": 120.1460},
            "rating": 4.7,
        },
        {
            "name": "湘湖午餐",
            "meal_type": "lunch",
            "location": {"lat": 30.1340, "lng": 120.2680},
            "rating": 4.8,
        },
        {
            "name": "湘湖晚餐",
            "meal_type": "dinner",
            "location": {"lat": 30.1360, "lng": 120.2720},
            "rating": 4.7,
        },
    ]
    day_attractions = [
        [
            {"name": "断桥", "location": {"lat": 30.2570, "lng": 120.1410}},
            {"name": "孤山", "location": {"lat": 30.2600, "lng": 120.1380}},
        ],
        [
            {"name": "湘湖", "location": {"lat": 30.1350, "lng": 120.2660}},
            {"name": "跨湖桥", "location": {"lat": 30.1320, "lng": 120.2710}},
        ],
    ]
    day_hotels = [
        {"name": "西湖酒店", "location": {"lat": 30.2580, "lng": 120.1450}},
        {"name": "湘湖酒店", "location": {"lat": 30.1330, "lng": 120.2700}},
    ]

    result = distribute_restaurants(
        restaurants,
        2,
        day_attractions=day_attractions,
        day_hotels=day_hotels,
    )

    assert [item["name"] for item in result[0]] == ["湖滨午餐", "湖畔晚餐"]
    assert [item["name"] for item in result[1]] == ["湘湖午餐", "湘湖晚餐"]
