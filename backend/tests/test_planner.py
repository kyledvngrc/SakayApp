"""TripPlanner and ranking, with real Prolog but no database."""
from decimal import Decimal as D

import pytest

from app import prolog_bridge
from app.config import Settings, settings
from app.fare_calc import FareRule
from app.geo import LatLng
from app.models import Network, Route, Stop, TripPlanner

# Small test network on a straight north-south line (~110 m per 0.001 deg).
#   R1: 1-2-3-4     R2: 4-5-6     R3 (express): 1-4
STOPS = {i: Stop(i, f"S{i}", 7.000 + 0.004 * (i - 1), 125.6) for i in range(1, 7)}
ROUTES = {
    "R1": Route("R1", "Route 1", "#E53935", "jeepney", True, (1, 2, 3, 4)),
    "R2": Route("R2", "Route 2", "#43A047", "jeepney", True, (4, 5, 6)),
    "R3": Route("R3", "Express", "#1E88E5", "jeepney", True, (1, 4)),
}
RULE = FareRule("jeepney", D("10.00"), D("4"), D("1.50"), D("0.20"), "test fixture", False)


def legs_for(routes):
    out = {}
    for r in routes.values():
        for a, b in zip(r.stop_ids, r.stop_ids[1:]):
            km = D("0.44") * abs(b - a)
            out[(r.code, a, b)] = km
            out[(r.code, b, a)] = km
    return out


def make_planner(rule=RULE, routes=ROUTES):
    net = Network(STOPS, routes, legs_for(routes), {"jeepney": rule} if rule else {})
    prolog_bridge.start(settings.prolog_rules_path)
    prolog_bridge.load_legs(net.legs)
    return TripPlanner(net, prolog_bridge.find_trips, Settings(walk_radius_m=300))


def at(stop_id, north_m=0.0):
    s = STOPS[stop_id]
    return LatLng(s.lat + north_m / 111_195, s.lng)


def test_direct_trip_preferred_and_deduped():
    trips = make_planner().plan(at(1), at(4))
    codes = [t.route_codes for t in trips]
    assert codes[0] in {("R1",), ("R3",)} and trips[0].transfers == 0
    assert len(codes) == len(set(codes)), "one trip per route sequence"


def test_transfer_trip_segments():
    trips = make_planner().plan(at(1), at(6))
    best = trips[0]
    assert best.transfers == 1 and best.route_codes[-1] == "R2"
    kinds = [s.kind for s in best.segments]
    assert kinds == ["walk", "ride", "ride", "walk"]
    assert best.total_fare == D("20.00")             # two boardings, each under base km


def test_discount_applied_per_ride():
    best = make_planner().plan(at(1), at(6), rider_type="student")[0]
    assert best.total_fare == D("16.00")


def test_placeholder_rule_gives_no_fare():
    rule = FareRule("jeepney", D("0"), D("4"), D("0"), D("0.2"), "PLACEHOLDER", True)
    best = make_planner(rule=rule).plan(at(1), at(6))[0]
    assert best.total_fare is None and best.to_dict()["fare_available"] is False


def test_missing_rule_gives_no_fare():
    assert make_planner(rule=None).plan(at(1), at(6))[0].total_fare is None


def test_too_far_from_any_stop():
    assert make_planner().plan(at(1, north_m=-5000), at(6)) == ()


def test_max_transfers_zero():
    assert make_planner().plan(at(1), at(6), max_transfers=0) == ()


def test_walk_segments_measure_distance():
    best = make_planner().plan(at(1, north_m=-100), at(6))[0]
    assert best.segments[0].distance_m == pytest.approx(100, abs=2)
