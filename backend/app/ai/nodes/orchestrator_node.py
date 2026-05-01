"""Orchestrator 节点：基于规则生成检索策略。

该节点是 LangGraph 的入口节点，负责：
1. 接收用户请求（TripRequest）
2. 提取用户偏好（companions, style_preferences, hotel_level）
3. 初始化状态中的所有字段为空值

图结构位置：
- 作为入口节点，接收 START 事件
- 路由到 attraction_agent 和 hotel_agent（Fan-out 模式）
"""

from app.config import get_logger
from app.ai.models.graph_models import TripState

logger = get_logger("Orchestrator")


def _price_range_by_level(hotel_level: str) -> str:
    mapping = {
        "经济型": "200,400",
        "舒适型": "300,800",
        "高档型": "600,1200",
        "豪华型": "1000,2500",
    }
    return mapping.get(str(hotel_level).strip(), "300,800")


def orchestrator_node(state: TripState) -> TripState:
    """根据用户偏好写入本轮规则化检索策略。"""
    request = state.get("request", {})
    if not request:
        state["status"] = "error"
        state["errors"] = "missing request"
        return state

    destination = str(request.get("destination", "")).strip()
    num_people = int(request.get("num_people", 1) or 1)
    companions = request.get("companions") or state.get("companions", "朋友")
    style_preferences = request.get("style_preferences") or state.get("style_preferences", [])
    hotel_level = request.get("hotel_level") or state.get("hotel_level", "舒适型")
    hotel_price_range = _price_range_by_level(str(hotel_level))

    # 从请求中提取天数
    days = int(request.get("days", 0) or request.get("duration", 3))  # 出行天数
    max_per_day = 2
    needed_attractions = min(days * max_per_day, 12)

    # 保存用户偏好到状态
    state["companions"] = companions  # 出行同伴（朋友/家人/情侣等），用于餐饮和交通规划
    state["style_preferences"] = style_preferences  # 旅行风格偏好，供各 agent 参考
    state["hotel_level"] = hotel_level  # 酒店档次（经济型/舒适型/高档型/豪华型）

    # 保存搜索参数到状态
    state["search_keywords"] = destination
    state["hotel_price_range"] = hotel_price_range  # 酒店价格区间，供酒店搜索用
    state["max_attractions_per_day"] = max_per_day  # 每日景点上限，用于行程规划
    state["needed_attractions"] = needed_attractions  # 景点总数需求（days * max_per_day）
    state["total_budget"] = 0.0  # 总预算，暂未使用

    # 初始化所有 Agent 输出字段
    state["attractions"] = []  # 最终筛选的景点列表
    state["hotels"] = []  # 最终筛选的酒店列表
    state["attraction_candidates"] = []  # 景点候选池（搜索结果）
    state["hotel_candidates"] = []  # 酒店候选池（搜索结果）
    state["restaurants"] = []  # 餐厅列表
    state["weather"] = []  # 天气数据
    state["reviewer_notes"] = []  # 评审节点备注
    state["transport"] = None  # 交通方案
    state["itinerary_draft"] = None  # 行程草稿
    state["status"] = "in_progress"  # 当前状态
    state["errors"] = ""  # 错误信息
    state["completed_agents"] = []  # 已完成的 agent 列表

    # 流式更新消息
    state["streaming_updates"] = f"已接收需求: {destination}, {days}天, {num_people}人"

    logger.info(
        "orchestrator ready destination=%s days=%s max/day=%s needed=%s",
        destination, days, max_per_day, needed_attractions,
    )
    return state
