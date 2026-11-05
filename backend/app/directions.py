"""Commuter-friendly directions.                           (FUNCTIONAL PARADIGM)

Jeepneys pick up and drop off anywhere, so directions never count stops.
Instead each boarding/alighting point is described by a landmark:
  - "at"   the stop itself is a landmark          -> "get off at SM Ecoland"
  - "near" a landmark is within LANDMARK_RADIUS_M -> "get off near SM Ecoland"
  - "none" no landmark close by                   -> "get off after about 1.7 km"

Pure functions only: values in, new values out.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Iterable, Literal, Sequence

from .geo import haversine_m

if TYPE_CHECKING:
    from .models import Route, Segment, Stop

LANDMARK_RADIUS_M = 300.0


@dataclass(frozen=True)
class Place:
    """How to describe a point on the map to a commuter."""
    kind: Literal["at", "near", "none"]
    name: str | None = None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name}


NOWHERE = Place("none")


def nearest_landmark(stop: Stop, landmarks: Iterable[Stop],
                     max_m: float = LANDMARK_RADIUS_M) -> Stop | None:
    candidates = filter(lambda pd: pd[1] <= max_m,
                        map(lambda lm: (lm, haversine_m(stop, lm)), landmarks))
    best = min(candidates, key=lambda pd: pd[1], default=None)
    return best[0] if best else None


def place_for(stop: Stop, landmarks: Iterable[Stop], max_m: float = LANDMARK_RADIUS_M) -> Place:
    if stop.is_landmark:
        return Place("at", stop.name)
    nearby = nearest_landmark(stop, landmarks, max_m)
    return Place("near", nearby.name) if nearby else NOWHERE


def place_label(place: Place, route: Route) -> str:
    """Short label for a boarding/alighting point, e.g. on a walking segment."""
    return {"at": place.name, "near": f"near {place.name}", "none": f"{route.code} route"}[place.kind]


def distance_text(metres: float) -> str:
    """'120 m' for short distances (nearest 10 m), '1.7 km' otherwise."""
    return f"{max(10, round(metres / 10) * 10):.0f} m" if metres < 950 else f"{metres / 1000:.1f} km"


def route_label(route: Route) -> str:
    return f"{route.code} ({route.name})"


def walk_to_ride(distance_m: float, route: Route, board: Place) -> str:
    target = {
        "at": f"{board.name}",
        "near": f"the {route.code} route near {board.name}",
        "none": f"the {route.code} route",
    }[board.kind]
    return f"Walk {distance_text(distance_m)} to {target}"


def ride(route: Route, alight: Place, km: Decimal, is_transfer: bool) -> str:
    verb = "Transfer to" if is_transfer else "Ride"
    about = f"about {distance_text(float(km) * 1000)}"
    end = {
        "at": f"get off at {alight.name}, {about}",
        "near": f"get off near {alight.name}, {about}",
        "none": f"get off after {about}",
    }[alight.kind]
    return f"{verb} {route_label(route)} and {end}"


def walk_to_destination(distance_m: float) -> str:
    return f"Walk {distance_text(distance_m)} to your destination"


def trip_instructions(segments: Sequence[Segment]) -> tuple[str, ...]:
    """One instruction per segment: walk, ride, (transfer ride...), walk."""
    from .models import RideSegment, WalkSegment

    def instruction(i: int) -> str:
        seg = segments[i]
        if isinstance(seg, RideSegment):
            is_transfer = any(isinstance(s, RideSegment) for s in segments[:i])
            return ride(seg.route, seg.alight_place, seg.distance_km, is_transfer)
        assert isinstance(seg, WalkSegment)
        following = segments[i + 1] if i + 1 < len(segments) else None
        if isinstance(following, RideSegment):
            return walk_to_ride(seg.distance_m, following.route, following.board_place)
        return walk_to_destination(seg.distance_m)

    return tuple(map(instruction, range(len(segments))))
