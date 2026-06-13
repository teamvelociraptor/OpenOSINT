-- OpenOSINT Cloud — database schema
-- Run once against your Heroku Postgres instance:
--   psql $DATABASE_URL -f db/init.sql

CREATE TABLE IF NOT EXISTS customers (
    api_key           TEXT        PRIMARY KEY,
    polar_customer_id TEXT,
    credits           INT         NOT NULL DEFAULT 0,
    plan              TEXT        NOT NULL DEFAULT 'payg',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique index lets us look customers up by Polar customer id.
CREATE UNIQUE INDEX IF NOT EXISTS customers_polar_id_idx
    ON customers (polar_customer_id)
    WHERE polar_customer_id IS NOT NULL;

-- Idempotency table — prevents double-credit on retried webhook deliveries.
CREATE TABLE IF NOT EXISTS processed_events (
    event_id    TEXT        PRIMARY KEY,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Customer BYOK keys, encrypted at rest with Fernet (CONFIG_ENCRYPTION_KEY).
-- Cascade delete removes keys when the customer row is deleted.
CREATE TABLE IF NOT EXISTS customer_keys (
    api_key          TEXT        NOT NULL REFERENCES customers(api_key) ON DELETE CASCADE ON UPDATE CASCADE,
    provider         TEXT        NOT NULL,
    secret_encrypted TEXT        NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (api_key, provider)
);
