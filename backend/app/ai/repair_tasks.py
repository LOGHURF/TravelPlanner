"""Helpers for evaluator-driven targeted repair tasks."""

from __future__ import annotations

from typing import Any

from app.ai.models.graph_models import TripState


def agent_repair_tasks(state: TripState, agent_id: str) -> list[dict[str, Any]]:
    tasks = state.get("active_repair_tasks") or []
    if not isinstance(tasks, list):
        raise ValueError("active_repair_tasks must be a list")

    result: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("repair task must be an object")
        agent = str(task.get("agent", "")).strip()
        if not agent:
            raise ValueError("repair task agent is required")
        task_name = str(task.get("task", "")).strip()
        if not task_name:
            raise ValueError("repair task name is required")
        constraints = task.get("constraints", {})
        if constraints is None:
            constraints = {}
        if not isinstance(constraints, dict):
            raise ValueError("repair task constraints must be an object")
        if agent == agent_id:
            result.append({**task, "agent": agent, "task": task_name, "constraints": constraints})
    return result


def _append_text_values(result: list[str], value: Any) -> None:
    if isinstance(value, str):
        text = value.strip()
        if text:
            result.append(text)
        return
    if isinstance(value, list):
        for item in value:
            _append_text_values(result, item)


def repair_keywords_for_agent(state: TripState, agent_id: str) -> list[str]:
    keywords: list[str] = []
    for task in agent_repair_tasks(state, agent_id):
        constraints = task["constraints"]
        for key in (
            "areas",
            "area",
            "location_area",
            "near",
            "nearby",
            "include",
            "style",
            "styles",
            "keywords",
        ):
            _append_text_values(keywords, constraints.get(key))

    result: list[str] = []
    for keyword in keywords:
        if keyword not in result:
            result.append(keyword)
    return result
