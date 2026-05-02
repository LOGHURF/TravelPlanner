import asyncio

from app.ai.nodes.attraction_node import (
    attraction_node,
    _clean_poi_to_attraction,
    _search_pois,
    _normalize_attraction_types,
)
from app.ai.errors import ToolInvocationError
from app.ai.utils import build_attraction_keywords
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


def test_normalize_attraction_types_accepts_explicit_typecodes_only() -> None:
    result = _normalize_attraction_types(
        "110202|140500",
    )

    assert result == ["110202", "140500"]


def test_normalize_attraction_types_rejects_alias_words() -> None:
    try:
        _normalize_attraction_types(["110202", "海洋馆"])
    except ValueError as exc:
        assert "invalid attraction typecode" in str(exc)
    else:
        raise AssertionError("attraction type aliases should not be silently accepted")


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


def test_search_pois_rejects_empty_keywords_without_blank_search() -> None:
    class UnexpectedTool:
        async def ainvoke(self, args):
            raise AssertionError("blank attraction search should not call the map tool")

    try:
        asyncio.run(
            _search_pois(
                UnexpectedTool(),
                "杭州",
                keywords=[],
                types=[],
            )
        )
    except ValueError as exc:
        assert "attraction search requires keywords" in str(exc)
    else:
        raise AssertionError("empty attraction keywords should fail fast")


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


def test_build_attraction_keywords_uses_recall_terms_not_named_hangzhou_pois() -> None:
    keywords = build_attraction_keywords(
        {
            "destination": "杭州",
            "companions": "情侣",
            "style_preferences": ["自然风光", "文化体验"],
            "pace": "适中",
        },
        limit=8,
    )

    assert all("西湖" not in keyword for keyword in keywords)
    assert all("灵隐" not in keyword for keyword in keywords)
    assert all("西溪" not in keyword for keyword in keywords)
    assert all("良渚" not in keyword for keyword in keywords)
    assert {"湖景", "湿地公园", "博物馆"}.issubset(set(keywords))


def test_build_attraction_keywords_does_not_add_generic_presets_without_signal() -> None:
    keywords = build_attraction_keywords(
        {
            "destination": "未知城市",
            "companions": "情侣",
            "style_preferences": [],
            "pace": "紧凑",
            "special_requirements": "",
        },
        limit=8,
    )

    assert keywords == []


def test_attraction_node_uses_hotspot_keywords_before_preference_keywords_and_skips_llm(monkeypatch) -> None:
    captured_keywords: list[str] = []

    async def fake_search_pois(tool, region, keywords, types, page=1):
        captured_keywords.extend(keywords)
        return [
            {
                "name": f"{keyword}{index}",
                "address": "杭州",
                "rating": 4.8,
                "photo": "",
                "location": {"lat": 30.2 + index / 1000, "lng": 120.1},
            }
            for keyword in keywords
            for index in range(2)
        ]

    async def fail_if_llm_is_called(**kwargs):
        raise AssertionError("attraction recall keywords should not be planned by LLM")

    monkeypatch.setattr("app.ai.nodes.attraction_node.get_tool", lambda tool_name: object())
    monkeypatch.setattr("app.ai.nodes.attraction_node._search_pois", fake_search_pois)
    monkeypatch.setattr(
        "app.ai.nodes.attraction_node._plan_recall_keywords_with_llm",
        fail_if_llm_is_called,
        raising=False,
    )

    result = asyncio.run(
        attraction_node(
            {
                "request": {
                    "destination": "杭州",
                    "companions": "情侣",
                    "style_preferences": ["自然风光", "文化体验"],
                    "pace": "适中",
                    "special_requirements": "",
                    "types": "",
                },
                "style_preferences": ["自然风光", "文化体验"],
                "companions": "情侣",
                "needed_attractions": 6,
                "attraction_candidates": [],
                "mcp_search_types": "",
            }
        )
    )

    assert len(result["attractions"]) == 6
    assert captured_keywords == ["热门景点", "旅游景点", "湖景", "历史街区"]
    assert result["attraction_query_keywords"] == ["热门景点", "旅游景点", "湖景", "历史街区"]


def test_attraction_node_requires_destination_before_search(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.ai.nodes.attraction_node.get_tool",
        lambda tool_name: (_ for _ in ()).throw(AssertionError("map tool should not be requested")),
    )

    try:
        asyncio.run(
            attraction_node(
                {
                    "request": {
                        "destination": "",
                        "style_preferences": [],
                        "types": "",
                    },
                    "style_preferences": [],
                    "needed_attractions": 2,
                    "attraction_candidates": [],
                    "mcp_search_types": "",
                }
            )
        )
    except ValueError as exc:
        assert "destination is required" in str(exc)
    else:
        raise AssertionError("missing destination should fail before search")


def test_attraction_node_requires_needed_attractions_before_search(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.ai.nodes.attraction_node.get_tool",
        lambda tool_name: (_ for _ in ()).throw(AssertionError("map tool should not be requested")),
    )

    try:
        asyncio.run(
            attraction_node(
                {
                    "request": {
                        "destination": "杭州",
                        "style_preferences": [],
                        "types": "",
                    },
                    "style_preferences": [],
                    "attraction_candidates": [],
                    "mcp_search_types": "",
                }
            )
        )
    except ValueError as exc:
        assert "needed_attractions is required" in str(exc)
    else:
        raise AssertionError("missing needed_attractions should fail before search")


def test_attraction_node_interleaves_map_results_by_keyword_without_rating_resorting(monkeypatch) -> None:
    class RecordingTool:
        def __init__(self) -> None:
            self.keyword_index = 0

        async def ainvoke(self, args):
            keyword = args["keywords"]
            keyword_index = self.keyword_index
            self.keyword_index += 1
            return POISearchResponse(
                status="1",
                count=2,
                pois=[
                    POI(
                        id=f"{keyword}-{index}",
                        name=f"{keyword}{index}",
                        address="杭州",
                        type="风景名胜;风景名胜相关;旅游景点",
                        typecode="110202",
                        location=f"120.1,{30.2 + index / 1000}",
                        business={"rating": str(3.0 + keyword_index / 10)},
                    )
                    for index in range(2)
                ],
            )

    tool = RecordingTool()
    monkeypatch.setattr("app.ai.nodes.attraction_node.get_tool", lambda tool_name: tool)

    result = asyncio.run(
        attraction_node(
            {
                "request": {
                    "destination": "杭州",
                    "companions": "情侣",
                    "style_preferences": ["自然风光", "文化体验"],
                    "pace": "适中",
                    "special_requirements": "",
                    "types": "",
                },
                "style_preferences": ["自然风光", "文化体验"],
                "companions": "情侣",
                "needed_attractions": 4,
                "attraction_candidates": [],
                "mcp_search_types": "",
            }
        )
    )

    assert [item["name"] for item in result["attractions"]] == [
        "热门景点0",
        "旅游景点0",
        "湖景0",
        "历史街区0",
    ]
