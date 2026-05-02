"""AI utilities - LLM helpers, POI parsing, search rules, and itinerary layout."""
from __future__ import annotations

import json
import re
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any, Tuple

from langchain_qwq import ChatQwen

from app.config import get_logger, settings
from app.ai.errors import LLMJsonError

logger = get_logger("AIUtils")

# ═══════════════════════════════════════════════════════════════════════════════
# LLM JSON 调用工具层
# ═══════════════════════════════════════════════════════════════════════════════


def _response_to_text(response: Any) -> str:
    """将 LangChain 响应统一转为纯文本。"""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """从文本中提取 JSON 对象。"""
    text = text.strip()
    if not text:
        return None

    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass

    fenced = re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
    for chunk in fenced:
        try:
            data = json.loads(chunk)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


async def invoke_llm_json_async(
    *,
    prompt: str,
    temperature: float = 1.2,
) -> dict[str, Any]:
    """异步调用 LLM 并返回 JSON 对象；失败时直接抛错。"""
    try:
        llm = ChatQwen(
            model="qwen3.5-flash-2026-02-23",
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.DASHSCOPE_BASE_URL,
            temperature=temperature,
            extra_body={
                "enable_thinking": False
            },
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        response = await llm.ainvoke(prompt)
        parsed = _extract_json_object(_response_to_text(response))
        if isinstance(parsed, dict):
            return parsed
        raise LLMJsonError("LLM response did not contain a valid JSON object")
    except Exception as exc:
        if isinstance(exc, LLMJsonError):
            raise
        raise LLMJsonError(f"LLM JSON call failed: {exc}") from exc


# ═══════════════════════════════════════════════════════════════════════════════
# POI 解析工具
# ═══════════════════════════════════════════════════════════════════════════════


def parse_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_location(value: Any) -> dict[str, float] | None:
    if isinstance(value, dict):
        try:
            lat = float(value.get("lat"))
            lng = float(value.get("lng"))
        except (TypeError, ValueError):
            return None
        return {"lat": lat, "lng": lng}

    if isinstance(value, str):
        parts = [item.strip() for item in value.split(",")]
        if len(parts) != 2:
            return None
        try:
            lng = float(parts[0])
            lat = float(parts[1])
        except ValueError:
            return None
        return {"lat": lat, "lng": lng}

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 搜索规则工具
# ═══════════════════════════════════════════════════════════════════════════════


def _uniq(values: list[str], limit: int) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


ATTRACTION_STYLE_MAP: dict[str, list[str]] = {
    "自然风光": ["湿地公园"],
    "历史古迹": ["历史古迹"],
    "文化体验": ["博物馆"],
    "购物": ["步行街"],
}

CITY_ATTRACTION_MAP: dict[str, list[str]] = {
    "杭州": ["湖景", "历史街区"],
    "北京": ["皇家古迹", "历史街区"],
    "上海": ["滨江地标", "历史街区"],
    "成都": ["历史街区", "博物馆"],
    "西安": ["古城墙", "博物馆"],
    "广州": ["历史街区", "博物馆"],
    "苏州": ["园林", "历史街区"],
}

FOOD_STYLE_MAP: dict[str, list[str]] = {
    "美食": ["本地菜", "特色菜", "老字号", "小吃", "人气餐厅"],
    "文化体验": ["老字号", "茶楼", "本地菜", "特色菜"],
    "购物": ["商圈美食", "网红餐厅", "咖啡馆", "甜品"],
    "自然风光": ["景观餐厅", "农家菜", "湖景餐厅", "露台餐厅"],
}

FOOD_COMPANION_MAP: dict[str, list[str]] = {
    "情侣": ["景观餐厅", "西餐", "甜品", "咖啡馆"],
    "家庭": ["亲子餐厅", "家常菜", "本地菜", "早茶"],
    "朋友": ["火锅", "烧烤", "夜宵", "啤酒餐吧"],
    "老人": ["茶楼", "粤菜", "汤馆", "家常菜"],
    "独自": ["小吃", "面馆", "简餐", "咖啡馆"],
}

CITY_CUISINE_MAP: dict[str, list[str]] = {
    "广州": ["粤菜", "早茶", "烧腊", "糖水"],
    "深圳": ["粤菜", "海鲜", "茶餐厅"],
    "佛山": ["粤菜", "顺德菜", "早茶"],
    "成都": ["川菜", "火锅", "串串", "小吃"],
    "重庆": ["火锅", "江湖菜", "小面"],
    "西安": ["陕菜", "小吃", "面馆"],
    "北京": ["京菜", "烤鸭", "炸酱面", "铜锅涮肉"],
    "上海": ["本帮菜", "生煎", "海派餐厅"],
    "苏州": ["苏帮菜", "面馆", "评弹茶馆"],
    "杭州": ["杭帮菜", "茶楼", "江景餐厅"],
}

HOTEL_LEVEL_MAP: dict[str, list[str]] = {
    "经济型": ["经济型酒店", "快捷酒店", "连锁酒店", "高性价比酒店"],
    "舒适型": ["舒适型酒店", "商务酒店", "精选酒店", "品质酒店"],
    "高档型": ["高档酒店", "四星酒店", "高端酒店", "品牌酒店"],
    "豪华型": ["豪华酒店", "五星级酒店", "国际酒店", "度假酒店"],
}

HOTEL_COMPANION_MAP: dict[str, list[str]] = {
    "情侣": ["江景酒店", "设计酒店", "度假酒店", "情侣酒店"],
    "家庭": ["亲子酒店", "家庭房酒店", "度假酒店", "公寓酒店"],
    "朋友": ["双床房酒店", "地铁口酒店", "商圈酒店"],
    "老人": ["安静酒店", "交通便利酒店", "电梯酒店"],
    "独自": ["地铁口酒店", "商务酒店", "交通便利酒店"],
}


def _special_requirement_keywords(text: str, category: str) -> list[str]:
    if not text:
        return []

    rules: list[tuple[list[str], list[str]]] = []
    if category == "attraction":
        rules = [
            (["夜景", "晚上"], ["夜景", "灯光秀"]),
            (["拍照", "出片"], ["花海", "观景台", "艺术馆"]),
            (["室内", "下雨"], ["博物馆", "艺术馆", "展览馆"]),
            (["亲子", "遛娃"], ["动物园", "植物园", "游乐园"]),
            (["安静"], ["湖景", "湿地公园", "文化馆"]),
        ]
    elif category == "food":
        rules = [
            (["夜宵", "晚上"], ["夜宵", "烧烤"]),
            (["拍照", "约会"], ["景观餐厅", "甜品", "咖啡馆"]),
            (["清淡"], ["粤菜", "汤馆", "家常菜"]),
            (["亲子"], ["亲子餐厅", "家常菜"]),
        ]
    elif category == "hotel":
        rules = [
            (["地铁", "交通便利"], ["地铁口酒店", "交通便利酒店"]),
            (["安静"], ["安静酒店", "度假酒店"]),
            (["亲子"], ["亲子酒店", "家庭房酒店"]),
            (["高层", "景观"], ["江景酒店", "景观酒店"]),
        ]

    result: list[str] = []
    for keys, values in rules:
        if _contains_any(text, keys):
            result.extend(values)
    return result


def build_attraction_keywords(request: dict[str, Any], *, seed_keywords: list[str] | None = None, limit: int = 8) -> list[str]:
    destination = str(request.get("destination", "")).strip()
    styles = [str(item).strip() for item in (request.get("style_preferences") or []) if str(item).strip()]
    special = str(request.get("special_requirements", "") or "").strip()

    values: list[str] = []
    values.extend(seed_keywords or [])
    values.extend(CITY_ATTRACTION_MAP.get(destination, []))
    for style in styles:
        values.extend(ATTRACTION_STYLE_MAP.get(style, []))
    values.extend(_special_requirement_keywords(special, "attraction"))

    return _uniq(values, limit)


def build_food_keywords(request: dict[str, Any], *, seed_keywords: list[str] | None = None, limit: int = 8) -> list[str]:
    destination = str(request.get("destination", "")).strip()
    companions = str(request.get("companions", "独自")).strip() or "独自"
    styles = [str(item).strip() for item in (request.get("style_preferences") or []) if str(item).strip()]
    special = str(request.get("special_requirements", "") or "").strip()

    values: list[str] = []
    values.extend(seed_keywords or [])
    values.extend(CITY_CUISINE_MAP.get(destination, []))
    for style in styles:
        values.extend(FOOD_STYLE_MAP.get(style, []))
    values.extend(FOOD_COMPANION_MAP.get(companions, []))
    values.extend(_special_requirement_keywords(special, "food"))
    values.extend(["本地菜", "特色菜", "老字号", "小吃"])
    return _uniq(values, limit)


def build_hotel_keywords(
    request: dict[str, Any],
    *,
    hotel_level: str,
    price_range: str = "",
    seed_keywords: list[str] | None = None,
    limit: int = 6,
) -> list[str]:
    companions = str(request.get("companions", "独自")).strip() or "独自"
    special = str(request.get("special_requirements", "") or "").strip()
    pace = str(request.get("pace", "适中")).strip()

    values: list[str] = []
    values.extend(seed_keywords or [])
    values.extend(HOTEL_LEVEL_MAP.get(hotel_level, HOTEL_LEVEL_MAP["舒适型"]))
    values.extend(HOTEL_COMPANION_MAP.get(companions, []))
    values.extend(_special_requirement_keywords(special, "hotel"))

    if pace == "紧凑":
        values.extend(["地铁口酒店", "商圈酒店"])
    elif pace == "宽松":
        values.extend(["度假酒店", "安静酒店"])

    low, high = 0, 0
    try:
        low_str, high_str = str(price_range).split(",")
        low, high = int(float(low_str)), int(float(high_str))
    except Exception:
        pass
    if high and high <= 400:
        values.append("高性价比酒店")
    elif low >= 800:
        values.append("豪华酒店")

    return _uniq(values, limit)


def compute_trip_strategy(request: dict[str, Any]) -> dict[str, Any]:
    start_date = request.get("start_date")
    end_date = request.get("end_date")
    try:
        start = datetime.strptime(str(start_date), "%Y-%m-%d").date()
        end = datetime.strptime(str(end_date), "%Y-%m-%d").date()
        days = max(1, (end - start).days + 1)
    except (TypeError, ValueError):
        days = max(1, int(request.get("days", 3) or 3))

    max_per_day = 2
    needed_attractions = max(2, days * max_per_day)
    return {
        "days": days,
        "max_attractions_per_day": max_per_day,
        "needed_attractions": needed_attractions,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 行程布局工具
# ═══════════════════════════════════════════════════════════════════════════════


def normalize_location(raw: Any) -> Optional[Dict[str, float]]:
    if not isinstance(raw, dict):
        return None

    try:
        lat = float(raw.get("lat"))
        lng = float(raw.get("lng"))
    except (TypeError, ValueError):
        return None

    if abs(lat) < 0.000001 and abs(lng) < 0.000001:
        return None

    return {"lat": lat, "lng": lng}


def _haversine_km(start: Dict[str, float], end: Dict[str, float]) -> float:
    lon1, lat1 = radians(start["lng"]), radians(start["lat"])
    lon2, lat2 = radians(end["lng"]), radians(end["lat"])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    arc = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(arc))


def _location_of(item: Dict[str, Any]) -> Optional[Dict[str, float]]:
    return normalize_location(item.get("location"))


def _item_rating(item: Dict[str, Any]) -> float:
    try:
        return float(item.get("rating", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _named_item_key(item: Dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("name", "")).strip(),
        str(item.get("address", "")).strip(),
    )


def _mean_location(locations: List[Dict[str, float]]) -> Optional[Dict[str, float]]:
    if not locations:
        return None
    return {
        "lat": sum(point["lat"] for point in locations) / len(locations),
        "lng": sum(point["lng"] for point in locations) / len(locations),
    }


def _distance_to_anchor(item: Dict[str, Any], anchor: Optional[Dict[str, float]]) -> float:
    item_location = _location_of(item)
    if not anchor or not item_location:
        return 999.0
    return round(_haversine_km(anchor, item_location), 3)


def _bucket_anchor(items: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    return _mean_location([location for location in (_location_of(item) for item in items) if location])


def _build_day_anchor(
    day_attractions: Optional[List[Dict[str, Any]]] = None,
    hotel: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, float]]:
    locations: List[Dict[str, float]] = []
    hotel_location = _location_of(hotel or {})
    if hotel_location:
        locations.append(hotel_location)

    for item in day_attractions or []:
        attraction_location = _location_of(item)
        if attraction_location:
            locations.append(attraction_location)

    return _mean_location(locations)


def _cluster_items_by_proximity(
    items: List[Dict[str, Any]],
    bucket_count: int,
    bucket_limit: int,
) -> List[List[Dict[str, Any]]]:
    buckets: List[List[Dict[str, Any]]] = [[] for _ in range(max(0, bucket_count))]
    if bucket_count <= 0 or bucket_limit <= 0:
        return buckets

    named_items = [item for item in items if item.get("name")]
    if not named_items:
        return buckets

    order_map = {id(item): index for index, item in enumerate(items)}
    capacity = bucket_count * bucket_limit
    usable_items = named_items[:capacity]
    located_items = [item for item in usable_items if _location_of(item)]
    unlocated_items = [item for item in usable_items if not _location_of(item)]

    remaining = sorted(
        located_items,
        key=lambda item: (
            round((_location_of(item) or {}).get("lng", 0), 6),
            round((_location_of(item) or {}).get("lat", 0), 6),
            -_item_rating(item),
        ),
    )

    for bucket_index in range(bucket_count):
        if not remaining:
            break

        current_bucket = [remaining.pop(0)]
        while remaining and len(current_bucket) < bucket_limit:
            anchor = _bucket_anchor(current_bucket)
            next_index = min(
                range(len(remaining)),
                key=lambda idx: (
                    _distance_to_anchor(remaining[idx], anchor),
                    -_item_rating(remaining[idx]),
                ),
            )
            current_bucket.append(remaining.pop(next_index))
        buckets[bucket_index] = current_bucket

    for item in unlocated_items:
        for bucket in buckets:
            if len(bucket) < bucket_limit:
                bucket.append(item)
                break

    ordered = sorted(
        buckets,
        key=lambda bucket: (
            round((_bucket_anchor(bucket) or {}).get("lng", 999), 6),
            round((_bucket_anchor(bucket) or {}).get("lat", 999), 6),
        ),
    )
    for bucket in ordered:
        bucket.sort(key=lambda item: order_map.get(id(item), 999))
    return ordered


def _bucket_distance(left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> float:
    left_anchor = _bucket_anchor(left)
    right_anchor = _bucket_anchor(right)
    if not left_anchor or not right_anchor:
        return 999.0
    return round(_haversine_km(left_anchor, right_anchor), 3)


def _order_buckets_for_itinerary(
    buckets: List[List[Dict[str, Any]]],
    *,
    stay_span: int = 2,
) -> List[List[Dict[str, Any]]]:
    non_empty = [bucket for bucket in buckets if bucket]
    empty = [bucket for bucket in buckets if not bucket]
    if stay_span != 2 or len(non_empty) <= 1:
        return non_empty + empty

    remaining = list(non_empty)
    ordered: List[List[Dict[str, Any]]] = []
    while len(remaining) >= 2:
        pair = min(
            (
                (left_index, right_index)
                for left_index in range(len(remaining))
                for right_index in range(left_index + 1, len(remaining))
            ),
            key=lambda indexes: _bucket_distance(remaining[indexes[0]], remaining[indexes[1]]),
        )
        left_bucket = remaining[pair[0]]
        right_bucket = remaining[pair[1]]
        ordered.extend(
            sorted(
                [left_bucket, right_bucket],
                key=lambda bucket: (
                    round((_bucket_anchor(bucket) or {}).get("lng", 999), 6),
                    round((_bucket_anchor(bucket) or {}).get("lat", 999), 6),
                ),
            )
        )
        for index in sorted(pair, reverse=True):
            remaining.pop(index)

    ordered.extend(remaining)
    ordered.extend(empty)
    return ordered


def distribute_attractions(
    attractions: List[Dict[str, Any]],
    days: int,
    max_per_day: int,
) -> List[List[Dict[str, Any]]]:
    if not attractions:
        return [[] for _ in range(days)]

    limit = max(1, min(2, int(max_per_day or 2)))
    target_per_day = limit if len(attractions) >= days * limit else max(1, min(limit, len(attractions) // max(days, 1)))
    result = _order_buckets_for_itinerary(
        _cluster_items_by_proximity(attractions, days, target_per_day),
        stay_span=2,
    )
    if len(result) < days:
        result.extend([[] for _ in range(days - len(result))])
    return result[:days]


def _fallback_restaurant_buckets(restaurants: List[Dict[str, Any]], days: int) -> List[List[Dict[str, Any]]]:
    if not restaurants:
        return [[] for _ in range(days)]

    valid = [
        item
        for item in restaurants
        if item.get("name") and normalize_location(item.get("location"))
    ]
    if not valid:
        return [[] for _ in range(days)]

    type_priority = {"breakfast": 0, "lunch": 1, "snack": 2, "dinner": 3}
    ordered = sorted(
        valid,
        key=lambda item: (
            type_priority.get(str(item.get("meal_type", item.get("type", ""))).strip().lower(), 9),
            -(float(item.get("rating", 0) or 0)),
        ),
    )

    bucket_limit = 2 if len(ordered) >= days * 2 else 1
    buckets: List[List[Dict[str, Any]]] = [[] for _ in range(days)]
    for index, item in enumerate(ordered):
        day_index = index % days
        if len(buckets[day_index]) >= bucket_limit:
            continue
        buckets[day_index].append(item)

    for bucket in buckets:
        bucket.sort(key=lambda item: type_priority.get(str(item.get("meal_type", item.get("type", ""))).strip().lower(), 9))

    return buckets


def _pick_nearest_restaurant(
    candidates: List[Dict[str, Any]],
    *,
    anchor: Optional[Dict[str, float]],
    meal_type: Optional[str] = None,
    excluded_keys: Optional[set[tuple[str, str]]] = None,
) -> Optional[Dict[str, Any]]:
    filtered = []
    for item in candidates:
        if excluded_keys and _named_item_key(item) in excluded_keys:
            continue
        if meal_type and str(item.get("meal_type", item.get("type", ""))).strip().lower() != meal_type:
            continue
        filtered.append(item)

    if not filtered:
        return None

    return min(
        filtered,
        key=lambda item: (
            _distance_to_anchor(item, anchor),
            -_item_rating(item),
        ),
    )


def distribute_restaurants(
    restaurants: List[Dict[str, Any]],
    days: int,
    *,
    day_attractions: Optional[List[List[Dict[str, Any]]]] = None,
    day_hotels: Optional[List[Optional[Dict[str, Any]]]] = None,
) -> List[List[Dict[str, Any]]]:
    if not restaurants:
        return [[] for _ in range(days)]

    valid = [
        item
        for item in restaurants
        if item.get("name") and normalize_location(item.get("location"))
    ]
    if not valid:
        return [[] for _ in range(days)]

    if not day_attractions and not day_hotels:
        return _fallback_restaurant_buckets(valid, days)

    type_priority = {"breakfast": 0, "lunch": 1, "snack": 2, "dinner": 3}
    bucket_limit = 2 if len(valid) >= days * 2 else 1
    buckets: List[List[Dict[str, Any]]] = [[] for _ in range(days)]
    used_keys: set[tuple[str, str]] = set()

    for day_index in range(days):
        anchor = _build_day_anchor(
            day_attractions[day_index] if day_attractions and day_index < len(day_attractions) else None,
            day_hotels[day_index] if day_hotels and day_index < len(day_hotels) else None,
        )
        preferred_types = [] if bucket_limit == 1 else ["lunch", "dinner"]
        bucket: List[Dict[str, Any]] = []

        for meal_type in preferred_types:
            candidate = _pick_nearest_restaurant(
                valid,
                anchor=anchor,
                meal_type=meal_type,
                excluded_keys=used_keys,
            )
            if not candidate:
                continue
            bucket.append(candidate)
            used_keys.add(_named_item_key(candidate))

        while len(bucket) < bucket_limit:
            candidate = _pick_nearest_restaurant(
                valid,
                anchor=anchor,
                excluded_keys=used_keys,
            )
            if not candidate:
                break
            bucket.append(candidate)
            used_keys.add(_named_item_key(candidate))

        bucket.sort(key=lambda item: type_priority.get(str(item.get("meal_type", item.get("type", ""))).strip().lower(), 9))
        buckets[day_index] = bucket

    return buckets


def distribute_hotels(
    hotels: List[Dict[str, Any]],
    days: int,
    *,
    stay_span: int = 2,
    day_attractions: Optional[List[List[Dict[str, Any]]]] = None,
) -> List[Optional[Dict[str, Any]]]:
    if days <= 0:
        return []
    if not hotels:
        return [None for _ in range(days)]

    valid = [item for item in hotels if item.get("name")]
    if not valid:
        return [None for _ in range(days)]

    span = max(1, int(stay_span or 2))
    geo_valid = [item for item in valid if _location_of(item)]
    if not geo_valid or not day_attractions:
        plan: List[Optional[Dict[str, Any]]] = []
        for day_index in range(days):
            hotel_index = min(day_index // span, len(valid) - 1)
            plan.append(valid[hotel_index])
        return plan

    plan: List[Optional[Dict[str, Any]]] = []
    used_keys: set[tuple[str, str]] = set()
    fallback_index = 0

    for block_start in range(0, days, span):
        block_days = day_attractions[block_start:block_start + span]
        anchor = _mean_location(
            [
                location
                for day_items in block_days
                for location in (_location_of(item) for item in day_items)
                if location
            ]
        )
        if anchor:
            hotel = min(
                geo_valid,
                key=lambda item: (
                    _distance_to_anchor(item, anchor),
                    0 if _named_item_key(item) not in used_keys else 1,
                    -_item_rating(item),
                ),
            )
            used_keys.add(_named_item_key(hotel))
        else:
            hotel = valid[min(fallback_index, len(valid) - 1)]
            fallback_index = min(fallback_index + 1, len(valid) - 1)

        for _ in range(span):
            if len(plan) >= days:
                break
            plan.append(hotel)

    return plan


def _create_stop(name: str, location: Dict[str, float], kind: str) -> Dict[str, Any]:
    return {
        "name": name,
        "location": location,
        "kind": kind,
    }


def _meal_groups(meals: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {
        "breakfast": [],
        "lunch": [],
        "snack": [],
        "dinner": [],
        "other": [],
    }
    for meal in meals:
        meal_type = str(meal.get("meal_type", meal.get("type", "")).strip().lower())
        key = meal_type if meal_type in grouped else "other"
        grouped[key].append(meal)
    return grouped


def build_day_stops(
    hotel: Optional[Dict[str, Any]],
    attractions: List[Dict[str, Any]],
    meals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    hotel_location = normalize_location((hotel or {}).get("location"))
    hotel_name = str((hotel or {}).get("name", "")).strip()
    valid_attractions = [
        item
        for item in attractions
        if item.get("name") and normalize_location(item.get("location"))
    ]
    grouped_meals = _meal_groups(meals)

    stops: List[Dict[str, Any]] = []
    if hotel_location and hotel_name:
        stops.append(_create_stop(hotel_name, hotel_location, "hotel"))

    if grouped_meals["breakfast"]:
        breakfast = grouped_meals["breakfast"][0]
        breakfast_location = normalize_location(breakfast.get("location"))
        if breakfast_location:
            stops.append(_create_stop(str(breakfast.get("name", "")).strip(), breakfast_location, "meal"))

    for index, attraction in enumerate(valid_attractions):
        attraction_location = normalize_location(attraction.get("location"))
        if not attraction_location:
            continue
        stops.append(_create_stop(str(attraction.get("name", "")).strip(), attraction_location, "attraction"))

        if index == 0 and grouped_meals["lunch"]:
            lunch = grouped_meals["lunch"][0]
            lunch_location = normalize_location(lunch.get("location"))
            if lunch_location:
                stops.append(_create_stop(str(lunch.get("name", "")).strip(), lunch_location, "meal"))

        if index == max(1, len(valid_attractions) - 1) and grouped_meals["snack"]:
            snack = grouped_meals["snack"][0]
            snack_location = normalize_location(snack.get("location"))
            if snack_location:
                stops.append(_create_stop(str(snack.get("name", "")).strip(), snack_location, "meal"))

    if not valid_attractions and grouped_meals["lunch"]:
        lunch = grouped_meals["lunch"][0]
        lunch_location = normalize_location(lunch.get("location"))
        if lunch_location:
            stops.append(_create_stop(str(lunch.get("name", "")).strip(), lunch_location, "meal"))

    if grouped_meals["dinner"]:
        dinner = grouped_meals["dinner"][0]
        dinner_location = normalize_location(dinner.get("location"))
        if dinner_location:
            stops.append(_create_stop(str(dinner.get("name", "")).strip(), dinner_location, "meal"))

    for extra_meal in grouped_meals["other"]:
        extra_location = normalize_location(extra_meal.get("location"))
        if extra_location:
            stops.append(_create_stop(str(extra_meal.get("name", "")).strip(), extra_location, "meal"))

    if hotel_location and hotel_name and len(stops) > 1:
        stops.append(_create_stop(hotel_name, hotel_location, "hotel"))

    deduped: List[Dict[str, Any]] = []
    for stop in stops:
        if not stop["name"]:
            continue
        if deduped:
            previous = deduped[-1]
            same_name = previous["name"] == stop["name"]
            same_location = previous["location"] == stop["location"]
            if same_name and same_location:
                continue
        deduped.append(stop)
    return deduped


def build_daily_timeline(
    hotel: Optional[Dict[str, Any]],
    attractions: List[Dict[str, Any]],
    meals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    stops = build_day_stops(hotel, attractions, meals)
    if not stops:
        return []

    default_times = ["09:00", "10:30", "12:30", "14:30", "16:30", "18:30", "20:30"]
    timeline: List[Dict[str, Any]] = []
    for index, stop in enumerate(stops):
        time = default_times[index] if index < len(default_times) else f"{9 + index:02d}:00"
        timeline.append(
            {
                "time": time,
                "activity": stop["name"],
                "type": stop["kind"] if stop["kind"] != "hotel" else "hotel",
            }
        )
    return timeline


def build_timeline_from_stop_plan(stops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not stops:
        return []

    default_times = ["09:00", "10:30", "12:30", "14:30", "16:30", "18:30", "20:30"]
    timeline: List[Dict[str, Any]] = []
    for index, stop in enumerate(stops):
        time = default_times[index] if index < len(default_times) else f"{9 + index:02d}:00"
        timeline.append(
            {
                "time": time,
                "activity": str(stop.get("name", "")).strip(),
                "type": str(stop.get("kind", "")).strip() or "other",
            }
        )
    return timeline


def sum_route_segment_cost(segments: List[Dict[str, Any]]) -> float:
    return round(sum(float(item.get("cost", 0) or 0) for item in segments), 2)
