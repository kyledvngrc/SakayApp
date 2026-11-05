import pytest

from app.connections import access_points, links
from app.models import Route

from .lines import at, line


def route(code, path, both=True):
    return Route.from_line(code, code, "#000000", "jeepney", both, path, 100)


NS = route("NS", line((0, 0), (0, 2000)))                       # north-south, 2 km
EW = route("EW", line((-1000, 1000), (1000, 1000)))             # crosses NS at 1 km north
PAR = route("PAR", line((150, 0), (150, 2000)))                 # parallel to NS, 150 m east
UTURN = route("U", line((0, -300), (400, -300), (400, -100), (0, -100)), both=False)


def test_access_one_point_per_pass():
    found = access_points(UTURN.samples(20), at(200, -200), radius_m=300, window_m=150)
    assert len(found) == 2                                       # passes south and north of it
    assert all(a.walk_m == pytest.approx(100, abs=1) for a in found)


def test_access_nearest_first_and_within_radius():
    found = access_points(NS.samples(20) + PAR.samples(20), at(40, 500), 500, 150)
    assert [a.route for a in found] == ["NS", "PAR"]
    assert found[0].walk_m == pytest.approx(40, abs=1) and found[0].along_m == pytest.approx(500, abs=10)
    assert access_points(NS.samples(20), at(800, 500), 500, 150) == ()


def test_crossing_link():
    found = [l for l in links({"NS": NS.samples(20), "EW": EW.samples(20)}, 200, 300)
             if l.from_route == "NS" and l.walk_m < 20]
    assert len(found) == 1
    assert found[0].from_m == pytest.approx(1000, abs=20) and found[0].to_m == pytest.approx(1000, abs=20)


def test_side_by_side_routes_link_every_spacing():
    found = [l for l in links({"NS": NS.samples(20), "PAR": PAR.samples(20)}, 200, 300)
             if l.from_route == "NS"]
    assert len(found) == 7                                       # 2 km / 300 m bins
    assert all(l.walk_m == pytest.approx(150, abs=1) for l in found)


def test_too_far_apart_no_link():
    far = route("FAR", line((500, 0), (500, 2000)))
    assert links({"NS": NS.samples(20), "FAR": far.samples(20)}, 200, 300) == ()
