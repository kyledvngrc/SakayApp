"""Fare strategies.                                          (OOP PARADIGM)

A FareStrategy turns a ride distance into a fare. Rider types pick a strategy:
regular riders use RegularFare; students, seniors and PWDs use DiscountedFare,
which inherits RegularFare and swaps in the discounted base fare and per-km
rate from the fare matrix.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from .fare_calc import FareRule, distance_fare

DISCOUNTED_RIDERS = frozenset({"student", "senior", "pwd"})


class FareStrategy(ABC):
    """Computes the fare for one ride under a given fare rule."""

    def __init__(self, rule: FareRule) -> None:
        self.rule = rule

    @property
    def is_placeholder(self) -> bool:
        return self.rule.is_placeholder

    @abstractmethod
    def fare_for(self, km: Decimal) -> Decimal:
        """Fare in pesos for riding `km` kilometres."""


class RegularFare(FareStrategy):
    """Full fare: base fare plus the per-km rate past the base distance."""

    def rates(self) -> tuple[Decimal, Decimal]:
        """(base fare, per-km rate) charged to this rider."""
        return self.rule.base_fare, self.rule.per_km_rate

    def fare_for(self, km: Decimal) -> Decimal:
        base, per_km = self.rates()
        return distance_fare(base, per_km, self.rule, km)


class DiscountedFare(RegularFare):
    """Student / senior / PWD fare: same calculation, discounted amounts."""

    def rates(self) -> tuple[Decimal, Decimal]:
        return self.rule.discounted_base_fare, self.rule.discounted_per_km_rate


def strategy_for(rider_type: str, rule: FareRule) -> FareStrategy:
    return DiscountedFare(rule) if rider_type in DISCOUNTED_RIDERS else RegularFare(rule)
