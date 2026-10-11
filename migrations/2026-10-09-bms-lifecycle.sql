-- Existing installations only. Does not recreate the database or change records.
-- Run after backing up the database, before loading BMS contributions.
BEGIN;
ALTER TABLE bd.product DROP CONSTRAINT IF EXISTS product_component_type_check;
ALTER TABLE bd.product ADD CONSTRAINT product_component_type_check CHECK (
  component_type IN ('contactor','fuse','precharge_contactor','precharge_resistor',
                    'inverter','dc_dc_converter','charger','bms'));
ALTER TABLE bd.product_revision ADD COLUMN IF NOT EXISTS lifecycle_evidence jsonb;
ALTER TABLE bd.product_revision ADD COLUMN IF NOT EXISTS bms_details jsonb;
-- psql resolves this path relative to this migration file.
\ir ../schema/137_bms_quantities.sql
COMMIT;
