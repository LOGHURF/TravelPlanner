"""Reviewer 节点：对候选池做 LLM 评审与重排。

职责：
1) 接收 attraction/hotel 的 TopN 候选池。
2) 让 LLM 结合用户偏好挑选最终推荐索引。
3) 输出最终景点/酒店列表与评审说明。

图结构位置：
- 接收 fan_in 的信号
- 输出最终评审后的 attractions 和 hotels
- 连接到 restaurant_agent
"""

from __future__ import annotations

import json
from datetime import datetime
from itertools import combinations
from math import asin, ceil, comb, cos, radians, sin, sqrt
from typing import Any

from app.config import get_logger
from app.ai.errors import LLMJsonError
from app.ai.models.graph_models import TripState
from app.ai.prompts import render_prompt
from app.ai.utils import (
    distribute_attractions,
    distribute_hotels,
    invoke_prompt_json_async,
    parse_location,
)

logger = get_logger("ReviewerService")


def _safe_days(request: dict[str, Any]) -> int:
    """根据日期计算出行天数"""
    try:
        start = datetime.strptime(str(request.get("start_date", "")), "%Y-%m-%d").date()
        end = datetime.strptime(str(request.get("end_date", "")), "%Y-%m-%d").date()
        return max(1, (end - start).days + 1)
    except (TypeError, ValueError):
        return max(1, int(request.get("days", 1) or 1))


def _fallback_rank(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """兜底排序：按评分降序"""
    return sorted(items, key=lambda x: float(x.get("rating", 0.0) or 0.0), reverse=True)


def _normalize_attraction_name(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "")
    for suffix in ("旅游风景区", "风景名胜区", "旅游景区", "风景区", "景区", "景点"):
        text = text.replace(suffix, "")
    return text


def _attraction_identity_key(item: dict[str, Any]) -> tuple[str, str]:
    name = _normalize_attraction_name(item.get("name", ""))
    address = str(item.get("address", "") or "").strip().lower().replace(" ", "")
    return name, address


def _attraction_category_key(item: dict[str, Any]) -> str:
    raw_type = str(item.get("type", "") or "").strip()
    if raw_type:
        parts = [part.strip() for part in raw_type.split(";") if part.strip()]
        if parts:
            return parts[-1]
    category = str(item.get("category", "") or "").strip()
    if category:
        return category
    typecode = str(item.get("typecode", "") or "").strip()
    if typecode.startswith("11"):
        return typecode
    return ""


def _dedupe_attractions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """景点去重：同名同址或常见景区别名视为同一景点。"""
    deduped: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    seen_names: set[str] = set()
    for item in items:
        key = _attraction_identity_key(item)
        if key in seen_keys:
            continue
        if key[0] and key[0] in seen_names:
            continue
        seen_keys.add(key)
        if key[0]:
            seen_names.add(key[0])
        deduped.append(item)
    return deduped


def _diversify_attractions(selected: list[dict[str, Any]], fallback_items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    """尽量让最终景点类型更多样；若候选不足，再允许同类补位。"""
    combined = _dedupe_attractions(list(selected) + list(fallback_items))
    result: list[dict[str, Any]] = []
    used_keys: set[tuple[str, str]] = set()
    used_categories: set[str] = set()

    for item in combined:
        key = _attraction_identity_key(item)
        category = _attraction_category_key(item)
        if key in used_keys:
            continue
        if category and category in used_categories:
            continue
        result.append(item)
        used_keys.add(key)
        if category:
            used_categories.add(category)
        if len(result) >= limit:
            return result

    for item in combined:
        key = _attraction_identity_key(item)
        if key in used_keys:
            continue
        result.append(item)
        used_keys.add(key)
        if len(result) >= limit:
            break
    return result[:limit]


def _haversine_km(start: dict[str, float], end: dict[str, float]) -> float:
    """计算两点之间的球面距离（公里）"""
    lon1, lat1 = radians(start["lng"]), radians(start["lat"])
    lon2, lat2 = radians(end["lng"]), radians(end["lat"])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    arc = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(arc))


def _needed_hotels(days: int) -> int:
    """计算所需酒店数量（约每2天1家）"""
    return max(1, ceil(max(1, days) / 2))


def _retained_hotel_count(days: int) -> int:
    """计算应保留的酒店候选数量"""
    needed = _needed_hotels(days)
    return max(3, min(6, needed + 2))


def _nearest_neighbor_distance(item: dict[str, Any], others: list[dict[str, Any]]) -> float:
    """计算景点到最近邻的距离"""
    start = parse_location(item.get("location"))
    if not start:
        return 999.0
    distances: list[float] = []
    for other in others:
        if other is item:
            continue
        end = parse_location(other.get("location"))
        if not end:
            continue
        distances.append(_haversine_km(start, end))
    return min(distances) if distances else 999.0


def _distance_to_hotel(item: dict[str, Any], hotel: dict[str, Any] | None) -> float:
    """计算景点到酒店的距离"""
    hotel_loc = parse_location((hotel or {}).get("location"))
    item_loc = parse_location(item.get("location"))
    if not hotel_loc or not item_loc:
        return 999.0
    return round(_haversine_km(hotel_loc, item_loc), 2)


def _build_candidate_brief(items: list[dict[str, Any]], with_price: bool) -> list[dict[str, Any]]:
    """压缩候选信息，减少 prompt token"""
    brief: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        row = {
            "index": idx,
            "name": item.get("name", ""),
            "rating": float(item.get("rating", 0.0) or 0.0),
            "category": item.get("category", "") or item.get("type", ""),
            "address": item.get("address", ""),
        }
        if with_price:
            row["price_per_night"] = float(item.get("price_per_night", 0.0) or 0.0)
            row["hotel_level"] = item.get("hotel_level", "")
        brief.append(row)
    return brief


def _pick_by_indexes(items: list[dict[str, Any]], indexes: Any, limit: int) -> list[dict[str, Any]]:
    """按 LLM 返回索引提取候选"""
    if not isinstance(indexes, list):
        return []
    chosen: list[dict[str, Any]] = []
    used: set[int] = set()
    for raw in indexes:
        try:
            idx = int(raw)
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(items) or idx in used:
            continue
        used.add(idx)
        chosen.append(items[idx])
        if len(chosen) >= limit:
            break
    return chosen


def _top_up_selection(selected: list[dict[str, Any]], fallback_items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    """当 LLM 选不满时，用兜底排序结果补足"""
    if len(selected) >= limit:
        return selected[:limit]
    existing_keys = {(str(item.get("name", "")).strip(), str(item.get("address", "")).strip()) for item in selected}
    result = list(selected)
    for item in fallback_items:
        key = (str(item.get("name", "")).strip(), str(item.get("address", "")).strip())
        if key in existing_keys:
            continue
        result.append(item)
        existing_keys.add(key)
        if len(result) >= limit:
            break
    return result[:limit]


def _drop_far_outlier_attractions(selected: list[dict[str, Any]], fallback_items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    """去除距离过远的异常景点"""
    if len(selected) < 4:
        return selected[:limit]

    nearest = [_nearest_neighbor_distance(item, selected) for item in selected]
    valid = sorted(distance for distance in nearest if distance < 999)
    if len(valid) < 3:
        return selected[:limit]

    baseline = valid[len(valid) // 2]
    kept: list[dict[str, Any]] = []
    removed_keys: set[tuple[str, str]] = set()
    for item, distance in zip(selected, nearest):
        is_outlier = distance >= 20 and distance >= max(12, baseline * 2.5)
        if is_outlier and len(selected) > 3:
            removed_keys.add((str(item.get("name", "")).strip(), str(item.get("address", "")).strip()))
            continue
        kept.append(item)

    if len(kept) >= limit:
        return kept[:limit]

    fallback_without_removed = [item for item in fallback_items if (str(item.get("name", "")).strip(), str(item.get("address", "")).strip()) not in removed_keys]
    return _top_up_selection(kept, fallback_without_removed, limit=limit)


def _required_count(items: list[dict[str, Any]], target: int) -> int:
    """计算需要选择的数量"""
    return min(max(0, target), len(items))


def _target_attractions_per_day(days: int, attraction_count: int) -> int:
    """计算每日目标景点数量"""
    if days <= 0 or attraction_count <= 0:
        return 0
    if attraction_count >= days * 2:
        return 2
    return 1


def _distance_between_items(start: dict[str, Any], end: dict[str, Any]) -> float:
    """计算两个景点之间的距离"""
    start_loc = parse_location(start.get("location"))
    end_loc = parse_location(end.get("location"))
    if not start_loc or not end_loc:
        return 999.0
    return round(_haversine_km(start_loc, end_loc), 2)


def _day_route_score(day_items: list[dict[str, Any]], hotel: dict[str, Any] | None) -> float:
    """计算一天路线的得分（距离越低越好）"""
    if not day_items:
        return 0.0
    if len(day_items) == 1:
        return _distance_to_hotel(day_items[0], hotel) * 2 if hotel else 0.0

    best_score = float("inf")
    candidate_orders = [day_items, list(reversed(day_items))]
    for ordered in candidate_orders:
        score = _distance_to_hotel(ordered[0], hotel) if hotel else 0.0
        for index in range(len(ordered) - 1):
            score += _distance_between_items(ordered[index], ordered[index + 1])
        score += _distance_to_hotel(ordered[-1], hotel) if hotel else 0.0
        best_score = min(best_score, score)
    return best_score


def _flatten_groups(groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """展开分组列表"""
    return [item for group in groups for item in group]


def _selection_score(selected_attractions: list[dict[str, Any]], hotels: list[dict[str, Any]], *, days: int) -> tuple[float, list[dict[str, Any]]]:
    """计算景点选择得分"""
    target_per_day = _target_attractions_per_day(days, len(selected_attractions))
    day_groups = distribute_attractions(selected_attractions, days, target_per_day)
    day_hotels = distribute_hotels(hotels, days, stay_span=2, day_attractions=day_groups)
    distance_score = sum(
        _day_route_score(day_items, day_hotels[index] if index < len(day_hotels) else None)
        for index, day_items in enumerate(day_groups)
    )
    rating_bonus = sum(float(item.get("rating", 0) or 0) for item in selected_attractions) * 2.0
    category_keys = [_attraction_category_key(item) for item in selected_attractions if _attraction_category_key(item)]
    category_penalty = max(0, len(category_keys) - len(set(category_keys))) * 4.0
    return distance_score - rating_bonus + category_penalty, _flatten_groups(day_groups)


def _optimize_attraction_selection(candidates: list[dict[str, Any]], hotels: list[dict[str, Any]], *, days: int, limit: int) -> list[dict[str, Any]]:
    """优化景点选择（组合优化）"""
    prepared = _fallback_rank(candidates)
    if limit <= 0 or not prepared:
        return []
    if len(prepared) <= limit:
        return prepared[:limit]

    search_space = prepared[:max(limit, min(len(prepared), 12))]
    if comb(len(search_space), limit) > 5000:
        search_space = search_space[:limit + 4]

    best_score = float("inf")
    best_selection = prepared[:limit]
    for combo in combinations(search_space, limit):
        score, ordered = _selection_score(list(combo), hotels, days=days)
        if score < best_score:
            best_score = score
            best_selection = ordered
    return best_selection[:limit]


def _hotel_distance_to_selection(hotel: dict[str, Any], attractions: list[dict[str, Any]]) -> float:
    """计算酒店到景点的平均距离"""
    distances = [_distance_to_hotel(item, hotel) for item in attractions]
    valid = [distance for distance in distances if distance < 999]
    if not valid:
        return 999.0
    return round(sum(valid) / len(valid), 2)


def _hotel_combo_score(hotels: list[dict[str, Any]], attractions: list[dict[str, Any]], *, days: int) -> float:
    """计算酒店组合得分"""
    if not hotels:
        return float("inf")

    target_per_day = _target_attractions_per_day(days, len(attractions))
    day_groups = distribute_attractions(attractions, days, target_per_day)
    distance_score = 0.0
    for day_items in day_groups:
        if not day_items:
            continue
        distance_score += min(sum(_distance_to_hotel(item, hotel) for item in day_items) for hotel in hotels)
    rating_bonus = sum(float(item.get("rating", 0) or 0) for item in hotels) * 0.5
    return distance_score - rating_bonus


def _optimize_hotel_selection(candidates: list[dict[str, Any]], attractions: list[dict[str, Any]], *, days: int, limit: int) -> list[dict[str, Any]]:
    """优化酒店选择"""
    prepared = _fallback_rank(candidates)
    if limit <= 0 or not prepared:
        return []
    if len(prepared) <= limit or not attractions:
        return prepared[:limit]

    best_score = float("inf")
    best_selection = prepared[:limit]
    for combo in combinations(prepared, limit):
        score = _hotel_combo_score(list(combo), attractions, days=days)
        if score < best_score:
            best_score = score
            best_selection = list(combo)

    return sorted(
        best_selection,
        key=lambda item: (_hotel_distance_to_selection(item, attractions), -float(item.get("rating", 0) or 0), item.get("name", "")),
    )[:limit]


def _build_prompt_variables(
    *,
    request: dict[str, Any],
    needed_attractions: int,
    needed_hotels: int,
    retained_hotels: int,
    attraction_brief: list[dict[str, Any]],
    hotel_brief: list[dict[str, Any]],
    retry_instruction: str = "",
) -> dict[str, Any]:
    """构造评审提示词变量"""
    context = {
        "destination": request.get("destination", ""),
        "days": request.get("days", request.get("duration", 1)),
        "num_people": request.get("num_people", 1),
        "companions": request.get("companions", "朋友"),
        "style_preferences": request.get("style_preferences", []),
        "hotel_level": request.get("hotel_level", "舒适型"),
        "needed_attractions": needed_attractions,
        "needed_hotels": needed_hotels,
        "retained_hotels": retained_hotels,
    }
    return {
        "needed_attractions": needed_attractions,
        "needed_hotels": needed_hotels,
        "retained_hotels": retained_hotels,
        "retry_instruction": retry_instruction,
        "context_json": json.dumps(context, ensure_ascii=False),
        "attraction_brief_json": json.dumps(attraction_brief, ensure_ascii=False),
        "hotel_brief_json": json.dumps(hotel_brief, ensure_ascii=False),
    }


def _selection_retry_instruction(*, selected_count: int, available_count: int, required_count: int) -> str:
    return render_prompt(
        "selection_retry",
        {
            "selected_count": selected_count,
            "available_count": available_count,
            "required_count": required_count,
        },
    )


async def reviewer_node(state: TripState) -> dict[str, Any]:
    """执行候选评审并输出最终选择"""
    request = state.get("request", {})
    days = _safe_days(request)
    needed = max(1, int(state.get("needed_attractions", days * 2) or days * 2))
    needed_hotels = _needed_hotels(days)
    retained_hotels = _retained_hotel_count(days)

    attraction_candidates = list(state.get("attraction_candidates") or state.get("attractions") or [])
    hotel_candidates = list(state.get("hotel_candidates") or state.get("hotels") or [])

    attraction_ranked = _dedupe_attractions(_fallback_rank(attraction_candidates))
    hotel_ranked = _fallback_rank(hotel_candidates)
    required_attractions = _required_count(attraction_ranked, needed)
    required_hotels = _required_count(hotel_ranked, retained_hotels)

    prompt_variables = _build_prompt_variables(
        request=request,
        needed_attractions=needed,
        needed_hotels=needed_hotels,
        retained_hotels=retained_hotels,
        attraction_brief=_build_candidate_brief(attraction_ranked, with_price=False),
        hotel_brief=_build_candidate_brief(hotel_ranked, with_price=True),
    )
    llm_data = await invoke_prompt_json_async(
        prompt_id="reviewer_selection",
        variables=prompt_variables,
        temperature=1.2,
    )

    # 处理景点选择
    selected_attractions = _pick_by_indexes(attraction_ranked, llm_data.get("selected_attraction_indexes"), limit=required_attractions)
    if len(selected_attractions) != required_attractions:
        retry_variables = {
            **prompt_variables,
            "retry_instruction": _selection_retry_instruction(
                selected_count=len(selected_attractions),
                available_count=len(attraction_ranked),
                required_count=required_attractions,
            ),
        }
        llm_data_retry = await invoke_prompt_json_async(
            prompt_id="reviewer_selection",
            variables=retry_variables,
            temperature=0.6,
        )
        selected_attractions = _pick_by_indexes(attraction_ranked, llm_data_retry.get("selected_attraction_indexes"), limit=required_attractions)
        if llm_data_retry.get("reviewer_notes"):
            llm_data["reviewer_notes"] = llm_data_retry.get("reviewer_notes")
    if len(selected_attractions) != required_attractions:
        raise LLMJsonError(
            f"reviewer returned insufficient attraction indexes: got={len(selected_attractions)} required={required_attractions}"
        )

    selected_attractions = _drop_far_outlier_attractions(selected_attractions, attraction_ranked, limit=required_attractions)[:required_attractions]
    selected_attractions = _diversify_attractions(selected_attractions, attraction_ranked, limit=required_attractions)

    # 处理酒店选择
    selected_hotels = _pick_by_indexes(hotel_ranked, llm_data.get("selected_hotel_indexes"), limit=required_hotels)
    if len(selected_hotels) != required_hotels:
        retry_variables = {
            **prompt_variables,
            "retry_instruction": _selection_retry_instruction(
                selected_count=len(selected_hotels),
                available_count=len(hotel_ranked),
                required_count=required_hotels,
            ),
        }
        llm_data_retry = await invoke_prompt_json_async(
            prompt_id="reviewer_selection",
            variables=retry_variables,
            temperature=0.6,
        )
        selected_hotels = _pick_by_indexes(hotel_ranked, llm_data_retry.get("selected_hotel_indexes"), limit=required_hotels)
        if llm_data_retry.get("reviewer_notes"):
            llm_data["reviewer_notes"] = llm_data_retry.get("reviewer_notes")
    if len(selected_hotels) != required_hotels:
        raise LLMJsonError(
            f"reviewer returned insufficient hotel indexes: got={len(selected_hotels)} required={required_hotels}"
        )

    selected_hotels = _top_up_selection(
        selected_hotels,
        _optimize_hotel_selection(hotel_ranked, selected_attractions, days=days, limit=required_hotels),
        limit=required_hotels,
    )

    # 处理评审说明
    notes_raw = llm_data.get("reviewer_notes")
    reviewer_notes = [str(x).strip() for x in notes_raw] if isinstance(notes_raw, list) else []
    reviewer_notes = [x for x in reviewer_notes if x]
    if not reviewer_notes:
        reviewer_notes = ["已按候选索引和路线约束完成评审。"]
    reviewer_notes.insert(0, "已使用LLM完成候选评审与重排。")

    logger.info(
        "reviewer done used_llm=%s attractions=%s->%s hotels=%s->%s needed_hotels=%s retained_hotels=%s",
        True, len(attraction_candidates), len(selected_attractions), len(hotel_candidates), len(selected_hotels), needed_hotels, required_hotels,
    )
    return {
        "attractions": selected_attractions,
        "hotels": selected_hotels,
        "reviewer_notes": reviewer_notes,
        "streaming_updates": f"\n评审完成: 景点{len(selected_attractions)}个, 酒店备选{len(selected_hotels)}家",
        "completed_agents": ["reviewer"],
    }
