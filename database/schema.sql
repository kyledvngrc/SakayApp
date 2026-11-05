-- SakayApp schema (PostgreSQL 16)
-- Route data is entered by admins; the back-end loads v_legs into Prolog as leg/3 facts.

BEGIN;

CREATE TYPE vehicle_type AS ENUM ('jeepney', 'bus', 'tricycle', 'uv_express');
CREATE TYPE user_role    AS ENUM ('admin', 'commuter');
CREATE TYPE rider_type   AS ENUM ('regular', 'student', 'senior', 'pwd');

CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,          -- bcrypt hash, never plain text
    display_name  TEXT,
    role          user_role NOT NULL DEFAULT 'commuter',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE stops (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    landmark     TEXT,                    -- e.g. "in front of SM Ecoland"
    is_landmark  BOOLEAN NOT NULL DEFAULT FALSE,  -- recognisable name, used in directions
    lat          DOUBLE PRECISION NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lng          DOUBLE PRECISION NOT NULL CHECK (lng BETWEEN -180 AND 180),
    data_source  TEXT,                    -- provenance, e.g. "group ride 2026-11-10"
    collected_on DATE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_stops_lat_lng ON stops (lat, lng);

CREATE TABLE routes (
    id               SERIAL PRIMARY KEY,
    code             TEXT NOT NULL UNIQUE   -- used as the Prolog atom, e.g. 'R03'
                     CHECK (code ~ '^[A-Za-z0-9_-]+$'),
    name             TEXT NOT NULL,         -- e.g. "Toril - Bankerohan"
    color            TEXT NOT NULL DEFAULT '#1E88E5'
                     CHECK (color ~ '^#[0-9A-Fa-f]{6}$'),
    vehicle_type     vehicle_type NOT NULL DEFAULT 'jeepney',
    is_bidirectional BOOLEAN NOT NULL DEFAULT TRUE,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    path_geojson     JSONB,                 -- GeoJSON LineString drawn in the admin page
    data_source      TEXT,
    collected_on     DATE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE route_stops (
    route_id              INT NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    stop_id               INT NOT NULL REFERENCES stops(id)  ON DELETE RESTRICT,
    sequence_no           INT NOT NULL CHECK (sequence_no >= 1),
    distance_from_prev_km NUMERIC(6,3) NOT NULL DEFAULT 0
                          CHECK (distance_from_prev_km >= 0),
    PRIMARY KEY (route_id, sequence_no),
    UNIQUE (route_id, stop_id)
);

-- Walking transfers between nearby stops, stored once per pair.
CREATE TABLE walk_links (
    stop_a     INT NOT NULL REFERENCES stops(id) ON DELETE CASCADE,
    stop_b     INT NOT NULL REFERENCES stops(id) ON DELETE CASCADE,
    distance_m INT NOT NULL CHECK (distance_m > 0),
    PRIMARY KEY (stop_a, stop_b),
    CHECK (stop_a < stop_b)
);

-- Fares are data, never hard-coded. Values must be cited from the official matrix.
CREATE TABLE fare_rules (
    id             SERIAL PRIMARY KEY,
    vehicle_type   vehicle_type NOT NULL,
    base_fare      NUMERIC(6,2) NOT NULL CHECK (base_fare >= 0),
    base_km        NUMERIC(5,2) NOT NULL CHECK (base_km >= 0),
    per_km_rate    NUMERIC(6,2) NOT NULL CHECK (per_km_rate >= 0),
    discount_rate  NUMERIC(4,3) NOT NULL DEFAULT 0
                   CHECK (discount_rate >= 0 AND discount_rate < 1),
    effective_date DATE NOT NULL,
    source         TEXT NOT NULL,          -- citation, e.g. LTFRB memorandum circular no.
    is_placeholder BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (vehicle_type, effective_date)
);

CREATE TABLE saved_trips (
    id          SERIAL PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label       TEXT,
    origin_lat  DOUBLE PRECISION NOT NULL,
    origin_lng  DOUBLE PRECISION NOT NULL,
    dest_lat    DOUBLE PRECISION NOT NULL,
    dest_lng    DOUBLE PRECISION NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Intentionally anonymous: no user id. Feeds the "popular routes" dashboard.
CREATE TABLE search_log (
    id              BIGSERIAL PRIMARY KEY,
    origin_stop_id  INT REFERENCES stops(id) ON DELETE SET NULL,
    dest_stop_id    INT REFERENCES stops(id) ON DELETE SET NULL,
    rider_type      rider_type NOT NULL DEFAULT 'regular',
    result_count    INT NOT NULL DEFAULT 0,
    top_route_codes TEXT[],
    searched_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Consecutive route_stops rows become legs; reverse legs added for bidirectional
-- routes; inactive routes excluded. The back-end asserts each row as
-- leg(RouteCode, FromStop, ToStop).
CREATE VIEW v_legs AS
WITH ordered AS (
    SELECT r.code AS route_code,
           r.vehicle_type,
           r.is_bidirectional,
           rs.stop_id,
           rs.sequence_no,
           LEAD(rs.stop_id)               OVER w AS next_stop,
           LEAD(rs.distance_from_prev_km) OVER w AS next_km
    FROM route_stops rs
    JOIN routes r ON r.id = rs.route_id
    WHERE r.is_active
    WINDOW w AS (PARTITION BY rs.route_id ORDER BY rs.sequence_no)
)
SELECT route_code, stop_id AS from_stop, next_stop AS to_stop,
       next_km AS km, vehicle_type
FROM ordered
WHERE next_stop IS NOT NULL
UNION ALL
SELECT route_code, next_stop AS from_stop, stop_id AS to_stop,
       next_km AS km, vehicle_type
FROM ordered
WHERE next_stop IS NOT NULL AND is_bidirectional;

COMMIT;
