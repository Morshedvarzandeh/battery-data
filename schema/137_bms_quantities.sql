-- BMS limits describe the monitoring system, not the cell or its power path.
SET search_path = bd, public;
INSERT INTO quantity (code,label,si_unit,dimension,required_conditions,is_derived,description) VALUES
('bms_series_cells_min','BMS minimum series cell channels','1','dimensionless','{}',false,'Minimum supported series cell channels; preserve controller/system scope in conditions.extra.'),
('bms_series_cells_max','BMS maximum series cell channels','1','dimensionless','{}',false,'Maximum supported series cell channels. A CMU limit is not a complete system limit.'),
('bms_pack_voltage_max','BMS maximum supported pack voltage','V','voltage','{electrical_system}',false,'Supported pack voltage, not the auxiliary supply, dielectric withstand or current sensor rating.'),
('bms_temperature_channels','BMS temperature sensor channels','1','dimensionless','{}',false,'Preserve whether this is per CMU, controller or complete system.'),
('bms_can_ports','BMS CAN interface count','1','dimensionless','{}',false,'Native CAN ports; do not count an optional external adapter as an integrated interface.'),
('bms_balancing_current','BMS balancing current per cell','A','current','{temperature_c}',false,'Preserve cell voltage, topology and simultaneous-channel restrictions in conditions.extra. Not charge/discharge current.'),
('bms_cell_banks_max','BMS maximum cell banks','1','dimensionless','{}',false,'Controller bank count, not cells or parallel strings.')
ON CONFLICT (code) DO NOTHING;
