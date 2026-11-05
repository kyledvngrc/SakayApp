"""Domain model.                                             (OOP PARADIGM)

Classes for the transit network and planned trips. A Route is a line drawn
along the streets; jeepneys pick up and drop off anywhere on it. Segment is an
abstract base class with WalkSegment and RideSegment subclasses; TripPlanner
coordinates the logic engine (Prolog), fare strategies and the functional
helpers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Literal, Mapping, Sequence

from . import connections, directions, geo, ranking
from .config import Settings
from .connections import Access, Link, Sample
from .directions import NOWHERE, Place
from .fare_calc import FareRule, total_fare
from .fares import FareStrategy, strategy_for

RouteKind = Literal["both", "oneway", "loop"]

# What the Prolog bridge returns: per plan, one (route, board_m, alight_m,
# ride_m, walk_to_next_m) tuple per ride. Starts/goals are (route, along_m, walk_m).
RawLeg = tuple[str, int, int, int, int]
Candidate = tuple[str, int, int]
TripFinder = Callable[[Sequence[Candidate], Sequence[Candidate], int], list[list[RawLeg]]]

MIN_TRANSFER_WALK_M = 15      # shorter walks are shown as "transfer here"


@dataclass(frozen=True)
class Landmark:
    """A named place used to describe where to get on or off."""
    id: int
    name: str
    lat: float
    lng: float
    description: str | None = None


@dataclass(frozen=True)
class Route:
    """A jeepney (or other vehicle) route: the line it travels along."""
    code: str
    name: str
    color: str
    vehicle_type: str
    is_bidirectional: bool
    path: tuple[geo.LatLng, ...]
    kind: RouteKind
    cum: tuple[float, ...] = field(repr=False)

    @classmethod
    def from_line(cls, code: str, name: str, color: str, vehicle_type: str,
                  is_bidirectional: bool, path: Sequence[geo.LatLng],
                  loop_tolerance_m: float) -> Route:
        """Build a route; a one-way line that ends where it starts is a loop."""
        path = tuple(path)
        kind: RouteKind = ("both" if is_bidirectional else
                           "loop" if geo.is_closed(path, loop_tolerance_m) else "oneway")
        return cls(code, name, color, vehicle_type, is_bidirectional, path, kind,
                   geo.cumulative_m(path))

    @property
    def length_m(self) -> float:
        return self.cum[-1]

    def point_at(self, along_m: float) -> geo.LatLng:
        return geo.point_at(self.path, self.cum, along_m)

    def slice(self, from_m: float, to_m: float) -> tuple[geo.LatLng, ...]:
        """The line ridden from one position to another, in travel order."""
        if self.kind == "loop" and to_m < from_m:              # wraps past the end
            return (geo.slice_path(self.path, self.cum, from_m, self.length_m)
                    + geo.slice_path(self.path, self.cum, 0.0, to_m)[1:])
        return geo.slice_path(self.path, self.cum, from_m, to_m)

    def samples(self, step_m: float) -> tuple[Sample, ...]:
        return tuple(Sample(self.code, d, p) for d, p in geo.sample_line(self.path, self.cum, step_m))

    def to_geojson(self) -> dict:
        return {"type": "LineString", "coordinates": [[p.lng, p.lat] for p in self.path]}


@dataclass(frozen=True)
class Network:
    """An immutable snapshot of routes, landmarks, fares and transfer links."""
    routes: Mapping[str, Route]
    landmarks: tuple[Landmark, ...]
    fare_rules: Mapping[str, FareRule]
    samples: tuple[Sample, ...]
    links: tuple[Link, ...]

    @classmethod
    def build(cls, routes: Mapping[str, Route], landmarks: Sequence[Landmark],
              fare_rules: Mapping[str, FareRule], s: Settings) -> Network:
        """Sample every route line and work out where routes connect."""
        by_route = {code: r.samples(s.sample_step_m) for code, r in routes.items()}
        samples = tuple(x for code in sorted(by_route) for x in by_route[code])
        return cls(routes, tuple(landmarks), fare_rules, samples,
                   connections.links(by_route, s.transfer_walk_m, s.link_spacing_m))


class Segment(ABC):
    """One part of a trip."""

    kind: str

    @property
    @abstractmethod
    def path(self) -> tuple[geo.LatLng, ...]: ...

    @abstractmethod
    def to_dict(self) -> dict: ...


def _points(path: Sequence[geo.LatLng]) -> list[dict]:
    return [{"lat": p.lat, "lng": p.lng} for p in path]


@dataclass(frozen=True)
class WalkSegment(Segment):
    """Walking to a route, between routes, or to the destination."""
    from_label: str
    to_label: str
    start: geo.LatLng
    end: geo.LatLng
    distance_m: float
    kind: str = field(default="walk", init=False)

    @property
    def path(self) -> tuple[geo.LatLng, ...]:
        return (self.start, self.end)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "from": self.from_label, "to": self.to_label,
                "distance_m": round(self.distance_m), "path": _points(self.path)}


@dataclass(frozen=True)
class RideSegment(Segment):
    """Riding one route from where the commuter boards to where they get off."""
    route: Route
    board_m: float
    alight_m: float
    distance_km: Decimal
    fare: Decimal | None          # None when no real fare rule is available
    board_place: Place = NOWHERE
    alight_place: Place = NOWHERE
    kind: str = field(default="ride", init=False)

    @property
    def board_point(self) -> geo.LatLng:
        return self.route.point_at(self.board_m)

    @property
    def alight_point(self) -> geo.LatLng:
        return self.route.point_at(self.alight_m)

    @property
    def path(self) -> tuple[geo.LatLng, ...]:
        return self.route.slice(self.board_m, self.alight_m)

    @property
    def heading(self) -> str | None:
        """'Agdao' for a both-ways route named 'Maa - Agdao' ridden forwards."""
        return directions.heading(self.route, forward=self.alight_m > self.board_m)

    def to_dict(self) -> dict:
        def end(point: geo.LatLng, along: float, place: Place) -> dict:
            return {"lat": point.lat, "lng": point.lng, "along_m": round(along),
                    "place": place.to_dict()}
        return {
            "kind": self.kind,
            "route": {"code": self.route.code, "name": self.route.name,
                      "color": self.route.color, "vehicle_type": self.route.vehicle_type},
            "heading": self.heading,
            "board": end(self.board_point, self.board_m, self.board_place),
            "alight": end(self.alight_point, self.alight_m, self.alight_place),
            "distance_km": float(self.distance_km),
            "fare": float(self.fare) if self.fare is not None else None,
            "path": _points(self.path),
        }


@dataclass(frozen=True)
class Trip:
    """A complete itinerary: walk, one or more rides (with transfers), walk."""
    segments: tuple[Segment, ...]

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
            "total_fare": float(fare) if fare is not None else None,
            "fare_available": fare is not None,
            "segments": [{**s.to_dict(), "instruction": text}
                         for s, text in zip(self.segments, directions.trip_instructions(self.segments))],
        }


class TripPlanner:
    """Plans trips between two points on the map.

    1. Finds where each route passes within walking distance of the origin and
       of the destination (functional helpers).
    2. Asks the logic engine for route plans between them, transferring where
       routes cross or come within a short walk (Prolog).
    3. Builds Trip objects with walking, ride distances and fares, then ranks them.
    """

    def __init__(self, network: Network, finder: TripFinder, settings: Settings) -> None:
        self.network = network
        self.finder = finder
        self.settings = settings

    def access(self, point: geo.LatLng) -> tuple[Access, ...]:
        """Places to catch a route near `point`, nearest first."""
        s = self.settings
        found = connections.access_points(self.network.samples, point, s.walk_radius_m,
                                          s.access_window_m)
        return found[:s.max_access_points]

    def nearby_routes(self, point: geo.LatLng) -> tuple[tuple[Route, Access], ...]:
        """Each route passing within walking distance, with its closest point."""
        closest: dict[str, Access] = {}
        for a in self.access(point):
            closest.setdefault(a.route, a)
        return tuple((self.network.routes[code], a) for code, a in closest.items())

    def plan(self, origin: geo.LatLng, destination: geo.LatLng,
             rider_type: str = "regular", max_transfers: int | None = None) -> tuple[Trip, ...]:
        starts = {(a.route, round(a.along_m)): a for a in self.access(origin)}
        goals = {(a.route, round(a.along_m)): a for a in self.access(destination)}
        if not starts or not goals:
            return ()
        cap = self.settings.max_transfers if max_transfers is None else max_transfers
        raw_plans = self.finder([(*k, round(a.walk_m)) for k, a in starts.items()],
                                [(*k, round(a.walk_m)) for k, a in goals.items()], cap)
        trips = [self._build_trip(p, origin, destination, starts, goals, rider_type)
                 for p in raw_plans]
        return ranking.rank_trips(trips, self.settings.max_results)

    def _strategy(self, route: Route, rider_type: str) -> FareStrategy | None:
        rule = self.network.fare_rules.get(route.vehicle_type)
        return strategy_for(rider_type, rule) if rule else None

    def _ride(self, leg: RawLeg, rider_type: str) -> RideSegment:
        code, board_m, alight_m, ride_m, _ = leg
        route = self.network.routes[code]
        km = (Decimal(ride_m) / 1000).quantize(Decimal("0.001"))
        strategy = self._strategy(route, rider_type)
        fare = None if strategy is None or strategy.is_placeholder else strategy.fare_for(km)
        landmarks = self.network.landmarks
        return RideSegment(route=route, board_m=board_m, alight_m=alight_m, distance_km=km,
                           fare=fare,
                           board_place=directions.place_for(route.point_at(board_m), landmarks),
                           alight_place=directions.place_for(route.point_at(alight_m), landmarks))

    def _build_trip(self, raw_plan: list[RawLeg], origin: geo.LatLng, destination: geo.LatLng,
                    starts: Mapping[tuple[str, int], Access], goals: Mapping[tuple[str, int], Access],
                    rider_type: str) -> Trip:
        rides = [self._ride(leg, rider_type) for leg in raw_plan]
        first, last = rides[0], rides[-1]
        segments: list[Segment] = [WalkSegment(
            "Your location", directions.place_label(first.board_place, first.route),
            origin, first.board_point, starts[(first.route.code, raw_plan[0][1])].walk_m)]
        for i, ride in enumerate(rides):
            segments.append(ride)
            walk_next = raw_plan[i][4]
            if i + 1 < len(rides) and walk_next >= MIN_TRANSFER_WALK_M:
                nxt = rides[i + 1]
                segments.append(WalkSegment(
                    directions.place_label(ride.alight_place, ride.route),
                    directions.place_label(nxt.board_place, nxt.route),
                    ride.alight_point, nxt.board_point, walk_next))
        segments.append(WalkSegment(
            directions.place_label(last.alight_place, last.route), "Destination",
            last.alight_point, destination, goals[(last.route.code, raw_plan[-1][2])].walk_m))
        return Trip(segments=tuple(segments))
