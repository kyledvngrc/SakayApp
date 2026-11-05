from decimal import Decimal

from app.geo import LatLng, haversine_m, nearby, path_km


def test_haversine_one_degree_latitude():
    assert abs(haversine_m(LatLng(7.0, 125.6), LatLng(8.0, 125.6)) - 111_195) < 50


def test_haversine_zero():
    assert haversine_m(LatLng(7.07, 125.61), LatLng(7.07, 125.61)) == 0


def test_nearby_filters_sorts_and_limits():
    pts = [LatLng(7.0, 125.0), LatLng(7.001, 125.0), LatLng(7.003, 125.0), LatLng(7.1, 125.0)]
    found = nearby(pts, LatLng(7.0, 125.0), radius_m=400, limit=2)
    assert [p for p, _ in found] == [pts[0], pts[1]]
    assert found[0][1] < found[1][1]


def test_nearby_does_not_mutate_input():
    pts = (LatLng(7.002, 125.0), LatLng(7.0, 125.0))
    nearby(pts, LatLng(7.0, 125.0), 1000, 5)
    assert pts == (LatLng(7.002, 125.0), LatLng(7.0, 125.0))


def test_path_km_sums_legs_in_order():
    legs = {("R1", 1, 2): Decimal("0.4"), ("R1", 2, 3): Decimal("0.6")}
    assert path_km(legs, "R1", (1, 2, 3)) == Decimal("1.0")
    assert path_km(legs, "R1", (1,)) == Decimal("0")
