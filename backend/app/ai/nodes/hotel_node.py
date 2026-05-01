"""酒店 Agent 流程。

负责搜索和筛选酒店候选池：
1. 基于规则生成酒店检索关键词
2. 调用地图工具搜索酒店
3. LLM 筛选和排序

图结构位置：
- 接收 orchestrator 的 Fan-out 信号
- 输出 hotel_candidates 和 hotels 到状态
- 连接到 fan_in 节点
"""

from __future__ import annotations

import json
from datetime import datetime
from math import ceil
from time import perf_counter
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_qwq import ChatQwen
from pydantic import BaseModel, Field

from app.config import get_logger, settings
from app.ai.models.graph_models import TripState
from app.ai.utils import parse_float, parse_location, build_hotel_keywords
from app.services.amap import POI, POISearchResponse
from app.ai.mcp.client import get_tool, invoke_tool_with_debug

logger = get_logger("HotelService")

# ══════════════════════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════════════════════
HOTEL_TOOL_NAME = "maps_text_search"
MAX_CANDIDATE_POOL = 16
FIXED_CITY_LIMIT = True
STRICT_HIGH_END_EXCLUDE = ("旅馆", "客栈", "招待所", "青年旅舍", "青旅", "民宿")
HIGH_END_POSITIVE = ("酒店", "大酒店", "高档型", "豪华", "高端", "星级", "度假", "国际")
HOTEL_TYPE_PREFIX = "10"
HOTEL_TEXT_MARKERS = ("住宿服务", "宾馆", "酒店", "旅馆", "客栈", "民宿", "招待所", "青年旅舍", "青旅", "hostel")

# 高德 POI 类型代码参考（住宿服务）
HOTEL_TYPE_CATALOG: dict[str, dict[str, list[str] | str]] = {
    "100000": {"label": "住宿服务", "aliases": ["住宿服务相关", "住宿服务", "酒店", "住宿"]},
    "100100": {"label": "宾馆酒店", "aliases": ["宾馆酒店", "酒店", "宾馆"]},
    "100101": {"label": "奢华酒店", "aliases": ["奢华酒店", "豪华酒店", "高端酒店", "度假酒店"]},
    "100102": {"label": "五星级宾馆", "aliases": ["五星级宾馆", "五星酒店", "五星级酒店", "五星宾馆"]},
    "100103": {"label": "四星级宾馆", "aliases": ["四星级宾馆", "四星酒店", "四星级酒店", "四星宾馆"]},
    "100104": {"label": "三星级宾馆", "aliases": ["三星级宾馆", "三星酒店", "三星级酒店", "三星宾馆"]},
    "100105": {"label": "经济型连锁酒店", "aliases": ["经济型连锁酒店", "经济型酒店", "快捷酒店", "连锁酒店"]},
    "100200": {"label": "旅馆招待所", "aliases": ["旅馆招待所", "旅馆", "招待所", "客栈", "民宿"]},
    "100201": {"label": "青年旅舍", "aliases": ["青年旅舍", "青旅", "hostel"]},
}

HOTEL_TYPE_HINTS_BY_LEVEL: dict[str, list[str]] = {
    "经济型": ["100105", "100200", "100201"],
    "舒适型": ["100100", "100104", "100105"],
    "高档型": ["100100", "100103", "100102", "100101"],
    "豪华型": ["100101", "100102"],
}

HOTEL_TYPE_HINTS_BY_COMPANION: dict[str, list[str]] = {
    "家庭": ["100100", "100101", "100103"],
    "情侣": ["100101", "100102", "100100"],
    "朋友": ["100100", "100104", "100105"],
    "老人": ["100100", "100103", "100104"],
    "独自": ["100100", "100105", "100201"],
}

HOTEL_TYPE_HINTS_BY_SPECIAL_REQUIREMENT: list[tuple[list[str], list[str]]] = [
    (["豪华", "高端", "度假"], ["100101", "100102"]),
    (["经济", "性价比", "便宜"], ["100105", "100200"]),
    (["青旅", "青年"], ["100201"]),
    (["亲子", "家庭房"], ["100100", "100101"]),
    (["安静", "景观"], ["100101", "100103"]),
]

VALID_HOTEL_TYPE_CODES = set(HOTEL_TYPE_CATALOG.keys())

HOTEL_TYPE_ALIAS_TO_CODE: dict[str, str] = {}
for _code, _meta in HOTEL_TYPE_CATALOG.items():
    _aliases = [_code, str(_meta["label"])] + [str(item) for item in _meta.get("aliases", [])]
    for _alias in _aliases:
        text = str(_alias).strip()
        if text:
            HOTEL_TYPE_ALIAS_TO_CODE[text] = _code
            HOTEL_TYPE_ALIAS_TO_CODE[text.replace(" ", "")] = _code


def _split_search_values(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    normalized = value.replace("，", "|").replace(",", "|").replace(";", "|").replace("；", "|")
    return [item.strip() for item in normalized.split("|") if item.strip()]


def _normalize_hotel_types(
    raw_types: List[str] | str | None,
    *,
    keywords: List[str] | None = None,
    allowed_types: List[str] | None = None,
    limit: int = 4,
) -> List[str]:
    allowed = set(allowed_types or [])
    result: List[str] = []

    def add_candidate(value: str) -> None:
        text = str(value or "").strip()
        if not text:
            return
        if text in VALID_HOTEL_TYPE_CODES:
            code = text
        else:
            code = HOTEL_TYPE_ALIAS_TO_CODE.get(text) or HOTEL_TYPE_ALIAS_TO_CODE.get(text.replace(" ", ""))
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


def _default_hotel_types(
    *,
    hotel_level: str,
    companions: str,
    special_requirements: str,
    allowed_types: List[str] | None = None,
    limit: int = 4,
) -> List[str]:
    seeds: List[str] = []
    seeds.extend(HOTEL_TYPE_HINTS_BY_LEVEL.get(str(hotel_level).strip(), HOTEL_TYPE_HINTS_BY_LEVEL["舒适型"]))
    seeds.extend(HOTEL_TYPE_HINTS_BY_COMPANION.get(str(companions).strip() or "独自", []))

    special_text = str(special_requirements or "").strip()
    for keys, codes in HOTEL_TYPE_HINTS_BY_SPECIAL_REQUIREMENT:
        if any(key in special_text for key in keys):
            seeds.extend(codes)

    seeds.extend(["100100", "100105", "100101"])
    return _normalize_hotel_types(seeds, allowed_types=allowed_types, limit=limit)


class HotelSelectionOutput(BaseModel):
    """酒店选择结果 schema"""
    selected_indexes: list[int] = Field(default_factory=list)
    is_sufficient: bool = False
    reason: str = ""


PROMPT_FILTER = """你是酒店筛选与住宿档次校验助手。请严格按用户的住宿档次要求筛选。

最终入住酒店数：{final_needed}
候选池目标数：{candidate_target}
用户要求档次：{hotel_level}
价格区间参考：{price_range}

规则：
1. 只返回索引，不要重写字段。
2. 酒店按约每 2 天 1 家来规划，优先保留位置互补、评分更高、图片更完整的候选。
3. 去掉明显重复的酒店。
4. 必须严格匹配住宿档次：
   - 如果用户要"高档型"或"豪华型"，不要选择旅馆、客栈、招待所、青年旅舍、民宿这类低档住宿。
   - 如果名称、类型、描述明显和用户档次冲突，直接排除。
5. 优先保留符合住宿档次、价格区间、交通便利性和用户偏好的候选。
6. 对于高档型/豪华型，优先星级酒店、品牌酒店、度假酒店、高端酒店；低档住宿即便评分高也不要保留。
7. 如果可用候选数不少于目标数量，你必须返回恰好 {candidate_target} 个不重复索引。
8. 如果可用候选数少于目标数量，你必须返回全部可用索引，并将 is_sufficient 设为 false。

只返回 JSON：
{{
  "selected_indexes": [0, 2, 5],
  "is_sufficient": true,
  "reason": "一句话说明"
}}
"""

_json_llm = ChatQwen(
    model="qwen3.5-flash-2026-02-23",
    api_key=settings.DASHSCOPE_API_KEY,
    base_url=settings.DASHSCOPE_BASE_URL,
    temperature=0.7,
    extra_body={"enable_thinking": False},
    model_kwargs={"response_format": {"type": "json_object"}},
)


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


def _hotel_target_counts(days: int) -> tuple[int, int]:
    """计算酒店目标数量：最终需要数量和候选池目标"""
    final_needed = max(1, ceil(max(1, days) / 2))
    candidate_target = min(MAX_CANDIDATE_POOL, max(4, final_needed + 4))
    return final_needed, candidate_target


def _default_keywords_for_types(types: List[str], *, limit: int = 4) -> List[str]:
    keywords: List[str] = []
    for code in types:
        meta = HOTEL_TYPE_CATALOG.get(code)
        if not meta:
            continue
        label = str(meta["label"]).strip()
        if label and label not in keywords:
            keywords.append(label)
        if len(keywords) >= limit:
            break
    return keywords


def _hotel_description(*, poi: POI, hotel_level: str, keyword: str, rating: float, price: float) -> str:
    """生成酒店描述"""
    parts: list[str] = []
    if hotel_level:
        parts.append(hotel_level)
    area = str(poi.business.business_area or "").strip()
    if area:
        parts.append(area)
    primary_type = HOTEL_TYPE_CATALOG.get(str(poi.typecode or "").strip(), {}).get("label", "")
    if not primary_type:
        type_parts = [item.strip() for item in str(poi.type or "").split(";") if item.strip()]
        primary_type = type_parts[-1] if type_parts else ""
    if primary_type:
        parts.append(str(primary_type))
    if keyword and keyword not in parts:
        parts.append(keyword)
    if rating > 0:
        parts.append(f"评分{rating:.1f}")
    if price > 0:
        parts.append(f"约{round(price)}元/晚")
    return "，".join(parts[:5])


def _is_hotel_poi(poi: POI) -> bool:
    """判断召回 POI 是否属于住宿。"""
    typecode = str(poi.typecode or "").strip()
    if typecode.startswith(HOTEL_TYPE_PREFIX):
        return True
    text = f"{poi.name or ''} {poi.type or ''}".lower()
    return any(marker.lower() in text for marker in HOTEL_TEXT_MARKERS)


def _hotel_level_matches(*, poi: POI, hotel_level: str, price: float) -> bool:
    """判断酒店是否符合档次要求"""
    text = f"{poi.name} {poi.type} {poi.typecode}".strip()
    level = str(hotel_level or "").strip()
    if level in {"高档型", "豪华型"}:
        if any(word in text for word in STRICT_HIGH_END_EXCLUDE):
            return False
        if price > 0 and level == "豪华型" and price < 600:
            return False
        if price > 0 and level == "高档型" and price < 350:
            return False
    if level == "豪华型":
        if price <= 0:
            return any(word in text for word in ("豪华", "五星", "国际", "度假", "高端"))
        return price >= 600 or any(word in text for word in ("豪华", "五星", "国际", "度假", "高端"))
    if level == "高档型":
        if price <= 0:
            return any(word in text for word in HIGH_END_POSITIVE)
        return price >= 350 or any(word in text for word in HIGH_END_POSITIVE)
    return True


def _clean_poi_to_hotel(poi: POI, *, hotel_level: str, days: int, keyword: str) -> dict[str, Any] | None:
    """将 POI 转换为酒店字典"""
    if not _is_hotel_poi(poi):
        return None

    business = poi.business
    biz_ext = poi.biz_ext
    location = parse_location(poi.location)
    photos = [p.url for p in poi.photos if p.url]
    tel = str(poi.tel or "").strip()
    open_time2 = str(biz_ext.opentime2 or business.opentime2 or "").strip()
    price = parse_float(biz_ext.cost or business.cost)
    rating = parse_float(biz_ext.rating or business.rating)
    if not _hotel_level_matches(poi=poi, hotel_level=hotel_level, price=price):
        return None
    description = _hotel_description(poi=poi, hotel_level=hotel_level, keyword=keyword, rating=rating, price=price)

    from app.ai.models import Hotel
    hotel = Hotel(
        name=str(poi.name or "").strip(),
        address=str(poi.address or "").strip(),
        location=location,
        description=description,
        keytag=str(poi.type or "").strip(),
        type=str(poi.type or poi.typecode or "").strip(),
        photos=photos,
        tel=tel,
        phone=tel,
        open_time2=open_time2,
        rating=rating,
        hotel_level=hotel_level,
        price_per_night=price,
        total_price=round(price * days, 2) if price > 0 else 0,
        distance_to_center=str(business.business_area or "").strip(),
        distance=str(poi.distance or "").strip(),
        amenities=[item.strip() for item in str(poi.type or "").split(";") if item.strip()][1:5],
        photo=photos[0] if photos else "",
        image_url=photos[0] if photos else "",
    )
    if not hotel.name:
        return None
    payload = hotel.model_dump()
    payload["typecode"] = str(poi.typecode or "").strip()
    payload["poi_id"] = str(poi.id or "").strip()
    return payload


def _preclean_candidates_from_results(mcp_results: list[dict[str, Any]], *, hotel_level: str, days: int, limit: int) -> list[dict[str, Any]]:
    """从 MCP 搜索结果中预清洗酒店候选"""
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
            hotel = _clean_poi_to_hotel(poi, hotel_level=hotel_level, days=days, keyword=keyword)
            if not hotel:
                continue
            candidates.append(hotel)
            if len(candidates) >= limit:
                return candidates
    return candidates


def _clean_candidates_from_results(mcp_results: list[dict[str, Any]], *, hotel_level: str, days: int, limit: int) -> list[dict[str, Any]]:
    """兼容旧测试入口。"""
    return _preclean_candidates_from_results(mcp_results, hotel_level=hotel_level, days=days, limit=limit)


def _compact_hotels_for_llm(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """压缩酒店信息用于 LLM 输入"""
    return [
        {
            "index": idx,
            "name": item.get("name", ""),
            "address": item.get("address", ""),
            "rating": item.get("rating", 0),
            "hotel_level": item.get("hotel_level", ""),
            "price_per_night": item.get("price_per_night", 0),
            "distance_to_center": item.get("distance_to_center", ""),
            "description": item.get("description", ""),
            "type": item.get("type", ""),
            "typecode": item.get("typecode", ""),
            "has_photo": bool(item.get("image_url") or item.get("photo")),
            "has_location": bool(item.get("location")),
        }
        for idx, item in enumerate(items)
    ]


def _pick_hotels_by_indexes(items: list[dict[str, Any]], indexes: Any, *, limit: int) -> list[dict[str, Any]]:
    """根据索引选择酒店"""
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
        try:
            from app.ai.models import Hotel
            selected.append(Hotel.model_validate(candidate).model_dump())
        except Exception:
            continue
        used_indexes.add(idx)
        used_keys.add(key)
        if len(selected) >= limit:
            break
    return selected


def _fallback_rank_hotels(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """无 LLM 时备用排序"""
    ranked = sorted(
        items,
        key=lambda item: (
            -float(item.get("rating", 0) or 0),
            0 if item.get("image_url") or item.get("photo") else 1,
            0 if float(item.get("price_per_night", 0) or 0) > 0 else 1,
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


async def _select_hotel_candidates_with_llm(
    *, request: dict[str, Any], candidates: list[dict[str, Any]], final_needed: int, candidate_target: int, price_range: str
) -> tuple[list[dict[str, Any]], str]:
    """LLM 筛选酒店候选"""
    if not candidates:
        return [], "无候选酒店"

    prompt = PROMPT_FILTER.format(
        final_needed=final_needed,
        candidate_target=candidate_target,
        hotel_level=request.get("hotel_level", "舒适型"),
        price_range=price_range,
    )
    context = {
        "destination": request.get("destination", ""),
        "companions": request.get("companions", ""),
        "style_preferences": request.get("style_preferences", []),
        "special_requirements": request.get("special_requirements", ""),
        "hotel_level": request.get("hotel_level", "舒适型"),
        "candidates": _compact_hotels_for_llm(candidates),
    }
    prepared_candidates = _fallback_rank_hotels(candidates)
    required = min(max(0, candidate_target), len(candidates))

    try:
        feedback = ""
        last_reason = ""
        for _ in range(2):
            messages = [
                SystemMessage(content=prompt),
                HumanMessage(content=json.dumps(context, ensure_ascii=False)),
            ]
            if feedback:
                messages.append(HumanMessage(content=feedback))
            response = await _json_llm.ainvoke(messages)
            data = json.loads(response.content)
            parsed = HotelSelectionOutput.model_validate(data)
            selected = _pick_hotels_by_indexes(prepared_candidates, parsed.selected_indexes, limit=required)
            last_reason = parsed.reason
            if len(selected) == required:
                return selected, parsed.reason
            feedback = (
                f"你上一次只返回了 {len(selected)} 个有效索引，但当前可用候选有 {len(prepared_candidates)} 个，"
                f"目标数量是 {required}。请严格重新选择足够数量。"
            )
        return prepared_candidates[:required], last_reason or "模型未按数量要求返回足够索引"
    except Exception as exc:
        logger.warning("酒店候选筛选失败: %s", exc)
        return prepared_candidates[:required], "LLM调用失败"


async def _collect_mcp_results(
    *,
    tool_name: str,
    request: dict[str, Any],
    keywords: list[str],
    target_candidates: int,
    hotel_level: str,
    days: int,
    types: list[str],
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """调用 MCP 工具收集酒店结果"""
    started = perf_counter()
    tool = get_tool(tool_name)
    if tool is None:
        raise RuntimeError(f"未找到酒店搜索工具: {tool_name}")

    destination = str(request.get("destination", "")).strip()
    types_str = "|".join(types)
    base_params = {
        "region": destination,
        "citylimit": FIXED_CITY_LIMIT,
        "extensions": "all",
        "page": 1,
        "offset": 10,
    }
    if types_str:
        base_params["types"] = types_str

    used_keywords: list[str] = []
    raw_results: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    for keyword in keywords:
        keyword_started = perf_counter()
        tool_args = {**base_params, "keywords": keyword}
        raw_result = await invoke_tool_with_debug(
            tool_name=tool_name,
            tool_args=tool_args,
            log=logger,
            context=f"hotel:{destination}:{keyword}",
        )
        raw_results.append({"tool_name": tool_name, "keyword": keyword, "tool_args": tool_args, "result": raw_result})
        used_keywords.append(keyword)
        candidates = _preclean_candidates_from_results(raw_results, hotel_level=hotel_level, days=days, limit=MAX_CANDIDATE_POOL)
        logger.info(
            "酒店候选预清洗 keyword=%s current_candidates=%s target=%s",
            keyword, len(candidates), target_candidates,
        )
        if len(candidates) >= target_candidates:
            break

    return used_keywords, raw_results, candidates


async def hotel_node(state: TripState) -> Dict[str, Any]:
    """酒店 Agent 主流程"""
    started = perf_counter()
    request = state["request"]
    hotel_level = str(state.get("hotel_level", request.get("hotel_level", "舒适型"))).strip() or "舒适型"
    price_range = str(state.get("hotel_price_range", "300,800")).strip() or "300,800"
    default_keyword = f"{hotel_level}酒店"
    days = _trip_days(request)
    final_needed, candidate_target = _hotel_target_counts(days)
    allowed_types = _normalize_hotel_types(
        request.get("types") or state.get("mcp_search_types", ""),
        limit=len(VALID_HOTEL_TYPE_CODES),
    )
    types = allowed_types[:4] if allowed_types else []
    keyword_seeds = _default_keywords_for_types(types) if types else []

    logger.info(
        "开始获取酒店，目的地=%s，酒店档次=%s，价格区间=%s，types=%s",
        request.get("destination", ""), hotel_level, price_range, types,
    )

    keywords = build_hotel_keywords(
        request,
        hotel_level=hotel_level,
        price_range=price_range,
        seed_keywords=keyword_seeds,
        limit=4,
    )
    target_raw_candidates = min(MAX_CANDIDATE_POOL, candidate_target + 4)

    used_keywords, mcp_results, precleaned_candidates = await _collect_mcp_results(
        tool_name=HOTEL_TOOL_NAME,
        request=request,
        keywords=keywords,
        target_candidates=target_raw_candidates,
        hotel_level=hotel_level,
        days=days,
        types=types,
    )
    hotel_candidates, selection_reason = await _select_hotel_candidates_with_llm(
        request=request, candidates=precleaned_candidates, final_needed=final_needed, candidate_target=candidate_target, price_range=price_range,
    )
    hotels = hotel_candidates

    logger.info(
        "酒店处理完成，used_keywords=%s，预清洗数量=%s，候选数量=%s，保留数量=%s total_duration_ms=%.1f",
        used_keywords, len(precleaned_candidates), len(hotel_candidates), len(hotels), (perf_counter() - started) * 1000,
    )

    return {
        "hotel_query_keyword": used_keywords[0] if used_keywords else default_keyword,
        "hotel_candidates": hotel_candidates,
        "hotels": hotels,
        "streaming_updates": (
            f"\n酒店类型: {', '.join([HOTEL_TYPE_CATALOG[code]['label'] for code in types if code in HOTEL_TYPE_CATALOG])}"
            f"\n酒店关键词: {', '.join(used_keywords)}"
            f"\n酒店候选完成: {len(hotel_candidates)}家(目标{candidate_target})"
            f"\n酒店初筛完成: {len(hotels)}家(供后续按区域择优分配)"
        ),
        "completed_agents": ["hotel"],
    }
