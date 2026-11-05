"""Geographic helpers.                                     (FUNCTIONAL PARADIGM)

Pure functions only: no I/O, no mutation. They take plain values and return
new values, built with map/filter/sorted and lambdas.
"""

from __future__ import annotations

import math
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
