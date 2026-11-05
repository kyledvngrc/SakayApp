-- SakayApp schema (PostgreSQL 16)
-- Route data is entered by admins. Each route is a line drawn along the streets;
-- jeepneys pick up and drop off anywhere on it, so there are no fixed stops.
-- The back-end computes where routes cross or come within walking distance
-- (transfer points) from the lines and asserts them into Prolog.

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

-- Named places used in directions ("get off near SM Ecoland"). Optional.
CREATE TABLE landmarks (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT,                    -- e.g. "in front of the main gate"
    lat          DOUBLE PRECISION NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lng          DOUBLE PRECISION NOT NULL CHECK (lng BETWEEN -180 AND 180),
    data_source  TEXT,
    collected_on DATE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_landmarks_lat_lng ON landmarks (lat, lng);

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
    path_geojson     JSONB NOT NULL,        -- GeoJSON LineString drawn in the admin page,
                                            -- in the direction the jeepney travels
    data_source      TEXT,
    collected_on     DATE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Fares are data, never hard-coded. Values must be cited from the official matrix.
CREATE TABLE fare_rules (
    id             SERIAL PRIMARY KEY,
    vehicle_type   vehicle_type NOT NULL,
    base_fare      NUMERIC(6,2) NOT NULL CHECK (base_fare >= 0),
    base_km        NUMERIC(5,2) NOT NULL CHECK (base_km >= 0),
    per_km_rate    NUMERIC(6,2) NOT NULL CHECK (per_km_rate >= 0),
    -- Student / senior / PWD amounts, entered as listed in the fare matrix.
    discounted_base_fare   NUMERIC(6,2) NOT NULL CHECK (discounted_base_fare >= 0),
    discounted_per_km_rate NUMERIC(6,2) NOT NULL CHECK (discounted_per_km_rate >= 0),
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
    rider_type      rider_type NOT NULL DEFAULT 'regular',
    result_count    INT NOT NULL DEFAULT 0,
    top_route_codes TEXT[],
    searched_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
