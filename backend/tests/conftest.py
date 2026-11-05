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

# Sample network (TEST DATA ONLY), both routes run both ways:
#   R01 runs north ~1.1 km from (7.0700, 125.6100) to the corner (7.0800, 125.6100)
#   R02 runs east  ~1.1 km from that corner to (7.0800, 125.6200)
# They meet at the corner, where "Sample Corner" is a landmark.
SAMPLE_SQL = """
INSERT INTO landmarks (name, lat, lng, data_source) VALUES
  ('Sample Corner', 7.0800, 125.6101, 'test fixture'),
  ('Sample Plaza',  7.0700, 125.6101, 'test fixture');
INSERT INTO routes (code, name, color, is_bidirectional, path_geojson, data_source) VALUES
  ('R01', 'Plaza - Corner', '#E53935', TRUE,
   '{"type": "LineString", "coordinates": [[125.6100, 7.0700], [125.6100, 7.0800]]}', 'test fixture'),
  ('R02', 'Corner - East End', '#43A047', TRUE,
   '{"type": "LineString", "coordinates": [[125.6100, 7.0800], [125.6200, 7.0800]]}', 'test fixture');
INSERT INTO fare_rules (vehicle_type, base_fare, base_km, per_km_rate, discounted_base_fare,
                        discounted_per_km_rate, effective_date, source, is_placeholder)
VALUES ('jeepney', 0, 4, 0, 0, 0, '2000-01-01', 'test placeholder', TRUE);
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
