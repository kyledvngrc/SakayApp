"""Database access.                                        (IMPERATIVE PARADIGM)

Opens connections, runs SQL, and loops over rows to build the in-memory
Network snapshot used by the trip planner.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Sequence

import psycopg2
from psycopg2.extras import RealDictCursor

from . import geo
from .config import Settings, settings
from .fare_calc import FareRule
from .models import Landmark, Network, Route


@contextmanager
def connection() -> Iterator[psycopg2.extensions.connection]:
    conn = psycopg2.connect(settings.database_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def transaction() -> Iterator[RealDictCursor]:
    """A dict cursor inside one transaction (commit on success, rollback on error)."""
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        yield cur


def fetch_all(sql: str, params: Sequence = ()) -> list[dict]:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def load_network(s: Settings = settings) -> Network:
    """Read active routes, landmarks and current fare rules into a Network."""
    routes: dict[str, Route] = {}
    for row in fetch_all("""SELECT code, name, color, vehicle_type::text AS vehicle_type,
                                   is_bidirectional, path_geojson
                            FROM routes WHERE is_active ORDER BY code"""):
        path = geo.geojson_path(row["path_geojson"])
        if not path or len(path) < 2:
            continue                                   # nothing to ride along
        routes[row["code"]] = Route.from_line(
            row["code"], row["name"], row["color"], row["vehicle_type"],
            row["is_bidirectional"], path, s.loop_tolerance_m)

    landmarks = [Landmark(id=row["id"], name=row["name"], lat=row["lat"], lng=row["lng"],
                          description=row["description"])
                 for row in fetch_all("SELECT id, name, description, lat, lng FROM landmarks")]

    # Latest rule already in effect, per vehicle type.
    fare_rules: dict[str, FareRule] = {}
    for row in fetch_all("""SELECT DISTINCT ON (vehicle_type) vehicle_type::text AS vehicle_type,
                                   base_fare, base_km, per_km_rate, discount_rate, source,
                                   is_placeholder
                            FROM fare_rules WHERE effective_date <= CURRENT_DATE
                            ORDER BY vehicle_type, effective_date DESC"""):
        fare_rules[row["vehicle_type"]] = FareRule(**row)

    return Network.build(routes, landmarks, fare_rules, s)


def log_search(rider_type: str, result_count: int, top_route_codes: list[str]) -> None:
    """Anonymous search log (no user id, no locations) for the popular-routes dashboard."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO search_log (rider_type, result_count, top_route_codes)
               VALUES (%s, %s, %s)""",
            (rider_type, result_count, top_route_codes))
