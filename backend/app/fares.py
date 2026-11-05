"""Fare strategies.                                          (OOP PARADIGM)

A FareStrategy turns a ride distance into a fare. Rider types pick a strategy:
regular riders use RegularFare; students, seniors and PWDs use DiscountedFare,
which inherits RegularFare and applies the discount rate from fare_rules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from .fare_calc import FareRule, apply_discount, regular_fare

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

    def fare_for(self, km: Decimal) -> Decimal:
        return regular_fare(self.rule, km)


class DiscountedFare(RegularFare):
    """Student / senior / PWD fare: the regular fare minus the discount rate."""

    def fare_for(self, km: Decimal) -> Decimal:
        return apply_discount(super().fare_for(km), self.rule.discount_rate)


def strategy_for(rider_type: str, rule: FareRule) -> FareStrategy:
    return DiscountedFare(rule) if rider_type in DISCOUNTED_RIDERS else RegularFare(rule)
