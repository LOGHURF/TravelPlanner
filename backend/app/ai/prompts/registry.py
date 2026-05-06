"""Centralized prompt template loading and rendering."""

from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Any, Literal

PromptId = Literal[
    "travel_strategy",
    "plan_evaluator",
    "final_summary",
]

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_TEMPLATE_FILES: dict[str, str] = {
    "travel_strategy": "travel_strategy.md",
    "plan_evaluator": "plan_evaluator.md",
    "final_summary": "final_summary.md",
}


def _load_template(prompt_id: str) -> Template:
    try:
        filename = _TEMPLATE_FILES[prompt_id]
    except KeyError as exc:
        raise KeyError(f"unknown prompt id: {prompt_id}") from exc

    path = _TEMPLATE_DIR / filename
    return Template(path.read_text(encoding="utf-8"))


def render_prompt(prompt_id: PromptId, variables: dict[str, Any] | None = None) -> str:
    """Render a managed prompt template with strict variable substitution."""
    data = {key: "" if value is None else value for key, value in (variables or {}).items()}
    return _load_template(prompt_id).substitute(data).strip()
