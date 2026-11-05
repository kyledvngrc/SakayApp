"""Fare arithmetic.                                         (FUNCTIONAL PARADIGM)

Pure functions over an immutable FareRule. The rule's numbers always come from
the fare_rules table (cited from the official LTFRB fare matrix); nothing here
hard-codes a peso amount.

Assumption to confirm against the official matrix: distance past the base km is
charged per started kilometre (rounded up), and amounts are rounded to the
centavo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import reduce
from operator import add
from typing import Iterable

CENTAVO = Decimal("0.01")


@dataclass(frozen=True)
class FareRule:
    """One row of fare_rules (immutable)."""
    vehicle_type: str
    base_fare: Decimal
    base_km: Decimal
    per_km_rate: Decimal
    discount_rate: Decimal
    source: str
    is_placeholder: bool


def to_centavo(amount: Decimal) -> Decimal:
    return amount.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def extra_km(rule: FareRule, km: Decimal) -> int:
    """Whole kilometres charged beyond the base distance."""
    return max(0, math.ceil(km - rule.base_km))


def regular_fare(rule: FareRule, km: Decimal) -> Decimal:
    return to_centavo(rule.base_fare + rule.per_km_rate * extra_km(rule, km))


def apply_discount(amount: Decimal, rate: Decimal) -> Decimal:
    return to_centavo(amount * (Decimal("1") - rate))


def total_fare(amounts: Iterable[Decimal]) -> Decimal:
    """Sum of the fares of every ride in a trip (each boarding pays its own fare)."""
    return reduce(add, amounts, Decimal("0.00"))
