-- Existing installations only. Adds the minute unit and the six lead-acid
-- rating quantities; does not change records. Idempotent.
BEGIN;
-- psql resolves this path relative to this migration file.
\ir ../schema/139_lead_acid_quantities.sql
COMMIT;
