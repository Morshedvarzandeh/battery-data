-- Battery protection and precharge: these are component ratings, not cell
-- impedance, stored battery energy, or converter output power.
SET search_path = bd, public;
INSERT INTO quantity (code,label,si_unit,dimension,required_conditions,is_derived,description) VALUES
('resistance_rating','Nominal resistor resistance','ohm','resistance','{temperature_c}',false,'Exact ordering-code resistance; distinguish from measured cell impedance.'),
('resistance_tolerance','Resistor resistance tolerance (±)','1','dimensionless','{}',false,'Symmetric tolerance magnitude, normally recorded in percent; not an absolute ohm tolerance.'),
('resistor_power_rating','Resistor dissipation rating','W','power','{temperature_c,temperature_reference,mounting_condition}',false,'Preserve case versus ambient temperature and heatsink/free-air mounting; not converter output power.'),
('resistor_pulse_energy','Resistor pulse energy rating','J','energy','{pulse_duration_s,temperature_c,temperature_reference,mounting_condition,pulse_waveform,pulse_wait_s}',false,'Energy per pulse under the stated waveform, mounting and recovery wait. Not battery stored energy or an unconditional pulse limit.'),
('resistor_voltage_limit','Resistor element voltage limit','V','voltage','{electrical_system}',false,'Element operating limit, not dielectric withstand. Power and resistance may impose a lower working voltage.'),
('fuse_trip_current','Fuse trigger current','A','current','{temperature_c}',false,'Trigger setting, distinct from continuous rated current and breaking capacity; retain asymmetric tolerances.'),
('minimum_interrupting_current','Minimum interrupting current','A','current','{test_voltage_v,electrical_system}',false,'Lower interruption limit of a partial-range fuse, distinct from maximum breaking capacity. Preserve circuit L/R and duty in extra.');
