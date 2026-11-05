"""Trip ranking.                                             (FUNCTIONAL PARADIGM)

Pure functions: take a collection of trips, return a new ranked tuple.
Order: fewest transfers, then lowest fare, then least walking, then shortest
ride distance.
"""

from __future__ import annotations

from decimal import Decimal
from itertools import groupby
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .models import Trip


def rank_key(trip: Trip) -> tuple:
    fare = trip.total_fare if trip.total_fare is not None else Decimal("0")
    return (trip.transfers, fare, round(trip.walking_m), trip.ride_km)


def dedupe_by_routes(trips: Iterable[Trip]) -> tuple[Trip, ...]:
    """Keep only the best trip for each sequence of routes.

    Plans that ride the same jeepneys but board or transfer a little earlier
    or later are near-identical; the commuter only needs the best of each.
    """
    by_routes = sorted(trips, key=lambda t: (t.route_codes, rank_key(t)))
    return tuple(next(group) for _, group in groupby(by_routes, key=lambda t: t.route_codes))


def rank_trips(trips: Iterable[Trip], limit: int) -> tuple[Trip, ...]:
    return tuple(sorted(dedupe_by_routes(trips), key=rank_key)[:limit])
