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

    # Trip search
    walk_radius_m: float = 500.0       # how far a commuter is asked to walk to/from a stop
    candidate_stops: int = 8           # nearest stops tried at each end
    max_transfers: int = 2
    max_results: int = 5

    # Time estimates (assumptions, shown to users as approximate)
    walk_m_per_min: float = 80.0       # about 4.8 km/h
    jeepney_kmh: float = 15.0          # average city speed incl. stops and traffic
    wait_min_per_ride: float = 5.0     # waiting for a jeepney at each boarding


settings = Settings()
