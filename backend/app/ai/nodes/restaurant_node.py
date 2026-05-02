"""美食 Agent 流程。

负责搜索和筛选餐厅候选：
1. 基于规则生成餐厅检索关键词
2. 调用地图工具搜索餐厅
3. LLM 筛选和选择

图结构位置：
- 接收 reviewer_agent 的输出
- 输出 restaurants 到状态
- 连接到 transport_agent
"""

from __future__ import annotations

import json
from datetime import datetime
from time import perf_counter
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.config import get_logger
from app.ai.models.graph_models import TripState
from app.ai.prompts import render_prompt
from app.ai.utils import invoke_prompt_json_async, parse_float, parse_int, parse_location, build_food_keywords
from app.services.amap import POI, POISearchResponse
from app.ai.mcp.client import get_tool, invoke_tool_with_debug

logger = get_logger("RestaurantService")

# ══════════════════════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════════════════════
RESTAURANT_TOOL_NAME = "maps_text_search"
MAX_CANDIDATE_POOL = 18
FIXED_CITY_LIMIT = True
RESTAURANT_TYPE_PREFIX = "05"
RESTAURANT_TEXT_MARKERS = (
    "餐饮服务",
    "餐厅",
    "酒楼",
    "饭店",
    "小吃",
    "菜",
    "火锅",
    "烧烤",
    "咖啡",
    "茶馆",
    "茶楼",
    "甜品",
    "面馆",
    "餐吧",
    "饮品",
    "冷饮",
    "糕饼",
)

RESTAURANT_TYPE_CATALOG: dict[str, dict[str, list[str] | str]] = {
    "050100": {"label": "中餐厅", "aliases": ["中餐厅", "中餐"]},
    "050101": {"label": "综合酒楼", "aliases": ["综合酒楼", "酒楼"]},
    "050102": {"label": "四川菜(川菜)", "aliases": ["四川菜", "川菜"]},
    "050103": {"label": "广东菜(粤菜)", "aliases": ["广东菜", "粤菜"]},
    "050104": {"label": "山东菜(鲁菜)", "aliases": ["山东菜", "鲁菜"]},
    "050105": {"label": "江苏菜", "aliases": ["江苏菜", "苏菜"]},
    "050106": {"label": "浙江菜", "aliases": ["浙江菜", "浙菜"]},
    "050107": {"label": "上海菜", "aliases": ["上海菜", "本帮菜"]},
    "050108": {"label": "湖南菜(湘菜)", "aliases": ["湖南菜", "湘菜"]},
    "050109": {"label": "安徽菜(徽菜)", "aliases": ["安徽菜", "徽菜"]},
    "050110": {"label": "福建菜", "aliases": ["福建菜", "闽菜"]},
    "050111": {"label": "北京菜", "aliases": ["北京菜", "京菜"]},
    "050112": {"label": "湖北菜(鄂菜)", "aliases": ["湖北菜", "鄂菜"]},
    "050113": {"label": "东北菜", "aliases": ["东北菜"]},
    "050114": {"label": "云贵菜", "aliases": ["云贵菜", "云南菜", "贵州菜"]},
    "050115": {"label": "西北菜", "aliases": ["西北菜"]},
    "050116": {"label": "老字号", "aliases": ["老字号"]},
    "050117": {"label": "火锅店", "aliases": ["火锅店", "火锅"]},
    "050118": {"label": "特色/地方风味餐厅", "aliases": ["特色餐厅", "地方风味", "地方风味餐厅", "特色/地方风味餐厅"]},
    "050119": {"label": "海鲜酒楼", "aliases": ["海鲜酒楼", "海鲜"]},
    "050120": {"label": "中式素菜馆", "aliases": ["中式素菜馆", "素菜馆", "素食"]},
    "050121": {"label": "清真菜馆", "aliases": ["清真菜馆", "清真"]},
    "050122": {"label": "台湾菜", "aliases": ["台湾菜"]},
    "050123": {"label": "潮州菜", "aliases": ["潮州菜", "潮汕菜"]},
    "050200": {"label": "外国餐厅", "aliases": ["外国餐厅", "西餐厅", "西餐"]},
    "050201": {"label": "西餐厅(综合风味)", "aliases": ["西餐厅", "综合西餐", "西餐厅(综合风味)"]},
    "050202": {"label": "日本料理", "aliases": ["日本料理", "日料"]},
    "050203": {"label": "韩国料理", "aliases": ["韩国料理", "韩料"]},
    "050204": {"label": "法国菜品餐厅", "aliases": ["法国菜", "法餐"]},
    "050205": {"label": "意式菜品餐厅", "aliases": ["意大利菜", "意餐", "意式菜品餐厅"]},
    "050206": {"label": "泰国/越南菜品餐厅", "aliases": ["泰国菜", "越南菜", "东南亚菜"]},
    "050207": {"label": "地中海风格菜品", "aliases": ["地中海菜", "地中海风格菜品"]},
    "050208": {"label": "美式风味", "aliases": ["美式风味", "美式餐厅", "美餐"]},
    "050209": {"label": "印度风味", "aliases": ["印度风味", "印度菜"]},
    "050210": {"label": "英式菜品餐厅", "aliases": ["英式菜品餐厅", "英式餐厅", "英餐"]},
    "050211": {"label": "牛扒店(扒房)", "aliases": ["牛扒店", "扒房", "牛排"]},
    "050212": {"label": "俄国菜", "aliases": ["俄国菜", "俄餐"]},
    "050213": {"label": "葡国菜", "aliases": ["葡国菜", "葡餐"]},
    "050214": {"label": "德国菜", "aliases": ["德国菜", "德餐"]},
    "050215": {"label": "巴西菜", "aliases": ["巴西菜"]},
    "050216": {"label": "墨西哥菜", "aliases": ["墨西哥菜", "墨餐"]},
    "050217": {"label": "其它亚洲菜", "aliases": ["其它亚洲菜", "其他亚洲菜", "亚洲菜"]},
    "050300": {"label": "快餐厅", "aliases": ["快餐厅", "快餐"]},
    "050301": {"label": "肯德基", "aliases": ["肯德基", "KFC"]},
    "050302": {"label": "麦当劳", "aliases": ["麦当劳", "M记"]},
    "050303": {"label": "必胜客", "aliases": ["必胜客", "Pizza Hut"]},
    "050304": {"label": "永和豆浆", "aliases": ["永和豆浆"]},
    "050305": {"label": "茶餐厅", "aliases": ["茶餐厅"]},
    "050306": {"label": "大家乐", "aliases": ["大家乐"]},
    "050307": {"label": "大快活", "aliases": ["大快活"]},
    "050308": {"label": "美心", "aliases": ["美心"]},
    "050309": {"label": "吉野家", "aliases": ["吉野家"]},
    "050310": {"label": "仙踪林", "aliases": ["仙踪林"]},
    "050311": {"label": "呷哺呷哺", "aliases": ["呷哺呷哺"]},
    "050400": {"label": "休闲餐饮场所", "aliases": ["休闲餐饮场所", "休闲餐饮"]},
    "050500": {"label": "咖啡厅", "aliases": ["咖啡厅", "咖啡店", "咖啡馆"]},
    "050501": {"label": "星巴克咖啡", "aliases": ["星巴克咖啡", "星巴克"]},
    "050502": {"label": "上岛咖啡", "aliases": ["上岛咖啡"]},
    "050503": {"label": "Pacific Coffee Company", "aliases": ["Pacific Coffee Company", "Pacific Coffee"]},
    "050504": {"label": "巴黎咖啡店", "aliases": ["巴黎咖啡店"]},
    "050600": {"label": "茶艺馆", "aliases": ["茶艺馆", "茶馆"]},
    "050700": {"label": "冷饮店", "aliases": ["冷饮店", "饮品店"]},
    "050800": {"label": "糕饼店", "aliases": ["糕饼店", "面包店"]},
    "050900": {"label": "甜品店", "aliases": ["甜品店", "甜品"]},
}

RESTAURANT_TYPE_HINTS_BY_STYLE: dict[str, list[str]] = {
    "美食": ["050118", "050116", "050117", "050123"],
    "文化体验": ["050116", "050118", "050305", "050600"],
    "购物": ["050500", "050900", "050300", "050400"],
    "自然风光": ["050119", "050118", "050500", "050600"],
}

RESTAURANT_TYPE_HINTS_BY_COMPANION: dict[str, list[str]] = {
    "情侣": ["050204", "050205", "050500", "050900"],
    "家庭": ["050103", "050117", "050118", "050305"],
    "朋友": ["050117", "050102", "050108", "050208"],
    "老人": ["050103", "050116", "050121", "050600"],
    "独自": ["050300", "050500", "050102", "050118"],
}

RESTAURANT_TYPE_HINTS_BY_SPECIAL_REQUIREMENT: list[tuple[list[str], list[str]]] = [
    (["火锅", "夜宵"], ["050117", "050300"]),
    (["咖啡", "下午茶"], ["050500", "050900"]),
    (["清淡", "养生"], ["050103", "050121", "050120"]),
    (["海鲜"], ["050119"]),
    (["本地", "特色"], ["050118", "050116"]),
]

VALID_RESTAURANT_TYPE_CODES = set(RESTAURANT_TYPE_CATALOG.keys())

RESTAURANT_TYPE_ALIAS_TO_CODE: dict[str, str] = {}
for _code, _meta in RESTAURANT_TYPE_CATALOG.items():
    _aliases = [_code, str(_meta["label"])] + [str(item) for item in _meta.get("aliases", [])]
    for _alias in _aliases:
        text = str(_alias).strip()
        if text:
            RESTAURANT_TYPE_ALIAS_TO_CODE[text] = _code
            RESTAURANT_TYPE_ALIAS_TO_CODE[text.replace(" ", "")] = _code


def _split_search_values(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    normalized = value.replace("，", "|").replace(",", "|").replace(";", "|").replace("；", "|")
    return [item.strip() for item in normalized.split("|") if item.strip()]


def _normalize_restaurant_types(
    raw_types: List[str] | str | None,
    *,
    keywords: List[str] | None = None,
    allowed_types: List[str] | None = None,
    limit: int = 6,
) -> List[str]:
    allowed = set(allowed_types or [])
    result: List[str] = []

    def add_candidate(value: str) -> None:
        text = str(value or "").strip()
        if not text:
            return
        if text in VALID_RESTAURANT_TYPE_CODES:
            code = text
        else:
            code = (
                RESTAURANT_TYPE_ALIAS_TO_CODE.get(text)
                or RESTAURANT_TYPE_ALIAS_TO_CODE.get(text.replace(" ", ""))
            )
        if not code:
            return
        if allowed and code not in allowed:
            return
        if code not in result:
            result.append(code)

    for item in _split_search_values(raw_types):
        add_candidate(item)
    for item in keywords or []:
        add_candidate(item)

    return result[:limit]


def _default_restaurant_types(
    *,
    preferences: List[str],
    companions: str,
    special_requirements: str,
    allowed_types: List[str] | None = None,
    limit: int = 6,
) -> List[str]:
    seeds: List[str] = []
    for preference in preferences:
        seeds.extend(RESTAURANT_TYPE_HINTS_BY_STYLE.get(str(preference).strip(), []))
    seeds.extend(RESTAURANT_TYPE_HINTS_BY_COMPANION.get(str(companions).strip() or "独自", []))

    special_text = str(special_requirements or "").strip()
    for keys, codes in RESTAURANT_TYPE_HINTS_BY_SPECIAL_REQUIREMENT:
        if any(key in special_text for key in keys):
            seeds.extend(codes)

    seeds.extend(["050118", "050116", "050500", "050300"])
    return _normalize_restaurant_types(seeds, allowed_types=allowed_types, limit=limit)


def _default_keywords_for_types(types: List[str], *, limit: int = 6) -> List[str]:
    result: List[str] = []
    for code in types:
        meta = RESTAURANT_TYPE_CATALOG.get(code)
        if not meta:
            continue
        label = str(meta["label"]).strip()
        if label and label not in result:
            result.append(label)
        if len(result) >= limit:
            break
    return result


class RestaurantSelectionOutput(BaseModel):
    """餐厅选择结果 schema"""
    selected_indexes: list[int] = Field(default_factory=list)
    is_sufficient: bool = False
    reason: str = ""


def _trip_days(request: dict[str, Any]) -> int:
    """计算出行天数"""
    days = int(request.get("days", 0) or 0)
    if days > 0:
        return days
    start_date = request.get("start_date")
    end_date = request.get("end_date")
    try:
        start = datetime.strptime(str(start_date), "%Y-%m-%d").date()
        end = datetime.strptime(str(end_date), "%Y-%m-%d").date()
        return max(1, (end - start).days + 1)
    except (TypeError, ValueError):
        return 1


def _restaurant_target_counts(days: int) -> tuple[int, int]:
    """计算餐厅目标数量"""
    final_needed = max(2, max(1, days) * 2)
    candidate_target = min(MAX_CANDIDATE_POOL, final_needed + 2)
    return final_needed, candidate_target


def _infer_meal_type(keyword: str, name: str) -> str:
    """根据关键词推断餐饮类型"""
    text = f"{keyword} {name}".lower()
    if any(token in text for token in ["早餐", "早茶", "面馆", "包点"]):
        return "breakfast"
    if any(token in text for token in ["夜宵", "烧烤", "酒吧", "餐吧"]):
        return "snack"
    if any(token in text for token in ["甜品", "咖啡", "茶饮"]):
        return "snack"
    if any(token in text for token in ["晚餐", "火锅", "烤肉"]):
        return "dinner"
    return "lunch"


def _restaurant_description(*, poi: POI, keyword: str, cuisine_type: str, rating: float, price_per_person: int) -> str:
    """生成餐厅描述"""
    parts: list[str] = []
    if cuisine_type:
        parts.append(cuisine_type)
    area = str(poi.business.business_area or "").strip()
    if area:
        parts.append(area)
    if keyword and keyword not in parts:
        parts.append(keyword)
    if rating > 0:
        parts.append(f"评分{rating:.1f}")
    if price_per_person > 0:
        parts.append(f"人均约{price_per_person}元")
    return "，".join(parts[:5])


def _extract_cuisine_type(poi: POI, keyword: str) -> str:
    """提取菜系类型"""
    parts = [item.strip() for item in str(poi.type or "").split(";") if item.strip()]
    if len(parts) >= 2:
        last = parts[-1]
        generic_labels = {"中餐厅", "外国餐厅", "快餐厅", "休闲餐饮场所", "咖啡厅", "茶艺馆", "冷饮店", "糕饼店", "甜品店"}
        if last and last not in generic_labels:
            return last
    typecode = str(poi.typecode or "").strip()
    if typecode in RESTAURANT_TYPE_CATALOG:
        return str(RESTAURANT_TYPE_CATALOG[typecode]["label"])
    if parts:
        return parts[0]
    return keyword.strip()


def _is_restaurant_poi(poi: POI) -> bool:
    """判断召回 POI 是否属于餐饮。"""
    typecode = str(poi.typecode or "").strip()
    if typecode.startswith(RESTAURANT_TYPE_PREFIX):
        return True
    text = f"{poi.name or ''} {poi.type or ''}"
    return any(marker in text for marker in RESTAURANT_TEXT_MARKERS)


def _clean_poi_to_restaurant(poi: POI, *, keyword: str) -> dict[str, Any] | None:
    """将 POI 转换为餐厅字典"""
    if not _is_restaurant_poi(poi):
        return None

    location = parse_location(poi.location)
    if not location:
        return None

    photos = [p.url for p in poi.photos if p.url]
    business = poi.business
    biz_ext = poi.biz_ext
    tel = str(poi.tel or "").strip()
    open_time2 = str(biz_ext.opentime2 or business.opentime2 or "").strip()
    cuisine_type = _extract_cuisine_type(poi, keyword)
    name = str(poi.name or "").strip()
    rating = parse_float(biz_ext.rating or business.rating)
    price_per_person = parse_int(biz_ext.cost or business.cost)
    description = _restaurant_description(poi=poi, keyword=keyword, cuisine_type=cuisine_type, rating=rating, price_per_person=price_per_person)

    from app.ai.models import Restaurant
    restaurant = Restaurant(
        name=name,
        type=str(poi.type or poi.typecode or "").strip(),
        meal_type=_infer_meal_type(keyword, name),
        address=str(poi.address or "").strip(),
        location=location,
        description=description,
        keytag=keyword,
        photos=photos,
        tel=tel,
        phone=tel,
        open_time2=open_time2,
        rating=rating,
        estimated_cost=price_per_person,
        price_per_person=price_per_person,
        cuisine_type=cuisine_type,
        is_recommended=False,
        photo=photos[0] if photos else "",
    )
    if not restaurant.name:
        return None
    payload = restaurant.model_dump()
    payload["typecode"] = str(poi.typecode or "").strip()
    payload["poi_id"] = str(poi.id or "").strip()
    return payload


def _preclean_candidates_from_results(mcp_results: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    """从 MCP 搜索结果中预清洗餐厅候选"""
    candidates: list[dict[str, Any]] = []
    for item in mcp_results:
        keyword = str(item.get("keyword", "") or "").strip()
        response = item.get("result")
        if isinstance(response, POISearchResponse):
            pois = response.pois
        elif isinstance(response, dict):
            pois_data = response.get("pois", [])
            if not isinstance(pois_data, list):
                continue
            pois = [poi for p in pois_data if isinstance(p, dict) if (poi := POI.from_dict(p)) is not None]
        else:
            continue
        for poi in pois:
            restaurant = _clean_poi_to_restaurant(poi, keyword=keyword)
            if not restaurant:
                continue
            candidates.append(restaurant)
            if len(candidates) >= limit:
                return candidates
    return candidates


def _clean_candidates_from_results(mcp_results: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    """兼容旧测试入口。"""
    return _preclean_candidates_from_results(mcp_results, limit=limit)


def _compact_restaurants_for_llm(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """压缩餐厅信息用于 LLM 输入"""
    return [
        {
            "index": idx,
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "typecode": item.get("typecode", ""),
            "meal_type": item.get("meal_type", "lunch"),
            "rating": item.get("rating", 0),
            "price_per_person": item.get("price_per_person", 0),
            "cuisine_type": item.get("cuisine_type", ""),
            "description": item.get("description", ""),
            "address": item.get("address", ""),
            "has_photo": bool(item.get("photo")),
        }
        for idx, item in enumerate(items)
    ]


def _pick_by_indexes(items: list[dict[str, Any]], indexes: Any, *, limit: int) -> list[dict[str, Any]]:
    """根据索引选择餐厅"""
    selected: list[dict[str, Any]] = []
    used_indexes: set[int] = set()
    used_keys: set[tuple[str, str]] = set()
    if not isinstance(indexes, list):
        return selected
    for raw in indexes:
        try:
            idx = int(raw)
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(items) or idx in used_indexes:
            continue
        candidate = items[idx]
        key = (str(candidate.get("name", "")).strip(), str(candidate.get("address", "")).strip())
        if key in used_keys:
            continue
        selected.append(candidate)
        used_indexes.add(idx)
        used_keys.add(key)
        if len(selected) >= limit:
            break
    return selected


def _fallback_rank_restaurants(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """无 LLM 时备用排序"""
    type_priority = {"lunch": 0, "dinner": 1, "snack": 2, "breakfast": 3}
    ranked = sorted(
        items,
        key=lambda item: (
            type_priority.get(str(item.get("meal_type", "")).strip().lower(), 9),
            -float(item.get("rating", 0) or 0),
            0 if item.get("photo") else 1,
            0 if int(item.get("price_per_person", 0) or 0) > 0 else 1,
            item.get("name", ""),
        ),
    )
    deduped: list[dict[str, Any]] = []
    used_keys: set[tuple[str, str]] = set()
    for item in ranked:
        key = (str(item.get("name", "")).strip(), str(item.get("address", "")).strip())
        if key in used_keys:
            continue
        deduped.append(item)
        used_keys.add(key)
    return deduped


async def _select_restaurants_with_llm(*, request: dict[str, Any], candidates: list[dict[str, Any]], final_needed: int, candidate_target: int) -> tuple[list[dict[str, Any]], str]:
    """LLM 筛选餐厅"""
    if not candidates:
        return [], "无候选餐厅"

    context = {
        "destination": request.get("destination", ""),
        "companions": request.get("companions", ""),
        "style_preferences": request.get("style_preferences", []),
        "special_requirements": request.get("special_requirements", ""),
        "candidates": _compact_restaurants_for_llm(candidates),
    }
    prepared_candidates = _fallback_rank_restaurants(candidates)
    required = min(max(0, candidate_target), len(candidates))

    try:
        retry_instruction = ""
        last_reason = ""
        for _ in range(2):
            data = await invoke_prompt_json_async(
                prompt_id="restaurant_filter",
                variables={
                    "final_needed": final_needed,
                    "candidate_target": candidate_target,
                    "context_json": json.dumps(context, ensure_ascii=False),
                    "retry_instruction": retry_instruction,
                },
                temperature=0.7,
            )
            parsed = RestaurantSelectionOutput.model_validate(data)
            selected = _pick_by_indexes(prepared_candidates, parsed.selected_indexes, limit=required)
            last_reason = parsed.reason
            if len(selected) == required:
                return selected, parsed.reason
            retry_instruction = render_prompt(
                "selection_retry",
                {
                    "selected_count": len(selected),
                    "available_count": len(prepared_candidates),
                    "required_count": required,
                },
            )
        return prepared_candidates[:required], last_reason or "模型未按数量要求返回足够索引"
    except Exception as exc:
        logger.warning("餐厅筛选失败: %s", exc)
        return prepared_candidates[:required], "LLM调用失败"


async def restaurant_node(state: TripState) -> Dict[str, Any]:
    """餐厅 Agent 主流程"""
    started = perf_counter()
    request = state["request"]
    days = _trip_days(request)
    final_needed, candidate_target = _restaurant_target_counts(days)
    allowed_types = _normalize_restaurant_types(
        request.get("types") or state.get("mcp_search_types", ""),
        limit=len(VALID_RESTAURANT_TYPE_CODES),
    )
    types = allowed_types[:6] if allowed_types else []
    keyword_seeds = _default_keywords_for_types(types) if types else []

    logger.info("开始获取餐厅，目的地=%s，types=%s", request.get("destination", ""), types)

    keywords = build_food_keywords(request, seed_keywords=keyword_seeds, limit=6)

    tool = get_tool(RESTAURANT_TOOL_NAME)
    if not tool:
        raise RuntimeError(f"未找到工具: {RESTAURANT_TOOL_NAME}")

    destination = str(request.get("destination", "")).strip()
    base_params = {"region": destination, "citylimit": FIXED_CITY_LIMIT, "extensions": "all", "page": 1, "offset": 10}
    if types:
        base_params["types"] = "|".join(types)

    used_keywords: list[str] = []
    raw_results: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    for keyword in keywords:
        tool_args = {**base_params, "keywords": keyword}
        raw_result = await invoke_tool_with_debug(tool_name=RESTAURANT_TOOL_NAME, tool_args=tool_args, log=logger, context=f"restaurant:{destination}:{keyword}")
        raw_results.append({"tool_name": RESTAURANT_TOOL_NAME, "keyword": keyword, "tool_args": tool_args, "result": raw_result})
        used_keywords.append(keyword)
        candidates = _preclean_candidates_from_results(raw_results, limit=MAX_CANDIDATE_POOL)
        if len(candidates) >= candidate_target:
            break

    restaurants, selection_reason = await _select_restaurants_with_llm(request=request, candidates=candidates, final_needed=final_needed, candidate_target=candidate_target)

    logger.info("餐厅处理完成，used_keywords=%s，候选数量=%s，最终数量=%s total_duration_ms=%.1f", used_keywords, len(candidates), len(restaurants), (perf_counter() - started) * 1000)

    return {
        "food_query_keywords": used_keywords,
        "restaurants": restaurants,
        "streaming_updates": (
            f"\n餐厅类型: {', '.join([RESTAURANT_TYPE_CATALOG[code]['label'] for code in types if code in RESTAURANT_TYPE_CATALOG])}"
            f"\n美食关键词: {', '.join(used_keywords)}"
            f"\n餐厅候选完成: {len(candidates)}家(目标{candidate_target})"
            f"\n餐厅完成: {len(restaurants)}家(按每天约2家推荐)"
        ),
        "completed_agents": ["restaurant"],
    }
