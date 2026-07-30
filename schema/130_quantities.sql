-- =====================================================================
-- battery-data : 130_quantities.sql
--
-- The quantity registry. `required_conditions` is the enforcement
-- mechanism described in docs/02-conventions.md: it is the list of
-- condition_set columns without which the quantity is not a fact.
--
-- Read the required_conditions column as an argument. Every entry is
-- there because the field has demonstrated, in published datasheets or
-- published papers, that omitting it produces numbers that look
-- comparable and are not.
-- =====================================================================

SET search_path = bd, public;

INSERT INTO quantity
  (code, label, si_unit, dimension, required_conditions, is_derived, bdf_name, description)
VALUES

-- ---- pure attributes: no conditions needed --------------------------
('mass',                'Mass',                'kg','mass',        '{}', false, NULL,
 'Basis matters (max vs typical, with or without wrap/washer/film) - record it in statistic and condition_set.extra.'),
('diameter',            'Diameter',            'm','length',       '{}', false, NULL,
 'Bare-can and with-sleeve diameters differ; Samsung publishes both. Use condition_set.extra.includes_wrap.'),
('height',              'Height',              'm','length',       '{}', false, NULL, NULL),
('length',              'Length',              'm','length',       '{}', false, NULL, NULL),
('width',               'Width',               'm','length',       '{}', false, NULL, NULL),
('thickness',           'Thickness',           'm','length',       '{}', false, NULL, NULL),
('volume',              'Volume',              'm3','volume',      '{}', false, NULL,
 'Circumscribed cylinder, bounding box and displaced volume differ by ~21% for cylindricals.'),
('electrode_area',      'Electrode area',      'm2','area',        '{}', false, NULL,
 'Required for any areal normalisation or ASI figure; pair with area_kind.'),
('nominal_voltage',     'Nominal voltage',     'V','voltage',      '{}', false, NULL,
 'A convention, not a measurement: 3.6 / 3.69 / 3.7 V all appear for the same class of cell. '
 'Record the basis in condition_set.extra.nominal_voltage_basis.'),
('charge_cutoff_voltage','Charge cutoff voltage','V','voltage',    '{}', false, NULL, NULL),
('discharge_cutoff_voltage','Discharge cutoff voltage','V','voltage','{}',false, NULL,
 'May itself be temperature-dependent: EVE uses 2.5 V above 0 C and 2.0 V at or below.'),
('absolute_max_voltage','Absolute maximum voltage','V','voltage',  '{}', false, NULL, NULL),
('absolute_min_voltage','Absolute minimum voltage','V','voltage',  '{}', false, NULL, NULL),
('shipping_voltage',    'Shipping voltage',    'V','voltage',      '{}', false, NULL, NULL),
('series_count',        'Cells in series',     '1','dimensionless','{}', false, NULL, NULL),
('parallel_count',      'Cells in parallel',   '1','dimensionless','{}', false, NULL, NULL),
('lithium_content',     'Lithium metal content','kg','mass',       '{}', false, NULL, NULL),

-- ---- capacity: the worst offender -----------------------------------
('capacity',            'Capacity',            'C','electric_charge',
 '{rate_value,rate_unit,temperature_c,voltage_lower_v}', false, NULL,
 'Meaningless without rate, temperature and discharge cutoff. Samsung INR21700-50E lists '
 '4900 mAh (0.2C "standard") and 4753 mAh (1C "rated") on the same page.'),
('energy',              'Energy',              'J','energy',
 '{rate_value,rate_unit,temperature_c}', false, NULL,
 'LG publishes no Ah rating for the M50LT at all, only Wh, and defines end-of-life on energy.'),
('usable_energy',       'Usable energy',       'J','energy',
 '{boundary,dod_pct}', false, NULL,
 'Nominal, usable, and guaranteed-at-year-N are three different quantities. '
 'Powerwall 3 quotes 13.5 kWh AC, i.e. already after inverter losses.'),
('specific_energy',     'Specific energy',     'J/kg','specific_energy',
 '{rate_value,rate_unit,temperature_c}', true, NULL,
 'Derived. Inherits the mass basis; max-mass understates and typical-mass overstates.'),
('energy_density',      'Energy density',      'J/m3','energy_density',
 '{rate_value,rate_unit,temperature_c}', true, NULL, 'Derived; inherits the volume basis.'),
('specific_power',      'Specific power',      'W/kg','specific_power',
 '{temperature_c,soc_pct,pulse_duration_s}', true, NULL, NULL),
('service_life_hours',  'Service life',        's','time',
 '{load_value,load_unit,duty_schedule,cutoff_voltage_v,temperature_c}', false, NULL,
 'Primary-cell datasheets (alkaline, Li/FeS2) have no capacity field at all - only '
 'service hours against a load, a duty schedule and a cutoff.'),

-- ---- resistance: never comparable without its method ----------------
('internal_resistance_ac','AC internal resistance','ohm','resistance',
 '{frequency_hz,soc_pct,temperature_c}', false, 'ac_internal_resistance_ohm',
 'The LG M50LT lists AC 1 kHz = 15 mohm and DC 10 s = 23 mohm for the same cell: 53% apart. '
 'Energizer states L91 is "120 to 240 milliohms (depending on method)".'),
('internal_resistance_dc','DC internal resistance','ohm','resistance',
 '{pulse_duration_s,pulse_current_a,soc_pct,temperature_c,direction}', false, 'dc_internal_resistance_ohm',
 'Pulse duration is the dominant variable and is usually unstated. 1/2/10/18/30 s capture '
 'different physics (ohmic, then charge transfer, then diffusion).'),
('area_specific_impedance','Area specific impedance','ohm*m2','area_specific_impedance',
 '{pulse_duration_s,soc_pct,temperature_c,area_cm2,area_kind}', true, NULL,
 'ASI = R x A, but A is variously separator area, single-sided or double-sided cathode area.'),
('ohmic_resistance',    'Ohmic resistance (EIS)','ohm','resistance',
 '{soc_pct,temperature_c}', true, NULL, 'High-frequency real-axis intercept.'),
('charge_transfer_resistance','Charge transfer resistance','ohm','resistance',
 '{soc_pct,temperature_c}', true, NULL,
 'Uninterpretable without the equivalent circuit string it was fitted with.'),

-- ---- current limits: 2-D lookup surfaces, not scalars ---------------
('max_continuous_discharge_current','Max continuous discharge current','A','current',
 '{temperature_c}', false, NULL,
 'LG M50LT: 0.5C at -20..10 C, 3.0C at 10..25 C, 1.5C at 25..55 C. A single scalar is wrong '
 'two-thirds of the time.'),
('max_continuous_charge_current','Max continuous charge current','A','current',
 '{temperature_c}', false, NULL, NULL),
('max_pulse_discharge_current','Max pulse discharge current','A','current',
 '{pulse_duration_s,temperature_c}', false, NULL,
 'A pulse rating without a duration is uninterpretable. Samsung states "max non-continuous '
 '14700 mA" with no duration at all.'),
('standard_charge_current','Standard charge current','A','current',
 '{temperature_c}', false, NULL, NULL),
('cv_cutoff_current',   'CV termination current','A','current', '{}', false, NULL, NULL),
('rated_power',         'Rated power',         'W','power',
 '{temperature_c,boundary}', false, NULL, NULL),
('peak_power',          'Peak power',          'W','power',
 '{pulse_duration_s,soc_pct,temperature_c,boundary}', false, NULL, NULL),

-- ---- efficiency ------------------------------------------------------
('round_trip_efficiency','Round-trip efficiency','1','dimensionless',
 '{boundary,rate_value,rate_unit,temperature_c}', false, NULL,
 'Megapack 2 XL quotes 91.7% (2-hour) and 93.7% (4-hour) for the same product. BYD quotes DC, '
 'Tesla quotes AC. Auxiliary inclusion moves it by points and is almost never stated.'),
('coulombic_efficiency','Coulombic efficiency','1','dimensionless',
 '{rate_value,rate_unit,temperature_c,cycle_index}', true, NULL,
 'A CV hold makes CE definitionally different. High-precision coulometry needs the temperature '
 'stability spec, not the setpoint.'),
('energy_efficiency',   'Energy efficiency',   '1','dimensionless',
 '{rate_value,rate_unit,temperature_c}', true, NULL, NULL),

-- ---- life ------------------------------------------------------------
('cycle_life',          'Cycle life',          '1','dimensionless',
 '{temperature_c,dod_pct,rate_value,rate_unit}', false, NULL,
 'A function, not a number. Molicel P45B at 500 cycles, 23 C: >=80% at 4.5 A, >=75% at 10 A, '
 '>=70% at 20 A. One cell, three answers. Prismatic figures additionally require clamp force '
 '(EVE specifies 300 kgf +/- 20).'),
('capacity_retention',  'Capacity retention',  '1','dimensionless',
 '{cycle_index,temperature_c,rate_value,rate_unit}', true, NULL, NULL),
('energy_retention',    'Energy retention',    '1','dimensionless',
 '{cycle_index,temperature_c}', true, NULL, NULL),
('resistance_growth',   'Resistance growth',   '1','dimensionless',
 '{cycle_index,temperature_c,pulse_duration_s}', true, NULL, NULL),
('calendar_life',       'Calendar life',       's','time',
 '{temperature_c,soc_pct}', false, NULL, NULL),
('knee_point_cycle',    'Knee point',          '1','dimensionless',
 '{temperature_c,dod_pct}', true, NULL,
 'No field consensus on the algorithm, and "knee point" and "knee onset" are different '
 'quantities. Always store the algorithm and version alongside.'),
('self_discharge_rate', 'Self-discharge rate', '1','dimensionless',
 '{temperature_c,soc_pct,duration_s}', false, NULL,
 'mV/day, uA, %/month and stand-test retention are not interconvertible without the OCV-SOC '
 'slope. Never coerce between them.'),
('leakage_current',     'Leakage current',     'A','current',
 '{temperature_c,soc_pct}', false, NULL, NULL),

-- ---- thermal ---------------------------------------------------------
('specific_heat_capacity','Specific heat capacity','J/(kg*K)','specific_heat',
 '{soc_pct,temperature_c}', false, NULL,
 'SOC-dependent: 6% difference between 50% and 100% SOC in a verified 20 Ah LFP measurement.'),
('thermal_conductivity_through_plane','Through-plane thermal conductivity','W/(m*K)','thermal_conductivity',
 '{temperature_c}', false, NULL,
 'Through-plane and in-plane differ by ~52x on the same pouch cell. A scalar k is a '
 'data-destroying schema choice.'),
('thermal_conductivity_in_plane','In-plane thermal conductivity','W/(m*K)','thermal_conductivity',
 '{temperature_c}', false, NULL, NULL),
('entropic_coefficient','Entropic coefficient','V/K','entropic',
 '{soc_pct,temperature_c}', false, NULL,
 'Sign convention and units both vary (mV/K, V/K, J/mol/K), and potentiometric, calorimetric '
 'and frequency-domain methods disagree.'),
('heat_generation_rate','Heat generation rate','W','power',
 '{rate_value,rate_unit,soc_pct,temperature_c}', false, NULL, NULL),
('runaway_onset_temperature','Thermal runaway onset temperature','K','temperature',
 '{soc_pct}', false, NULL, 'Not comparable across labs without the ARC phi factor.'),
('max_runaway_temperature','Peak runaway temperature','K','temperature',
 '{soc_pct}', false, NULL, NULL),

-- ---- mechanical ------------------------------------------------------
('reversible_expansion','Reversible expansion','1','dimensionless',
 '{soc_pct,constraint_mode,temperature_c}', false, NULL,
 'Constant-force and constant-gap fixtures measure different physical quantities.'),
('irreversible_expansion','Irreversible expansion','1','dimensionless',
 '{cycle_index,constraint_mode}', false, NULL, NULL),
('stack_pressure',      'Stack pressure',      'Pa','pressure',
 '{soc_pct,constraint_mode}', false, NULL, NULL),
('expansion_force',     'Expansion force',     'N','force',
 '{soc_pct,constraint_mode}', false, NULL, NULL),

-- ---- operating envelope ---------------------------------------------
('operating_temperature_min','Minimum operating temperature','K','temperature',
 '{temperature_reference,direction}', false, NULL,
 'Ambient and cell-surface limits differ; Molicel publishes both, most vendors state neither.'),
('operating_temperature_max','Maximum operating temperature','K','temperature',
 '{temperature_reference,direction}', false, NULL, NULL),
('storage_temperature_min','Minimum storage temperature','K','temperature',
 '{duration_s}', false, NULL,
 'Storage ranges are banded by duration and by SOC state; Samsung gives 1 yr / 3 mo / 1 mo bands.'),
('storage_temperature_max','Maximum storage temperature','K','temperature',
 '{duration_s}', false, NULL, NULL),

-- ---- electrochemistry / materials -----------------------------------
('specific_capacity',   'Specific capacity',   'C/kg','specific_charge',
 '{rate_value,rate_unit,temperature_c,voltage_lower_v}', false, NULL, NULL),
('areal_capacity',      'Areal capacity',      'C/m2','areal_charge',
 '{rate_value,rate_unit,area_kind}', false, NULL, NULL),
('first_cycle_efficiency','First-cycle coulombic efficiency','1','dimensionless',
 '{rate_value,rate_unit,temperature_c}', true, NULL, NULL),
('diffusion_coefficient','Li diffusion coefficient','m2/s','diffusivity',
 '{soc_pct,temperature_c}', true, NULL,
 'From GITT via Weppner-Huggins: needs molar volume, molar mass, electrode mass, area and '
 'pulse time, none of which are in a cycler file.'),
('open_circuit_voltage','Open circuit voltage','V','voltage',
 '{soc_pct,temperature_c,direction,rest_before_s}', false, NULL,
 'Path-dependent. Direction is mandatory; for LFP and Si-bearing cells hysteresis is large '
 'enough that voltage-based SOC is unusable.'),

-- ---- system level ----------------------------------------------------
('soc_estimation_accuracy','SOC estimation accuracy','1','dimensionless','{}', false, NULL, NULL),
('soh_estimation_accuracy','SOH estimation accuracy','1','dimensionless','{}', false, NULL, NULL),
('standby_consumption', 'Standby consumption', 'W','power',   '{}', false, NULL, NULL),
('cooling_capacity',    'Cooling capacity',    'W','power',   '{temperature_c}', false, NULL, NULL),
('warranty_throughput', 'Warranty energy throughput','J','energy','{}', false, NULL, NULL),
('warranty_cycles',     'Warranty cycles',     '1','dimensionless','{}', false, NULL, NULL),

-- ---- carbon / regulatory (EU 2023/1542) -----------------------------
('carbon_footprint_per_kwh','Carbon footprint','1','dimensionless','{}', false, NULL,
 'kg CO2e per kWh of total energy over service life; Annex II lifecycle stages break out separately.'),
('recycled_content_cobalt','Recycled content, cobalt','1','dimensionless','{}', false, NULL, NULL),
('recycled_content_lithium','Recycled content, lithium','1','dimensionless','{}', false, NULL, NULL),
('recycled_content_nickel','Recycled content, nickel','1','dimensionless','{}', false, NULL, NULL),
('recycled_content_lead','Recycled content, lead','1','dimensionless','{}', false, NULL, NULL),
('state_of_health',     'State of health',     '1','dimensionless',
 '{temperature_c,rate_value,rate_unit}', true, NULL,
 'Capacity-based, resistance-based and blended SOH are different numbers; CATL claims '
 '"<+/-5%" without saying which.');

-- Axis quantities used by curve.x_quantity_id / y_quantity_id
INSERT INTO quantity (code, label, si_unit, dimension, required_conditions, is_derived, bdf_name) VALUES
('time',            'Time',              's','time',            '{}', false, 'test_time_second'),
('voltage',         'Voltage',           'V','voltage',         '{}', false, 'voltage_volt'),
('current',         'Current',           'A','current',         '{}', false, 'current_ampere'),
('temperature',     'Temperature',       'K','temperature',     '{}', false, 'ambient_temperature_celsius'),
('state_of_charge', 'State of charge',   '1','dimensionless',   '{}', false, NULL),
('cycle_number',    'Cycle number',      '1','dimensionless',   '{}', false, 'cycle_count'),
('frequency',       'Frequency',         'Hz','frequency',      '{}', false, NULL),
('impedance_real',  'Re(Z)',             'ohm','resistance',    '{}', false, 'real_impedance_ohm'),
('impedance_imag',  'Im(Z)',             'ohm','resistance',    '{}', false, 'imaginary_impedance_ohm'),
('dqdv',            'dQ/dV',             'C/V','dimensionless', '{}', true,  NULL),
('dvdq',            'dV/dQ',             'V/C','dimensionless', '{}', true,  NULL),
('relaxation_time', 'Relaxation time',   's','time',            '{}', true,  NULL),
('drt_gamma',       'DRT gamma',         'ohm','resistance',    '{}', true,  NULL),
('power',           'Power',             'W','power',           '{}', false, 'power_watt'),
('pressure',        'Pressure',          'Pa','pressure',       '{}', false, 'applied_pressure_pa'),
('displacement',    'Displacement',      'm','length',          '{}', false, NULL),
('force',           'Force',             'N','force',           '{}', false, NULL),
('two_theta',       '2-theta',           'deg','angle',         '{}', false, NULL),
('intensity',       'Intensity',         '1','dimensionless',   '{}', false, NULL);
