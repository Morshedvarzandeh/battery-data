-- Main-contact dynamics. A bound is not a nominal simulation parameter;
-- timing retains coil option, bounce and test-current context in conditions.extra.
SET search_path = bd, public;
INSERT INTO unit (symbol,si_symbol,factor,offset_,dimension) VALUES ('ms','s',0.001,0,'time');

INSERT INTO quantity (code,label,si_unit,dimension,required_conditions,is_derived,description) VALUES
('contact_resistance','Main contact resistance','ohm','resistance','{temperature_c}',false,'Retain measurement current, typical intervals and upper bounds; this is not battery internal resistance.'),
('operate_time','Contactor operate time','s','time','{temperature_c}',false,'Preserve coil designation and bounce inclusion. A maximum is not a typical delay.'),
('release_time','Contactor release time','s','time','{temperature_c}',false,'Preserve coil designation, load and arc context. Mechanical release timing is not an independently qualified HV interruption rating.');
