"""Place search for the app's From / To fields.           (IMPERATIVE PARADIGM)

Our own landmarks first, then addresses and places from OpenStreetMap through
the Photon geocoder (https://photon.komoot.io, fair use). Queries are biased to
Davao City; the commuter's own location is never sent. Results are cached so
repeated searches don't hit the public service again.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from functools import lru_cache

from fastapi import APIRouter, Query

from .. import places, services
from ..config import settings
from ..directions import nearest_landmark
from ..geo import LatLng

router = APIRouter(prefix="/places", tags=["places"])
log = logging.getLogger("sakay")

USER_AGENT = "SakayApp/0.1 (university capstone; https://github.com/kyledvngrc/SakayApp)"


def _photon(path: str, params: dict) -> list[dict]:
    url = f"{settings.photon_url}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=settings.photon_timeout_s) as res:
        return json.load(res).get("features", [])


@lru_cache(maxsize=1024)
def _search_osm(query: str) -> tuple[dict, ...]:
    lat, lng = settings.city_center
    w, s, e, n = settings.city_bbox
    features = _photon("/api/", {"q": query, "limit": 10, "lang": "en", "lat": lat, "lon": lng,
                                 "bbox": f"{w},{s},{e},{n}"})
    return tuple(places.places_from_features(features, limit=8))


@lru_cache(maxsize=1024)
def _reverse_osm(lat: float, lng: float) -> dict | None:
    found = places.places_from_features(_photon("/reverse", {"lat": lat, "lon": lng, "limit": 1,
                                                            "lang": "en"}), limit=1)
    return found[0] if found else None


@router.get("/search")
def search(q: str = Query(min_length=2, max_length=100)) -> dict:
    query = " ".join(q.split())
    own = places.landmark_matches(services.planner().network.landmarks, query, limit=5)
    try:
        osm = list(_search_osm(query.casefold()))
        available = True
    except Exception:                     # the public geocoder is down or slow
        log.warning("place search failed for %r", query, exc_info=True)
        osm, available = [], False
    return {"results": own + osm, "search_available": available,
            "attribution": "Search data © OpenStreetMap contributors"}


@router.get("/reverse")
def reverse(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180)) -> dict:
    """A name for a dropped pin: a nearby landmark, else the nearest OSM place."""
    point = LatLng(lat, lng)
    found = nearest_landmark(point, services.planner().network.landmarks, max_m=100)
    if found:
        return {"label": f"Near {found[0].name}"}
    try:
        place = _reverse_osm(round(lat, 4), round(lng, 4))
    except Exception:
        log.warning("reverse lookup failed", exc_info=True)
        place = None
    if place is None:
        return {"label": "Dropped pin"}
    near = place["name"]
    street = place["detail"].split(",")[0] if place["detail"] else ""
    return {"label": f"Near {near}" + (f", {street}" if street and street != near else "")}
