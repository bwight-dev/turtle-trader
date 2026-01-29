-- Migration: 005_create_alerts_tables
-- Description: Create alerts and open_positions tables for dashboard
-- Created: 2026-01-29

-- Alerts table: immutable event log
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    symbol VARCHAR(20) NOT NULL,
    alert_type VARCHAR(30) NOT NULL,
    direction VARCHAR(10),
    system VARCHAR(5),
    price DECIMAL(14,6),
    details JSONB,
    acknowledged BOOLEAN DEFAULT FALSE
);

-- Index for recent alerts query
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp
    ON alerts(timestamp DESC);

-- Index for symbol-specific alerts
CREATE INDEX IF NOT EXISTS idx_alerts_symbol
    ON alerts(symbol, timestamp DESC);

-- Partial index for unacknowledged alerts (notification badge)
CREATE INDEX IF NOT EXISTS idx_alerts_unacknowledged
    ON alerts(acknowledged) WHERE acknowledged = FALSE;

-- Open positions table: current state snapshot
CREATE TABLE IF NOT EXISTS open_positions (
    symbol VARCHAR(20) PRIMARY KEY,
    direction VARCHAR(10) NOT NULL,
    system VARCHAR(5) NOT NULL,
    entry_price DECIMAL(14,6) NOT NULL,
    entry_date TIMESTAMPTZ NOT NULL,
    contracts INTEGER NOT NULL,
    units INTEGER NOT NULL DEFAULT 1,
    current_price DECIMAL(14,6),
    stop_price DECIMAL(14,6),
    unrealized_pnl DECIMAL(14,2),
    n_value DECIMAL(12,6),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Record this migration
INSERT INTO schema_migrations (version) VALUES ('005_create_alerts_tables')
ON CONFLICT (version) DO NOTHING;
