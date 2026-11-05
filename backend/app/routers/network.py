"""Read-only route and landmark endpoints.                 (IMPERATIVE PARADIGM)"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import services
from ..geo import LatLng

router = APIRouter(tags=["network"])


def route_dict(r) -> dict:
    return {"code": r.code, "name": r.name, "color": r.color, "vehicle_type": r.vehicle_type,
            "is_bidirectional": r.is_bidirectional, "kind": r.kind,
            "length_km": round(r.length_m / 1000, 2), "path_geojson": r.to_geojson()}


def landmark_dict(lm) -> dict:
    return {"id": lm.id, "name": lm.name, "description": lm.description,
            "lat": lm.lat, "lng": lm.lng}


@router.get("/routes")
def list_routes() -> list[dict]:
    return [route_dict(r) for r in services.planner().network.routes.values()]


@router.get("/routes/nearby")
def nearby_routes(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180)) -> list[dict]:
    """Routes passing within walking distance, nearest first, with where to catch them."""
    found = services.planner().nearby_routes(LatLng(lat, lng))
    return [{"code": r.code, "name": r.name, "color": r.color, "kind": r.kind,
             "walk_m": round(a.walk_m), "catch_at": {"lat": a.point.lat, "lng": a.point.lng}}
            for r, a in found]


@router.get("/routes/{code}")
def get_route(code: str) -> dict:
    route = services.planner().network.routes.get(code)
    if route is None:
        raise HTTPException(status_code=404, detail=f"route {code} not found")
    return route_dict(route)


@router.get("/landmarks")
def list_landmarks() -> list[dict]:
    return [landmark_dict(lm) for lm in services.planner().network.landmarks]
