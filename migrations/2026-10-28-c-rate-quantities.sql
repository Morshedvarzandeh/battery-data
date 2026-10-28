-- Existing installations only. Adds the C-rate unit and the four C-rate
-- current-limit quantities; does not change records. Idempotent.
BEGIN;
-- psql resolves this path relative to this migration file.
\ir ../schema/138_c_rate_quantities.sql
COMMIT;
