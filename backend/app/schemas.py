"""Request validation schemas (pydantic)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

RiderType = Literal["regular", "student", "senior", "pwd"]


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class PlanRequest(BaseModel):
    origin: Point
    destination: Point
    rider_type: RiderType = "regular"
    max_transfers: int = Field(default=2, ge=0, le=2)

    @model_validator(mode="after")
    def different_points(self) -> "PlanRequest":
        if (self.origin.lat, self.origin.lng) == (self.destination.lat, self.destination.lng):
            raise ValueError("origin and destination must be different")
        return self


# --- Admin --------------------------------------------------------------------
from datetime import date  # noqa: E402
from decimal import Decimal  # noqa: E402

VehicleType = Literal["jeepney", "bus", "tricycle", "uv_express"]


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class LandmarkIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=200)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    data_source: str | None = Field(default=None, max_length=200)
    collected_on: date | None = None


class LandmarkPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    data_source: str | None = Field(default=None, max_length=200)
    collected_on: date | None = None


class RouteIn(BaseModel):
    """A route is the line it travels along, drawn in the direction of travel."""
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default="#1E88E5", pattern=r"^#[0-9A-Fa-f]{6}$")
    vehicle_type: VehicleType = "jeepney"
    is_bidirectional: bool = True
    is_active: bool = True
    path: list[Point] = Field(min_length=2, max_length=5000)
    data_source: str | None = Field(default=None, max_length=200)
    collected_on: date | None = None


class FareRuleIn(BaseModel):
    vehicle_type: VehicleType = "jeepney"
    base_fare: Decimal = Field(ge=0, max_digits=6, decimal_places=2)
    base_km: Decimal = Field(ge=0, max_digits=5, decimal_places=2)
    per_km_rate: Decimal = Field(ge=0, max_digits=6, decimal_places=2)
    discounted_base_fare: Decimal = Field(ge=0, max_digits=6, decimal_places=2)
    discounted_per_km_rate: Decimal = Field(ge=0, max_digits=6, decimal_places=2)
    effective_date: date
    source: str = Field(min_length=3, max_length=300)
    is_placeholder: bool = False

    @model_validator(mode="after")
    def discount_not_higher(self) -> "FareRuleIn":
        if (self.discounted_base_fare > self.base_fare
                or self.discounted_per_km_rate > self.per_km_rate):
            raise ValueError("discounted amounts cannot be higher than the regular ones")
        return self
