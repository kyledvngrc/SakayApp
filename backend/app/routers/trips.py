"""Trip planning endpoint.                                 (IMPERATIVE PARADIGM)"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from .. import db, services
from ..geo import LatLng, haversine_m
from ..schemas import PlanRequest

router = APIRouter(prefix="/trips", tags=["trips"])
log = logging.getLogger("sakay")


@router.post("/plan")
def plan_trip(req: PlanRequest, log_search: bool = True) -> dict:
    """Plan trips. The admin test panel passes log_search=false to keep tests out of the stats."""
    planner = services.planner()
    origin = LatLng(req.origin.lat, req.origin.lng)
    destination = LatLng(req.destination.lat, req.destination.lng)

    trips = planner.plan(origin, destination, req.rider_type, req.max_transfers)

    radius = planner.settings.walk_radius_m
    notice = None
    if not planner.access(origin):
        notice = f"No jeepney route passes within {radius:.0f} m of your starting point."
    elif not planner.access(destination):
        notice = f"No jeepney route passes within {radius:.0f} m of your destination."
    elif not trips:
        notice = "No jeepney route connects these places yet."
    elif haversine_m(origin, destination) <= radius:
        notice = "Your destination is within walking distance."

    if log_search:
        _log_search(req.rider_type, trips)

    fare_rule = next(iter(planner.network.fare_rules.values()), None)
    return {
        "trips": [t.to_dict() for t in trips],
        "notice": notice,
        "rider_type": req.rider_type,
        "fare_source": fare_rule.source if fare_rule and not fare_rule.is_placeholder else None,
        "estimates_note": "Distances and fares are estimates.",
    }


def _log_search(rider_type: str, trips) -> None:
    best = trips[0] if trips else None
    try:
        db.log_search(rider_type, len(trips), list(best.route_codes) if best else [])
    except Exception:                       # logging must never break trip planning
        log.exception("could not write search_log")
