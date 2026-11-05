"""Fare logic tests. The numbers below are TEST FIXTURES, not real fares."""
from decimal import Decimal as D

import pytest

from app.fare_calc import FareRule, apply_discount, extra_km, regular_fare, total_fare
from app.fares import DiscountedFare, FareStrategy, RegularFare, strategy_for

RULE = FareRule("jeepney", base_fare=D("10.00"), base_km=D("4"), per_km_rate=D("1.50"),
                discount_rate=D("0.20"), source="test fixture", is_placeholder=False)


@pytest.mark.parametrize("km,extra", [("0", 0), ("4", 0), ("4.01", 1), ("5", 1), ("6.5", 3)])
def test_extra_km_rounds_started_km_up(km, extra):
    assert extra_km(RULE, D(km)) == extra


def test_regular_fare():
    assert regular_fare(RULE, D("3")) == D("10.00")
    assert regular_fare(RULE, D("6.5")) == D("14.50")


def test_discount_rounds_to_centavo():
    assert apply_discount(D("14.50"), D("0.20")) == D("11.60")
    assert apply_discount(D("10.01"), D("0.20")) == D("8.01")


def test_total_fare_reduces():
    assert total_fare([D("10.00"), D("11.50")]) == D("21.50")
    assert total_fare([]) == D("0.00")


@pytest.mark.parametrize("rider,cls", [("regular", RegularFare), ("student", DiscountedFare),
                                       ("senior", DiscountedFare), ("pwd", DiscountedFare)])
def test_strategy_for_rider(rider, cls):
    s = strategy_for(rider, RULE)
    assert type(s) is cls and isinstance(s, FareStrategy)


def test_discounted_inherits_regular():
    assert issubclass(DiscountedFare, RegularFare)
    assert DiscountedFare(RULE).fare_for(D("6.5")) == D("11.60")


def test_fare_strategy_is_abstract():
    with pytest.raises(TypeError):
        FareStrategy(RULE)
