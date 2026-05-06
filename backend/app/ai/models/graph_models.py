"""
TripState 定义 - LangGraph 全局状态

贯穿整个旅行规划流程，携带所有上下文信息
"""

from typing import Annotated, TypedDict, List, Dict, Any, Optional
from datetime import date


def _concat_streaming_updates(left: str, right: str) -> str:
    """Reducer: 合并并行步骤产生的流式更新文本。"""
    left_text = left or ""
    right_text = right or ""
    if not right_text:
        return left_text
    if left_text and right_text.startswith(left_text):
        return right_text
    return left_text + right_text


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

    注意：worker 节点应避免写入同一字段。当前 strategy-first 流程的主要写入边界：
    - strategy_agent: strategy_plan
    - anchor_resolver_agent: resolved_anchors, hotel_area_anchors
    - nearby_poi_agent: attractions, hotels, restaurants
    - route_matrix_agent: route_matrix
    - itinerary_composer_agent: transport
    - weather_agent: weather
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
    # Phase 1: Strategy-first planning artifacts
    # ═══════════════════════════════════════════════════════
    strategy_plan: Dict[str, Any]  # LLM 生成的每日片区/锚点骨架
    resolved_anchors: List[Dict[str, Any]]  # POI 验证后的景点锚点
    hotel_area_anchors: List[Dict[str, Any]]  # POI 验证后的住宿片区锚点
    anchor_resolution_results: List[Dict[str, Any]]  # 每个策略锚点的 POI 解析结果
    planning_blockers: List[Dict[str, Any]]  # 可修复的业务阻塞，不是系统异常
    route_matrix: Dict[str, Any]  # 前置路线矩阵与风险

    # ═══════════════════════════════════════════════════════
    # Search and request-derived parameters used by current nodes and shared models
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
    attraction_candidates: List[Dict[str, Any]]
    hotel_candidates: List[Dict[str, Any]]
    attractions: List[Dict[str, Any]]  # verified anchor attractions
    hotels: List[Dict[str, Any]]  # nearby hotel POIs
    restaurants: List[Dict[str, Any]]  # nearby restaurant POIs
    weather: List[Dict[str, Any]]  # 天气预报（Weather Agent 输出）
    reviewer_notes: List[str]  # 评审说明

    # ═══════════════════════════════════════════════════════
    # Phase 3: 路线规划结果
    # ═══════════════════════════════════════════════════════
    transport: Optional[Dict[str, Any]]  # 行程组合器生成的交通/每日安排

    # ═══════════════════════════════════════════════════════
    # Phase 4: 最终行程（DailyPlan + TripPlan）
    # ═══════════════════════════════════════════════════════
    itinerary_draft: Optional[Dict[str, Any]]  # 最终日程（TripPlan结构）

    # ═══════════════════════════════════════════════════════
    # Phase 5: 方案审核与定向修复循环
    # ═══════════════════════════════════════════════════════
    planning_iteration: int  # 当前修复迭代轮次，初始为0
    max_planning_iterations: int  # 最大修复迭代次数
    evaluation: Optional[Dict[str, Any]]  # 最新方案审核结果
    evaluation_history: List[Dict[str, Any]]  # 每轮方案审核历史
    active_repair_tasks: List[Dict[str, Any]]  # 当前轮需要执行的定向修复任务
    repair_targets: List[str]  # 当前轮要派发的 worker 节点
    next_workers: List[str]  # Orchestrator 本轮派发的 worker 节点
    current_workers: List[str]  # 当前正在汇合的 worker 批次
    completed_workers_in_batch: List[str]  # 当前批次已汇合的 worker 节点
    worker_batch_completed: bool  # 当前 worker 批次是否已汇合完成
    worker_queue: List[List[str]]  # Orchestrator 尚未派发的后续 worker 批次
    final_with_warnings: bool  # 达到最大修复轮后是否带风险成稿
    evaluation_failed_after_max_iterations: bool  # 审核未通过但修复轮耗尽
    orchestration_initialized: bool  # Orchestrator 是否已完成首次初始化
    orchestration_action: str  # "worker_batch" | "evaluate" | "final"
    orchestration_step: int  # Orchestrator 调度步数，用于流式事件去重
    evaluate_after_workers: bool  # worker 队列跑完后是否进入方案审核

    # ═══════════════════════════════════════════════════════
    # 流程控制字段
    # ═══════════════════════════════════════════════════════
    status: str  # "in_progress" | "completed" | "error"
    errors: str  # 错误信息

    # 新增：流式更新（用于SSE推送到前端）
    streaming_updates: Annotated[str, _concat_streaming_updates]  # 进度更新消息（可追加）

    # 新增：并行执行控制
    completed_agents: Annotated[List[str], _merge_completed_agents]  # 已完成Agent列表，如["attraction", "hotel", "weather"]
