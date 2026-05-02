"""旅行规划 API 端点 - 使用新 TripRequest 和 TripState。"""

import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ai.models import (
    Attraction,
    DailyPlan,
    HealthResponse,
    Hotel,
    ItineraryResponse,
    PlanSyncResponse,
    Restaurant,
    TransportPlan,
    TripPlan,
    TripRequest,
    WeatherInfo,
    TripState,
)
from app.api.deps import get_graph
from app.config import get_logger

logger = get_logger("TravelAPI")
router = APIRouter()

AGENT_META: dict[str, dict[str, str]] = {
    "orchestrator": {"label": "需求拆解", "phase": "prepare"},
    "attraction_agent": {"label": "景点 Agent", "phase": "parallel"},
    "hotel_agent": {"label": "酒店 Agent", "phase": "parallel"},
    "reviewer_agent": {"label": "评审 Agent", "phase": "refine"},
    "restaurant_agent": {"label": "餐饮 Agent", "phase": "enrich"},
    "transport_agent": {"label": "交通 Agent", "phase": "route"},
    "weather_agent": {"label": "天气 Agent", "phase": "enrich"},
    "final_planning": {"label": "成稿 Agent", "phase": "finalize"},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dump_model(model_cls: type[BaseModel], payload: object) -> dict[str, object]:
    return model_cls.model_validate(payload).model_dump(mode="json")


def _dump_model_list(model_cls: type[BaseModel], payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, list):
        return []
    return [model_cls.model_validate(item).model_dump(mode="json") for item in payload]


def _sse_event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _build_agent_payload(
    event_type: str,
    agent_id: str,
    *,
    status: str,
    message: str = "",
    progress: int | None = None,
    counts: dict[str, int] | None = None,
) -> dict[str, object]:
    agent_meta = AGENT_META[agent_id]
    payload: dict[str, object] = {
        "type": event_type,
        "agentId": agent_id,
        "label": agent_meta["label"],
        "phase": agent_meta["phase"],
        "status": status,
        "timestamp": _utc_now(),
    }
    if message:
        payload["message"] = message
    if progress is not None:
        payload["progress"] = progress
    if counts:
        payload["counts"] = counts
    return payload


def _iter_new_update_lines(emitted_lines: set[str], current_updates: str) -> list[str]:
    if not current_updates:
        return []

    new_lines: list[str] = []
    for line in current_updates.splitlines():
        text = line.strip()
        if not text or text in emitted_lines:
            continue
        emitted_lines.add(text)
        new_lines.append(text)
    return new_lines


def _extract_counts(node_name: str, node_state: TripState) -> dict[str, int]:
    if node_name == "attraction_agent":
        return {"items": len(node_state.get("attractions", []))}
    if node_name == "hotel_agent":
        return {"items": len(node_state.get("hotels", []))}
    if node_name == "reviewer_agent":
        return {
            "attractions": len(node_state.get("attractions", [])),
            "hotels": len(node_state.get("hotels", [])),
        }
    if node_name == "restaurant_agent":
        return {"items": len(node_state.get("restaurants", []))}
    if node_name == "transport_agent":
        transport = node_state.get("transport") or {}
        daily_plan = transport.get("daily_plan", []) if isinstance(transport, dict) else []
        return {"days": len(daily_plan)}
    if node_name == "weather_agent":
        return {"days": len(node_state.get("weather", []))}
    if node_name == "final_planning":
        itinerary = node_state.get("itinerary_draft") or {}
        statistics = itinerary.get("statistics", {}) if isinstance(itinerary, dict) else {}
        days = itinerary.get("days", []) if isinstance(itinerary, dict) else []
        return {
            "days": len(days),
            "attractions": int(statistics.get("attraction_count", 0) or 0),
        }
    return {}


def _build_node_artifact_payloads(node_name: str, node_state: TripState) -> list[dict[str, object]]:
    if node_name == "attraction_agent":
        attractions = node_state.get("attractions", [])
        if not attractions:
            return []
        return [{"type": "attractions", "data": _dump_model_list(Attraction, attractions)}]

    if node_name == "hotel_agent":
        hotels = node_state.get("hotels", [])
        if not hotels:
            return []
        return [{"type": "hotels", "data": _dump_model_list(Hotel, hotels)}]

    if node_name == "restaurant_agent":
        restaurants = node_state.get("restaurants", [])
        if not restaurants:
            return []
        return [{"type": "restaurants", "data": _dump_model_list(Restaurant, restaurants)}]

    if node_name == "weather_agent":
        weather = node_state.get("weather", [])
        if not weather:
            return []
        return [{"type": "weather", "data": _dump_model_list(WeatherInfo, weather)}]

    if node_name == "transport_agent":
        transport = node_state.get("transport", {})
        if not transport:
            return []
        return [{"type": "routes", "data": _dump_model(TransportPlan, transport)}]

    if node_name == "final_planning":
        itinerary = node_state.get("itinerary_draft")
        if not itinerary:
            raise RuntimeError("final_planning completed without itinerary_draft")

        itinerary_payload = _dump_model(TripPlan, itinerary)
        payloads: list[dict[str, object]] = []
        narrative = itinerary_payload.get("narrative_plan", "")
        if narrative:
            payloads.append({"type": "narrative", "data": narrative})
        payloads.append({"type": "itinerary", "data": itinerary_payload})
        return payloads

    return []


def _build_node_completion_payloads(node_name: str, node_state: TripState) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    counts: dict[str, int] = {}

    if node_name in AGENT_META:
        counts = _extract_counts(node_name, node_state)
        if counts:
            payloads.append(
                _build_agent_payload(
                    "agent_result",
                    node_name,
                    status="running",
                    message="已收到阶段性结果",
                    progress=86,
                    counts=counts,
                )
            )

    payloads.extend(_build_node_artifact_payloads(node_name, node_state))

    if node_name in AGENT_META:
        payloads.append(
            _build_agent_payload(
                "agent_done",
                node_name,
                status="completed",
                message="已完成当前阶段处理",
                progress=100,
                counts=counts or None,
            )
        )

    return payloads


def _resolve_next_agent_starts(node_name: str, node_state: TripState) -> list[str]:
    if node_name == "orchestrator":
        return ["attraction_agent", "hotel_agent", "weather_agent"]
    if node_name == "fan_in":
        errors = node_state.get("errors", "")
        status = node_state.get("status", "")
        if status == "error" and "未找到任何" in errors:
            return ["final_planning"]
        return ["reviewer_agent"]
    if node_name == "reviewer_agent":
        return ["restaurant_agent"]
    if node_name == "restaurant_agent":
        return ["transport_agent"]
    if node_name == "transport_agent":
        return ["final_planning"]
    return []


def create_initial_state(request: TripRequest) -> TripState:
    """从 TripRequest 创建初始 TripState"""
    request_payload = request.model_dump()
    request_payload["days"] = request.days
    return {
        "request": request_payload,
        "companions": request.companions,
        "style_preferences": request.style_preferences,
        "pace": request.pace,
        "hotel_level": request.hotel_level,
        "attractions": [],
        "hotels": [],
        "attraction_candidates": [],
        "hotel_candidates": [],
        "restaurants": [],
        "weather": [],
        "reviewer_notes": [],
        "transport": None,
        "itinerary_draft": None,
        "total_budget": 0.0,
        "status": "in_progress",
        "errors": "",
        "streaming_updates": "",
        "completed_agents": [],
        "search_keywords": "",
        "hotel_price_range": "",
        "max_attractions_per_day": 2,
        "needed_attractions": max(2, request.days * 2),
        "attraction_query_keywords": [],
        "food_query_keywords": [],
        "hotel_query_keyword": "",
        "mcp_search_types": request.types,
        "mcp_search_show_fields": request.show_fields,
    }


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(status="ok", version="3.0.0")


@router.post("/plan")
async def plan_travel(request: TripRequest, graph=Depends(get_graph)):
    """
    旅行规划接口（流式输出）- 新版本
    
    请求体：TripRequest
    - destination: 目的地
    - start_date: 开始日期
    - end_date: 结束日期
    - num_people: 出行人数
    - preferences: 偏好标签列表
    - special_requirements: 特殊要求
    - origin: 出发地（可选）
    """
    logger.info(
        "plan request origin=%s destination=%s days=%s people=%s",
        request.origin or "",
        request.destination,
        request.days,
        request.num_people,
    )
    if request.special_requirements:
        logger.info("special requirements: %s", request.special_requirements)
    
    async def event_stream():
        """SSE 流式输出"""
        initial_state = create_initial_state(request)
        
        logger.info("graph execution started")
        
        # 生成唯一的 thread_id
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        
        # 跟踪进度
        emitted_update_lines: set[str] = set()
        started_agents = {"orchestrator"}

        yield _sse_event(
            _build_agent_payload(
                "agent_start",
                "orchestrator",
                status="running",
                message="开始拆解用户需求并生成检索参数",
                progress=12,
            )
        )
        
        try:
            async for event in graph.astream(initial_state, config):
                for node_name, node_state in event.items():
                    if node_name == "__start__":
                        continue
                    
                    logger.info("node done: %s", node_name)
                    
                    # 获取进度更新
                    current_updates = node_state.get("streaming_updates", "")
                    new_lines = _iter_new_update_lines(emitted_update_lines, current_updates)
                    if new_lines:
                        for line in new_lines:
                            yield _sse_event({"type": "progress", "message": line})
                            if node_name in AGENT_META:
                                yield _sse_event(
                                    _build_agent_payload(
                                        "agent_progress",
                                        node_name,
                                        status="running",
                                        message=line,
                                        progress=72,
                                    )
                                )

                    for payload in _build_node_completion_payloads(node_name, node_state):
                        yield _sse_event(payload)

                    for next_agent in _resolve_next_agent_starts(node_name, node_state):
                        if next_agent in started_agents:
                            continue
                        started_agents.add(next_agent)
                        yield _sse_event(
                            _build_agent_payload(
                                "agent_start",
                                next_agent,
                                status="running",
                                message=f"{AGENT_META[next_agent]['label']}已开始处理",
                                progress=12,
                            )
                        )
        
        except Exception as e:
            logger.error("streaming plan failed: %s", e)
            yield _sse_event({"type": "error", "message": str(e)})
            logger.info("streaming plan failed")
            return
        
        yield _sse_event({"type": "done"})
        logger.info("streaming plan done")
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/plan/sync", response_model=PlanSyncResponse)
async def plan_travel_sync(request: TripRequest, graph=Depends(get_graph)):
    """
    旅行规划接口（同步返回）- 新版本
    """
    initial_state = create_initial_state(request)
    
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = await graph.ainvoke(initial_state, config)
    
    itinerary = result.get("itinerary_draft", {})
    updates = result.get("streaming_updates", "").split("\n")

    if itinerary:
        validated_itinerary = TripPlan.model_validate(itinerary)
        itinerary_response = ItineraryResponse(
            destination=validated_itinerary.city or request.destination,
            days=validated_itinerary.total_days or request.days,
            hotel=validated_itinerary.days[0].hotel if validated_itinerary.days else None,
            daily_plans=validated_itinerary.days,
            attraction_count=validated_itinerary.statistics.get("attraction_count", 0),
            restaurant_count=validated_itinerary.statistics.get("restaurant_count", 0),
            narrative_plan=validated_itinerary.narrative_plan,
        )
    else:
        itinerary_response = ItineraryResponse(
            destination=request.destination,
            days=request.days,
        )
    
    return PlanSyncResponse(
        success=result.get("status") == "completed",
        itinerary=itinerary_response,
        updates=[u.strip() for u in updates if u.strip()]
    )
