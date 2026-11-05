"""Read-only stop and route endpoints.                     (IMPERATIVE PARADIGM)"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import services
from ..geo import LatLng

router = APIRouter(tags=["network"])


def _stop(s) -> dict:
    return {"id": s.id, "name": s.name, "landmark": s.landmark, "is_landmark": s.is_landmark,
            "lat": s.lat, "lng": s.lng}


def _route(r) -> dict:
    return {"code": r.code, "name": r.name, "color": r.color, "vehicle_type": r.vehicle_type,
            "is_bidirectional": r.is_bidirectional, "stop_ids": list(r.stop_ids),
            "path_geojson": r.path_geojson}


@router.get("/stops")
def list_stops() -> list[dict]:
    return [_stop(s) for s in services.planner().network.stops.values()]


@router.get("/stops/nearby")
def nearby_stops(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180)) -> list[dict]:
    found = services.planner().nearby_stops(LatLng(lat, lng))
    return [{**_stop(s), "distance_m": round(d)} for s, d in found]


@router.get("/routes")
def list_routes() -> list[dict]:
    return [_route(r) for r in services.planner().network.routes.values()]


@router.get("/routes/{code}")
def get_route(code: str) -> dict:
    network = services.planner().network
    route = network.routes.get(code)
    if route is None:
        raise HTTPException(status_code=404, detail=f"route {code} not found")
    return {**_route(route), "stops": [_stop(network.stops[i]) for i in route.stop_ids]}
