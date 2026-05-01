"""景点 Agent - ReAct 模式搜索

采用 ReAct (Reasoning + Acting + Observing) 模式：
1. Think: LLM 分析当前候选池是否足够，决定搜索策略
2. Act: 调用 MCP 工具搜索景点（优先用自然关键词，types 只作为显式精确过滤）
3. Observe: 观察结果，清洗并加入候选池

循环直到候选足够或达到最大迭代次数。

图结构位置：
- 接收 orchestrator 的 Fan-out 信号
- 输出 attraction_candidates 和 attractions 到状态
- 连接到 fan_in 节点
"""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_qwq import ChatQwen
from pydantic import BaseModel, Field

from app.config import get_logger, settings
from app.ai.errors import LLMJsonError, NoCandidatesError, ToolInvocationError
from app.ai.models.graph_models import TripState
from app.ai.models.travel_models import Attraction
from app.ai.utils import parse_float, parse_location
from app.ai.mcp.client import get_tool
from app.services.amap import POISearchResponse, POI

logger = get_logger("AttractionService")

# ══════════════════════════════════════════════════════════════
# 配置常量
# ══════════════════════════════════════════════════════════════
TOOL_NAME = "maps_text_search"
MAX_ITERATIONS = 5  # 最多迭代次数

# 高德 POI 风景名胜类型代码参考。只作为可选精确过滤器，不作为景点合法性的全集。
ATTRACTION_TYPE_CATALOG: dict[str, dict[str, list[str] | str]] = {
    "110000": {"label": "旅游景点", "aliases": ["风景名胜相关", "旅游景点", "景点", "景区"]},
    "110100": {"label": "公园广场", "aliases": ["公园广场"]},
    "110101": {"label": "公园", "aliases": ["公园", "城市公园", "湿地公园", "森林公园"]},
    "110102": {"label": "动物园", "aliases": ["动物园", "野生动物园"]},
    "110103": {"label": "植物园", "aliases": ["植物园", "花园", "花海"]},
    "110104": {"label": "水族馆", "aliases": ["水族馆", "海洋馆"]},
    "110105": {"label": "城市广场", "aliases": ["城市广场", "广场"]},
    "110106": {"label": "公园内部设施", "aliases": ["公园内部设施"]},
    "110200": {"label": "风景名胜", "aliases": ["风景名胜", "风景区", "景区", "风景名胜区"]},
    "110201": {"label": "世界遗产", "aliases": ["世界遗产", "文化遗产", "遗产地"]},
    "110202": {"label": "国家级景点", "aliases": ["国家级景点", "5a景区", "5A景区", "4a景区", "4A景区", "国家景区"]},
    "110203": {"label": "省级景点", "aliases": ["省级景点", "省级景区"]},
    "110204": {"label": "纪念馆", "aliases": ["纪念馆", "故居", "陈列馆"]},
    "110205": {"label": "寺庙道观", "aliases": ["寺庙道观", "寺庙", "古寺", "道观"]},
    "110206": {"label": "教堂", "aliases": ["教堂", "天主教堂"]},
    "110207": {"label": "回教寺", "aliases": ["回教寺", "清真寺"]},
    "110208": {"label": "海滩", "aliases": ["海滩", "沙滩", "海边"]},
    "110209": {"label": "观景点", "aliases": ["观景点", "观景台", "夜景", "地标", "景观点"]},
    "110210": {"label": "红色景区", "aliases": ["红色景区", "红色旅游", "革命纪念地"]},
}

VALID_ATTRACTION_TYPE_CODES = set(ATTRACTION_TYPE_CATALOG.keys())
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

ATTRACTION_TYPE_ALIAS_TO_CODE: dict[str, str] = {}
for _code, _meta in ATTRACTION_TYPE_CATALOG.items():
    _aliases = [_code, str(_meta["label"])] + [str(item) for item in _meta.get("aliases", [])]
    for _alias in _aliases:
        text = str(_alias).strip()
        if text:
            ATTRACTION_TYPE_ALIAS_TO_CODE[text] = _code
            ATTRACTION_TYPE_ALIAS_TO_CODE[text.replace(" ", "")] = _code


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
        code = None
        if text in VALID_ATTRACTION_TYPE_CODES:
            code = text
        else:
            code = ATTRACTION_TYPE_ALIAS_TO_CODE.get(text) or ATTRACTION_TYPE_ALIAS_TO_CODE.get(text.replace(" ", ""))
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


def _format_attraction_type_catalog() -> str:
    return "\n".join(
        f"- {code}: {meta['label']}"
        for code, meta in ATTRACTION_TYPE_CATALOG.items()
    )


ATTRACTION_TYPE_CATALOG_TEXT = _format_attraction_type_catalog()


# ══════════════════════════════════════════════════════════════
# Schema 定义
# ══════════════════════════════════════════════════════════════


class ActResult(BaseModel):
    """LLM ReAct 思考结果"""
    thought: str  # 思考过程
    action: str = Field(default="search")  # "search" 或 "finish"
    reason: str  # 判断理由
    keywords: List[str] = Field(default_factory=list)  # 搜索关键词列表
    types: List[str] = Field(default_factory=list)  # 高德类型代码列表


# ══════════════════════════════════════════════════════════════
# 提示词 - ReAct Agent 模式
# ══════════════════════════════════════════════════════════════
PROMPT_REACT = """## 角色：景点搜索 Agent（ReAct 模式）

你是一个景点搜索助手。你的任务是为用户找到适合的景点。

## 任务信息
- 目的地：{destination}
- 用户偏好类型：{preferences}
- 同行人群：{companions}
- 特殊要求：{special_requirements}
- 目标数量：{needed} 个景点

## 可选的高德风景名胜 types 参考
{type_catalog}

## 指定类型限制
{allowed_types}

## 搜索历史
{history}

## 已搜索过的查询
{searched_queries}

## 当前候选景点
{current_pool}

## 你的决策

分析已有候选和搜索历史，决定下一步行动：

### 决策规则
1. 不要只按数量判断结束；只有候选数量达到目标，且能覆盖用户偏好、城市代表性和体验多样性时，才输出 "finish"
2. 如果候选同质、只有泛景区、缺少用户偏好的主题，或搜索历史还没有覆盖关键方向，需要继续搜索
3. **keywords**: 生成 2-4 个彼此独立的自然搜索词；系统会分别搜索每个关键词，不要把多个意图塞进一个词里
4. 关键词可以是具体 POI、街区、主题、场馆、本地表达或用户原话；优先让关键词表达真实意图，不要被上面的 types 参考限制
5. **types 是可选精确过滤器**：只有你明确知道某个高德代码与本次搜索完全吻合时才填写；没有把握时返回空数组
6. 不要为了匹配关键词硬凑 types；关键词搜索可以独立工作
7. 如果请求里已经限定了可选 types，types 只能从限定集合里选
8. 不要重复已经搜索过的 keywords + types 组合
9. 不要把餐饮、住宿、交通站点作为景点；但博物馆、艺术馆、展馆、历史街区、商业街区、演出场馆、主题乐园可以作为行程 POI

### 输出格式（严格 JSON）
```json
{{
  "thought": "你的思考过程，分析当前情况和下一步决策",
  "action": "search" 或 "finish",
  "reason": "简要说明判断理由",
  "types": [],
  "keywords": ["博物馆", "历史街区", "艺术馆"]
}}
```

- `action` 为 "finish" 时，`types` 和 `keywords` 填空数组
"""


# ══════════════════════════════════════════════════════════════
# LLM 实例
# ══════════════════════════════════════════════════════════════

_json_llm = ChatQwen(
    model="qwen3.5-flash-2026-02-23",
    api_key=settings.DASHSCOPE_API_KEY,
    base_url=settings.DASHSCOPE_BASE_URL,
    temperature=0.3,
    extra_body={"enable_thinking": False},
    model_kwargs={"response_format": {
        "type": "json_object"
    }},
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


def _simple_dedupe_and_rank(items: List[dict[str, Any]]) -> list[dict[str, Any]]:
    """简单去重 + 排序（替代 LLM filter）"""
    # 按评分、有图、有坐标排序
    ranked = sorted(
        items,
        key=lambda item: (
            -float(item.get("rating", 0) or 0),
            0 if item.get("photo") or (item.get("photos") or []) else 1,
            0 if item.get("location") else 1,
        ),
    )

    # 去重（名称相似视为重复）
    deduped = []
    seen_names: set[str] = set()
    for item in ranked:
        name = str(item.get("name", "")).strip().lower()
        # 标准化：去空格和常见后缀
        normalized = name.replace(" ", "").replace("旅游景区", "").replace("风景区", "").replace("景区", "")
        if normalized in seen_names:
            continue
        seen_names.add(normalized)
        deduped.append(item)

    return deduped


def _search_signature(*, keywords: List[str], types: List[str]) -> str:
    """生成搜索去重键，避免 LLM 在同一轮规划中重复调用同一查询。"""
    keyword_part = "|".join(_uniq_text(keywords, limit=8))
    type_part = "|".join(_uniq_text(types, limit=8))
    return f"keywords={keyword_part};types={type_part}"


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
    types_str = "|".join([t.strip() for t in types if t.strip()]) if types else ""
    query_terms = search_keywords or [""]
    cleaned_items: list[dict[str, Any]] = []

    for keyword in query_terms:
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

        cleaned_items.extend([a for p in (response.pois or []) if (a := _clean_poi_to_attraction(p))])

    return cleaned_items


# ══════════════════════════════════════════════════════════════
# LLM 思考
# ══════════════════════════════════════════════════════════════


async def _llm_decide(
    destination: str,
    preferences: List[str],
    companions: str,
    special_requirements: str,
    needed: int,
    pool: List[dict],
    history: str,
    searched_queries: List[str],
    allowed_types: List[str] | None = None,
) -> ActResult:
    """LLM ReAct 决策步骤：分析当前情况并决定下一步行动"""
    started = perf_counter()

    pool_info = [
        {
            "name": a.get("name", ""),
            "rating": a.get("rating", 0),
            "type": a.get("type", ""),
        }
        for a in pool
    ]

    prompt = PROMPT_REACT.format(
        destination=destination,
        preferences=preferences,
        companions=companions or "独自",
        special_requirements=special_requirements or "无",
        needed=needed,
        type_catalog=ATTRACTION_TYPE_CATALOG_TEXT,
        allowed_types=(
            ", ".join([f"{code}:{ATTRACTION_TYPE_CATALOG[code]['label']}" for code in allowed_types])
            if allowed_types
            else "未指定；types 可为空，优先使用 keywords 扩展召回"
        ),
        history=history or "暂无搜索历史",
        current_pool=json.dumps(pool_info, ensure_ascii=False),
        searched_queries=", ".join(searched_queries) if searched_queries else "无",
    )

    try:
        resp = await _json_llm.ainvoke([
            SystemMessage(content=prompt),
        ])
        data = json.loads(resp.content)
    except Exception as exc:
        raise LLMJsonError(f"attraction decision failed: {exc}") from exc

    action = str(data.get("action", "finish" if len(pool) >= needed else "search")).strip()
    if action not in {"search", "finish"}:
        raise LLMJsonError(f"attraction decision returned invalid action: {action}")

    keywords = data.get("keywords", [])
    types = _normalize_attraction_types(
        data.get("types", []),
        allowed_types=allowed_types,
        limit=3,
    )
    normalized_keywords = _uniq_text(
        [k for k in keywords if isinstance(k, str) and k.strip()],
        limit=4,
    ) if isinstance(keywords, list) else []
    if allowed_types and action == "search" and not types:
        raise LLMJsonError(
            "attraction decision returned search without allowed types while request restricts types"
        )
    if action == "search" and not types and not normalized_keywords:
        raise LLMJsonError("attraction decision returned search without types or keywords")

    logger.info(
        "llm_decide duration_ms=%.1f pool=%s action=%s",
        (perf_counter() - started) * 1000,
        len(pool),
        action,
    )
    return ActResult(
        thought=data.get("thought", ""),
        action=action,
        reason=data.get("reason", ""),
        keywords=normalized_keywords,
        types=types,
    )


# ══════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════


async def attraction_node(state: TripState) -> Dict[str, Any]:
    """景点 Agent 主流程 - ReAct Agent 模式。

    流程：
    1. LLM 根据当前候选池和搜索历史，决定是继续搜索还是结束
    2. 如果继续搜索，LLM 生成关键词
    3. 调用 MCP 工具搜索景点
    4. 简单清洗后，循环回步骤 1

    Args:
        state: LangGraph 全局状态

    Returns:
        更新状态，包含 attraction_candidates、attractions、streaming_updates、completed_agents
    """
    started = perf_counter()
    logger.info("景点搜索开始 [ReAct Agent 模式]")

    request = state["request"]
    destination = request.get("destination", "")
    preferences = state.get("style_preferences", [])
    companions = str(state.get("companions") or request.get("companions") or "独自").strip() or "独自"
    special_requirements = str(request.get("special_requirements", "") or "").strip()
    needed = int(state.get("needed_attractions", 6) or 6)
    allowed_types = _normalize_attraction_types(
        request.get("types") or state.get("mcp_search_types", ""),
        limit=len(VALID_ATTRACTION_TYPE_CODES),
    )

    tool = get_tool(TOOL_NAME)
    if not tool:
        raise RuntimeError(f"未找到工具: {TOOL_NAME}")

    pool: List[dict] = list(state.get("attraction_candidates", []))
    iterations = 0
    search_history: List[str] = []
    searched_queries: List[str] = []

    # ══════════════════════════════════════════════════════════
    # ReAct 循环
    # ══════════════════════════════════════════════════════════
    while iterations < MAX_ITERATIONS:
        iterations += 1
        logger.info("ReAct iteration=%d pool=%d needed=%d", iterations, len(pool), needed)

        # Step 1: Think - LLM 根据当前情况决定是否继续搜索
        history_str = "\n".join([f"- 第{i+1}次: {h}" for i, h in enumerate(search_history)])
        act = await _llm_decide(
            destination,
            preferences,
            companions,
            special_requirements,
            needed,
            pool,
            history_str,
            searched_queries,
            allowed_types=allowed_types,
        )
        logger.info("LLM decision: action=%s reason=%s types=%s keywords=%s",
                    act.action, act.reason, act.types, act.keywords)

        # LLM 决定结束
        if act.action == "finish":
            if len(pool) < needed:
                raise LLMJsonError(
                    f"attraction decision finished early: pool={len(pool)} needed={needed}"
                )
            logger.info("LLM 决定结束搜索")
            break

        query_signature = _search_signature(keywords=act.keywords, types=act.types)
        if query_signature in searched_queries:
            raise LLMJsonError(f"attraction decision repeated search query: {query_signature}")
        searched_queries.append(query_signature)

        # Step 2: Act - 调用 MCP 搜索
        types_str = "|".join(act.types)
        keywords_str = "|".join([k.strip() for k in act.keywords if k.strip()])
        type_labels = [str(ATTRACTION_TYPE_CATALOG[code]["label"]) for code in act.types if code in ATTRACTION_TYPE_CATALOG]
        search_history.append(f"搜索 types={types_str} labels={type_labels} keywords={keywords_str}")

        new_items = await _search_pois(
            tool, destination,
            keywords=act.keywords,
            types=act.types,
        )
        logger.info("搜索完成: types=%s keywords=%s new_items=%d", types_str, keywords_str, len(new_items))

        if new_items:
            # Step 3: Observe - 合并到候选池并简单清洗
            all_items = pool + new_items
            pool = _simple_dedupe_and_rank(all_items)[:needed + 4]
            logger.info("候选池更新: pool=%d", len(pool))

            # 记录搜索结果
            types_found = list(set([a.get("type", "").split(";")[0] for a in new_items]))
            search_history.append(f"→ 获得 {len(new_items)} 个景点，类型: {types_found}")
        else:
            search_history.append(f"→ 获得 0 个景点")

    # ══════════════════════════════════════════════════════════
    # 输出结果
    # ══════════════════════════════════════════════════════════
    final = pool[:needed]
    if len(final) < needed:
        raise NoCandidatesError(f"景点候选不足: got={len(final)} needed={needed}")
    logger.info(
        "景点搜索完成: %d 个景点 duration_ms=%.1f iterations=%d",
        len(final),
        (perf_counter() - started) * 1000,
        iterations,
    )

    return {
        "attraction_candidates": pool,
        "attractions": final,
        "streaming_updates": f"\n景点完成: {len(final)}个",
        "completed_agents": ["attraction"],
    }
