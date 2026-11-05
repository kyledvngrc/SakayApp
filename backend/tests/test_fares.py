"""Fare logic tests. The numbers below are TEST FIXTURES, not real fares."""
from decimal import Decimal as D

import pytest

from app.fare_calc import FareRule, discounted_fare, extra_km, regular_fare, total_fare
from app.fares import DiscountedFare, FareStrategy, RegularFare, strategy_for

# Same shape as a fare matrix row: regular 14.00 + 2.00/km, discounted 11.20 + 1.60/km.
RULE = FareRule("jeepney", base_fare=D("14.00"), base_km=D("4"), per_km_rate=D("2.00"),
                discounted_base_fare=D("11.20"), discounted_per_km_rate=D("1.60"),
                source="test fixture", is_placeholder=False)


@pytest.mark.parametrize("km,extra", [("0", 0), ("4", 0), ("4.01", 1), ("5", 1), ("6.5", 3)])
def test_extra_km_rounds_started_km_up(km, extra):
    assert extra_km(RULE, D(km)) == extra


def test_regular_fare():
    assert regular_fare(RULE, D("3")) == D("14.00")
    assert regular_fare(RULE, D("6.5")) == D("20.00")              # 14 + 3 x 2


def test_discounted_fare_uses_its_own_amounts():
    assert discounted_fare(RULE, D("3")) == D("11.20")
    assert discounted_fare(RULE, D("6.5")) == D("16.00")           # 11.20 + 3 x 1.60
    rounded = FareRule("jeepney", D("13.00"), D("4"), D("1.80"), D("10.40"), D("1.50"), "test", False)
    assert discounted_fare(rounded, D("5")) == D("11.90")          # not a fixed percentage


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
    assert DiscountedFare(RULE).fare_for(D("6.5")) == D("16.00")
    assert RegularFare(RULE).fare_for(D("6.5")) == D("20.00")


def test_fare_strategy_is_abstract():
    with pytest.raises(TypeError):
        FareStrategy(RULE)
