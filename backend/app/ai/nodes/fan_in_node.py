"""Worker join node: 汇合 Orchestrator 派发的 worker 批次。

职责：
1. 记录当前 worker 批次已经汇合
2. 生成准确的批次完成进度
3. 把控制权交回 Orchestrator

图结构位置：
- 接收所有 worker 节点输出
- 统一返回 orchestrator
"""

from __future__ import annotations

from app.config import get_logger
from app.ai.models.graph_models import TripState

logger = get_logger("FanInService")


async def fan_in_node(state: TripState) -> TripState:
    """汇合当前 worker 批次，不做旧 Phase-1 路由判断。"""
    current_workers = [
        str(worker).strip()
        for worker in state.get("current_workers", [])
        if str(worker).strip()
    ]
    completed_agents = state.get("completed_agents", [])
    state["completed_workers_in_batch"] = current_workers
    state["worker_batch_completed"] = True
    state["status"] = state.get("status") or "in_progress"
    worker_text = ", ".join(current_workers) if current_workers else "unknown"
    state["streaming_updates"] = (
        state.get("streaming_updates", "")
        + f"\nWorker批次完成: {worker_text}"
    )

    logger.info(
        "worker join done current_workers=%s completed_agents=%s status=%s",
        current_workers,
        completed_agents,
        state.get("status"),
    )
    return state
