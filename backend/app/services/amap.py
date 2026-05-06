"""AMap (高德地图) HTTP API 封装模块。

该模块直接调用高德地图的 REST API，不是 MCP 协议。
提供 POI 搜索、天气查询、路径规划等功能。

主要功能：
1. POI 关键词搜索 (search_pois_by_text)
2. POI 周边搜索 (search_pois_nearby)
3. 城市天气查询 (get_city_weather)
4. 公交路径规划 (get_transit_integrated_route)
5. 驾车路径规划 (get_driving_route)

使用方式：
    from app.services.amap import search_pois_by_text, get_city_weather
"""

from __future__ import annotations

from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from app.config import settings

AMAP_V5_BASE_URL = "https://restapi.amap.com/v5"
AMAP_V3_BASE_URL = "https://restapi.amap.com/v3"
DEFAULT_SHOW_FIELDS = "business,children,indoor,navi,photos"


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic 模型定义
# ═══════════════════════════════════════════════════════════════════════════════


class POIPhoto(BaseModel):
    """POI 照片"""
    url: str = ""


class POIBizExt(BaseModel):
    """POI 扩展业务信息"""
    rating: str = ""
    cost: str = ""
    opentime2: str = ""


class POIBusiness(BaseModel):
    """POI 商业信息"""
    rating: str = ""
    cost: str = ""
    business_area: str = ""
    opentime2: str = ""


class POI(BaseModel):
    """POI (Point of Interest) 数据结构。

    包含景点的完整信息：名称、地址、坐标、类型、评分、照片等。
    """
    id: str = ""
    name: str = ""
    address: str = ""
    location: str = ""
    type: str = ""
    typecode: str = ""
    adname: str = ""
    cityname: str = ""
    pname: str = ""
    distance: str = ""
    tel: str = ""
    photos: list[POIPhoto] = Field(default_factory=list)
    business: POIBusiness = Field(default_factory=POIBusiness)
    biz_ext: POIBizExt = Field(default_factory=POIBizExt)
    indoor: dict[str, Any] = Field(default_factory=dict)
    navi: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Optional[POI]:
        """从高德原始 POI 数据转换。

        Args:
            data: 高德 API 返回的原始 POI 字典

        Returns:
            POI 实例，如果数据无效则返回 None
        """
        if not isinstance(data, dict) or not data.get("name"):
            return None

        # 解析 photos
        raw_photos = data.get("photos", [])
        photos = []
        if isinstance(raw_photos, list):
            for item in raw_photos:
                if isinstance(item, str):
                    if item.strip():
                        photos.append(POIPhoto(url=item.strip()))
                elif isinstance(item, dict):
                    url = item.get("url", "") or item.get("photo", "") or item.get("photo_url", "")
                    if url:
                        photos.append(POIPhoto(url=str(url).strip()))

        # 解析 business
        raw_business = data.get("business", {})
        if not isinstance(raw_business, dict):
            raw_business = {}

        rating = raw_business.get("rating") or data.get("rating") or ""
        cost = raw_business.get("cost") or data.get("cost") or data.get("price") or ""
        open_time2 = (
            raw_business.get("opentime_today")
            or raw_business.get("opentime_week")
            or raw_business.get("opentime")
            or raw_business.get("open_time")
            or data.get("opentime2")
            or data.get("open_time2")
            or ""
        )

        business = POIBusiness(
            rating=str(rating) if rating else "",
            cost=str(cost) if cost else "",
            business_area=raw_business.get("business_area", ""),
            opentime2=str(open_time2) if open_time2 else "",
        )

        biz_ext = POIBizExt(
            rating=business.rating,
            cost=business.cost,
            opentime2=business.opentime2,
        )

        return cls(
            id=str(data.get("id", "") or "").strip(),
            name=str(data.get("name", "") or "").strip(),
            address=str(data.get("address", "") or "").strip(),
            location=data.get("location", "") or "",
            type=str(data.get("type", "") or "").strip(),
            typecode=str(data.get("typecode", "") or "").strip(),
            adname=str(data.get("adname", "") or "").strip(),
            cityname=str(data.get("cityname", "") or "").strip(),
            pname=str(data.get("pname", "") or "").strip(),
            distance=str(data.get("distance", "") or ""),
            tel=str(data.get("tel", "") or "").strip(),
            photos=photos,
            business=business,
            biz_ext=biz_ext,
            indoor=data.get("indoor", {}),
            navi=data.get("navi", {}),
        )


class POISearchResponse(BaseModel):
    """POI 搜索响应"""
    status: str = ""
    info: str = ""
    infocode: str = ""
    count: int = 0
    query: dict[str, Any] = Field(default_factory=dict)
    pois: list[POI] = Field(default_factory=list)


class WeatherInfo(BaseModel):
    """单日天气信息"""
    date: str = ""
    day_weather: str = ""
    night_weather: str = ""
    day_temp: str = ""
    night_temp: str = ""
    wind_direction: str = ""
    wind_power: str = ""
    humidity: str = ""
    province: str = ""
    city: str = ""
    adcode: str = ""
    reporttime: str = ""


class WeatherResponse(BaseModel):
    """天气查询响应"""
    status: str = ""
    info: str = ""
    infocode: str = ""
    province: str = ""
    city: str = ""
    adcode: str = ""
    weather: str = ""
    temperature: str = ""
    winddirection: str = ""
    windpower: str = ""
    humidity: str = ""
    reporttime: str = ""
    forecasts: list[WeatherInfo] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════════════════════════════════════════


def _ensure_api_key() -> str:
    """获取高德 API Key。"""
    api_key = settings.amap_key
    if not api_key:
        raise RuntimeError("AMAP_MAPS_API_KEY 环境变量未设置")
    return api_key


async def _request_json(
    *,
    base_url: str,
    path: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """发送 HTTP GET 请求并返回 JSON 响应。

    Args:
        base_url: API 基础 URL
        path: API 路径
        params: 查询参数

    Returns:
        响应 JSON 数据

    Raises:
        RuntimeError: 当响应不是字典对象时
    """
    async with httpx.AsyncClient(timeout=20.0, base_url=base_url) as client:
        response = await client.get(path, params=params)
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, dict):
        raise RuntimeError("高德接口返回了非对象响应")
    return payload


async def _resolve_city_descriptor(city: str) -> dict[str, str]:
    """将城市名称解析为高德行政区划代码。

    Args:
        city: 城市名称或行政区划代码

    Returns:
        包含 adcode、city、province、formatted_address 的字典
    """
    raw_city = str(city or "").strip()
    if not raw_city:
        return {}
    if raw_city.isdigit():
        return {"adcode": raw_city}

    payload = await _request_json(
        base_url=AMAP_V3_BASE_URL,
        path="/geocode/geo",
        params={
            "key": _ensure_api_key(),
            "address": raw_city,
        },
    )
    geocodes = payload.get("geocodes")
    if not isinstance(geocodes, list) or not geocodes:
        return {}

    first = geocodes[0] if isinstance(geocodes[0], dict) else {}
    return {
        "adcode": str(first.get("adcode", "") or "").strip(),
        "city": str(first.get("city", "") or "").strip(),
        "province": str(first.get("province", "") or "").strip(),
        "formatted_address": str(first.get("formatted_address", "") or "").strip(),
    }


def _normalize_location_text(location: str) -> str:
    """规范化位置字符串为 '经度,纬度' 格式。

    Args:
        location: 位置字符串（可能是 'lng,lat' 或 'lat,lng'）

    Returns:
        规范化后的 '经度,纬度' 字符串

    Raises:
        ValueError: 当格式不正确时
    """
    parts = [item.strip() for item in str(location or "").split(",")]
    if len(parts) != 2:
        raise ValueError("location 必须是 '经度,纬度' 格式")

    try:
        lng = float(parts[0])
        lat = float(parts[1])
    except ValueError as exc:
        raise ValueError("location 必须包含合法的经纬度数值") from exc

    return f"{lng},{lat}"


def _poi_matches_city(raw_poi: dict[str, Any], descriptor: dict[str, str]) -> bool:
    """判断 POI 是否属于指定城市。"""
    candidates = [
        descriptor.get("city", ""),
        descriptor.get("province", ""),
        descriptor.get("formatted_address", ""),
    ]
    comparable_fields = [
        str(raw_poi.get("cityname", "") or "").strip(),
        str(raw_poi.get("adname", "") or "").strip(),
        str(raw_poi.get("pname", "") or "").strip(),
        str(raw_poi.get("address", "") or "").strip(),
    ]
    return any(
        cand and cand in field
        for field in comparable_fields
        for cand in candidates
        if cand
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 公共 API 函数
# ═══════════════════════════════════════════════════════════════════════════════


async def search_pois_by_text(
    *,
    keywords: str,
    city: str = "",
    types: str = "",
    citylimit: bool = False,
    extensions: str = "all",
    page: int = 1,
    offset: int = 10,
    show_fields: str = DEFAULT_SHOW_FIELDS,
    region: str = "",
    sortrule: str = "",
) -> POISearchResponse:
    """关键词搜索 POI，返回结构化响应。

    Args:
        keywords: 搜索关键词（多个用 | 分隔）
        city: 城市名称
        types: POI 类型编码
        citylimit: 是否限制在城市内
        extensions: 扩展信息（"all" 返回详细信息）
        page: 页码
        offset: 每页数量（最大 25）
        show_fields: 指定返回字段
        region: 区域名称
        sortrule: 排序规则

    Returns:
        POISearchResponse 结构化响应
    """
    api_key = _ensure_api_key()
    requested_region = str(region or city).strip()
    region_descriptor = await _resolve_city_descriptor(requested_region)
    resolved_region = region_descriptor.get("adcode", requested_region)
    requested_show_fields = str(show_fields or "").strip() or DEFAULT_SHOW_FIELDS

    params: dict[str, Any] = {
        "key": api_key,
        "keywords": keywords,
        "page_num": max(1, int(page or 1)),
        "page_size": max(1, min(int(offset or 10), 25)),
        "show_fields": requested_show_fields,
    }
    if resolved_region:
        params["region"] = resolved_region
    if types:
        params["types"] = types
    if citylimit and resolved_region:
        params["city_limit"] = "true"
    if sortrule:
        params["sortrule"] = sortrule

    payload = await _request_json(
        base_url=AMAP_V5_BASE_URL,
        path="/place/text",
        params=params,
    )

    # 城市过滤
    raw_pois = payload.get("pois", [])
    if citylimit and requested_region and isinstance(raw_pois, list):
        raw_pois = [
            item
            for item in raw_pois
            if isinstance(item, dict) and _poi_matches_city(item, region_descriptor)
        ]

    # 转换为 Pydantic 模型
    pois = [poi for item in raw_pois if (poi := POI.from_dict(item)) is not None]

    return POISearchResponse(
        status=payload.get("status", ""),
        info=payload.get("info", ""),
        infocode=payload.get("infocode", ""),
        count=payload.get("count", len(pois)),
        query={
            "keywords": keywords,
            "city": city,
            "region": resolved_region,
            "requested_region": requested_region,
            "types": types,
            "citylimit": citylimit,
            "extensions": extensions,
            "page": page,
            "offset": offset,
            "show_fields": requested_show_fields,
        },
        pois=pois,
    )


async def search_pois_nearby(
    *,
    location: str,
    keywords: str = "",
    city: str = "",
    types: str = "",
    radius: int = 3000,
    sortrule: str = "distance",
    page: int = 1,
    offset: int = 10,
    show_fields: str = DEFAULT_SHOW_FIELDS,
    region: str = "",
    citylimit: bool = False,
) -> POISearchResponse:
    """周边搜索 POI，返回结构化响应。

    Args:
        location: 中心点坐标（'经度,纬度'）
        keywords: 关键词
        city: 城市名称
        types: POI 类型
        radius: 搜索半径（米，最大 50000）
        sortrule: 排序规则（"distance" 按距离）
        page: 页码
        offset: 每页数量
        show_fields: 返回字段
        region: 区域
        citylimit: 是否限制城市

    Returns:
        POISearchResponse 结构化响应
    """
    api_key = _ensure_api_key()
    requested_region = str(region or city).strip()
    region_descriptor = await _resolve_city_descriptor(requested_region)
    resolved_region = region_descriptor.get("adcode", requested_region)
    requested_show_fields = str(show_fields or "").strip() or DEFAULT_SHOW_FIELDS

    params: dict[str, Any] = {
        "key": api_key,
        "location": _normalize_location_text(location),
        "radius": max(1, min(int(radius or 3000), 50000)),
        "sortrule": str(sortrule or "distance").strip() or "distance",
        "page_num": max(1, int(page or 1)),
        "page_size": max(1, min(int(offset or 10), 25)),
        "show_fields": requested_show_fields,
    }
    if keywords:
        params["keywords"] = keywords
    if types:
        params["types"] = types
    if resolved_region:
        params["region"] = resolved_region
    if citylimit and resolved_region:
        params["city_limit"] = "true"

    payload = await _request_json(
        base_url=AMAP_V5_BASE_URL,
        path="/place/around",
        params=params,
    )

    # 城市过滤
    raw_pois = payload.get("pois", [])
    if citylimit and requested_region and isinstance(raw_pois, list):
        raw_pois = [
            item
            for item in raw_pois
            if isinstance(item, dict) and _poi_matches_city(item, region_descriptor)
        ]

    # 转换为 Pydantic 模型
    pois = [poi for item in raw_pois if (poi := POI.from_dict(item)) is not None]

    return POISearchResponse(
        status=payload.get("status", ""),
        info=payload.get("info", ""),
        infocode=payload.get("infocode", ""),
        count=payload.get("count", len(pois)),
        query={
            "location": params["location"],
            "keywords": keywords,
            "city": city,
            "region": resolved_region,
            "requested_region": requested_region,
            "types": types,
            "radius": params["radius"],
            "sortrule": params["sortrule"],
            "citylimit": citylimit,
            "page": page,
            "offset": offset,
            "show_fields": requested_show_fields,
        },
        pois=pois,
    )


async def get_city_weather(
    *,
    city: str,
    extensions: str = "all",
) -> WeatherResponse:
    """查询城市天气，返回结构化响应。

    Args:
        city: 城市名称或行政区划代码
        extensions: 扩展信息（"all" 返回多日预报）

    Returns:
        WeatherResponse 结构化响应
    """
    api_key = _ensure_api_key()
    descriptor = await _resolve_city_descriptor(city)
    weather_city = descriptor.get("adcode", str(city or "").strip())
    payload = await _request_json(
        base_url=AMAP_V3_BASE_URL,
        path="/weather/weatherInfo",
        params={
            "key": api_key,
            "city": weather_city,
            "extensions": extensions,
        },
    )

    # 解析 forecasts (当 extensions="all" 时)
    forecasts: list[WeatherInfo] = []
    if extensions == "all":
        forecast_list = payload.get("forecasts", [])
        if isinstance(forecast_list, list):
            for fc in forecast_list:
                if isinstance(fc, dict):
                    casts = fc.get("casts", [])
                    if isinstance(casts, list):
                        for c in casts:
                            if isinstance(c, dict):
                                forecasts.append(WeatherInfo(
                                    date=c.get("date", ""),
                                    day_weather=c.get("dayweather", ""),
                                    night_weather=c.get("nightweather", ""),
                                    day_temp=c.get("daytemp", ""),
                                    night_temp=c.get("nighttemp", ""),
                                    wind_direction=c.get("winddir", ""),
                                    wind_power=c.get("windpower", ""),
                                    humidity=c.get("humidity", ""),
                                ))

    return WeatherResponse(
        status=payload.get("status", ""),
        info=payload.get("info", ""),
        infocode=payload.get("infocode", ""),
        province=payload.get("province", ""),
        city=payload.get("city", ""),
        adcode=payload.get("adcode", ""),
        weather=payload.get("weather", ""),
        temperature=payload.get("temperature", ""),
        winddirection=payload.get("winddirection", ""),
        windpower=payload.get("windpower", ""),
        humidity=payload.get("humidity", ""),
        reporttime=payload.get("reporttime", ""),
        forecasts=forecasts,
    )


async def get_transit_integrated_route(
    *,
    origin: str,
    destination: str,
    originpoi: str = "",
    destinationpoi: str = "",
    ad1: str = "",
    ad2: str = "",
    city1: str = "",
    city2: str = "",
    strategy: str = "0",
    AlternativeRoute: int = 1,
    multiexport: int = 0,
    max_trans: int = 3,
    nightflag: int = 0,
    date: str = "",
    time: str = "",
    show_fields: str = "",
) -> dict[str, Any]:
    """公交路径规划，返回原始结构化响应。

    Args:
        origin: 起点坐标（'经度,纬度'）
        destination: 终点坐标（'经度,纬度'）
        originpoi: 起点 POI ID
        destinationpoi: 终点 POI ID
        ad1: 起点所在城市编码
        ad2: 终点所在城市编码
        city1: 起点城市名称
        city2: 终点城市名称
        strategy: 公交出行策略（0-10）
        AlternativeRoute: 备选路线数量
        multiexport: 多经停点导出（0/1）
        max_trans: 最大换乘次数
        nightflag: 夜班公交（0/1）
        date: 日期（YYYY-MM-DD）
        time: 时间（HH:mm）
        show_fields: 返回字段

    Returns:
        包含路径规划结果的字典
    """
    api_key = _ensure_api_key()
    params: dict[str, Any] = {
        "key": api_key,
        "origin": _normalize_location_text(origin),
        "destination": _normalize_location_text(destination),
        "strategy": str(strategy or "0").strip() or "0",
        "AlternativeRoute": max(1, min(int(AlternativeRoute or 1), 10)),
        "multiexport": max(0, min(int(multiexport or 0), 1)),
        "max_trans": max(0, min(int(max_trans or 3), 4)),
        "nightflag": max(0, min(int(nightflag or 0), 1)),
        "output": "JSON",
    }
    if originpoi and destinationpoi:
        params["originpoi"] = str(originpoi).strip()
        params["destinationpoi"] = str(destinationpoi).strip()
    if ad1:
        params["ad1"] = str(ad1).strip()
    if ad2:
        params["ad2"] = str(ad2).strip()
    if city1:
        params["city1"] = str(city1).strip()
    if city2:
        params["city2"] = str(city2).strip()
    if date:
        params["date"] = str(date).strip()
    if time:
        params["time"] = str(time).strip()
    if show_fields:
        params["show_fields"] = str(show_fields).strip()

    payload = await _request_json(
        base_url=AMAP_V5_BASE_URL,
        path="/direction/transit/integrated",
        params=params,
    )
    payload["query"] = {
        "origin": params["origin"],
        "destination": params["destination"],
        "strategy": params["strategy"],
        "AlternativeRoute": params["AlternativeRoute"],
        "max_trans": params["max_trans"],
        "nightflag": params["nightflag"],
        "city1": params.get("city1", ""),
        "city2": params.get("city2", ""),
        "ad1": params.get("ad1", ""),
        "ad2": params.get("ad2", ""),
        "show_fields": params.get("show_fields", ""),
    }
    return payload


async def get_driving_route(
    *,
    origin: str,
    destination: str,
    strategy: str = "32",
    show_fields: str = "",
) -> dict[str, Any]:
    """驾车路径规划，返回原始结构化响应。"""
    api_key = _ensure_api_key()
    params: dict[str, Any] = {
        "key": api_key,
        "origin": _normalize_location_text(origin),
        "destination": _normalize_location_text(destination),
        "strategy": str(strategy or "32").strip() or "32",
        "output": "JSON",
    }
    if show_fields:
        params["show_fields"] = str(show_fields).strip()

    payload = await _request_json(
        base_url=AMAP_V5_BASE_URL,
        path="/direction/driving",
        params=params,
    )
    payload["query"] = {
        "origin": params["origin"],
        "destination": params["destination"],
        "strategy": params["strategy"],
        "show_fields": params.get("show_fields", ""),
    }
    return payload


__all__ = [
    "DEFAULT_SHOW_FIELDS",
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
