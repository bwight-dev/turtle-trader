-- Migration: 001_create_markets_table
-- Description: Create the markets table for storing tradable instrument metadata
-- Created: 2026-01-27

CREATE TABLE IF NOT EXISTS markets (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    asset_class VARCHAR(20) NOT NULL,  -- futures, stock, forex
    correlation_group VARCHAR(30),      -- metals, equity_us, energy, etc.
    point_value DECIMAL(12, 4) NOT NULL DEFAULT 1.0,
    tick_size DECIMAL(12, 6) NOT NULL DEFAULT 0.01,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for common lookups
CREATE INDEX IF NOT EXISTS idx_markets_symbol ON markets(symbol);
CREATE INDEX IF NOT EXISTS idx_markets_correlation_group ON markets(correlation_group);
CREATE INDEX IF NOT EXISTS idx_markets_active ON markets(is_active) WHERE is_active = TRUE;

-- Seed with initial futures markets
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size)
VALUES
    ('/MGC', 'Micro Gold', 'COMEX', 'futures', 'metals', 10.0, 0.10),
    ('/SIL', 'Micro Silver', 'COMEX', 'futures', 'metals', 50.0, 0.005),
    ('/M2K', 'Micro Russell 2000', 'CME', 'futures', 'equity_us', 5.0, 0.10),
    ('/MES', 'Micro E-mini S&P 500', 'CME', 'futures', 'equity_us', 5.0, 0.25),
    ('/MNQ', 'Micro E-mini NASDAQ', 'CME', 'futures', 'equity_us', 2.0, 0.25),
    ('/MYM', 'Micro E-mini Dow', 'CME', 'futures', 'equity_us', 0.5, 1.0),
    ('/MCL', 'Micro WTI Crude Oil', 'NYMEX', 'futures', 'energy', 100.0, 0.01),
    ('/MNG', 'Micro Natural Gas', 'NYMEX', 'futures', 'energy', 1000.0, 0.001)
ON CONFLICT (symbol) DO NOTHING;

-- Create migrations tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Record this migration
INSERT INTO schema_migrations (version) VALUES ('001_create_markets_table')
ON CONFLICT (version) DO NOTHING;
