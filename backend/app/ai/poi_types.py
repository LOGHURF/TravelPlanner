"""Shared AMap POI top-level type configuration for active travel planning."""

from __future__ import annotations

ATTRACTION_TYPE_CODES = "110000|140000|080000|190000"
HOTEL_TYPE_CODE = "100000"
RESTAURANT_TYPE_CODE = "050000"

ATTRACTION_TYPE_PREFIXES = ("11", "14", "08", "19")
HOTEL_TYPE_PREFIX = "10"
RESTAURANT_TYPE_PREFIX = "05"


def has_type_prefix(typecode: str, prefix: str) -> bool:
    return any(part.strip().startswith(prefix) for part in str(typecode or "").split("|"))
