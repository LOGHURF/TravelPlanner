"""Orchestrator 节点：主控调度旅行规划循环。

该节点是 LangGraph 的入口和循环控制器，负责：
1. 接收用户请求（TripRequest）
2. 提取用户偏好（companions, style_preferences, hotel_level）
3. 派发 worker 批次
4. 消费 evaluator repair tasks，进入下一轮定向修复

图结构位置：
- START 和 evaluator/fan_in 都回到 orchestrator
- orchestrator 决定下一步是 worker batch、evaluator 还是 final_planning
"""

from app.config import get_logger
from app.ai.models.graph_models import TripState
from app.ai.planning_gates import evaluate_resource_gate

logger = get_logger("Orchestrator")


def _price_range_by_level(hotel_level: str) -> str:
    mapping = {
        "经济型": "200,400",
        "舒适型": "300,800",
        "高档型": "600,1200",
        "豪华型": "1000,2500",
    }
    return mapping.get(str(hotel_level).strip(), "300,800")


def _foundation_queue() -> list[list[str]]:
    return [
        ["strategy_agent", "weather_agent"],
        ["anchor_resolver_agent"],
        ["nearby_poi_agent"],
        ["route_matrix_agent"],
        ["itinerary_composer_agent"],
    ]


def _repair_queue(targets: list[str]) -> list[list[str]]:
    if not targets:
        raise ValueError("repair targets are required")

    queue: list[list[str]] = []
    foundation = [
        target
        for target in ["strategy_agent", "weather_agent"]
        if target in targets
    ]
    if foundation:
        queue.append(foundation)
        queue.extend([["anchor_resolver_agent"], ["nearby_poi_agent"], ["route_matrix_agent"], ["itinerary_composer_agent"]])
        return queue

    if "anchor_resolver_agent" in targets:
        queue.extend([["anchor_resolver_agent"], ["nearby_poi_agent"], ["route_matrix_agent"], ["itinerary_composer_agent"]])
        return queue

    if "nearby_poi_agent" in targets:
        queue.extend([["nearby_poi_agent"], ["route_matrix_agent"], ["itinerary_composer_agent"]])
        return queue

    if "route_matrix_agent" in targets:
        queue.extend([["route_matrix_agent"], ["itinerary_composer_agent"]])
        return queue

    if "itinerary_composer_agent" in targets:
        queue.append(["itinerary_composer_agent"])
        return queue

    raise ValueError(f"unknown repair targets: {targets}")


def _repair_targets(repair_tasks: list[dict]) -> list[str]:
    targets: list[str] = []
    for task in repair_tasks:
        if not isinstance(task, dict):
            raise ValueError("repair task must be an object")
        agent = str(task.get("agent", "")).strip()
        if not agent:
            raise ValueError("repair task agent is required")
        if agent not in targets:
            targets.append(agent)
    return targets


def _current_batch_completed_anchor_boundary(state: TripState) -> bool:
    current_workers = {
        str(worker).strip()
        for worker in state.get("current_workers", [])
        if str(worker).strip()
    }
    return bool(current_workers & {"anchor_resolver_agent", "nearby_poi_agent"})


def _collect_planning_blockers(state: TripState) -> list[dict]:
    blockers = [item for item in state.get("planning_blockers") or [] if isinstance(item, dict)]
    if blockers:
        return blockers
    if _current_batch_completed_anchor_boundary(state):
        return evaluate_resource_gate(state)
    return []


def _clear_artifacts_for_targets(state: TripState, targets: list[str]) -> None:
    if "strategy_agent" in targets:
        for key in (
            "strategy_plan",
            "resolved_anchors",
            "hotel_area_anchors",
            "anchor_resolution_results",
            "attractions",
            "hotels",
            "restaurants",
            "route_matrix",
        ):
            state[key] = [] if key != "strategy_plan" and key != "route_matrix" else {}
        state["transport"] = None
        state["itinerary_draft"] = None
        return

    if "anchor_resolver_agent" in targets:
        for key in ("resolved_anchors", "hotel_area_anchors", "anchor_resolution_results", "attractions", "hotels", "restaurants"):
            state[key] = []
        state["route_matrix"] = {}
        state["transport"] = None
        state["itinerary_draft"] = None
        return

    if "nearby_poi_agent" in targets:
        for key in ("attractions", "hotels", "restaurants"):
            state[key] = []
        state["route_matrix"] = {}
        state["transport"] = None
        state["itinerary_draft"] = None
        return

    if "route_matrix_agent" in targets:
        state["route_matrix"] = {}
        state["transport"] = None
        state["itinerary_draft"] = None
        return

    if "itinerary_composer_agent" in targets:
        state["transport"] = None
        state["itinerary_draft"] = None


def _dispatch_blocker_repair(state: TripState, blockers: list[dict]) -> TripState:
    planning_iteration = int(state.get("planning_iteration", 0) or 0)
    max_iterations = int(state.get("max_planning_iterations", 3) or 3)
    if planning_iteration >= max_iterations:
        state["status"] = "error"
        state["errors"] = "规划阻塞超过最大修复轮次: " + "; ".join(
            str(blocker.get("message", "") or blocker.get("reason_code", "")).strip()
            for blocker in blockers
        )
        state["orchestration_action"] = "error"
        state["next_workers"] = []
        state["current_workers"] = []
        state["worker_queue"] = []
        state["planning_blockers"] = blockers
        return state

    targets = _repair_targets(
        [
            {
                "agent": str(blocker.get("target_agent", "")).strip(),
                "task": str(blocker.get("reason_code", "")).strip(),
                "reason": str(blocker.get("message", "")).strip(),
                "constraints": blocker.get("constraints") or {},
            }
            for blocker in blockers
        ]
    )
    state["planning_iteration"] = planning_iteration + 1
    state["repair_targets"] = targets
    state["active_repair_tasks"] = []
    state["planning_blockers"] = []
    state["evaluate_after_workers"] = True
    _clear_artifacts_for_targets(state, targets)
    state["streaming_updates"] = (
        state.get("streaming_updates", "")
        + f"\n第{state['planning_iteration']}轮结构化阻塞修复: {', '.join(targets)}"
    )
    logger.info("orchestrator blocker repair iteration=%s targets=%s", state["planning_iteration"], targets)
    return _dispatch_next_batch(state, _repair_queue(targets))


def _dispatch_next_batch(state: TripState, queue: list[list[str]]) -> TripState:
    if not queue:
        state["next_workers"] = []
        state["current_workers"] = []
        state["worker_queue"] = []
        state["orchestration_action"] = "evaluate" if state.get("evaluate_after_workers") else "final"
        state["evaluate_after_workers"] = False
        return state

    batch = queue[0]
    remaining = queue[1:]
    state["next_workers"] = batch
    state["current_workers"] = batch
    state["completed_workers_in_batch"] = []
    state["worker_batch_completed"] = False
    state["worker_queue"] = remaining
    state["orchestration_action"] = "worker_batch"
    return state


def _initialize_planning_state(state: TripState, request: dict) -> TripState:
    destination = str(request.get("destination", "")).strip()
    num_people = int(request.get("num_people", 1) or 1)
    companions = request.get("companions") or state.get("companions", "朋友")
    style_preferences = request.get("style_preferences") or state.get("style_preferences", [])
    hotel_level = request.get("hotel_level") or state.get("hotel_level", "舒适型")
    hotel_price_range = _price_range_by_level(str(hotel_level))

    days = int(request.get("days", 0) or request.get("duration", 3))
    max_per_day = 2
    needed_attractions = min(days * max_per_day, 12)

    state["companions"] = companions
    state["style_preferences"] = style_preferences
    state["hotel_level"] = hotel_level
    state["search_keywords"] = destination
    state["hotel_price_range"] = hotel_price_range
    state["max_attractions_per_day"] = max_per_day
    state["needed_attractions"] = needed_attractions
    state["total_budget"] = 0.0

    state["attractions"] = []
    state["hotels"] = []
    state["strategy_plan"] = {}
    state["resolved_anchors"] = []
    state["hotel_area_anchors"] = []
    state["anchor_resolution_results"] = []
    state["planning_blockers"] = []
    state["route_matrix"] = {}
    state["attraction_candidates"] = []
    state["hotel_candidates"] = []
    state["restaurants"] = []
    state["weather"] = []
    state["reviewer_notes"] = []
    state["transport"] = None
    state["itinerary_draft"] = None
    state["status"] = "in_progress"
    state["errors"] = ""
    state["completed_agents"] = []
    state["planning_iteration"] = 0
    state["max_planning_iterations"] = int(state.get("max_planning_iterations", 3) or 3)
    state["evaluation"] = None
    state["evaluation_history"] = []
    state["active_repair_tasks"] = []
    state["repair_targets"] = []
    state["current_workers"] = []
    state["completed_workers_in_batch"] = []
    state["worker_batch_completed"] = False
    state["final_with_warnings"] = False
    state["evaluation_failed_after_max_iterations"] = False
    state["orchestration_initialized"] = True
    state["orchestration_step"] = 0
    state["evaluate_after_workers"] = True
    state["streaming_updates"] = f"已接收需求: {destination}, {days}天, {num_people}人"

    logger.info(
        "orchestrator initialized destination=%s days=%s max/day=%s needed=%s",
        destination,
        days,
        max_per_day,
        needed_attractions,
    )
    return _dispatch_next_batch(state, _foundation_queue())


def _consume_evaluation(state: TripState) -> TripState:
    evaluation = state.get("evaluation")
    if not isinstance(evaluation, dict):
        state["orchestration_action"] = "final"
        state["next_workers"] = []
        return state

    planning_iteration = int(state.get("planning_iteration", 0) or 0)
    max_iterations = int(state.get("max_planning_iterations", 3) or 3)
    if evaluation.get("passed") is True or planning_iteration >= max_iterations:
        if evaluation.get("passed") is not True:
            state["orchestration_action"] = "final_with_warnings"
            state["final_with_warnings"] = True
            state["evaluation_failed_after_max_iterations"] = True
            state["streaming_updates"] = (
                state.get("streaming_updates", "")
                + f"\n已达到最大修复轮({max_iterations})，方案仍存在审核风险，将带风险说明成稿"
            )
        else:
            state["orchestration_action"] = "final"
            state["final_with_warnings"] = False
            state["evaluation_failed_after_max_iterations"] = False
        state["next_workers"] = []
        state["current_workers"] = []
        state["worker_queue"] = []
        return state

    repair_tasks = evaluation.get("repair_tasks")
    if not isinstance(repair_tasks, list) or not repair_tasks:
        raise ValueError("failed evaluation requires repair_tasks")

    targets = _repair_targets(repair_tasks)
    state["planning_iteration"] = planning_iteration + 1
    state["active_repair_tasks"] = repair_tasks
    state["repair_targets"] = targets
    state["evaluate_after_workers"] = True
    state["streaming_updates"] = (
        state.get("streaming_updates", "")
        + f"\n第{state['planning_iteration']}轮定向修复: {', '.join(targets)}"
    )
    logger.info("orchestrator repair iteration=%s targets=%s", state["planning_iteration"], targets)
    return _dispatch_next_batch(state, _repair_queue(targets))


def orchestrator_node(state: TripState) -> TripState:
    """初始化规划或根据当前状态派发下一步。"""
    state["orchestration_step"] = int(state.get("orchestration_step", 0) or 0) + 1
    request = state.get("request", {})
    if not request:
        state["status"] = "error"
        state["errors"] = "missing request"
        return state

    if not state.get("orchestration_initialized"):
        return _initialize_planning_state(state, request)

    blockers = _collect_planning_blockers(state)
    if blockers:
        return _dispatch_blocker_repair(state, blockers)

    queue = list(state.get("worker_queue") or [])
    if queue:
        return _dispatch_next_batch(state, queue)

    if state.get("evaluate_after_workers"):
        state["orchestration_action"] = "evaluate"
        state["next_workers"] = []
        state["evaluate_after_workers"] = False
        return state

    return _consume_evaluation(state)
