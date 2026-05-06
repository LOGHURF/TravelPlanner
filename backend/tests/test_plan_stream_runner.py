import asyncio

import pytest

from app.api.plan_stream_runner import STREAM_END, start_payload_producer


@pytest.mark.anyio
async def test_payload_producer_runs_without_waiting_for_sse_consumer() -> None:
    produced: list[int] = []

    async def payloads():
        for value in range(3):
            produced.append(value)
            yield {"type": "progress", "message": str(value)}

    queue, task = start_payload_producer(payloads())
    await asyncio.sleep(0)

    assert produced == [0, 1, 2]
    assert task.done()

    drained = []
    while True:
        item = await queue.get()
        if item is STREAM_END:
            break
        drained.append(item)

    assert [item["message"] for item in drained] == ["0", "1", "2"]


@pytest.mark.anyio
async def test_payload_producer_emits_error_event_for_exceptions() -> None:
    async def payloads():
        yield {"type": "progress", "message": "started"}
        raise RuntimeError("boom")

    queue, task = start_payload_producer(payloads())
    await task

    first = await queue.get()
    second = await queue.get()
    end = await queue.get()

    assert first == {"type": "progress", "message": "started"}
    assert second == {"type": "error", "message": "boom"}
    assert end is STREAM_END


@pytest.mark.anyio
async def test_payload_producer_logs_exceptions(caplog) -> None:
    async def payloads():
        raise RuntimeError("boom")
        yield {}

    queue, task = start_payload_producer(payloads())
    await task
    await queue.get()

    assert "payload producer failed" in caplog.text
