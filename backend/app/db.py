"""Database access.                                        (IMPERATIVE PARADIGM)

Opens connections, runs SQL, and loops over rows to build the in-memory
Network snapshot used by the trip planner.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Sequence

import psycopg2
from psycopg2.extras import RealDictCursor

from .config import settings
from .fare_calc import FareRule
from .models import Network, Route, Stop


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


def load_network() -> Network:
    """Read stops, active routes, legs and current fare rules into a Network."""
    stops: dict[int, Stop] = {}
    for row in fetch_all("SELECT id, name, landmark, lat, lng FROM stops"):
        stops[row["id"]] = Stop(id=row["id"], name=row["name"], landmark=row["landmark"],
                                lat=row["lat"], lng=row["lng"])

    stop_ids_by_route: dict[int, list[int]] = {}
    for row in fetch_all("SELECT route_id, stop_id FROM route_stops ORDER BY route_id, sequence_no"):
        stop_ids_by_route.setdefault(row["route_id"], []).append(row["stop_id"])

    routes: dict[str, Route] = {}
    for row in fetch_all("""SELECT id, code, name, color, vehicle_type::text AS vehicle_type,
                                   is_bidirectional, path_geojson
                            FROM routes WHERE is_active"""):
        routes[row["code"]] = Route(
            code=row["code"], name=row["name"], color=row["color"],
            vehicle_type=row["vehicle_type"], is_bidirectional=row["is_bidirectional"],
            stop_ids=tuple(stop_ids_by_route.get(row["id"], [])),
            path_geojson=row["path_geojson"])

    leg_km = {}
    for row in fetch_all("SELECT route_code, from_stop, to_stop, km FROM v_legs"):
        leg_km[(row["route_code"], row["from_stop"], row["to_stop"])] = row["km"]

    # Latest rule already in effect, per vehicle type.
    fare_rules: dict[str, FareRule] = {}
    for row in fetch_all("""SELECT DISTINCT ON (vehicle_type) vehicle_type::text AS vehicle_type,
                                   base_fare, base_km, per_km_rate, discount_rate, source,
                                   is_placeholder
                            FROM fare_rules WHERE effective_date <= CURRENT_DATE
                            ORDER BY vehicle_type, effective_date DESC"""):
        fare_rules[row["vehicle_type"]] = FareRule(**row)

    return Network(stops=stops, routes=routes, leg_km=leg_km, fare_rules=fare_rules)


def log_search(origin_stop_id: int | None, dest_stop_id: int | None, rider_type: str,
               result_count: int, top_route_codes: list[str]) -> None:
    """Anonymous search log (no user id) for the popular-routes dashboard."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO search_log (origin_stop_id, dest_stop_id, rider_type,
                                       result_count, top_route_codes)
               VALUES (%s, %s, %s, %s, %s)""",
            (origin_stop_id, dest_stop_id, rider_type, result_count, top_route_codes))
