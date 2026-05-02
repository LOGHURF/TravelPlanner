"""景点 Agent - 宽关键词候选召回

使用类目/场景级关键词召回 POI 候选，避免在召回阶段让 LLM 直接点名具体景点。
具体取舍交给 reviewer 节点完成。

图结构位置：
- 接收 orchestrator 的 Fan-out 信号
- 输出 attraction_candidates 和 attractions 到状态
- 连接到 fan_in 节点
"""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Dict, List

from app.config import get_logger
from app.ai.errors import NoCandidatesError, ToolInvocationError
from app.ai.models.graph_models import TripState
from app.ai.models.travel_models import Attraction
from app.ai.utils import build_attraction_keywords, parse_float, parse_location
from app.ai.mcp.client import get_tool
from app.services.amap import POISearchResponse, POI

logger = get_logger("AttractionService")

# ══════════════════════════════════════════════════════════════
# 配置常量
# ══════════════════════════════════════════════════════════════
TOOL_NAME = "maps_text_search"
HOTSPOT_RECALL_KEYWORDS = ["热门景点", "旅游景点"]
PREFERENCE_RECALL_KEYWORD_COUNT = 2

EXCLUDED_ATTRACTION_TYPE_PREFIXES = ("05", "09", "10", "12", "13", "15", "16", "17")
EXCLUDED_ATTRACTION_TYPE_TEXT = (
    "餐饮服务",
    "住宿服务",
    "医疗保健服务",
    "商务住宅",
    "政府机构及社会团体",
    "交通设施服务",
    "金融保险服务",
    "公司企业",
)


def _uniq_text(values: List[str], limit: int) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _split_search_values(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    normalized = value.replace("，", "|").replace(",", "|").replace(";", "|").replace("；", "|")
    return [item.strip() for item in normalized.split("|") if item.strip()]


def _normalize_attraction_types(
    raw_types: List[str] | str | None,
    *,
    limit: int = 4,
) -> List[str]:
    result: List[str] = []
    invalid: List[str] = []

    for item in _split_search_values(raw_types):
        text = str(item or "").strip()
        if not text:
            continue
        if not (text.isdigit() and len(text) == 6):
            invalid.append(text)
            continue
        if text not in result:
            result.append(text)
        if len(result) >= limit:
            break

    if invalid:
        raise ValueError(f"invalid attraction typecode: {invalid}")
    return result


# ══════════════════════════════════════════════════════════════
# 搜索词规划
# ══════════════════════════════════════════════════════════════


def _build_recall_keywords(request: dict[str, Any]) -> list[str]:
    preference_keywords = build_attraction_keywords(
        request,
        limit=PREFERENCE_RECALL_KEYWORD_COUNT,
    )
    return _uniq_text(
        HOTSPOT_RECALL_KEYWORDS + preference_keywords[:PREFERENCE_RECALL_KEYWORD_COUNT],
        limit=len(HOTSPOT_RECALL_KEYWORDS) + PREFERENCE_RECALL_KEYWORD_COUNT,
    )


# ══════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════


def _clean_poi_to_attraction(poi: POI) -> dict[str, Any] | None:
    """将高德 POI 数据清洗为景点字典。"""
    if not poi.name:
        return None

    typecode = str(poi.typecode or "").strip()
    type_text = str(poi.type or "").strip()
    if _is_obviously_non_attraction_poi(typecode=typecode, type_text=type_text):
        return None

    photos = [item.url for item in poi.photos if item.url]
    rating = parse_float(poi.business.rating or poi.biz_ext.rating)
    location = parse_location(poi.location)

    attraction = Attraction(
        name=str(poi.name).strip(),
        address=str(poi.address or "").strip(),
        location=location,
        description=str(poi.type or "").strip(),
        keytag=str(poi.type or "").strip(),
        type=str(poi.type or poi.typecode or "").strip(),
        photos=photos,
        tel=str(poi.tel or "").strip(),
        rating=rating,
        category=str(poi.type or "").split(";")[0].strip(),
        indoor=bool(poi.indoor),
        open_time2=str(poi.biz_ext.opentime2 or poi.business.opentime2 or "").strip(),
        phone=str(poi.tel or "").strip(),
        photo=photos[0] if photos else "",
    )
    payload = attraction.model_dump()
    payload["typecode"] = str(poi.typecode or "").strip()
    return payload


def _is_obviously_non_attraction_poi(*, typecode: str, type_text: str) -> bool:
    """排除住宿、餐饮、交通等明显非行程景点的 POI。"""
    code = str(typecode or "").strip()
    if code.startswith(EXCLUDED_ATTRACTION_TYPE_PREFIXES):
        return True

    text = str(type_text or "").strip()
    return any(marker in text for marker in EXCLUDED_ATTRACTION_TYPE_TEXT)


def _dedupe_attractions(items: List[dict[str, Any]]) -> list[dict[str, Any]]:
    """按搜索返回顺序去重。"""
    deduped = []
    seen_names: set[str] = set()
    for item in items:
        name = str(item.get("name", "")).strip().lower()
        normalized = name.replace(" ", "").replace("旅游景区", "").replace("风景区", "").replace("景区", "")
        if normalized in seen_names:
            continue
        seen_names.add(normalized)
        deduped.append(item)

    return deduped


def _interleave_keyword_results(groups: List[List[dict[str, Any]]]) -> list[dict[str, Any]]:
    interleaved: list[dict[str, Any]] = []
    max_size = max((len(group) for group in groups), default=0)
    for index in range(max_size):
        for group in groups:
            if index < len(group):
                interleaved.append(group[index])
    return interleaved


# ══════════════════════════════════════════════════════════════
# MCP 调用
# ══════════════════════════════════════════════════════════════


async def _search_pois(
    tool,
    region: str,
    keywords: List[str],
    types: List[str],
    page: int = 1,
) -> List[dict[str, Any]]:
    """调用 MCP 工具搜索景点，返回清洗后的列表。"""
    search_keywords = _uniq_text([k.strip() for k in keywords if k.strip()], limit=8)
    if not search_keywords:
        raise ValueError("attraction search requires keywords")
    types_str = "|".join([t.strip() for t in types if t.strip()]) if types else ""
    keyword_groups: list[list[dict[str, Any]]] = []

    for keyword in search_keywords:
        args: dict[str, Any] = {
            "keywords": keyword,
            "region": region,
            "citylimit": True,
            "page": page,
            "offset": 20,
        }
        if types_str:
            args["types"] = types_str

        try:
            result = await tool.ainvoke(args)
        except Exception as exc:
            raise ToolInvocationError(f"maps_text_search failed: keywords={keyword} types={types_str}") from exc

        response: POISearchResponse
        if isinstance(result, list) and result:
            first = result[0]
            if isinstance(first, dict) and "text" in first:
                text_content = first.get("text", "")
                if isinstance(text_content, str):
                    try:
                        data = json.loads(text_content)
                    except json.JSONDecodeError as exc:
                        raise ToolInvocationError("maps_text_search returned invalid JSON text") from exc
                    response = POISearchResponse.model_validate(data)
                elif isinstance(text_content, dict):
                    response = POISearchResponse.model_validate(text_content)
                else:
                    raise ToolInvocationError("maps_text_search returned unsupported text content")
            elif isinstance(result, POISearchResponse):
                response = result
            else:
                raise ToolInvocationError(f"maps_text_search returned unsupported list payload: {type(first)}")
        elif isinstance(result, POISearchResponse):
            response = result
        else:
            raise ToolInvocationError(f"maps_text_search returned unsupported payload: {type(result)}")

        keyword_groups.append([a for p in (response.pois or []) if (a := _clean_poi_to_attraction(p))])

    return _interleave_keyword_results(keyword_groups)


async def attraction_node(state: TripState) -> Dict[str, Any]:
    """景点 Agent 主流程：使用宽关键词做候选召回。

    流程：
    1. 根据目的地、偏好和同行人群生成类目/场景级召回关键词
    2. 调用 MCP 工具搜索候选 POI
    3. 候选足够即结束，后续 reviewer 再做筛选

    Args:
        state: LangGraph 全局状态

    Returns:
        更新状态，包含 attraction_candidates、attractions、streaming_updates、completed_agents
    """
    started = perf_counter()
    logger.info("景点搜索开始 [宽召回模式]")

    request = state["request"]
    destination = str(request.get("destination", "") or "").strip()
    if not destination:
        raise ValueError("destination is required for attraction search")

    needed_raw = state.get("needed_attractions")
    if needed_raw is None:
        raise ValueError("needed_attractions is required for attraction search")
    needed = int(needed_raw)
    if needed <= 0:
        raise ValueError("needed_attractions must be greater than 0")

    preferences = state.get("style_preferences", [])
    special_requirements = str(request.get("special_requirements", "") or "").strip()
    allowed_types = _normalize_attraction_types(
        request.get("types") or state.get("mcp_search_types", ""),
        limit=8,
    )

    tool = get_tool(TOOL_NAME)
    if not tool:
        raise RuntimeError(f"未找到工具: {TOOL_NAME}")

    pool: List[dict] = list(state.get("attraction_candidates", []))
    search_rounds = 0

    keyword_request = {
        **request,
        "style_preferences": preferences,
        "special_requirements": special_requirements,
    }
    recall_keywords = _build_recall_keywords(keyword_request)
    recall_types = allowed_types
    logger.info("recall keywords=%s types=%s", recall_keywords, recall_types)
    used_keywords: list[str] = []

    if len(pool) < needed:
        search_rounds += 1
        logger.info(
            "recall search round=%d pool=%d needed=%d keywords=%s types=%s",
            search_rounds,
            len(pool),
            needed,
            recall_keywords,
            recall_types,
        )

        types_str = "|".join(recall_types)
        keywords_str = "|".join([k.strip() for k in recall_keywords if k.strip()])

        new_items = await _search_pois(
            tool,
            destination,
            keywords=recall_keywords,
            types=recall_types,
        )
        logger.info("搜索完成: types=%s keywords=%s new_items=%d", types_str, keywords_str, len(new_items))
        used_keywords.extend(recall_keywords)

        if new_items:
            all_items = pool + new_items
            pool = _dedupe_attractions(all_items)[:needed + 4]
            logger.info("候选池更新: pool=%d", len(pool))

    # ══════════════════════════════════════════════════════════
    # 输出结果
    # ══════════════════════════════════════════════════════════
    final = pool[:needed]
    if len(final) < needed:
        raise NoCandidatesError(f"景点候选不足: got={len(final)} needed={needed}")
    logger.info(
        "景点搜索完成: %d 个景点 duration_ms=%.1f search_rounds=%d",
        len(final),
        (perf_counter() - started) * 1000,
        search_rounds,
    )

    return {
        "attraction_candidates": pool,
        "attractions": final,
        "attraction_query_keywords": used_keywords,
        "streaming_updates": f"\n景点完成: {len(final)}个",
        "completed_agents": ["attraction"],
    }
