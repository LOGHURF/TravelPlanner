import asyncio

from app.ai.errors import LLMJsonError
from app.ai import utils


class _FakeResponse:
    content = "not json"


class _FakeChatOpenAI:
    last_kwargs = {}

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _FakeChatOpenAI.last_kwargs = kwargs

    async def ainvoke(self, prompt):
        return _FakeResponse()


class _FakeJsonResponse:
    content = '{"ok": true}'


class _FakeJsonChatOpenAI(_FakeChatOpenAI):
    async def ainvoke(self, prompt):
        return _FakeJsonResponse()


def test_invoke_llm_json_async_raises_on_non_json(monkeypatch) -> None:
    monkeypatch.setattr(utils.settings, "LLM_API_KEY", "sk-test")
    monkeypatch.setattr(utils, "ChatOpenAI", _FakeChatOpenAI)

    try:
        asyncio.run(utils.invoke_llm_json_async(prompt="return json", temperature=0.2))
    except LLMJsonError as exc:
        assert "valid JSON object" in str(exc)
    else:
        raise AssertionError("invoke_llm_json_async returned a fallback instead of raising")


def test_invoke_llm_json_async_requests_json_object_response(monkeypatch) -> None:
    monkeypatch.setattr(utils.settings, "LLM_API_KEY", "sk-test")
    monkeypatch.setattr(utils, "ChatOpenAI", _FakeJsonChatOpenAI)

    data = asyncio.run(utils.invoke_llm_json_async(prompt="return json", temperature=0.2))

    assert data == {"ok": True}
    assert _FakeJsonChatOpenAI.last_kwargs["model_kwargs"] == {
        "response_format": {"type": "json_object"},
        "max_tokens": 2048,
    }


def test_invoke_llm_json_async_allows_smaller_output_limit(monkeypatch) -> None:
    monkeypatch.setattr(utils.settings, "LLM_API_KEY", "sk-test")
    monkeypatch.setattr(utils, "ChatOpenAI", _FakeJsonChatOpenAI)

    asyncio.run(utils.invoke_llm_json_async(prompt="return json", temperature=0.2, max_tokens=768))

    assert _FakeJsonChatOpenAI.last_kwargs["model_kwargs"]["max_tokens"] == 768


def test_invoke_prompt_json_async_renders_managed_template(monkeypatch) -> None:
    seen_prompt = ""

    class FakePromptChatOpenAI(_FakeJsonChatOpenAI):
        async def ainvoke(self, prompt):
            nonlocal seen_prompt
            seen_prompt = prompt
            return _FakeJsonResponse()

    monkeypatch.setattr(utils.settings, "LLM_API_KEY", "sk-test")
    monkeypatch.setattr(utils, "ChatOpenAI", FakePromptChatOpenAI)

    data = asyncio.run(
        utils.invoke_prompt_json_async(
            prompt_id="travel_strategy",
            variables={
                "days": 2,
                "request_context_json": '{"destination":"杭州","days":2}',
            },
            temperature=0.2,
            max_tokens=512,
        )
    )

    assert data == {"ok": True}
    assert "必须返回 2 天" in seen_prompt
    assert _FakeJsonChatOpenAI.last_kwargs["model_kwargs"]["max_tokens"] == 512
