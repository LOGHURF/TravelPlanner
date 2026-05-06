"""Local AMap MCP server exposed over stdio via FastMCP."""

from __future__ import annotations

from fastmcp import FastMCP

from app.services.amap import (
    DEFAULT_SHOW_FIELDS,
    POISearchResponse,
    WeatherResponse,
    get_city_weather,
    get_driving_route,
    get_transit_integrated_route,
    search_pois_by_text,
    search_pois_nearby,
)

mcp = FastMCP("amap-local")


@mcp.tool(name="maps_text_search")
async def maps_text_search(
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
    """Search POIs using AMap POI 2.0 keyword search."""

    return await search_pois_by_text(
        keywords=keywords,
        city=city,
        types=types,
        citylimit=citylimit,
        extensions=extensions,
        page=page,
        offset=offset,
        show_fields=show_fields,
        region=region,
        sortrule=sortrule,
    )


@mcp.tool(name="maps_nearby_search")
async def maps_nearby_search(
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
    """Search nearby POIs using AMap nearby search."""

    return await search_pois_nearby(
        location=location,
        keywords=keywords,
        city=city,
        types=types,
        radius=radius,
        sortrule=sortrule,
        page=page,
        offset=offset,
        show_fields=show_fields,
        region=region,
        citylimit=citylimit,
    )


@mcp.tool(name="maps_weather")
async def maps_weather(city: str, extensions: str = "all") -> WeatherResponse:
    """Query city weather using AMap weather service."""

    return await get_city_weather(city=city, extensions=extensions)


@mcp.tool(name="maps_transit_integrated")
async def maps_transit_integrated(
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
) -> dict:
    """Query integrated public transit route using AMap direction 2.0."""

    return await get_transit_integrated_route(
        origin=origin,
        destination=destination,
        originpoi=originpoi,
        destinationpoi=destinationpoi,
        ad1=ad1,
        ad2=ad2,
        city1=city1,
        city2=city2,
        strategy=strategy,
        AlternativeRoute=AlternativeRoute,
        multiexport=multiexport,
        max_trans=max_trans,
        nightflag=nightflag,
        date=date,
        time=time,
        show_fields=show_fields,
    )


@mcp.tool(name="maps_direction_driving")
async def maps_direction_driving(
    origin: str,
    destination: str,
    strategy: str = "32",
    show_fields: str = "",
) -> dict:
    """Query driving route using AMap direction 2.0."""

    return await get_driving_route(
        origin=origin,
        destination=destination,
        strategy=strategy,
        show_fields=show_fields,
    )


server = mcp


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
