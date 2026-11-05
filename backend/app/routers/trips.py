"""Trip planning endpoint.                                 (IMPERATIVE PARADIGM)"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from .. import db, services
from ..geo import LatLng
from ..schemas import PlanRequest

router = APIRouter(prefix="/trips", tags=["trips"])
log = logging.getLogger("sakay")



@router.post("/plan")
def plan_trip(req: PlanRequest, log_search: bool = True) -> dict:
    """Plan trips. The admin test panel passes log_search=false to keep tests out of the stats."""
    planner = services.planner()
    origin = LatLng(req.origin.lat, req.origin.lng)
    destination = LatLng(req.destination.lat, req.destination.lng)

    near_origin = planner.nearby_stops(origin)
    near_dest = planner.nearby_stops(destination)
    trips = planner.plan(origin, destination, req.rider_type, req.max_transfers)

    notice = None
    if not near_origin:
        notice = f"No stops within {planner.settings.walk_radius_m:.0f} m of your starting point."
    elif not near_dest:
        notice = f"No stops within {planner.settings.walk_radius_m:.0f} m of your destination."
    elif not trips:
        notice = "No jeepney route connects these places yet."

    if log_search:
        _log_search(req.rider_type, trips)

    fare_rule = next(iter(planner.network.fare_rules.values()), None)
    return {
        "trips": [t.to_dict() for t in trips],
        "notice": notice,
        "rider_type": req.rider_type,
        "fare_source": fare_rule.source if fare_rule and not fare_rule.is_placeholder else None,
        "estimates_note": "Times and fares are estimates.",
    }


def _log_search(rider_type: str, trips) -> None:
    best = trips[0] if trips else None
    try:
        db.log_search(best.rides[0].board.id if best else None,
                      best.rides[-1].alight.id if best else None,
                      rider_type, len(trips), list(best.route_codes) if best else [])
    except Exception:                       # logging must never break trip planning
        log.exception("could not write search_log")
