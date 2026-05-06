"""Shared helpers for the strategy-first travel planning nodes."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any

from app.ai.models import Attraction, Hotel, Restaurant
from app.ai.utils import parse_float, parse_int, parse_location
from app.services.amap import POI


def location_from_poi(poi: POI, *, prefer_navi: bool = True) -> dict[str, float] | None:
    """Return a route-friendly location from AMap POI data."""
    if prefer_navi and isinstance(poi.navi, dict):
        navi_location = parse_location(poi.navi.get("entr_location"))
        if navi_location:
            return navi_location
    return parse_location(poi.location)


def location_text(location: dict[str, float] | None) -> str:
    if not location:
        return ""
    return f"{location['lng']},{location['lat']}"


def straight_line_distance_km(start: dict[str, float], end: dict[str, float]) -> float:
    """Calculate direct distance between two parsed coordinates."""
    lon1, lat1 = radians(start["lng"]), radians(start["lat"])
    lon2, lat2 = radians(end["lng"]), radians(end["lat"])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    arc = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return round(6371.0 * 2 * asin(sqrt(arc)), 3)


def poi_photo_urls(poi: POI) -> list[str]:
    return [photo.url for photo in poi.photos if photo.url]


def poi_rating(poi: POI) -> float:
    return parse_float(poi.business.rating or poi.biz_ext.rating)


def poi_cost(poi: POI) -> float:
    return parse_float(poi.business.cost or poi.biz_ext.cost)


def anchor_from_poi(
    *,
    query: str,
    day_index: int | None,
    role: str,
    poi: POI,
    confidence: float,
    display_name: str | None = None,
) -> dict[str, Any]:
    location = location_from_poi(poi)
    raw_location = parse_location(poi.location)
    return {
        "query": query,
        "day_index": day_index,
        "role": role,
        "name": display_name or poi.name,
        "poi_name": poi.name,
        "poi_id": poi.id,
        "type": poi.type,
        "typecode": poi.typecode,
        "address": poi.address,
        "cityname": poi.cityname,
        "adname": poi.adname,
        "business_area": poi.business.business_area,
        "location": location,
        "raw_location": raw_location,
        "navi": poi.navi,
        "rating": poi_rating(poi),
        "open_time2": poi.business.opentime2 or poi.biz_ext.opentime2,
        "photos": poi_photo_urls(poi),
        "confidence": confidence,
    }


def anchor_to_attraction(anchor: dict[str, Any]) -> dict[str, Any]:
    attraction = Attraction(
        name=str(anchor.get("name", "") or anchor.get("query", "")).strip(),
        address=str(anchor.get("address", "") or ""),
        location=anchor.get("location"),
        description=str(anchor.get("type", "") or ""),
        keytag=str(anchor.get("type", "") or ""),
        type=str(anchor.get("type", "") or ""),
        photos=list(anchor.get("photos") or []),
        rating=float(anchor.get("rating", 0) or 0),
        category=str(anchor.get("role", "") or "景点"),
        tags=[str(anchor.get("business_area", "") or ""), str(anchor.get("adname", "") or "")],
        visit_duration="2小时",
        open_hours=str(anchor.get("open_time2", "") or ""),
        open_time2=str(anchor.get("open_time2", "") or ""),
        photo=(list(anchor.get("photos") or []) or [""])[0],
    )
    payload = attraction.model_dump()
    payload["day_index"] = int(anchor.get("day_index", 0) or 0)
    payload["poi_id"] = str(anchor.get("poi_id", "") or "")
    payload["source_query"] = str(anchor.get("query", "") or "")
    payload["confidence"] = float(anchor.get("confidence", 0) or 0)
    return payload


def poi_to_hotel(poi: POI, *, hotel_level: str) -> dict[str, Any]:
    photos = poi_photo_urls(poi)
    price = poi_cost(poi)
    hotel = Hotel(
        name=poi.name,
        address=poi.address,
        location=location_from_poi(poi),
        description=f"{hotel_level}，{poi.business.business_area or poi.adname}，{poi.type}",
        keytag=poi.type,
        type=poi.type,
        photos=photos,
        rating=poi_rating(poi),
        hotel_level=hotel_level,
        price_per_night=price,
        total_price=price,
        distance_to_center=poi.business.business_area or poi.adname,
        distance=poi.distance,
        amenities=[item.strip() for item in poi.type.split(";") if item.strip()],
        open_time2=poi.business.opentime2 or poi.biz_ext.opentime2,
        photo=(photos or [""])[0],
        image_url=(photos or [""])[0],
    )
    payload = hotel.model_dump()
    payload["poi_id"] = poi.id
    return payload


def poi_to_restaurant(poi: POI, *, keyword: str, meal_type: str, day_index: int) -> dict[str, Any]:
    photos = poi_photo_urls(poi)
    cost = parse_int(poi.business.cost or poi.biz_ext.cost)
    restaurant = Restaurant(
        name=poi.name,
        type=poi.type,
        meal_type=meal_type,
        address=poi.address,
        location=location_from_poi(poi),
        description=f"{keyword}，{poi.business.business_area or poi.adname}，{poi.type}",
        keytag=keyword,
        photos=photos,
        rating=poi_rating(poi),
        estimated_cost=cost,
        price_per_person=cost,
        cuisine_type=keyword,
        open_time2=poi.business.opentime2 or poi.biz_ext.opentime2,
        photo=(photos or [""])[0],
    )
    payload = restaurant.model_dump()
    payload["day_index"] = day_index
    payload["poi_id"] = poi.id
    payload["source_keyword"] = keyword
    return payload
