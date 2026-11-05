-- ============================================================
-- SAMPLE DATA ONLY. Not real routes, stops, distances or fares.
-- Replace through the admin page with data the group has
-- collected and verified (fill in data_source and collected_on).
-- ============================================================

BEGIN;

INSERT INTO stops (name, landmark, lat, lng, data_source) VALUES
  ('Sample Stop A', 'placeholder', 7.0700, 125.6100, 'PLACEHOLDER'),
  ('Sample Stop B', 'placeholder', 7.0730, 125.6125, 'PLACEHOLDER'),
  ('Sample Stop C', 'placeholder', 7.0760, 125.6150, 'PLACEHOLDER'),
  ('Sample Stop D', 'placeholder', 7.0790, 125.6130, 'PLACEHOLDER'),
  ('Sample Stop E', 'placeholder', 7.0820, 125.6110, 'PLACEHOLDER');

INSERT INTO routes (code, name, color, is_bidirectional, data_source) VALUES
  ('R01', 'Sample Route 1 (A - C)', '#E53935', TRUE,  'PLACEHOLDER'),
  ('R02', 'Sample Route 2 (C - E)', '#43A047', TRUE,  'PLACEHOLDER');

-- R01: A -> B -> C ; R02: C -> D -> E  (transfer at C)
INSERT INTO route_stops (route_id, stop_id, sequence_no, distance_from_prev_km)
SELECT r.id, s.id, v.seq, v.km
FROM (VALUES
  ('R01', 'Sample Stop A', 1, 0.000),
  ('R01', 'Sample Stop B', 2, 0.430),
  ('R01', 'Sample Stop C', 3, 0.430),
  ('R02', 'Sample Stop C', 1, 0.000),
  ('R02', 'Sample Stop D', 2, 0.400),
  ('R02', 'Sample Stop E', 3, 0.400)
) AS v(code, stop_name, seq, km)
JOIN routes r ON r.code = v.code
JOIN stops  s ON s.name = v.stop_name;

-- Placeholder values to be replaced with the cited LTFRB fare matrix.
-- The 20% discount is a placeholder to be confirmed against the official rule.
INSERT INTO fare_rules (vehicle_type, base_fare, base_km, per_km_rate,
                        discount_rate, effective_date, source, is_placeholder)
VALUES ('jeepney', 0.00, 4.00, 0.00, 0.200, '2000-01-01',
        'PLACEHOLDER - replace with official LTFRB fare matrix citation', TRUE);

COMMIT;
