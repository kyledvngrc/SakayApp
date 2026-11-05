"""Settings read from the environment / .env file at the repo root."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


def _path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else REPO_ROOT / p


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://sakay@localhost:5432/sakay")
    prolog_rules_path: Path = _path(os.getenv("PROLOG_RULES_PATH", "prolog/routes.pl"))
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    token_ttl_hours: int = 12

    # Trip search (distances in metres)
    walk_radius_m: float = 500.0       # furthest walk to catch / from the last route
    transfer_walk_m: float = 200.0     # furthest walk between two routes
    max_transfers: int = 2
    max_results: int = 5
    max_access_points: int = 16        # places to catch a route tried at each end

    # Route geometry
    sample_step_m: float = 20.0        # route lines are checked every this many metres
    access_window_m: float = 150.0     # one access point per pass of a route
    link_spacing_m: float = 300.0      # where routes run side by side, a transfer every ...
    loop_tolerance_m: float = 100.0    # a one-way line ending this close to its start is a loop


    # Place search (OpenStreetMap via Photon), biased to Davao City
    photon_url: str = os.getenv("PHOTON_URL", "https://photon.komoot.io")
    photon_timeout_s: float = 4.0
    city_center: tuple[float, float] = (7.0731, 125.6128)
    city_bbox: tuple[float, float, float, float] = (125.20, 6.95, 125.75, 7.60)   # W, S, E, N


settings = Settings()
