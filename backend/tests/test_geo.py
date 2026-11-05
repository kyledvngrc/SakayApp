from app.geo import (LatLng, cumulative_m, geojson_path, haversine_m, is_closed, nearby,
                     point_at, position_along, sample_line, slice_path)

D = 1000 / 111_195          # ~1 km of latitude
L_PATH = (LatLng(7.0, 125.6), LatLng(7.0 + D, 125.6), LatLng(7.0 + D, 125.6 + D / 0.99255))


def test_haversine_one_degree_latitude():
    assert abs(haversine_m(LatLng(7.0, 125.6), LatLng(8.0, 125.6)) - 111_195) < 50


def test_haversine_zero():
    assert haversine_m(LatLng(7.07, 125.61), LatLng(7.07, 125.61)) == 0


def test_nearby_filters_sorts_and_limits():
    pts = [LatLng(7.0, 125.0), LatLng(7.001, 125.0), LatLng(7.003, 125.0), LatLng(7.1, 125.0)]
    found = nearby(pts, LatLng(7.0, 125.0), radius_m=400, limit=2)
    assert [p for p, _ in found] == [pts[0], pts[1]]


def test_cumulative_and_point_at():
    cum = cumulative_m(L_PATH)
    assert abs(cum[-1] - 2000) < 5
    mid = point_at(L_PATH, cum, 1500)
    assert haversine_m(mid, LatLng(7.0 + D, 125.6 + D / 0.99255 / 2)) < 5
    assert point_at(L_PATH, cum, -10) == L_PATH[0] and point_at(L_PATH, cum, 99999) == L_PATH[-1]


def test_slice_path_forward_and_backward():
    cum = cumulative_m(L_PATH)
    forward = slice_path(L_PATH, cum, 500, 1500)
    assert len(forward) == 3 and forward[1] == L_PATH[1]          # passes the corner
    backward = slice_path(L_PATH, cum, 1500, 500)
    assert backward == tuple(reversed(forward))


def test_is_closed():
    loop = (LatLng(7.0, 125.6), LatLng(7.0 + D, 125.6), LatLng(7.0 + D, 125.61), LatLng(7.0005, 125.6))
    assert is_closed(loop, 100) and not is_closed(L_PATH, 100)


def test_sample_line_includes_ends():
    cum = cumulative_m(L_PATH)
    samples = sample_line(L_PATH, cum, 300)
    assert samples[0][0] == 0 and abs(samples[-1][0] - cum[-1]) < 1e-6
    assert all(b[0] - a[0] <= 300 for a, b in zip(samples, samples[1:]))


def test_position_along_reports_offset():
    along, offset = position_along(L_PATH, LatLng(7.0 + D / 2, 125.6005))
    assert abs(along - 500) < 5 and abs(offset - 55) < 3


def test_geojson_path():
    assert geojson_path({"type": "LineString", "coordinates": [[125.6, 7.0], [125.7, 7.1]]}) == (
        LatLng(7.0, 125.6), LatLng(7.1, 125.7))
    assert geojson_path(None) is None and geojson_path({"type": "Point"}) is None
