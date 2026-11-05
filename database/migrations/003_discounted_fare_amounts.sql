-- Discounted fares as amounts from the fare matrix, not a single rate (2026-11-05).
-- The matrix lists the student / senior / PWD base fare and per-km rate
-- separately (e.g. base 14.00 -> 11.20, per km 2.00 -> 1.60).
-- Existing rules are converted with their old discount rate.
--   docker compose exec -T db psql -U sakay -d sakay < database/migrations/003_discounted_fare_amounts.sql
BEGIN;

ALTER TABLE fare_rules
    ADD COLUMN discounted_base_fare   NUMERIC(6,2),
    ADD COLUMN discounted_per_km_rate NUMERIC(6,2);

UPDATE fare_rules
   SET discounted_base_fare   = round(base_fare   * (1 - discount_rate), 2),
       discounted_per_km_rate = round(per_km_rate * (1 - discount_rate), 2);

ALTER TABLE fare_rules
    ALTER COLUMN discounted_base_fare   SET NOT NULL,
    ALTER COLUMN discounted_per_km_rate SET NOT NULL,
    ADD CHECK (discounted_base_fare >= 0),
    ADD CHECK (discounted_per_km_rate >= 0),
    DROP COLUMN discount_rate;

COMMIT;
