-- =====================================================================
-- battery-data : 139_lead_acid_quantities.sql
--
-- Ratings lead-acid sheets print and no lithium-ion sheet does.
--
-- A starter battery is sold on its cranking current and reserve capacity; a
-- standby battery on its float voltage. None of these is a capacity, a
-- discharge limit or a cut-off voltage, and storing them as one would make
-- them compare against lithium-ion figures they have nothing to do with.
--
--   cranking_current      CCA, CA/MCA, HCA and their pulse forms. One quantity,
--                         many ratings: the rating name and the standard
--                         (EN 50342-1, SAE J537, DIN, JIS) go in
--                         conditions.extra, because EN and SAE CCA differ in
--                         duration and end voltage.
--   reserve_capacity      minutes at a constant current (25 A in SAE J537) to
--                         an end voltage. A time; never ampere-hours.
--   float_charge_voltage  standby (float) charge voltage.
--   cyclic_charge_voltage absorption / boost / "bulk" stage voltage after
--                         cycling. Not a maximum voltage rating.
--   equalize_charge_voltage  periodic equalising charge of flooded batteries.
--   short_circuit_current prospective short-circuit current as printed
--                         (IEC 60896-21 defines it from a two-point DC test).
--
-- Unit: 'min' (minutes) for reserve capacity.
-- =====================================================================

SET search_path = bd, public;

INSERT INTO unit (symbol, si_symbol, factor, offset_, dimension) VALUES
  ('min', 's', 60, 0, 'time')
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO quantity (code, label, si_unit, dimension, required_conditions, is_derived, description) VALUES
('cranking_current', 'Cranking current', 'A', 'current', '{temperature_c,duration_s,voltage_lower_v}', false,
 'A starter-battery cranking rating: the current a fully charged battery holds for a set time at a set '
 'temperature above a set terminal voltage. Keep the rating (CCA, CA, MCA, HCA, ...) and the standard in '
 'conditions.extra; EN and SAE CCA are different tests and are never compared as one number.'),
('reserve_capacity', 'Reserve capacity', 's', 'time', '{rate_value,rate_unit,temperature_c,voltage_lower_v}', false,
 'Time a fully charged battery sustains a constant discharge current before reaching the end voltage. '
 'A time, not a charge: never convert to ampere-hours.'),
('float_charge_voltage', 'Float charge voltage', 'V', 'voltage', '{temperature_c}', false,
 'Constant voltage at which a charged lead-acid battery is held in standby. Keep any printed tolerance and '
 'temperature-compensation coefficient in conditions.extra.'),
('cyclic_charge_voltage', 'Cyclic (absorption) charge voltage', 'V', 'voltage', '{temperature_c}', false,
 'Constant-voltage limit of the absorption (boost, bulk) stage when a lead-acid battery is recharged after '
 'cycling. A charger setting, not a maximum voltage rating.'),
('equalize_charge_voltage', 'Equalize charge voltage', 'V', 'voltage', '{temperature_c}', false,
 'Periodic equalising (overcharge) voltage for flooded lead-acid batteries.'),
('short_circuit_current', 'Short-circuit current', 'A', 'current', '{temperature_c}', false,
 'Prospective short-circuit current as the source prints it. Keep the standard in conditions.extra; '
 'it is not a usable discharge rating.')
ON CONFLICT (code) DO NOTHING;
