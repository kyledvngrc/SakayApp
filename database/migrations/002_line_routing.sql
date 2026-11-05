-- Switch from fixed stops to route lines (2026-11-05).
-- Jeepneys stop anywhere along their route, so trips are planned along the drawn
-- route lines. Transfer points are computed from the geometry, not stored.
--
-- Run once on an existing database (back it up first):
--   docker compose exec -T db psql -U sakay -d sakay < database/migrations/002_line_routing.sql
--
-- Removes: route_stops, walk_links, v_legs, and the auto-placed generic stops
-- (is_landmark = FALSE). Named stops are kept as landmarks.
BEGIN;

DROP VIEW IF EXISTS v_legs;
DROP TABLE IF EXISTS route_stops;
DROP TABLE IF EXISTS walk_links;

ALTER TABLE search_log DROP COLUMN IF EXISTS origin_stop_id,
                       DROP COLUMN IF EXISTS dest_stop_id;

DELETE FROM stops WHERE NOT is_landmark;
ALTER TABLE stops DROP COLUMN is_landmark;
ALTER TABLE stops RENAME COLUMN landmark TO description;
ALTER TABLE stops RENAME TO landmarks;
ALTER SEQUENCE stops_id_seq RENAME TO landmarks_id_seq;
ALTER INDEX idx_stops_lat_lng RENAME TO idx_landmarks_lat_lng;

-- A route is its line; one without a line cannot be planned.
ALTER TABLE routes ALTER COLUMN path_geojson SET NOT NULL;

COMMIT;
