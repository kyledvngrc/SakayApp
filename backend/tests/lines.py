"""Helpers to build test route lines in metres (TEST DATA ONLY)."""
from app.geo import LatLng

BASE = LatLng(7.0700, 125.6100)
M_LAT = 1 / 111_195
M_LNG = 1 / (111_195 * 0.99255)


def at(east_m: float = 0.0, north_m: float = 0.0) -> LatLng:
    return LatLng(BASE.lat + north_m * M_LAT, BASE.lng + east_m * M_LNG)


def line(*points_m: tuple[float, float]) -> tuple[LatLng, ...]:
    return tuple(at(e, n) for e, n in points_m)
