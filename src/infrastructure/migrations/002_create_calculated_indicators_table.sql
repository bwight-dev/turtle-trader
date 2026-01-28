-- Migration: 002_create_calculated_indicators_table
-- Description: Create table for persisting N values and Donchian channels
-- Created: 2026-01-27

CREATE TABLE IF NOT EXISTS calculated_indicators (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    calc_date DATE NOT NULL,

    -- N (ATR) value
    n_value DECIMAL(12, 6) NOT NULL,

    -- Donchian channels
    donchian_10_upper DECIMAL(12, 6),
    donchian_10_lower DECIMAL(12, 6),
    donchian_20_upper DECIMAL(12, 6),
    donchian_20_lower DECIMAL(12, 6),
    donchian_55_upper DECIMAL(12, 6),
    donchian_55_lower DECIMAL(12, 6),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint: one row per symbol per date
    UNIQUE (symbol, calc_date)
);

-- Index for common lookups
CREATE INDEX IF NOT EXISTS idx_indicators_symbol_date
    ON calculated_indicators(symbol, calc_date DESC);

CREATE INDEX IF NOT EXISTS idx_indicators_date
    ON calculated_indicators(calc_date DESC);

-- Record this migration
INSERT INTO schema_migrations (version) VALUES ('002_create_calculated_indicators_table')
ON CONFLICT (version) DO NOTHING;
