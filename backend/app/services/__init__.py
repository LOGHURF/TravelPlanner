"""Services package - External service integrations."""
from app.services.amap import (
    POI,
    POIPhoto,
    POIBusiness,
    POIBizExt,
    POISearchResponse,
    WeatherInfo,
    WeatherResponse,
    get_city_weather,
    get_driving_route,
    get_transit_integrated_route,
    search_pois_by_text,
    search_pois_nearby,
)

__all__ = [
    "POI",
    "POIPhoto",
    "POIBusiness",
    "POIBizExt",
    "POISearchResponse",
    "WeatherInfo",
    "WeatherResponse",
    "get_city_weather",
    "get_driving_route",
    "get_transit_integrated_route",
    "search_pois_by_text",
    "search_pois_nearby",
]
