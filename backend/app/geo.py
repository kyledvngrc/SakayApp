"""Geographic helpers.                                     (FUNCTIONAL PARADIGM)

Pure functions only: no I/O, no mutation. They take plain values and return
new values, built with map/filter/sorted and lambdas.
"""

from __future__ import annotations

import math
from itertools import accumulate
from decimal import Decimal
from typing import Iterable, Mapping, NamedTuple, Protocol, Sequence, TypeVar

EARTH_RADIUS_M = 6_371_000.0


class HasLatLng(Protocol):
    lat: float
    lng: float


class LatLng(NamedTuple):
    lat: float
    lng: float


P = TypeVar("P", bound=HasLatLng)


def haversine_m(a: HasLatLng, b: HasLatLng) -> float:
    """Great-circle distance between two points, in metres."""
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    dphi = phi2 - phi1
    dlmb = math.radians(b.lng - a.lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def nearby(points: Iterable[P], center: HasLatLng, radius_m: float,
           limit: int) -> tuple[tuple[P, float], ...]:
    """The closest `limit` points within `radius_m` of `center`, nearest first,
    each paired with its distance in metres."""
    with_distance = map(lambda p: (p, haversine_m(center, p)), points)
    within = filter(lambda pd: pd[1] <= radius_m, with_distance)
    return tuple(sorted(within, key=lambda pd: pd[1])[:limit])


def path_km(leg_km: Mapping[tuple[str, int, int], Decimal], route_code: str,
            stop_ids: Sequence[int]) -> Decimal:
    """Total distance of riding `route_code` through `stop_ids` in order."""
    hops = zip(stop_ids, stop_ids[1:])
    return sum(map(lambda hop: leg_km[(route_code, hop[0], hop[1])], hops), Decimal("0"))


# --- Distances along a drawn route line -------------------------------------
# The admin draws each route as a polyline. Stop-to-stop distance is measured
# along that line (roads curve), falling back to a straight line if needed.

def _local_xy(origin: HasLatLng, p: HasLatLng) -> tuple[float, float]:
    """Metres east/north of `origin` (equirectangular; accurate at city scale)."""
    x = math.radians(p.lng - origin.lng) * EARTH_RADIUS_M * math.cos(math.radians(origin.lat))
    y = math.radians(p.lat - origin.lat) * EARTH_RADIUS_M
    return x, y


def _project_on_segment(a: HasLatLng, b: HasLatLng, p: HasLatLng) -> tuple[float, float]:
    """(fraction 0..1 along a->b of the closest point to p, distance from p to it in m)."""
    bx, by = _local_xy(a, b)
    px, py = _local_xy(a, p)
    seg2 = bx * bx + by * by
    t = 0.0 if seg2 == 0 else max(0.0, min(1.0, (px * bx + py * by) / seg2))
    return t, math.hypot(px - t * bx, py - t * by)


def position_along(path: Sequence[HasLatLng], p: HasLatLng) -> tuple[float, float]:
    """(metres along `path` to the point nearest p, offset of p from the path in m)."""
    segments = tuple(zip(path, path[1:]))
    lengths = tuple(map(lambda seg: haversine_m(*seg), segments))
    starts = tuple(accumulate(lengths, initial=0.0))     # metres to the start of each segment

    def candidate(i: int) -> tuple[float, float]:
        t, offset = _project_on_segment(*segments[i], p)
        return starts[i] + t * lengths[i], offset

    return min(map(candidate, range(len(segments))), key=lambda c: c[1],
               default=(0.0, haversine_m(path[0], p)))


def stop_distances_km(path: Sequence[HasLatLng] | None,
                      stops: Sequence[HasLatLng]) -> tuple[Decimal, ...]:
    """distance_from_prev_km for each stop in order (first is 0).

    Uses distance along `path` when it exists and the stops move forward along
    it; otherwise the straight-line distance for that hop.
    """
    positions = tuple(position_along(path, s)[0] for s in stops) if path and len(path) > 1 else None

    def hop_m(i: int) -> float:
        along = positions[i] - positions[i - 1] if positions else -1.0
        return along if along > 0 else haversine_m(stops[i - 1], stops[i])

    return tuple(Decimal("0") if i == 0 else Decimal(str(round(hop_m(i) / 1000, 3)))
                 for i in range(len(stops)))


def geojson_path(geojson: Mapping | None) -> tuple[LatLng, ...] | None:
    """LatLng points of a GeoJSON LineString ([lng, lat] pairs), or None."""
    if not geojson or geojson.get("type") != "LineString":
        return None
    return tuple(LatLng(lat=c[1], lng=c[0]) for c in geojson.get("coordinates", ()))
