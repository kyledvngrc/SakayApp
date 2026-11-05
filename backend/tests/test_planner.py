"""TripPlanner with real Prolog but no database (TEST DATA ONLY)."""
from decimal import Decimal as D

import pytest

from app import prolog_bridge
from app.config import Settings, settings
from app.fare_calc import FareRule
from app.models import Landmark, Network, Route, TripPlanner

from .lines import at, line

S = Settings(walk_radius_m=300)
RULE = FareRule("jeepney", D("10.00"), D("4"), D("1.50"), D("0.20"), "test fixture", False)


def route(code, name, path, both=True):
    return Route.from_line(code, name, "#123456", "jeepney", both, path, S.loop_tolerance_m)


#   NS: Plaza - Market, 3 km north.   EW: West - East, crosses NS at 2 km north.
#   PAR: parallel to EW 150 m further north (walk transfer from NS only near its end).
#   ONE: one way, east from (0, -1000) to (2000, -1000).
#   LOOP: one-way loop around a 1 km square south-west of the base.
ROUTES = {r.code: r for r in [
    route("NS", "Plaza - Market", line((0, 0), (0, 3000))),
    route("EW", "West - East", line((-2000, 2000), (2000, 2000))),
    route("ONE", "One Way", line((0, -1000), (2000, -1000)), both=False),
    route("LOOP", "Loop", line((-3000, 0), (-2000, 0), (-2000, -1000), (-3000, -1000), (-3000, 0)),
          both=False),
]}
LANDMARKS = (Landmark(1, "City Hall", *at(0, 2010)), Landmark(2, "East Gate", *at(1500, 2050)))


def make_planner(rule=RULE, routes=ROUTES, extra=()):
    routes = {**routes, **{r.code: r for r in extra}}
    net = Network.build(routes, LANDMARKS, {"jeepney": rule} if rule else {}, S)
    prolog_bridge.start(settings.prolog_rules_path)
    prolog_bridge.load_network(net.routes.values(), net.links)
    return TripPlanner(net, prolog_bridge.best_trips, S)


def test_direct_ride_along_the_line():
    best = make_planner().plan(at(30, 100), at(-20, 1500))[0]
    assert best.route_codes == ("NS",) and best.transfers == 0
    assert float(best.ride_km) == pytest.approx(1.4, abs=0.03)
    assert [s.kind for s in best.segments] == ["walk", "ride", "walk"]
    assert best.segments[0].distance_m == pytest.approx(30, abs=2)


def test_transfer_where_lines_cross():
    best = make_planner().plan(at(0, 500), at(1500, 2100))[0]
    assert best.route_codes == ("NS", "EW")
    assert [s.kind for s in best.segments] == ["walk", "ride", "ride", "walk"]   # no walk between
    ns, ew = best.rides
    assert ns.alight_m == pytest.approx(2000, abs=20) and ew.board_m == pytest.approx(2000, abs=20)


def test_transfer_with_short_walk_between_routes():
    side = route("SIDE", "Side", line((150, 2600), (150, 5000)))          # 150 m east of NS, past EW
    best = make_planner(extra=(side,)).plan(at(0, 500), at(150, 4500))[0]
    assert best.route_codes == ("NS", "SIDE")
    walk = best.segments[2]
    assert walk.kind == "walk" and walk.distance_m == pytest.approx(150, abs=2)


def test_one_way_route_only_forward():
    planner = make_planner()
    assert planner.plan(at(300, -1000), at(1700, -1000))[0].route_codes == ("ONE",)
    assert planner.plan(at(1700, -1000), at(300, -1000)) == ()


def test_loop_wraps_around():
    # The loop starts at (-3000, 0); ride from its last side to its first side.
    best = make_planner().plan(at(-3000, -500), at(-2500, 0))[0]
    assert best.route_codes == ("LOOP",)
    assert float(best.ride_km) == pytest.approx(1.0, abs=0.05)               # 500 m + 500 m


def test_fares_per_ride_and_discount():
    planner = make_planner()
    assert planner.plan(at(0, 500), at(1500, 2100))[0].total_fare == D("20.00")
    assert planner.plan(at(0, 500), at(1500, 2100), "student")[0].total_fare == D("16.00")


def test_placeholder_or_missing_rule_gives_no_fare():
    rule = FareRule("jeepney", D("0"), D("4"), D("0"), D("0.2"), "PLACEHOLDER", True)
    best = make_planner(rule=rule).plan(at(0, 500), at(0, 1500))[0]
    assert best.total_fare is None and best.to_dict()["fare_available"] is False
    assert make_planner(rule=None).plan(at(0, 500), at(0, 1500))[0].total_fare is None


def test_too_far_from_any_route():
    assert make_planner().plan(at(5000, 500), at(0, 1500)) == ()


def test_max_transfers_zero():
    assert make_planner().plan(at(0, 500), at(1500, 2100), max_transfers=0) == ()


def test_ride_path_follows_the_line():
    ride = make_planner().plan(at(0, 500), at(1500, 2100))[0].rides[1]
    path = ride.path
    assert len(path) >= 2 and path[-1] == ride.alight_point


def test_instructions_use_landmarks_and_heading():
    trip = make_planner().plan(at(0, 500), at(1500, 2100))[0].to_dict()
    texts = [seg["instruction"] for seg in trip["segments"]]
    assert texts[0] == "Walk 10 m to the NS route"
    assert texts[1] == "Ride NS (Plaza - Market) toward Market and get off at City Hall, about 1.5 km"
    assert texts[2] == "Transfer to EW (West - East) toward East and get off near East Gate, about 1.5 km"
    assert texts[3].startswith("Walk ") and texts[3].endswith(" to your destination")
    assert "minutes" not in trip


def test_heading_backwards():
    trip = make_planner().plan(at(0, 2500), at(0, 600))[0]
    assert trip.rides[0].heading == "Plaza"


def test_nearby_routes():
    found = make_planner().nearby_routes(at(100, 2000))
    assert [r.code for r, _ in found][:2] == ["EW", "NS"]
