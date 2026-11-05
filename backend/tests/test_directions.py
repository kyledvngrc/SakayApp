from decimal import Decimal as D

from app import directions as dr
from app.directions import Place
from app.models import Route, Stop

ROUTE = Route("R03", "Toril - Bankerohan", "#E53935", "jeepney", True, ())
MALL = Stop(1, "SM Ecoland", 7.0500, 125.6000, is_landmark=True)
SCHOOL = Stop(2, "Ateneo", 7.0700, 125.6000, is_landmark=True)
GENERIC_NEAR = Stop(3, "R03 stop 7", 7.0518, 125.6000)      # ~200 m from the mall
GENERIC_FAR = Stop(4, "R03 stop 9", 7.0600, 125.6000)       # ~1.1 km from both
LANDMARKS = (MALL, SCHOOL)


def test_place_at_landmark():
    assert dr.place_for(MALL, LANDMARKS) == Place("at", "SM Ecoland")


def test_place_near_closest_landmark():
    assert dr.place_for(GENERIC_NEAR, LANDMARKS) == Place("near", "SM Ecoland")


def test_place_none_when_no_landmark_close():
    assert dr.place_for(GENERIC_FAR, LANDMARKS) == dr.NOWHERE
    assert dr.place_for(GENERIC_NEAR, ()) == dr.NOWHERE


def test_distance_text():
    assert dr.distance_text(3) == "10 m"
    assert dr.distance_text(244) == "240 m"
    assert dr.distance_text(1720) == "1.7 km"


def test_ride_instruction_never_counts_stops():
    assert dr.ride(ROUTE, Place("at", "SM Ecoland"), D("1.72"), False) == \
        "Ride R03 (Toril - Bankerohan) and get off at SM Ecoland, about 1.7 km"
    assert dr.ride(ROUTE, Place("near", "Ateneo"), D("0.43"), True) == \
        "Transfer to R03 (Toril - Bankerohan) and get off near Ateneo, about 430 m"
    assert dr.ride(ROUTE, dr.NOWHERE, D("2.0"), False) == \
        "Ride R03 (Toril - Bankerohan) and get off after about 2.0 km"


def test_walk_instructions():
    assert dr.walk_to_ride(250, ROUTE, Place("at", "SM Ecoland")) == "Walk 250 m to SM Ecoland"
    assert dr.walk_to_ride(250, ROUTE, Place("near", "Ateneo")) == "Walk 250 m to the R03 route near Ateneo"
    assert dr.walk_to_ride(250, ROUTE, dr.NOWHERE) == "Walk 250 m to the R03 route"
    assert dr.walk_to_destination(118) == "Walk 120 m to your destination"


def test_place_label():
    assert dr.place_label(Place("near", "Ateneo"), ROUTE) == "near Ateneo"
    assert dr.place_label(dr.NOWHERE, ROUTE) == "R03 route"
