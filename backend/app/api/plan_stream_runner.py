"""Background producer for travel planning SSE payloads."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.config import get_logger

STREAM_END = object()
logger = get_logger("PlanStreamRunner")


def start_payload_producer(
    payloads: AsyncIterator[dict[str, Any]],
) -> tuple[asyncio.Queue[dict[str, Any] | object], asyncio.Task[None]]:
    """Run a payload iterator in the background and expose an event queue."""
    queue: asyncio.Queue[dict[str, Any] | object] = asyncio.Queue()

    async def produce() -> None:
        try:
            async for payload in payloads:
                await queue.put(payload)
        except Exception as exc:
            logger.exception("payload producer failed")
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(STREAM_END)

    return queue, asyncio.create_task(produce())
