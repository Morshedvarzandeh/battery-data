-- Electrical switching, protection and power-conversion quantities.
SET search_path = bd, public;
INSERT INTO unit (symbol,si_symbol,factor,offset_,dimension) VALUES ('kA','A',1000,0,'current');

INSERT INTO quantity (code,label,si_unit,dimension,required_conditions,is_derived,description) VALUES
('contact_voltage_rating','Main contact voltage rating','V','voltage','{electrical_system}',false,'Contact circuit only; do not confuse with coil voltage or dielectric withstand.'),
('continuous_carry_current','Continuous contact carry current','A','current','{temperature_c,conductor_description}',false,'Carry current is distinct from make/break current; preserve conductor basis.'),
('coil_voltage_min','Minimum coil voltage','V','voltage','{}',false,'Coil operating supply range, not contact voltage.'),
('coil_voltage_max','Maximum coil voltage','V','voltage','{}',false,'Coil operating supply range, not contact voltage.'),
('coil_nominal_voltage','Nominal coil voltage','V','voltage','{}',false,'Exact coil variant; no family-wide assignment across coil options.'),
('fuse_current_rating','Fuse rated current','A','current','{temperature_c,conductor_description}',false,'Nameplate rating; separate from derated allowable current and interruption capacity.'),
('fuse_voltage_rating','Fuse rated voltage','V','voltage','{electrical_system}',false,'Part-specific rating; family headline may not apply to all amperages.'),
('interrupting_current','Interrupting current','A','current','{test_voltage_v,electrical_system}',false,'Breaking capacity at stated voltage; retain circuit time constant and duty in extra.'),
('input_voltage_min','Minimum input voltage','V','voltage','{electrical_system}',false,'Component supply-input window, not a battery cutoff.'),
('input_voltage_max','Maximum input voltage','V','voltage','{electrical_system}',false,'Component supply-input window, not a battery cutoff.'),
('rated_output_voltage','Rated output voltage','V','voltage','{electrical_system}',false,'Record operating mode and adjustment/tolerance in conditions.extra.'),
('rated_output_current','Rated output current','A','current','{temperature_c,boundary}',false,'Output rating at stated temperature and mode; do not confuse with battery charge limits.');
