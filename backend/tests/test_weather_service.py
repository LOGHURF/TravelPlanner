from app.ai.nodes import weather_node as weather_service
from app.services.amap import WeatherInfo as AMapWeatherInfo, WeatherResponse


async def _fake_invoke_tool_with_debug(**_: object) -> dict[str, object]:
    return {
        "status": "1",
        "info": "OK",
        "infocode": "10000",
        "province": "云南",
        "city": "大理白族自治州",
        "adcode": "532900",
        "weather": "",
        "temperature": "",
        "winddirection": "",
        "windpower": "",
        "humidity": "",
        "reporttime": "",
        "forecasts": [
            {
                "date": "2026-03-02",
                "day_weather": "晴",
                "night_weather": "多云",
                "day_temp": "18",
                "night_temp": "7",
                "wind_direction": "西南",
                "wind_power": "3",
                "humidity": "",
                "province": "",
                "city": "",
                "adcode": "",
                "reporttime": "",
            }
        ],
    }


def test_collect_mcp_result_parses_dict_payload(monkeypatch) -> None:
    monkeypatch.setattr(weather_service, "get_tool", lambda name: object() if name == "maps_weather" else None)
    monkeypatch.setattr(weather_service, "invoke_tool_with_debug", _fake_invoke_tool_with_debug)

    result = __import__("asyncio").run(
        weather_service._collect_mcp_result(
            tool_name="maps_weather",
            request={"destination": "大理"},
        )
    )

    assert result.city == "大理白族自治州"
    assert len(result.forecasts) == 1
    assert result.forecasts[0].date == "2026-03-02"


def test_format_weather_response_converts_forecasts_without_llm() -> None:
    response = WeatherResponse(
        city="大理白族自治州",
        forecasts=[
            AMapWeatherInfo(
                date="2026-03-02",
                day_weather="晴",
                night_weather="多云",
                day_temp="18",
                night_temp="7",
                wind_direction="西南",
                wind_power="3",
            )
        ],
    )

    items = weather_service._format_weather_response(response, limit=4)

    assert len(items) == 1
    assert items[0]["day_temp"] == 18
    assert items[0]["night_temp"] == 7
    assert items[0]["day_weather"] == "晴"
