"""
TripState 定义 - LangGraph 全局状态

贯穿整个旅行规划流程，携带所有上下文信息
"""

from typing import Annotated, TypedDict, List, Dict, Any, Optional
from datetime import date


def _concat_streaming_updates(left: str, right: str) -> str:
    """Reducer: 合并并行步骤产生的流式更新文本。"""
    return (left or "") + (right or "")


def _merge_completed_agents(left: List[str], right: List[str]) -> List[str]:
    """Reducer: 合并并去重并行步骤上报的完成 Agent 名称。"""
    merged: List[str] = []
    for name in (left or []) + (right or []):
        if name and name not in merged:
            merged.append(name)
    return merged


class TripState(TypedDict, total=False):
    """旅行规划全局状态 - 优化版本（支持并行Fan-out）

    字段说明：
    - request: 用户原始请求（结构化）
    - 偏好字段: companions, style_preferences, pace, hotel_level
    - 搜索参数: search_keywords, hotel_price_range等（由Supervisor生成）
    - Agent输出: candidates + reviewed结果 + restaurants/weather/transport
    - 流程控制: status, errors, streaming_updates, completed_agents
    - 最终结果: itinerary_draft（TripPlan结构）

    注意：并行节点应避免写入同一字段。每个Agent应只写入自己的输出字段：
    - attraction_agent: 只写入 attraction_candidates
    - hotel_agent: 只写入 hotel_candidates
    - reviewer_agent: 写入 attractions/hotels（评审后结果）
    - weather_agent: 只写入 weather
    - restaurant_agent: 只写入 restaurants
    - transport_agent: 只写入 transport 和 itinerary_draft
    """

    # ═══════════════════════════════════════════════════════
    # Phase 0: 用户请求（来自结构化表单）
    # ═══════════════════════════════════════════════════════
    request: Dict[str, Any]  # TripRequest 的 dict 形式

    # 新增：用户偏好字段（前端直接映射，无需LLM解析）
    companions: str  # 同行伙伴："独自"/"家庭"/"情侣"/"朋友"/"老人"
    style_preferences: List[str]  # 风格偏好：["文化体验","自然风光","历史古迹"]
    pace: str  # 行程节奏："紧凑"/"适中"/"宽松"
    hotel_level: str  # 住宿偏好："舒适型"/"高档型"/"豪华型"

    # ═══════════════════════════════════════════════════════
    # Phase 1: Supervisor 生成的搜索参数
    # ═══════════════════════════════════════════════════════
    search_keywords: str  # 生成的搜索关键词
    hotel_price_range: str  # 酒店价格范围，如"200,500"
    max_attractions_per_day: int  # 每日景点上限
    needed_attractions: int  # 所需景点总数
    total_budget: float  # 用户预算（可空，默认0；最终以系统估算为主）
    attraction_query_keywords: List[str]  # 景点检索关键词（每个关键词仅调用一次）
    food_query_keywords: List[str]  # 美食检索关键词（每个关键词仅调用一次）
    hotel_query_keyword: str  # 酒店检索关键词（用于召回多家候选酒店）
    mcp_search_types: str  # 可选：透传给 maps_text_search 的 types 参数
    mcp_search_show_fields: str  # 可选：透传给 maps_text_search 的 show_fields 参数

    # ═══════════════════════════════════════════════════════
    # Phase 2: Agent 输出结果（并行采集）
    # ═══════════════════════════════════════════════════════
    attraction_candidates: List[Dict[str, Any]]  # 景点候选池（Attraction Agent输出）
    hotel_candidates: List[Dict[str, Any]]  # 酒店候选池（Hotel Agent输出）
    attractions: List[Dict[str, Any]]  # 评审后景点列表（Reviewer Agent输出）
    hotels: List[Dict[str, Any]]  # 评审后酒店列表（Reviewer Agent输出）
    restaurants: List[Dict[str, Any]]  # 餐厅列表（Restaurant Agent输出）
    weather: List[Dict[str, Any]]  # 天气预报（Weather Agent输出）
    reviewer_notes: List[str]  # 评审说明

    # ═══════════════════════════════════════════════════════
    # Phase 3: 路线规划结果
    # ═══════════════════════════════════════════════════════
    transport: Optional[Dict[str, Any]]  # 交通/路线规划（Transport Agent输出）

    # ═══════════════════════════════════════════════════════
    # Phase 4: 最终行程（DailyPlan + TripPlan）
    # ═══════════════════════════════════════════════════════
    itinerary_draft: Optional[Dict[str, Any]]  # 最终日程（TripPlan结构）

    # ═══════════════════════════════════════════════════════
    # 流程控制字段
    # ═══════════════════════════════════════════════════════
    status: str  # "in_progress" | "completed" | "error"
    errors: str  # 错误信息

    # 新增：流式更新（用于SSE推送到前端）
    streaming_updates: Annotated[str, _concat_streaming_updates]  # 进度更新消息（可追加）

    # 新增：并行执行控制
    completed_agents: Annotated[List[str], _merge_completed_agents]  # 已完成Agent列表，如["attraction", "hotel", "weather"]