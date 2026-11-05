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


# --- along-path distances -----------------------------------------------------
from app.geo import geojson_path, position_along, stop_distances_km  # noqa: E402

D = 1000 / 111_195          # ~1 km of latitude
L_PATH = (LatLng(7.0, 125.6), LatLng(7.0 + D, 125.6), LatLng(7.0 + D, 125.6 + D / 0.99255))


def test_position_along_l_shaped_path():
    along, offset = position_along(L_PATH, L_PATH[2])
    assert abs(along - 2000) < 5 and offset < 1


def test_position_along_reports_offset():
    along, offset = position_along(L_PATH, LatLng(7.0 + D / 2, 125.6005))
    assert abs(along - 500) < 5 and abs(offset - 55) < 3


def test_stop_distances_follow_the_line():
    assert stop_distances_km(L_PATH, [L_PATH[0], L_PATH[2]]) == (Decimal("0"), Decimal("2.0"))


def test_stop_distances_fall_back_to_straight_line():
    assert stop_distances_km(None, [L_PATH[0], L_PATH[2]])[1] == Decimal("1.414")
    assert stop_distances_km(L_PATH, [L_PATH[2], L_PATH[0]])[1] == Decimal("1.414")   # backwards


def test_geojson_path():
    assert geojson_path({"type": "LineString", "coordinates": [[125.6, 7.0], [125.7, 7.1]]}) == (
        LatLng(7.0, 125.6), LatLng(7.1, 125.7))
    assert geojson_path(None) is None and geojson_path({"type": "Point"}) is None
