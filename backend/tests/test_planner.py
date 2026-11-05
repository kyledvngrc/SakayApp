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
# Stop 4 (the transfer stop) and 6 are landmarks; the others are generic.
STOPS = {i: Stop(i, f"S{i}", 7.000 + 0.004 * (i - 1), 125.6, is_landmark=i in (4, 6))
         for i in range(1, 7)}
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


def test_instructions_use_landmarks_not_stop_counts():
    best = make_planner().plan(at(1), at(6))[0].to_dict()
    texts = [seg["instruction"] for seg in best["segments"]]
    # Stop 1 is generic, stop 4 (S4) is 445 m away: beyond the 300 m landmark radius.
    assert texts[0].startswith("Walk 10 m to the ") and texts[0].endswith(" route")
    assert texts[1].endswith("and get off at S4, about 1.3 km")
    assert texts[2].startswith("Transfer to R2 (Route 2) and get off at S6")
    assert texts[3] == "Walk 10 m to your destination"
    assert all("stops" not in t for t in texts)
    assert "num_stops" not in best["segments"][1]


def test_generic_stop_described_near_landmark():
    # Get off at stop 5 (generic), 445 m from S4 and S6 -> no landmark; move closer:
    stops = {**STOPS, 5: Stop(5, "S5", STOPS[6].lat - 0.002, 125.6)}   # ~220 m from S6
    net = make_planner().network
    from app.models import Network
    planner = TripPlanner(Network(stops, net.routes, net.leg_km, net.fare_rules),
                          prolog_bridge.find_trips, Settings(walk_radius_m=100))
    ride = next(s for s in planner.plan(at(4), LatLng(stops[5].lat, 125.6))[0].segments
                if s.kind == "ride")
    assert ride.alight_place.kind == "near" and ride.alight_place.name == "S6"
