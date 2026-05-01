import asyncio
import json

from app.ai.nodes.attraction_node import (
    _clean_poi_to_attraction,
    _llm_decide,
    _search_pois,
    _normalize_attraction_types,
)
from app.ai.errors import ToolInvocationError
from app.services.amap import POI, POISearchResponse


def test_clean_poi_to_attraction_parses_required_fields() -> None:
    poi = POI(
        id="attraction-1",
        name="大理古城",
        address="大理古城人民路",
        type="风景名胜;风景名胜相关;旅游景点",
        typecode="110202",
        location="100.160,25.694",
        business={"rating": "4.2"},
        photos=[{"url": "https://example.com/attraction.jpg"}],
    )

    attraction = _clean_poi_to_attraction(poi)

    assert attraction is not None
    assert attraction["name"] == "大理古城"
    assert attraction["typecode"] == "110202"
    assert attraction["rating"] == 4.2
    assert attraction["photo"] == "https://example.com/attraction.jpg"


def test_clean_poi_to_attraction_rejects_non_attraction_typecode() -> None:
    poi = POI(
        id="hotel-1",
        name="景区旁度假酒店",
        address="景区入口",
        type="住宿服务;宾馆酒店;奢华酒店",
        typecode="100101",
        location="100.160,25.694",
        business={"rating": "4.6"},
    )

    attraction = _clean_poi_to_attraction(poi)

    assert attraction is None


def test_clean_poi_to_attraction_accepts_cultural_poi_outside_scenic_typecodes() -> None:
    poi = POI(
        id="museum-1",
        name="浙江省博物馆",
        address="西湖区孤山路",
        type="科教文化服务;博物馆;博物馆",
        typecode="140500",
        location="120.141,30.253",
        business={"rating": "4.7"},
    )

    attraction = _clean_poi_to_attraction(poi)

    assert attraction is not None
    assert attraction["name"] == "浙江省博物馆"
    assert attraction["typecode"] == "140500"
    assert attraction["category"] == "科教文化服务"


def test_normalize_attraction_types_accepts_valid_codes_and_aliases() -> None:
    result = _normalize_attraction_types(
        ["110202", "海洋馆", "寺庙", "无效类型"],
        keywords=["观景台"],
    )

    assert result == ["110202", "110104", "110205", "110209"]


def test_normalize_attraction_types_respects_allowed_types() -> None:
    result = _normalize_attraction_types(
        ["110202", "海洋馆", "寺庙"],
        allowed_types=["110104", "110205"],
    )

    assert result == ["110104", "110205"]


def test_search_pois_raises_when_tool_fails() -> None:
    class FailingTool:
        async def ainvoke(self, args):
            raise RuntimeError("network down")

    try:
        __import__("asyncio").run(
            _search_pois(
                FailingTool(),
                "杭州",
                keywords=["景点"],
                types=["110202"],
            )
        )
    except ToolInvocationError as exc:
        assert "maps_text_search failed" in str(exc)
    else:
        raise AssertionError("_search_pois swallowed the tool failure")


def test_search_pois_allows_keyword_only_cultural_search() -> None:
    class RecordingTool:
        def __init__(self) -> None:
            self.args = None

        async def ainvoke(self, args):
            self.args = args
            return POISearchResponse(
                status="1",
                count=1,
                pois=[
                    POI(
                        id="museum-1",
                        name="浙江省博物馆",
                        address="西湖区孤山路",
                        type="科教文化服务;博物馆;博物馆",
                        typecode="140500",
                        location="120.141,30.253",
                    )
                ],
            )

    tool = RecordingTool()

    result = asyncio.run(
        _search_pois(
            tool,
            "杭州",
            keywords=["博物馆"],
            types=[],
        )
    )

    assert tool.args["keywords"] == "博物馆"
    assert "types" not in tool.args
    assert [item["name"] for item in result] == ["浙江省博物馆"]


def test_search_pois_runs_each_keyword_as_independent_query() -> None:
    class RecordingTool:
        def __init__(self) -> None:
            self.calls = []

        async def ainvoke(self, args):
            self.calls.append(args)
            keyword = args["keywords"]
            return POISearchResponse(
                status="1",
                count=1,
                pois=[
                    POI(
                        id=keyword,
                        name=f"杭州{keyword}",
                        address="杭州",
                        type="风景名胜;风景名胜相关;旅游景点",
                        typecode="110202",
                        location="120.141,30.253",
                    )
                ],
            )

    tool = RecordingTool()

    result = asyncio.run(
        _search_pois(
            tool,
            "杭州",
            keywords=["博物馆", "历史街区"],
            types=[],
        )
    )

    assert [call["keywords"] for call in tool.calls] == ["博物馆", "历史街区"]
    assert [item["name"] for item in result] == ["杭州博物馆", "杭州历史街区"]


def test_llm_decide_keeps_keyword_only_search(monkeypatch) -> None:
    class Response:
        content = json.dumps(
            {
                "thought": "文化体验需要搜博物馆",
                "action": "search",
                "reason": "候选不足",
                "keywords": ["博物馆"],
                "types": [],
            },
            ensure_ascii=False,
        )

    class FakeLLM:
        def __init__(self) -> None:
            self.messages = None

        async def ainvoke(self, messages):
            self.messages = messages
            return Response()

    fake_llm = FakeLLM()
    monkeypatch.setattr("app.ai.nodes.attraction_node._json_llm", fake_llm)

    result = asyncio.run(
        _llm_decide(
            "杭州",
            ["文化体验"],
            "独自",
            "",
            4,
            [],
            "",
            [],
        )
    )

    assert result.keywords == ["博物馆"]
    assert result.types == []
    prompt = fake_llm.messages[0].content
    assert "types 是可选精确过滤器" in prompt
