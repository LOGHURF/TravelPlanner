"""Fan-in node: 验证 Phase-1 数据后进入 Phase-2 规划。

职责：
1. 验证 attraction 和 hotel agent 的输出
2. 检查数据完整性和质量
3. 决定是进入 reviewer 还是跳过直接到 final_planning

图结构位置：
- 接收 attraction_agent 和 hotel_agent 的 Fan-out 结果
- 根据数据质量决定路由到 reviewer_agent 或 final_planning
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.config import get_logger
from app.ai.models.graph_models import TripState

logger = get_logger("FanInService")


def _safe_days(state: TripState) -> int:
    """从 request 中获取出行天数"""
    request = state.get("request", {})
    return int(request.get("days", 1) or 1)


async def fan_in_node(state: TripState) -> TripState:
    """Fan-in 主流程：验证数据并决定下游路由。

    检查：
    1. 景点和酒店候选是否为空
    2. 数据量是否低于最低要求
    3. 评分是否过低

    Args:
        state: LangGraph 全局状态

    Returns:
        更新后的 state
    """
    attractions = state.get("attractions", [])
    hotels = state.get("hotels", [])
    completed_agents = state.get("completed_agents", [])

    days = _safe_days(state)
    expected_attractions = int(state.get("needed_attractions", days * 2) or days * 2)
    min_required_attractions = min(2, expected_attractions)

    issues: List[str] = []
    warnings: List[str] = []

    # 检查景点
    if not attractions:
        issues.append("未找到任何景点")
    elif len(attractions) < min_required_attractions:
        warnings.append(f"景点数量较少（{len(attractions)}个）")

    # 检查酒店
    if not hotels:
        issues.append("未找到任何酒店")
    elif len(hotels) > 1:
        warnings.append(f"酒店候选较多（{len(hotels)}家），将交由评审节点挑选主推荐")

    # 检查评分
    if attractions:
        avg_rating = sum(a.get("rating", 0) for a in attractions) / len(attractions)
        if avg_rating < 4.0:
            warnings.append(f"景点评分偏低（{avg_rating:.1f}）")

    # 设置状态
    if issues:
        state["errors"] = "; ".join(issues)
        state["status"] = "error"
    elif warnings:
        state["errors"] = "; ".join(warnings)
        state["status"] = state.get("status") or "in_progress"
    else:
        state["errors"] = ""
        state["status"] = state.get("status") or "in_progress"

    # 生成摘要消息
    summary = (
        "\n基础数据采集完成\n"
        f"景点: {len(attractions)}个\n"
        f"酒店: {len(hotels)}家(待评审排序)\n"
        "进入评审: 偏好匹配与候选重排"
    )
    if issues:
        summary += f"\n问题: {'; '.join(issues)}"
    elif warnings:
        summary += f"\n提示: {'; '.join(warnings)}"
    else:
        summary += "\n进入下一阶段: 餐饮与交通"

    state["streaming_updates"] = state.get("streaming_updates", "") + summary
    state["phase_1_completed"] = True

    logger.info(
        "fan_in done completed=%s attractions=%s hotels=%s weather=%s status=%s",
        completed_agents,
        len(attractions),
        len(hotels),
        len(state.get("weather", [])),
        state.get("status"),
    )
    return state


def check_phase1_complete(state: TripState) -> bool:
    """检查 Phase-1 是否完成"""
    required_agents = ["attraction", "hotel"]
    completed = state.get("completed_agents", [])

    for agent in required_agents:
        if agent not in completed:
            return False

    if not state.get("attractions"):
        return False
    if not state.get("hotels"):
        return False
    return True


def get_phase1_progress(state: TripState) -> Dict[str, Any]:
    """获取 Phase-1 进度"""
    required_agents = ["attraction", "hotel"]
    completed = state.get("completed_agents", [])

    completed_count = sum(1 for agent in required_agents if agent in completed)
    progress_percent = int((completed_count / len(required_agents)) * 100) if required_agents else 100

    if "attraction" not in completed:
        current_step = "搜索景点"
    elif "hotel" not in completed:
        current_step = "筛选酒店"
    else:
        current_step = "数据汇聚"

    return {
        "progress_percent": progress_percent,
        "current_step": current_step,
        "completed_agents": completed,
        "is_complete": completed_count == len(required_agents),
    }