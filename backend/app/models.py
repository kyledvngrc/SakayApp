"""Domain model.                                             (OOP PARADIGM)

Classes for the transit network and planned trips. Segment is an abstract base
class with WalkSegment and RideSegment subclasses; TripPlanner coordinates the
logic engine (Prolog), fare strategies and the functional helpers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from . import geo, ranking
from .config import Settings
from .fare_calc import FareRule, total_fare
from .fares import FareStrategy, strategy_for

# A plan as returned by the Prolog bridge: one (route, board, alight, stop ids) per ride.
RawRide = tuple[str, int, int, tuple[int, ...]]
TripFinder = Callable[[Sequence[int], Sequence[int], int], list[list[RawRide]]]


@dataclass(frozen=True)
class Stop:
    """A place where a commuter can board or alight."""
    id: int
    name: str
    lat: float
    lng: float
    landmark: str | None = None


@dataclass(frozen=True)
class Route:
    """A jeepney (or other vehicle) route and its ordered stops."""
    code: str
    name: str
    color: str
    vehicle_type: str
    is_bidirectional: bool
    stop_ids: tuple[int, ...]
    path_geojson: Any = None


@dataclass(frozen=True)
class Network:
    """An immutable snapshot of the routes, stops and fares loaded from the DB."""
    stops: Mapping[int, Stop]
    routes: Mapping[str, Route]
    leg_km: Mapping[tuple[str, int, int], Decimal]
    fare_rules: Mapping[str, FareRule]

    @property
    def legs(self) -> list[tuple[str, int, int]]:
        return list(self.leg_km)


class Segment(ABC):
    """One part of a trip."""

    kind: str

    @abstractmethod
    def minutes(self, s: Settings) -> float: ...

    @abstractmethod
    def to_dict(self) -> dict: ...


@dataclass(frozen=True)
class WalkSegment(Segment):
    """Walking between a point (the user's origin/destination) and a stop."""
    from_label: str
    to_label: str
    path: tuple[geo.LatLng, geo.LatLng]
    distance_m: float
    kind: str = field(default="walk", init=False)

    def minutes(self, s: Settings) -> float:
        return self.distance_m / s.walk_m_per_min

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "from": self.from_label,
            "to": self.to_label,
            "distance_m": round(self.distance_m),
            "path": [{"lat": p.lat, "lng": p.lng} for p in self.path],
        }


@dataclass(frozen=True)
class RideSegment(Segment):
    """Riding one route from a boarding stop to an alighting stop."""
    route: Route
    stops: tuple[Stop, ...]
    distance_km: Decimal
    fare: Decimal | None          # None when no real fare rule is available
    kind: str = field(default="ride", init=False)

    @property
    def board(self) -> Stop:
        return self.stops[0]

    @property
    def alight(self) -> Stop:
        return self.stops[-1]

    def minutes(self, s: Settings) -> float:
        return s.wait_min_per_ride + float(self.distance_km) / s.jeepney_kmh * 60

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "route": {"code": self.route.code, "name": self.route.name,
                      "color": self.route.color, "vehicle_type": self.route.vehicle_type},
            "board": _stop_dict(self.board),
            "alight": _stop_dict(self.alight),
            "num_stops": len(self.stops) - 1,
            "distance_km": float(self.distance_km),
            "fare": float(self.fare) if self.fare is not None else None,
            "path": [{"lat": st.lat, "lng": st.lng} for st in self.stops],
        }


def _stop_dict(stop: Stop) -> dict:
    return {"id": stop.id, "name": stop.name, "landmark": stop.landmark,
            "lat": stop.lat, "lng": stop.lng}


@dataclass(frozen=True)
class Trip:
    """A complete itinerary: walk, one or more rides, walk."""
    segments: tuple[Segment, ...]
    settings: Settings

    @property
    def rides(self) -> tuple[RideSegment, ...]:
        return tuple(s for s in self.segments if isinstance(s, RideSegment))

    @property
    def route_codes(self) -> tuple[str, ...]:
        return tuple(r.route.code for r in self.rides)

    @property
    def transfers(self) -> int:
        return len(self.rides) - 1

    @property
    def ride_km(self) -> Decimal:
        return sum((r.distance_km for r in self.rides), Decimal("0"))

    @property
    def walking_m(self) -> float:
        return sum(s.distance_m for s in self.segments if isinstance(s, WalkSegment))

    @property
    def minutes(self) -> float:
        return sum(s.minutes(self.settings) for s in self.segments)

    @property
    def total_fare(self) -> Decimal | None:
        fares = [r.fare for r in self.rides]
        return None if any(f is None for f in fares) else total_fare(fares)

    def to_dict(self) -> dict:
        fare = self.total_fare
        return {
            "route_codes": list(self.route_codes),
            "transfers": self.transfers,
            "ride_km": float(self.ride_km),
            "walking_m": round(self.walking_m),
            "minutes": round(self.minutes),
            "total_fare": float(fare) if fare is not None else None,
            "fare_available": fare is not None,
            "segments": [s.to_dict() for s in self.segments],
        }


class TripPlanner:
    """Plans trips between two points on the map.

    1. Finds stops within walking distance of each end (functional helpers).
    2. Asks the logic engine for every route plan between them (Prolog).
    3. Builds Trip objects with walking, ride distances and fares, then ranks them.
    """

    def __init__(self, network: Network, finder: TripFinder, settings: Settings) -> None:
        self.network = network
        self.finder = finder
        self.settings = settings

    def nearby_stops(self, point: geo.LatLng) -> tuple[tuple[Stop, float], ...]:
        s = self.settings
        return geo.nearby(self.network.stops.values(), point, s.walk_radius_m, s.candidate_stops)

    def plan(self, origin: geo.LatLng, destination: geo.LatLng,
             rider_type: str = "regular", max_transfers: int | None = None) -> tuple[Trip, ...]:
        starts = dict((st.id, d) for st, d in self.nearby_stops(origin))
        ends = dict((st.id, d) for st, d in self.nearby_stops(destination))
        if not starts or not ends:
            return ()
        cap = self.settings.max_transfers if max_transfers is None else max_transfers
        raw_plans = self.finder(list(starts), list(ends), cap)
        trips = [self._build_trip(p, origin, destination, starts, ends, rider_type)
                 for p in raw_plans]
        return ranking.rank_trips(trips, self.settings.max_results)

    def _strategy(self, route: Route, rider_type: str) -> FareStrategy | None:
        rule = self.network.fare_rules.get(route.vehicle_type)
        return strategy_for(rider_type, rule) if rule else None

    def _ride(self, raw: RawRide, rider_type: str) -> RideSegment:
        code, _, _, stop_ids = raw
        route = self.network.routes[code]
        km = geo.path_km(self.network.leg_km, code, stop_ids)
        strategy = self._strategy(route, rider_type)
        fare = None if strategy is None or strategy.is_placeholder else strategy.fare_for(km)
        stops = tuple(self.network.stops[i] for i in stop_ids)
        return RideSegment(route=route, stops=stops, distance_km=km, fare=fare)

    def _build_trip(self, raw_plan: list[RawRide], origin: geo.LatLng, destination: geo.LatLng,
                    starts: Mapping[int, float], ends: Mapping[int, float],
                    rider_type: str) -> Trip:
        rides = [self._ride(r, rider_type) for r in raw_plan]
        first, last = rides[0].board, rides[-1].alight
        walk_in = WalkSegment("Your location", first.name,
                              (origin, geo.LatLng(first.lat, first.lng)), starts[first.id])
        walk_out = WalkSegment(last.name, "Destination",
                               (geo.LatLng(last.lat, last.lng), destination), ends[last.id])
        return Trip(segments=(walk_in, *rides, walk_out), settings=self.settings)
