-- =====================================================================
-- battery-data : 131_component_quantities.sql
--
-- The quantities a battery SYSTEM needs and a cell datasheet never has:
-- what its contactors, fuses, pyro-fuses, DC-DC converters, chargers,
-- BMS and sensors are rated for -- and the quantities lead-acid practice
-- uses that lithium practice does not.
--
-- The rule is the one in 130: every required condition is there because
-- the field has shown that omitting it produces numbers that look
-- comparable and are not.
--
--   * A DC contactor's breaking capacity is meaningless without the
--     circuit voltage and the L/R time constant of the test circuit: the
--     same device interrupts 2000 A at 450 V with L/R = 1 ms and far less
--     with a longer time constant. UL 1604 / IEC 60947-4-1 / EV-specific
--     tests all state both. So both are required.
--   * A fuse's rated current is a derating curve pretending to be a number:
--     it is stated at an ambient temperature and falls above it.
--   * Contact resistance is quoted at a test current, and rises at low
--     currents where the film resistance dominates.
--   * Conversion efficiency is a surface over load and input voltage; a
--     "96% efficient" converter is 96% at one operating point.
--   * Cold cranking amps mean different things under SAE J537, EN 50342-1,
--     DIN 43539 and JIS D 5301: different temperature, duration and cutoff.
--     Temperature, duration and cutoff are therefore required conditions,
--     and the standard is recorded in condition_set.extra.standard.
-- =====================================================================

SET search_path = bd, public;

INSERT INTO unit (symbol, si_symbol, factor, offset_, dimension) VALUES
  ('kA','A',1e3,0,'current'),
  ('A2s','A2s',1,0,'i2t'),                    ('kA2s','A2s',1e6,0,'i2t'),
  ('min','s',60,0,'time'),                    ('ms','s',1e-3,0,'time'),
  ('us','s',1e-6,0,'time'),
  ('mV/°C','V/K',1e-3,0,'entropic'),          ('mV/degC','V/K',1e-3,0,'entropic'),
  ('mV/K','V/K',1e-3,0,'entropic'),
  ('MΩ','ohm',1e6,0,'resistance'),            ('Mohm','ohm',1e6,0,'resistance'),
  ('kΩ','ohm',1e3,0,'resistance'),            ('kohm','ohm',1e3,0,'resistance'),
  ('operations','1',1,0,'dimensionless')
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO quantity
  (code, label, si_unit, dimension, required_conditions, is_derived, bdf_name, description)
VALUES

-- ---- the gap the CATL derating map exposed -----------------------------
('max_pulse_charge_current','Max pulse charge current','A','current',
 '{pulse_duration_s,temperature_c}', false, NULL,
 'Regenerative-braking rating. Zero at and below 0 C on LFP; a pulse rating without a duration is uninterpretable.'),
('short_circuit_current','Short-circuit current','A','current', '{}', false, NULL,
 'Prospective short-circuit current of a cell, module or pack; what a fuse or pyro-fuse has to interrupt.'),

-- ---- switching and protection ------------------------------------------
('rated_voltage',       'Rated voltage',       'V','voltage',      '{}', false, NULL,
 'DC rated (insulation/operating) voltage of a contactor, fuse, busbar, connector or converter port.'),
('rated_current',       'Rated current',       'A','current',      '{temperature_c}', false, NULL,
 'Continuous carry current. A derating curve pretending to be a number: stated at an ambient and falling above it.'),
('breaking_capacity',   'Breaking capacity',   'A','current',
 '{circuit_voltage_v,time_constant_ms}', false, NULL,
 'Current a contactor or fuse can interrupt. DC interruption depends on circuit voltage and the L/R time constant; both are required.'),
('making_capacity',     'Making capacity',     'A','current',      '{circuit_voltage_v}', false, NULL,
 'Current a contactor can close onto without welding; pre-charge design depends on it.'),
('i2t_prearcing',       'Pre-arcing I2t',      'A2s','i2t',        '{}', false, NULL,
 'Melting integral of a fuse element; independent of voltage.'),
('i2t_total',           'Total clearing I2t',  'A2s','i2t',        '{circuit_voltage_v}', false, NULL,
 'Pre-arcing plus arcing integral; the arcing part depends on circuit voltage.'),
('minimum_breaking_current','Minimum breaking current','A','current','{circuit_voltage_v}', false, NULL,
 'Below this a fuse may melt without clearing; the gap between rated and minimum breaking current is where DC fuses fail dangerously.'),
('contact_resistance',  'Contact resistance',  'ohm','resistance', '{rate_value,rate_unit}', false, NULL,
 'Quoted at a test current (rate_value in A); film resistance dominates at low current.'),
('coil_voltage',        'Coil voltage',        'V','voltage',      '{}', false, NULL,
 'Nominal coil supply; pickup and dropout carry their own quantities.'),
('coil_power',          'Coil power',          'W','power',        '{}', false, NULL,
 'Hold power unless the statistic or extra says pickup; economiser coils differ by an order of magnitude between the two.'),
('pickup_voltage',      'Pickup voltage',      'V','voltage',      '{}', false, NULL, NULL),
('dropout_voltage',     'Dropout voltage',     'V','voltage',      '{}', false, NULL, NULL),
('electrical_endurance','Electrical endurance','1','dimensionless',
 '{circuit_voltage_v,rate_value,rate_unit}', false, NULL,
 'Operations under load; meaningless without the voltage and current switched.'),
('mechanical_endurance','Mechanical endurance','1','dimensionless','{}', false, NULL,
 'Operations with no load.'),
('dielectric_strength', 'Dielectric strength', 'V','voltage',      '{duration_s}', false, NULL,
 'Withstand voltage for a stated duration (usually 60 s), coil to contacts or terminal to case.'),
('insulation_resistance','Insulation resistance','ohm','resistance','{circuit_voltage_v}', false, NULL,
 'Measured at a stated DC test voltage (500 V and 1000 V are both common).'),
('voltage_drop',        'Voltage drop',        'V','voltage',      '{rate_value,rate_unit}', false, NULL,
 'Across a fuse or contactor at a stated current.'),
('cold_resistance',     'Cold resistance',     'ohm','resistance', '{}', false, NULL,
 'Fuse element resistance at 25 C before any current.'),
('power_dissipation',   'Power dissipation',   'W','power',        '{rate_value,rate_unit}', false, NULL,
 'At a stated current; sizes the busbar and cooling around a fuse or contactor.'),
('operate_time',        'Operate time',        's','time',         '{}', false, NULL,
 'Coil energised to contacts closed.'),
('release_time',        'Release time',        's','time',         '{}', false, NULL,
 'Coil de-energised to contacts open; a pyro-fuse states its firing time here.'),

-- ---- power conversion and sensing --------------------------------------
('input_voltage_min',   'Minimum input voltage','V','voltage',     '{}', false, NULL, NULL),
('input_voltage_max',   'Maximum input voltage','V','voltage',     '{}', false, NULL, NULL),
('output_voltage_min',  'Minimum output voltage','V','voltage',    '{}', false, NULL, NULL),
('output_voltage_max',  'Maximum output voltage','V','voltage',    '{}', false, NULL, NULL),
('output_current',      'Output current',      'A','current',      '{temperature_c}', false, NULL,
 'Continuous output of a converter or charger at a stated ambient; derates above it.'),
('conversion_efficiency','Conversion efficiency','1','dimensionless',
 '{circuit_voltage_v,rate_value,rate_unit}', false, NULL,
 'A surface over input voltage and load. rate_value/rate_unit carry the load point (W, A or pct of rated).'),
('switching_frequency', 'Switching frequency', 'Hz','frequency',   '{}', false, NULL, NULL),
('measurement_range_max','Measurement range',  'A','current',      '{}', false, NULL,
 'Full-scale current of a sensor or shunt.'),
('measurement_accuracy','Measurement accuracy','1','dimensionless','{temperature_c}', false, NULL,
 'Fraction of reading or of full scale; extra.basis says which. Temperature-dependent.'),
('balancing_current',   'Balancing current',   'A','current',      '{}', false, NULL,
 'Per-cell balancing current of a BMS.'),

-- ---- lead-acid ---------------------------------------------------------
('cold_cranking_current','Cold cranking current','A','current',
 '{temperature_c,duration_s,cutoff_voltage_v}', false, NULL,
 'SAE J537 (-18 C, 30 s, 7.2 V), EN 50342-1, DIN 43539 and JIS D 5301 differ in temperature, duration and cutoff. All three are required and the standard goes in extra.standard.'),
('reserve_capacity_minutes','Reserve capacity','s','time',
 '{load_value,load_unit,cutoff_voltage_v,temperature_c}', false, NULL,
 'Minutes to a cutoff at a fixed load (SAE: 25 A to 10.5 V at 27 C). A capacity in disguise, with its conditions.'),
('float_charge_voltage','Float charge voltage','V','voltage',      '{temperature_c}', false, NULL,
 'Standby voltage; temperature-compensated, so the reference temperature is required.'),
('cycle_charge_voltage','Cycle charge voltage','V','voltage',      '{temperature_c}', false, NULL,
 'Boost or cycle-use charge voltage; distinct from float.'),
('temperature_compensation_coefficient','Charge voltage temperature coefficient','V/K','entropic',
 '{}', false, NULL,
 'mV per degree per cell or per battery; extra.per says which.');
