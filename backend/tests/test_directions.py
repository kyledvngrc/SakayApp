from decimal import Decimal as D

from app import directions as dr
from app.directions import Place
from app.models import Landmark, Route

from .lines import at, line

ROUTE = Route.from_line("R03", "Toril - Bankerohan", "#E53935", "jeepney", True,
                        line((0, 0), (0, 1000)), 100)
ONE_WAY = Route.from_line("R04", "Toril - Bankerohan", "#E53935", "jeepney", False,
                          line((0, 0), (0, 1000)), 100)
MALL = Landmark(1, "SM Ecoland", *at(0, 0))
SCHOOL = Landmark(2, "Ateneo", *at(0, 2000))
LANDMARKS = (MALL, SCHOOL)


def test_place_at_near_and_none():
    assert dr.place_for(at(20, 0), LANDMARKS) == Place("at", "SM Ecoland")
    assert dr.place_for(at(0, 200), LANDMARKS) == Place("near", "SM Ecoland")
    assert dr.place_for(at(0, 1000), LANDMARKS) == dr.NOWHERE
    assert dr.place_for(at(0, 0), ()) == dr.NOWHERE


def test_heading_from_route_name():
    assert dr.heading(ROUTE, forward=True) == "Bankerohan"
    assert dr.heading(ROUTE, forward=False) == "Toril"
    assert dr.heading(ONE_WAY, forward=True) is None
    plain = Route.from_line("X", "Bangkal", "#000000", "jeepney", True, line((0, 0), (0, 9)), 100)
    assert dr.heading(plain, True) is None


def test_distance_text():
    assert dr.distance_text(3) == "10 m"
    assert dr.distance_text(244) == "240 m"
    assert dr.distance_text(1720) == "1.7 km"


def test_ride_instruction():
    assert dr.ride(ROUTE, Place("at", "SM Ecoland"), D("1.72"), False) == \
        "Ride Toril - Bankerohan and get off at SM Ecoland, about 1.7 km"
    assert dr.ride(ROUTE, Place("near", "Ateneo"), D("0.43"), True, "Toril") == \
        "Transfer to Toril - Bankerohan toward Toril and get off near Ateneo, about 430 m"
    assert dr.ride(ROUTE, dr.NOWHERE, D("2.0"), False) == \
        "Ride Toril - Bankerohan and get off after about 2.0 km"


def test_walk_instructions():
    assert dr.walk_to_ride(250, ROUTE, Place("at", "SM Ecoland")) == "Walk 250 m to the Toril - Bankerohan route at SM Ecoland"
    assert dr.walk_to_ride(250, ROUTE, Place("near", "Ateneo")) == "Walk 250 m to the Toril - Bankerohan route near Ateneo"
    assert dr.walk_to_ride(250, ROUTE, dr.NOWHERE) == "Walk 250 m to the Toril - Bankerohan route"
    assert dr.walk_to_destination(118) == "Walk 120 m to your destination"


def test_place_label():
    assert dr.place_label(Place("near", "Ateneo"), ROUTE) == "near Ateneo"
    assert dr.place_label(dr.NOWHERE, ROUTE) == "Toril - Bankerohan route"
