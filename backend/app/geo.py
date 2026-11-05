"""Geographic helpers.                                     (FUNCTIONAL PARADIGM)

Pure functions only: no I/O, no mutation. They take plain values and return
new values, built with map/filter/sorted, comprehensions and lambdas.

A route is a polyline (`path`) drawn along the streets. A position on a route
is the distance in metres along that line from its first point.
"""

from __future__ import annotations

import bisect
import math
from itertools import accumulate
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


# --- Lines --------------------------------------------------------------------

def cumulative_m(path: Sequence[HasLatLng]) -> tuple[float, ...]:
    """Metres along `path` to each of its points (first is 0)."""
    return tuple(accumulate((haversine_m(a, b) for a, b in zip(path, path[1:])), initial=0.0))


def point_at(path: Sequence[HasLatLng], cum: Sequence[float], d: float) -> LatLng:
    """The point `d` metres along `path` (clamped to its ends)."""
    if d <= 0:
        return LatLng(path[0].lat, path[0].lng)
    if d >= cum[-1]:
        return LatLng(path[-1].lat, path[-1].lng)
    i = bisect.bisect_right(cum, d) - 1
    seg = cum[i + 1] - cum[i]
    t = 0.0 if seg == 0 else (d - cum[i]) / seg
    a, b = path[i], path[i + 1]
    return LatLng(a.lat + t * (b.lat - a.lat), a.lng + t * (b.lng - a.lng))


def slice_path(path: Sequence[HasLatLng], cum: Sequence[float],
               start_m: float, end_m: float) -> tuple[LatLng, ...]:
    """The part of `path` between two positions, in travel order (backwards if
    end_m < start_m), including the exact end points."""
    lo, hi = sorted((start_m, end_m))
    inner = tuple(LatLng(p.lat, p.lng) for p, d in zip(path, cum) if lo < d < hi)
    forward = (point_at(path, cum, lo), *inner, point_at(path, cum, hi))
    return forward if start_m <= end_m else tuple(reversed(forward))


def is_closed(path: Sequence[HasLatLng], tolerance_m: float) -> bool:
    """Whether the line ends (about) where it starts, i.e. a loop."""
    return len(path) > 2 and haversine_m(path[0], path[-1]) <= tolerance_m


def sample_line(path: Sequence[HasLatLng], cum: Sequence[float],
                step_m: float) -> tuple[tuple[float, LatLng], ...]:
    """(position, point) every `step_m` metres along the line, both ends included."""
    total = cum[-1]
    count = max(1, math.ceil(total / step_m))
    return tuple((total * i / count, point_at(path, cum, total * i / count))
                 for i in range(count + 1))


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
    starts = tuple(accumulate(lengths, initial=0.0))

    def candidate(i: int) -> tuple[float, float]:
        t, offset = _project_on_segment(*segments[i], p)
        return starts[i] + t * lengths[i], offset

    return min(map(candidate, range(len(segments))), key=lambda c: c[1],
               default=(0.0, haversine_m(path[0], p)))


def geojson_path(geojson: Mapping | None) -> tuple[LatLng, ...] | None:
    """LatLng points of a GeoJSON LineString ([lng, lat] pairs), or None."""
    if not geojson or geojson.get("type") != "LineString":
        return None
    return tuple(LatLng(lat=c[1], lng=c[0]) for c in geojson.get("coordinates", ()))
