"""Where commuters catch, leave and switch routes.         (FUNCTIONAL PARADIGM)

Each route line is sampled every few metres. From those samples:
  - access points: where to catch (or leave) a route near a place, one per
    pass of the route (a route that passes twice gives two choices);
  - links: where a commuter can get off one route and catch another, either
    where the lines cross or where they come within a short walk.

Pure functions: tuples in, new tuples out. No database, no Prolog.
"""

from __future__ import annotations

import math
from itertools import chain, groupby
from typing import Iterable, Mapping, NamedTuple, Sequence

from .geo import HasLatLng, LatLng, haversine_m

M_PER_DEG_LAT = 111_195.0


class Sample(NamedTuple):
    """A point on a route line, `along_m` metres from where the line starts."""
    route: str
    along_m: float
    point: LatLng


class Access(NamedTuple):
    """A place to catch or leave `route`, and the walk to it from somewhere."""
    route: str
    along_m: float
    point: LatLng
    walk_m: float


class Link(NamedTuple):
    """Get off `from_route` at from_m, walk walk_m, catch `to_route` at to_m."""
    from_route: str
    from_m: float
    from_point: LatLng
    to_route: str
    to_m: float
    to_point: LatLng
    walk_m: float


def _box(center: HasLatLng, radius_m: float) -> tuple[float, float, float, float]:
    dlat = radius_m / M_PER_DEG_LAT
    dlng = dlat / max(0.01, math.cos(math.radians(center.lat)))
    return center.lat - dlat, center.lat + dlat, center.lng - dlng, center.lng + dlng


def _in_box(p: HasLatLng, box: tuple[float, float, float, float]) -> bool:
    return box[0] <= p.lat <= box[1] and box[2] <= p.lng <= box[3]


def access_points(samples: Iterable[Sample], place: HasLatLng, radius_m: float,
                  window_m: float) -> tuple[Access, ...]:
    """Closest points on each route within `radius_m` of `place`.

    A sample is kept when no other sample of the same route within `window_m`
    along the line is closer, so each pass of a route near the place gives one
    access point, nearest first.
    """
    box = _box(place, radius_m)
    within = tuple(a for a in (Access(s.route, s.along_m, s.point, haversine_m(place, s.point))
                               for s in samples if _in_box(s.point, box))
                   if a.walk_m <= radius_m)

    def is_closest_nearby(a: Access) -> bool:
        return not any(b.route == a.route and abs(b.along_m - a.along_m) <= window_m
                       and (b.walk_m, b.along_m) < (a.walk_m, a.along_m) for b in within)

    return tuple(sorted(filter(is_closest_nearby, within), key=lambda a: a.walk_m))


def links(samples_by_route: Mapping[str, Sequence[Sample]], max_walk_m: float,
          spacing_m: float) -> tuple[Link, ...]:
    """Every place to switch from one route to another.

    Pairs samples of different routes at most `max_walk_m` apart, using a grid
    so only nearby samples are compared. Where two routes run side by side,
    one link (the shortest walk) is kept per `spacing_m` of the first route.
    """
    everything = tuple(chain.from_iterable(samples_by_route.values()))
    if not everything:
        return ()
    cell_lat = max_walk_m / M_PER_DEG_LAT
    cell_lng = cell_lat / max(0.01, math.cos(math.radians(everything[0].point.lat)))

    def cell(s: Sample) -> tuple[int, int]:
        return math.floor(s.point.lat / cell_lat), math.floor(s.point.lng / cell_lng)

    grid = {c: tuple(group) for c, group in groupby(sorted(everything, key=cell), key=cell)}

    def neighbours(s: Sample) -> Iterable[Sample]:
        cx, cy = cell(s)
        return chain.from_iterable(grid.get((cx + dx, cy + dy), ())
                                   for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    candidates = ((s, o, haversine_m(s.point, o.point))
                  for s in everything for o in neighbours(s) if o.route != s.route)
    close = filter(lambda c: c[2] <= max_walk_m, candidates)

    def group_key(c: tuple[Sample, Sample, float]) -> tuple[str, str, int]:
        return c[0].route, c[1].route, int(c[0].along_m // spacing_m)

    best = (min(group, key=lambda c: (c[2], c[0].along_m))
            for _, group in groupby(sorted(close, key=group_key), key=group_key))
    return tuple(Link(s.route, s.along_m, s.point, o.route, o.along_m, o.point, d)
                 for s, o, d in best)
