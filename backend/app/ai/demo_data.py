"""内置演示数据，用于无 API Key 时跑通完整规划链路。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


def trip_days(request: dict[str, Any]) -> int:
    """从请求中稳定计算行程天数。"""
    days = int(request.get("days", 0) or request.get("duration", 0) or 0)
    if days > 0:
        return max(1, min(days, 7))

    start_date = request.get("start_date")
    end_date = request.get("end_date")
    try:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        return max(1, min((end - start).days + 1, 7))
    except (TypeError, ValueError):
        return 3


def _parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def start_date(request: dict[str, Any]) -> date:
    """获取演示行程开始日期。"""
    raw = request.get("start_date")
    if raw:
        try:
            return _parse_date(raw)
        except (TypeError, ValueError):
            pass
    return datetime.now().date()


def _base_location(destination: str) -> tuple[float, float]:
    """按城市给出一个稳定基准坐标，返回 lng/lat。"""
    city = destination.strip()
    presets = {
        "深圳": (114.0579, 22.5431),
        "广州": (113.2644, 23.1291),
        "上海": (121.4737, 31.2304),
        "北京": (116.4074, 39.9042),
        "杭州": (120.1551, 30.2741),
        "成都": (104.0668, 30.5728),
        "重庆": (106.5516, 29.5630),
        "南京": (118.7969, 32.0603),
        "苏州": (120.5853, 31.2989),
        "西安": (108.9398, 34.3416),
    }
    return presets.get(city, (114.0579, 22.5431))


def _point(destination: str, index: int) -> dict[str, float]:
    lng, lat = _base_location(destination)
    offsets = [
        (0.000, 0.000),
        (0.010, 0.006),
        (0.020, -0.004),
        (-0.012, 0.014),
        (-0.022, -0.007),
        (0.030, 0.012),
        (-0.032, 0.016),
        (0.016, -0.018),
        (-0.018, -0.020),
        (0.038, -0.006),
        (-0.040, 0.002),
        (0.006, 0.030),
    ]
    dlng, dlat = offsets[index % len(offsets)]
    return {"lng": round(lng + dlng, 6), "lat": round(lat + dlat, 6)}


def strategy_plan(request: dict[str, Any]) -> dict[str, Any]:
    """生成演示用每日片区策略。"""
    destination = str(request.get("destination") or "深圳").strip()
    days = trip_days(request)
    preferences = request.get("style_preferences") or []
    theme = "城市文化与轻松美食"
    if "自然风光" in preferences:
        theme = "城市自然与慢节奏探索"
    elif "历史古迹" in preferences or "文化体验" in preferences:
        theme = "城市文化地标探索"
    elif "美食" in preferences:
        theme = "城市美食与经典地标"

    daily_area_plan: list[dict[str, Any]] = []
    anchors = _anchor_names(destination, days)
    for day_index in range(1, days + 1):
        first = anchors[(day_index - 1) * 2]
        second = anchors[(day_index - 1) * 2 + 1]
        daily_area_plan.append(
            {
                "day_index": day_index,
                "area_name": f"{destination}核心片区{day_index}",
                "required_anchors": [
                    {
                        "name": first,
                        "kind": "attraction",
                        "required": True,
                        "reason": "演示模式内置景点锚点",
                    },
                    {
                        "name": second,
                        "kind": "attraction",
                        "required": True,
                        "reason": "演示模式内置景点锚点",
                    },
                ],
                "restaurant_area_keywords": [f"{destination}本地菜", f"{destination}人气餐厅"],
                "reason": "按每天两个核心点控制节奏，方便地图演示和路线串联。",
            }
        )

    return {
        "trip_theme": theme,
        "daily_area_plan": daily_area_plan,
        "hotel_area_keywords": [
            {
                "name": f"{destination}中心酒店圈",
                "kind": "hotel_area",
                "required": False,
                "reason": "靠近主要公共交通和日间游览区域",
            }
        ],
        "avoid_rules": ["避免单日跨区过多", "保留午晚餐和休息时间"],
        "planning_notes": ["演示模式使用内置数据，不代表真实营业状态和价格。"],
    }


def _anchor_names(destination: str, days: int) -> list[str]:
    names = {
        "深圳": ["莲花山公园", "深圳博物馆", "华侨城创意文化园", "欢乐海岸", "深圳湾公园", "南头古城"],
        "广州": ["越秀公园", "陈家祠", "沙面岛", "永庆坊", "广州塔", "花城广场"],
        "上海": ["外滩", "豫园", "上海博物馆", "武康路", "陆家嘴", "徐家汇书院"],
        "北京": ["故宫博物院", "景山公园", "什刹海", "南锣鼓巷", "天坛公园", "前门大街"],
        "杭州": ["西湖", "浙江省博物馆", "河坊街", "南宋御街", "灵隐寺", "龙井村"],
    }.get(destination)
    if not names:
        names = [
            f"{destination}城市公园",
            f"{destination}博物馆",
            f"{destination}老街",
            f"{destination}文化广场",
            f"{destination}滨水公园",
            f"{destination}美食街区",
        ]
    needed = max(days * 2, 2)
    while len(names) < needed:
        names.append(f"{destination}精选景点{len(names) + 1}")
    return names[:needed]


def resolved_anchors(request: dict[str, Any], plan: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """生成演示用 POI 验真结果。"""
    destination = str(request.get("destination") or "深圳").strip()
    plan = plan or strategy_plan(request)
    resolved: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    index = 0
    for day in plan.get("daily_area_plan") or []:
        day_index = int(day.get("day_index", 1) or 1)
        for anchor in day.get("required_anchors") or []:
            name = str(anchor.get("name") or f"{destination}景点").strip()
            poi = _anchor_payload(
                destination=destination,
                name=name,
                query=name,
                day_index=day_index,
                index=index,
                role="attraction",
                poi_type="风景名胜;公园广场;文化场馆",
            )
            resolved.append(poi)
            results.append(
                {
                    "query": name,
                    "kind": "attraction",
                    "status": "resolved",
                    "required": True,
                    "day_index": day_index,
                    "reason_code": "",
                    "message": "演示模式内置命中",
                    "resolved_anchor": poi,
                    "candidates": [],
                }
            )
            index += 1

    hotel_anchor = _anchor_payload(
        destination=destination,
        name=f"{destination}中心酒店圈",
        query=f"{destination}中心酒店圈",
        day_index=None,
        index=index + 1,
        role="hotel_area",
        poi_type="住宿服务;宾馆酒店",
    )
    return resolved, [hotel_anchor], results


def _anchor_payload(
    *,
    destination: str,
    name: str,
    query: str,
    day_index: int | None,
    index: int,
    role: str,
    poi_type: str,
) -> dict[str, Any]:
    location = _point(destination, index)
    return {
        "query": query,
        "day_index": day_index,
        "role": role,
        "name": name,
        "poi_name": name,
        "poi_id": f"demo-{role}-{index}",
        "type": poi_type,
        "typecode": "110000",
        "address": f"{destination}演示地址{index + 1}号",
        "cityname": destination,
        "adname": "演示区",
        "business_area": f"{destination}中心片区",
        "location": location,
        "raw_location": location,
        "navi": {},
        "rating": round(4.7 - min(index, 5) * 0.05, 1),
        "open_time2": "09:00-21:00",
        "photos": [],
        "confidence": 0.98,
    }


def attractions(request: dict[str, Any], anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """生成演示景点列表。"""
    items: list[dict[str, Any]] = []
    for index, anchor in enumerate(anchors):
        items.append(
            {
                "name": anchor.get("name", ""),
                "address": anchor.get("address", ""),
                "location": anchor.get("location"),
                "description": f"{anchor.get('name', '')}是演示模式下的精选城市点位，适合用于完整流程展示。",
                "keytag": "演示景点;城市地标",
                "type": "风景名胜;文化场馆",
                "photos": [],
                "tel": "",
                "rating": anchor.get("rating", 4.6),
                "category": "景点",
                "tags": ["演示", "城市地标"],
                "visit_duration": "2小时",
                "indoor": index % 2 == 1,
                "best_time": "上午" if index % 2 == 0 else "下午",
                "ticket_price": 0 if index % 3 else 30,
                "open_hours": "09:00-21:00",
                "phone": "",
                "open_time2": "09:00-21:00",
                "photo": "",
                "day_index": anchor.get("day_index"),
                "poi_id": anchor.get("poi_id"),
                "source_query": anchor.get("query"),
                "confidence": anchor.get("confidence", 0.98),
            }
        )
    return items


def hotels(request: dict[str, Any]) -> list[dict[str, Any]]:
    """生成演示酒店列表。"""
    destination = str(request.get("destination") or "深圳").strip()
    level = str(request.get("hotel_level") or "舒适型").strip()
    base_prices = {"经济型": 260, "舒适型": 420, "高档型": 760, "豪华型": 1280}
    price = base_prices.get(level, 420)
    return [
        {
            "name": f"{destination}中心演示酒店",
            "address": f"{destination}中心片区演示路88号",
            "location": _point(destination, 10),
            "description": f"{level}，靠近核心游览区域，适合作为演示住宿点。",
            "keytag": "酒店;住宿",
            "type": "住宿服务;宾馆酒店",
            "photos": [],
            "tel": "",
            "open_time2": "全天",
            "rating": 4.7,
            "hotel_level": level,
            "star_rating": 4 if level in {"高档型", "豪华型"} else 3,
            "price_per_night": price,
            "total_price": price,
            "distance_to_center": "核心片区",
            "distance": "1.2km",
            "amenities": ["Wi-Fi", "早餐", "行李寄存"],
            "phone": "",
            "photo": "",
            "image_url": "",
            "poi_id": "demo-hotel-1",
        },
        {
            "name": f"{destination}城市漫游酒店",
            "address": f"{destination}演示大道66号",
            "location": _point(destination, 11),
            "description": f"{level}，交通便利，适合多日城市行程。",
            "keytag": "酒店;住宿",
            "type": "住宿服务;宾馆酒店",
            "photos": [],
            "tel": "",
            "open_time2": "全天",
            "rating": 4.5,
            "hotel_level": level,
            "star_rating": 3,
            "price_per_night": max(180, price - 80),
            "total_price": max(180, price - 80),
            "distance_to_center": "交通枢纽",
            "distance": "2.1km",
            "amenities": ["Wi-Fi", "自助早餐"],
            "phone": "",
            "photo": "",
            "image_url": "",
            "poi_id": "demo-hotel-2",
        },
    ]


def restaurants(request: dict[str, Any], anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """生成演示餐厅列表，每天午餐和晚餐各一处。"""
    destination = str(request.get("destination") or "深圳").strip()
    days = trip_days(request)
    items: list[dict[str, Any]] = []
    for day_index in range(1, days + 1):
        day_anchors = [item for item in anchors if int(item.get("day_index", 0) or 0) == day_index]
        first = day_anchors[0] if day_anchors else {}
        last = day_anchors[-1] if day_anchors else first
        for meal_offset, (meal_type, label, anchor, role) in enumerate(
            [
                ("lunch", "午餐", first, "first_attraction"),
                ("dinner", "晚餐", last, "last_attraction"),
            ]
        ):
            index = (day_index - 1) * 2 + meal_offset
            items.append(
                {
                    "name": f"{destination}演示{label}餐厅{day_index}",
                    "type": "餐饮服务;中餐厅;特色餐厅",
                    "meal_type": meal_type,
                    "address": f"{destination}美食街演示{index + 1}号",
                    "location": _point(destination, index + 4),
                    "description": f"靠近{anchor.get('name', '当日景点')}，适合作为{label}安排。",
                    "keytag": f"{destination}本地菜",
                    "photos": [],
                    "tel": "",
                    "phone": "",
                    "open_time2": "10:30-22:00",
                    "rating": 4.6,
                    "estimated_cost": 85 if meal_type == "lunch" else 120,
                    "price_per_person": 85 if meal_type == "lunch" else 120,
                    "cuisine_type": "本地菜",
                    "is_recommended": True,
                    "meal_anchor_name": anchor.get("name", ""),
                    "meal_anchor_role": role,
                    "distance_to_anchor_km": 0.8,
                    "photo": "",
                    "day_index": day_index,
                    "poi_id": f"demo-restaurant-{index + 1}",
                    "source_keyword": f"{destination}本地菜",
                }
            )
    return items


def weather(request: dict[str, Any]) -> list[dict[str, Any]]:
    """生成演示天气。"""
    start = start_date(request)
    days = trip_days(request)
    patterns = [
        ("多云", "多云", 29, 23, "东南风", "2级", "适合户外游览，注意补水。"),
        ("晴", "多云", 31, 24, "南风", "2级", "紫外线偏强，建议防晒。"),
        ("小雨", "阴", 27, 22, "东北风", "3级", "建议携带雨具，室内外结合安排。"),
        ("阴", "多云", 28, 22, "东风", "2级", "天气温和，适合城市漫步。"),
    ]
    return [
        {
            "date": (start + timedelta(days=index)).strftime("%Y-%m-%d"),
            "day_weather": patterns[index % len(patterns)][0],
            "night_weather": patterns[index % len(patterns)][1],
            "day_temp": patterns[index % len(patterns)][2],
            "night_temp": patterns[index % len(patterns)][3],
            "wind_direction": patterns[index % len(patterns)][4],
            "wind_power": patterns[index % len(patterns)][5],
            "suggestion": patterns[index % len(patterns)][6],
            "uv_index": "中等",
            "comfort_index": "较舒适",
        }
        for index in range(days)
    ]


def route_matrix(attractions_payload: list[dict[str, Any]]) -> dict[str, Any]:
    """生成演示路线矩阵。"""
    grouped: dict[int, list[dict[str, Any]]] = {}
    for attraction in attractions_payload:
        day_index = int(attraction.get("day_index", 0) or 0)
        if day_index > 0:
            grouped.setdefault(day_index, []).append(attraction)

    legs: list[dict[str, Any]] = []
    daily_routes: list[list[dict[str, Any]]] = []
    for day_index, day_items in sorted(grouped.items()):
        day_legs: list[dict[str, Any]] = []
        for leg_index in range(len(day_items) - 1):
            start = day_items[leg_index]
            end = day_items[leg_index + 1]
            segment = {
                "day_index": day_index,
                "leg_index": leg_index + 1,
                "from_name": start.get("name", ""),
                "to_name": end.get("name", ""),
                "from_location": start.get("location"),
                "to_location": end.get("location"),
                "mode": "transit",
                "distance": 3.2,
                "duration": 24,
                "cost": 4,
                "instruction": "演示模式估算公共交通接驳，实际出行请打开地图复核。",
                "status": "ok",
                "issue": "",
            }
            legs.append(segment)
            day_legs.append(segment)
        daily_routes.append(day_legs)

    return {
        "mode": "transit",
        "legs": legs,
        "issues": [],
        "daily_routes": daily_routes,
    }


def evaluation() -> dict[str, Any]:
    """生成演示审核结果。"""
    return {
        "passed": True,
        "score": 0.92,
        "dimensions": {
            "completeness": 0.95,
            "preference_fit": 0.9,
            "route_efficiency": 0.88,
            "poi_confidence": 0.93,
        },
        "blocking_issues": [],
        "repair_tasks": [],
        "residual_risks": ["演示模式数据仅用于流程展示，真实出行前请复核天气、营业时间和交通。"],
    }
