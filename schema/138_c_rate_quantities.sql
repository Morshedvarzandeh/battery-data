-- =====================================================================
-- battery-data : 138_c_rate_quantities.sql
--
-- Current limits printed only as a C-rate.
--
-- Many sheets print "20C cont / 70C pulse" and never say which capacity the
-- C refers to (nominal, minimum, typical, at which rate). Two wrong ways to
-- store that were available: put 20 in a current quantity with unit "C",
-- which this schema's unit table reads as twenty coulombs, or multiply by a
-- capacity the source never named as the reference. These quantities hold the
-- rate as printed. A source that prints amperes still goes in the *_current
-- quantities; nothing here is converted.
--
-- Unit: 'C-rate' (1/h, stored in SI as 1/s). Same required conditions as the
-- ampere quantities they shadow.
-- =====================================================================

SET search_path = bd, public;

INSERT INTO unit (symbol, si_symbol, factor, offset_, dimension) VALUES
  ('C-rate', '1/s', 1.0 / 3600, 0, 'c_rate')
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO quantity (code, label, si_unit, dimension, required_conditions, is_derived, description) VALUES
('max_continuous_discharge_rate', 'Max continuous discharge rate (C-rate)', '1/s', 'c_rate', '{temperature_c}', false,
 'A continuous discharge limit printed only as a multiple of capacity. Keep the capacity basis in '
 'conditions.extra or rate_reference_*; never convert to amperes unless the source does.'),
('max_pulse_discharge_rate', 'Max pulse discharge rate (C-rate)', '1/s', 'c_rate', '{pulse_duration_s,temperature_c}', false,
 'A pulse discharge limit printed only as a C-rate. A pulse without a duration is uninterpretable; '
 'declare it unstated when the source omits it.'),
('max_continuous_charge_rate', 'Max continuous charge rate (C-rate)', '1/s', 'c_rate', '{temperature_c}', false,
 'A charge limit printed only as a C-rate. When the source does not say whether a rate is standard '
 'or maximum, continuous or peak, record that in conditions.extra.'),
('standard_charge_rate', 'Standard charge rate (C-rate)', '1/s', 'c_rate', '{temperature_c}', false,
 'The recommended (standard) charge rate printed only as a C-rate.')
ON CONFLICT (code) DO NOTHING;
