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
