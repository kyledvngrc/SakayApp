"""Place search results from OpenStreetMap (Photon).        (FUNCTIONAL PARADIGM)

Pure functions that turn Photon GeoJSON features into the app's place format.
The HTTP calls live in routers/places.py.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from .geo import LatLng, haversine_m


def place_detail(props: Mapping) -> str:
    """'J. P. Laurel Avenue, Lanang, Davao City' from a feature's address parts."""
    street = " ".join(p for p in (props.get("housenumber"), props.get("street")) if p)
    parts = (street, props.get("locality"), props.get("district"), props.get("city"))
    seen: list[str] = []
    for part in parts:
        if part and part not in seen and part != props.get("name"):
            seen.append(part)
    return ", ".join(seen)


def place_from_feature(feature: Mapping) -> dict | None:
    """One search result, or None when the feature has no usable point or name."""
    props = feature.get("properties") or {}
    coords = (feature.get("geometry") or {}).get("coordinates") or ()
    name = props.get("name") or props.get("street")
    if len(coords) < 2 or not name:
        return None
    return {"name": name, "detail": place_detail(props), "lat": coords[1], "lng": coords[0],
            "source": "osm"}


def places_from_features(features: Iterable[Mapping], limit: int) -> list[dict]:
    """Usable places, without repeats of the same name at (about) the same spot."""
    places = [p for p in map(place_from_feature, features) if p]

    def is_repeat(i: int) -> bool:
        p = places[i]
        return any(q["name"] == p["name"] and haversine_m(LatLng(q["lat"], q["lng"]),
                                                          LatLng(p["lat"], p["lng"])) < 150
                   for q in places[:i])

    return [p for i, p in enumerate(places) if not is_repeat(i)][:limit]


def landmark_matches(landmarks: Iterable, query: str, limit: int) -> list[dict]:
    """Our own landmarks whose name or description contains the query."""
    q = query.casefold()
    found = (lm for lm in landmarks
             if q in lm.name.casefold() or q in (lm.description or "").casefold())
    return [{"name": lm.name, "detail": lm.description or "", "lat": lm.lat, "lng": lm.lng,
             "source": "landmark"} for lm in found][:limit]
