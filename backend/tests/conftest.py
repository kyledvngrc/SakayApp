"""Test setup: run every test against a throwaway database, never the real one.

Before any app module is imported, DATABASE_URL is pointed at `sakay_test`,
which is dropped, recreated from database/schema.sql, and filled with the
sample network below. Your real `sakay` database is never touched.
If PostgreSQL isn't running, the database tests skip themselves.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_DB = "sakay_test"

_real_url = os.getenv("DATABASE_URL") or dotenv_values(REPO_ROOT / ".env").get(
    "DATABASE_URL", "postgresql://sakay@localhost:5432/sakay")
_parts = urlsplit(_real_url)
TEST_URL = urlunsplit(_parts._replace(path=f"/{TEST_DB}"))
assert _parts.path.lstrip("/") != TEST_DB, "DATABASE_URL already points at the test database"

# Sample network (TEST DATA ONLY): R01 A-B-C, R02 C-D-E, transfer at C.
SAMPLE_SQL = """
INSERT INTO stops (name, landmark, lat, lng, data_source, is_landmark) VALUES
  ('Sample Stop A', 'test', 7.0700, 125.6100, 'test fixture', TRUE),
  ('Sample Stop B', 'test', 7.0730, 125.6125, 'test fixture', TRUE),
  ('Sample Stop C', 'test', 7.0760, 125.6150, 'test fixture', TRUE),
  ('Sample Stop D', 'test', 7.0790, 125.6130, 'test fixture', TRUE),
  ('Sample Stop E', 'test', 7.0820, 125.6110, 'test fixture', TRUE);
INSERT INTO routes (code, name, color, is_bidirectional, data_source) VALUES
  ('R01', 'Sample Route 1 (A - C)', '#E53935', TRUE, 'test fixture'),
  ('R02', 'Sample Route 2 (C - E)', '#43A047', TRUE, 'test fixture');
INSERT INTO route_stops (route_id, stop_id, sequence_no, distance_from_prev_km)
SELECT r.id, s.id, v.seq, v.km
FROM (VALUES ('R01', 'Sample Stop A', 1, 0.000), ('R01', 'Sample Stop B', 2, 0.430),
             ('R01', 'Sample Stop C', 3, 0.430), ('R02', 'Sample Stop C', 1, 0.000),
             ('R02', 'Sample Stop D', 2, 0.400), ('R02', 'Sample Stop E', 3, 0.400))
     AS v(code, stop_name, seq, km)
JOIN routes r ON r.code = v.code JOIN stops s ON s.name = v.stop_name;
INSERT INTO fare_rules (vehicle_type, base_fare, base_km, per_km_rate, discount_rate,
                        effective_date, source, is_placeholder)
VALUES ('jeepney', 0, 4, 0, 0.2, '2000-01-01', 'test placeholder', TRUE);
"""


def _build_test_database() -> bool:
    try:
        admin = psycopg2.connect(_real_url)
    except psycopg2.OperationalError:
        return False
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        cur.execute(f"CREATE DATABASE {TEST_DB}")
    admin.close()
    conn = psycopg2.connect(TEST_URL)
    with conn, conn.cursor() as cur:
        cur.execute((REPO_ROOT / "database" / "schema.sql").read_text())
        cur.execute(SAMPLE_SQL)
    conn.close()
    return True


DB_AVAILABLE = _build_test_database()
os.environ["DATABASE_URL"] = TEST_URL     # read by app.config, which is imported after this
