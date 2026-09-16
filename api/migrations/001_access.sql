-- Private service state. Never include this schema in public data exports.
CREATE SCHEMA IF NOT EXISTS lemonergy_api;
REVOKE ALL ON SCHEMA lemonergy_api FROM PUBLIC;
CREATE TABLE IF NOT EXISTS lemonergy_api.account (
    id uuid PRIMARY KEY,
    label text NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    paid_until timestamptz,
    monthly_limit integer NOT NULL CHECK (monthly_limit > 0),
    minute_limit integer NOT NULL CHECK (minute_limit > 0),
    minute_start timestamptz,
    minute_used integer NOT NULL DEFAULT 0 CHECK (minute_used >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS lemonergy_api.api_key (
    id uuid PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES lemonergy_api.account(id),
    digest text UNIQUE NOT NULL CHECK (length(digest) = 64),
    label text NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS api_key_account_idx ON lemonergy_api.api_key(account_id);
CREATE TABLE IF NOT EXISTS lemonergy_api.monthly_usage (
    account_id uuid NOT NULL REFERENCES lemonergy_api.account(id),
    month date NOT NULL CHECK (extract(day FROM month) = 1),
    used integer NOT NULL DEFAULT 0 CHECK (used >= 0),
    PRIMARY KEY (account_id, month)
);
CREATE TABLE IF NOT EXISTS lemonergy_api.audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES lemonergy_api.account(id),
    action text NOT NULL,
    detail jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON ALL TABLES IN SCHEMA lemonergy_api FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA lemonergy_api FROM PUBLIC;
