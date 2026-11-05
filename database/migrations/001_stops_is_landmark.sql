-- Adds stops.is_landmark: TRUE for stops with a name commuters recognise
-- (terminals, malls, schools, corners). Directions use landmarks; generic
-- auto-placed stops are described as "near <closest landmark>".
-- Safe to run on an existing database:
--   docker compose exec -T db psql -U sakay -d sakay < database/migrations/001_stops_is_landmark.sql
ALTER TABLE stops ADD COLUMN IF NOT EXISTS is_landmark BOOLEAN NOT NULL DEFAULT FALSE;
