"""Planner domain errors."""

from __future__ import annotations


class PlannerError(RuntimeError):
    """Base error for planning failures that must be surfaced to clients."""


class ToolInvocationError(PlannerError):
    """Raised when an external tool call fails or returns an invalid shape."""


class LLMJsonError(PlannerError):
    """Raised when an LLM call fails or does not return a valid JSON object."""


class NoCandidatesError(PlannerError):
    """Raised when a required retrieval step cannot produce enough candidates."""


class InvalidPlannerStateError(PlannerError):
    """Raised when required graph state is missing or inconsistent."""
