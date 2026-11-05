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


class StopIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    landmark: str | None = Field(default=None, max_length=200)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    data_source: str | None = Field(default=None, max_length=200)
    collected_on: date | None = None


class StopPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    landmark: str | None = Field(default=None, max_length=200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    data_source: str | None = Field(default=None, max_length=200)
    collected_on: date | None = None


class RouteStopRef(BaseModel):
    """An existing stop (id) or a new stop to create (name + lat/lng)."""
    id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def existing_or_new(self) -> "RouteStopRef":
        if self.id is None and (self.name is None or self.lat is None or self.lng is None):
            raise ValueError("a new stop needs name, lat and lng")
        return self


class RouteIn(BaseModel):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default="#1E88E5", pattern=r"^#[0-9A-Fa-f]{6}$")
    vehicle_type: VehicleType = "jeepney"
    is_bidirectional: bool = True
    is_active: bool = True
    path: list[Point] = Field(default_factory=list)
    stops: list[RouteStopRef] = Field(min_length=2)
    data_source: str | None = Field(default=None, max_length=200)
    collected_on: date | None = None

    @model_validator(mode="after")
    def no_repeated_stops(self) -> "RouteIn":
        ids = [s.id for s in self.stops if s.id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("a stop can appear only once on a route")
        return self


class FareRuleIn(BaseModel):
    vehicle_type: VehicleType = "jeepney"
    base_fare: Decimal = Field(ge=0, max_digits=6, decimal_places=2)
    base_km: Decimal = Field(ge=0, max_digits=5, decimal_places=2)
    per_km_rate: Decimal = Field(ge=0, max_digits=6, decimal_places=2)
    discount_rate: Decimal = Field(ge=0, lt=1, max_digits=4, decimal_places=3)
    effective_date: date
    source: str = Field(min_length=3, max_length=300)
    is_placeholder: bool = False
