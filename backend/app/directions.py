"""Commuter-friendly directions.                           (FUNCTIONAL PARADIGM)

Jeepneys pick up and drop off anywhere, so directions describe a point on the
road by the closest landmark, when there is one:
  - "at"   a landmark within AT_RADIUS_M        -> "get off at SM Ecoland"
  - "near" a landmark within LANDMARK_RADIUS_M  -> "get off near SM Ecoland"
  - "none" no landmark close by                 -> "get off after about 1.7 km"

Pure functions only: values in, new values out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Iterable, Literal, Sequence

from .geo import HasLatLng, haversine_m

if TYPE_CHECKING:
    from .models import Landmark, Route, Segment

AT_RADIUS_M = 40.0
LANDMARK_RADIUS_M = 300.0
_NAME_ENDS = re.compile(r"\s+[-–—]\s+|\s+to\s+", re.IGNORECASE)


@dataclass(frozen=True)
class Place:
    """How to describe a point on the map to a commuter."""
    kind: Literal["at", "near", "none"]
    name: str | None = None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name}


NOWHERE = Place("none")


def nearest_landmark(point: HasLatLng, landmarks: Iterable[Landmark],
                     max_m: float = LANDMARK_RADIUS_M) -> tuple[Landmark, float] | None:
    candidates = filter(lambda ld: ld[1] <= max_m,
                        map(lambda lm: (lm, haversine_m(point, lm)), landmarks))
    return min(candidates, key=lambda ld: ld[1], default=None)


def place_for(point: HasLatLng, landmarks: Iterable[Landmark],
              max_m: float = LANDMARK_RADIUS_M) -> Place:
    found = nearest_landmark(point, landmarks, max_m)
    if found is None:
        return NOWHERE
    landmark, distance = found
    return Place("at" if distance <= AT_RADIUS_M else "near", landmark.name)


def heading(route: Route, forward: bool) -> str | None:
    """Which way to ride a both-ways route, from its name ("Maa - Agdao").

    The line is drawn from the first place in the name to the last, so riding
    forwards heads to the last one. One-way routes only go one way: None.
    """
    if route.kind != "both":
        return None
    ends = [p.strip() for p in _NAME_ENDS.split(route.name) if p.strip()]
    if len(ends) < 2:
        return None
    return ends[-1] if forward else ends[0]


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
        "at": f"the {route.code} route at {board.name}",
        "near": f"the {route.code} route near {board.name}",
        "none": f"the {route.code} route",
    }[board.kind]
    return f"Walk {distance_text(distance_m)} to {target}"


def ride(route: Route, alight: Place, km: Decimal, is_transfer: bool,
         toward: str | None = None) -> str:
    verb = "Transfer to" if is_transfer else "Ride"
    direction = f" toward {toward}" if toward else ""
    about = f"about {distance_text(float(km) * 1000)}"
    end = {
        "at": f"get off at {alight.name}, {about}",
        "near": f"get off near {alight.name}, {about}",
        "none": f"get off after {about}",
    }[alight.kind]
    return f"{verb} {route_label(route)}{direction} and {end}"


def walk_to_destination(distance_m: float) -> str:
    return f"Walk {distance_text(distance_m)} to your destination"


def trip_instructions(segments: Sequence[Segment]) -> tuple[str, ...]:
    """One instruction per segment: walk, ride, (walk,) transfer ride, ..., walk."""
    from .models import RideSegment, WalkSegment

    def instruction(i: int) -> str:
        seg = segments[i]
        if isinstance(seg, RideSegment):
            is_transfer = any(isinstance(s, RideSegment) for s in segments[:i])
            return ride(seg.route, seg.alight_place, seg.distance_km, is_transfer, seg.heading)
        assert isinstance(seg, WalkSegment)
        following = segments[i + 1] if i + 1 < len(segments) else None
        if isinstance(following, RideSegment):
            return walk_to_ride(seg.distance_m, following.route, following.board_place)
        return walk_to_destination(seg.distance_m)

    return tuple(map(instruction, range(len(segments))))
