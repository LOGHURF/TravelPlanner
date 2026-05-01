from app.ai.nodes.hotel_node import _clean_candidates_from_results as clean_hotel_candidates
from app.ai.nodes.restaurant_node import _clean_candidates_from_results as clean_restaurant_candidates


def test_hotel_candidates_accept_structured_poi_models_from_dict_payload() -> None:
    results = [
        {
            "keyword": "舒适型酒店",
            "result": {
                "pois": [
                    {
                        "id": "hotel-1",
                        "name": "大理古城花园酒店",
                        "address": "大理古城",
                        "location": "100.160,25.694",
                        "type": "住宿服务;宾馆酒店;舒适型酒店",
                        "distance": "850",
                        "business": {
                            "rating": "4.7",
                            "cost": "368",
                            "business_area": "大理古城",
                        },
                        "photos": [{"url": "https://example.com/hotel.jpg"}],
                    },
                    {
                        "id": "invalid-hotel",
                        "address": "missing name should be filtered",
                    },
                ]
            },
        }
    ]

    hotels = clean_hotel_candidates(results, hotel_level="舒适型", days=2, limit=5)

    assert len(hotels) == 1
    assert hotels[0]["name"] == "大理古城花园酒店"
    assert hotels[0]["distance_to_center"] == "大理古城"
    assert hotels[0]["distance"] == "850"
    assert hotels[0]["price_per_night"] == 368
    assert hotels[0]["total_price"] == 736


def test_restaurant_candidates_accept_structured_poi_models_from_dict_payload() -> None:
    results = [
        {
            "keyword": "特色美食",
            "result": {
                "pois": [
                    {
                        "id": "food-1",
                        "name": "大理段公子",
                        "address": "人民路 88 号",
                        "location": "100.161,25.695",
                        "type": "餐饮服务;中餐厅;云南菜",
                        "business": {
                            "rating": "4.6",
                            "cost": "88",
                        },
                        "photos": [{"url": "https://example.com/food.jpg"}],
                    },
                    {
                        "id": "invalid-food",
                        "location": "100.161,25.695",
                    },
                ]
            },
        }
    ]

    restaurants = clean_restaurant_candidates(results, limit=5)

    assert len(restaurants) == 1
    assert restaurants[0]["name"] == "大理段公子"
    assert restaurants[0]["address"] == "人民路 88 号"
    assert restaurants[0]["rating"] == 4.6
    assert restaurants[0]["price_per_person"] == 88
    assert restaurants[0]["estimated_cost"] == 88
