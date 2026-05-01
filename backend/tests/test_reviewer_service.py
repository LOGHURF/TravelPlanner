from app.ai.nodes.reviewer_node import (
    _dedupe_attractions,
    _diversify_attractions,
    _drop_far_outlier_attractions,
    _needed_hotels,
    _optimize_attraction_selection,
    _optimize_hotel_selection,
    _retained_hotel_count,
    _top_up_selection,
)


def test_top_up_selection_fills_missing_items_to_limit() -> None:
    selected = [
        {"name": "A", "address": "addr-a"},
        {"name": "B", "address": "addr-b"},
    ]
    fallback = [
        {"name": "A", "address": "addr-a"},
        {"name": "B", "address": "addr-b"},
        {"name": "C", "address": "addr-c"},
        {"name": "D", "address": "addr-d"},
    ]

    result = _top_up_selection(selected, fallback, limit=4)

    assert [item["name"] for item in result] == ["A", "B", "C", "D"]


def test_needed_hotels_uses_two_day_rotation_rule() -> None:
    assert _needed_hotels(1) == 1
    assert _needed_hotels(2) == 1
    assert _needed_hotels(3) == 2
    assert _needed_hotels(4) == 2
    assert _needed_hotels(5) == 3


def test_retained_hotel_count_keeps_extra_options_for_replanning() -> None:
    assert _retained_hotel_count(1) == 3
    assert _retained_hotel_count(3) == 4
    assert _retained_hotel_count(5) == 5


def test_drop_far_outlier_attractions_replaces_isolated_spot() -> None:
    selected = [
        {"name": "A", "address": "a", "location": {"lat": 25.0, "lng": 100.0}, "rating": 4.8},
        {"name": "B", "address": "b", "location": {"lat": 25.01, "lng": 100.01}, "rating": 4.7},
        {"name": "C", "address": "c", "location": {"lat": 25.02, "lng": 100.02}, "rating": 4.6},
        {"name": "Far", "address": "far", "location": {"lat": 26.2, "lng": 101.4}, "rating": 4.5},
    ]
    fallback = [
        *selected,
        {"name": "D", "address": "d", "location": {"lat": 25.03, "lng": 100.03}, "rating": 4.4},
    ]

    result = _drop_far_outlier_attractions(selected, fallback, limit=4)

    assert [item["name"] for item in result] == ["A", "B", "C", "D"]


def test_dedupe_attractions_merges_same_spot_variants() -> None:
    items = [
        {"name": "西湖风景区", "address": "杭州西湖", "rating": 4.9},
        {"name": "西湖景区", "address": "杭州西湖景区", "rating": 4.8},
        {"name": "灵隐寺", "address": "灵隐路", "rating": 4.7},
    ]

    result = _dedupe_attractions(items)

    assert [item["name"] for item in result] == ["西湖风景区", "灵隐寺"]


def test_diversify_attractions_prefers_different_categories_when_available() -> None:
    selected = [
        {"name": "古城墙", "address": "a1", "rating": 4.9, "type": "风景名胜;国家级景点"},
        {"name": "古街区", "address": "a2", "rating": 4.8, "type": "风景名胜;国家级景点"},
        {"name": "古寺", "address": "a3", "rating": 4.7, "type": "风景名胜;寺庙道观"},
    ]
    fallback = [
        *selected,
        {"name": "博物馆", "address": "b1", "rating": 4.6, "type": "风景名胜;纪念馆"},
        {"name": "观景台", "address": "b2", "rating": 4.5, "type": "风景名胜;观景点"},
    ]

    result = _diversify_attractions(selected, fallback, limit=4)

    assert [item["name"] for item in result] == ["古城墙", "古寺", "博物馆", "观景台"]


def test_optimize_attraction_selection_prefers_compact_group_near_hotels() -> None:
    hotels = [
        {"name": "西湖酒店", "address": "west", "location": {"lat": 30.2580, "lng": 120.1450}, "rating": 4.8},
        {"name": "湖滨酒店", "address": "center", "location": {"lat": 30.2500, "lng": 120.1500}, "rating": 4.7},
    ]
    candidates = [
        {"name": "断桥", "address": "a1", "location": {"lat": 30.2570, "lng": 120.1410}, "rating": 4.6},
        {"name": "曲院风荷", "address": "a2", "location": {"lat": 30.2520, "lng": 120.1340}, "rating": 4.5},
        {"name": "苏堤", "address": "a3", "location": {"lat": 30.2480, "lng": 120.1390}, "rating": 4.5},
        {"name": "湖滨公园", "address": "a4", "location": {"lat": 30.2470, "lng": 120.1600}, "rating": 4.4},
        {"name": "远郊寺庙", "address": "b1", "location": {"lat": 30.0500, "lng": 120.4200}, "rating": 4.9},
        {"name": "远郊山谷", "address": "b2", "location": {"lat": 30.0300, "lng": 120.4500}, "rating": 4.8},
    ]

    result = _optimize_attraction_selection(candidates, hotels, days=2, limit=4)

    assert [item["name"] for item in result] == ["曲院风荷", "苏堤", "断桥", "湖滨公园"]


def test_optimize_hotel_selection_prefers_hotels_close_to_selected_attractions() -> None:
    attractions = [
        {"name": "断桥", "address": "a1", "location": {"lat": 30.2570, "lng": 120.1410}, "rating": 4.6},
        {"name": "苏堤", "address": "a2", "location": {"lat": 30.2480, "lng": 120.1390}, "rating": 4.5},
        {"name": "湘湖", "address": "a3", "location": {"lat": 30.1350, "lng": 120.2660}, "rating": 4.5},
        {"name": "跨湖桥", "address": "a4", "location": {"lat": 30.1320, "lng": 120.2710}, "rating": 4.4},
    ]
    hotels = [
        {"name": "西湖酒店", "address": "west", "location": {"lat": 30.2580, "lng": 120.1450}, "rating": 4.8},
        {"name": "湘湖酒店", "address": "south", "location": {"lat": 30.1330, "lng": 120.2700}, "rating": 4.7},
        {"name": "远郊酒店", "address": "far", "location": {"lat": 29.9500, "lng": 120.6000}, "rating": 4.9},
    ]

    result = _optimize_hotel_selection(hotels, attractions, days=2, limit=2)

    assert [item["name"] for item in result] == ["湘湖酒店", "西湖酒店"]
