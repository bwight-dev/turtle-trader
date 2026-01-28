-- Migration: 003_create_trades_table
-- Description: Create table for trade audit records (used for S1 filter)
-- Created: 2026-01-27

CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('long', 'short')),
    system VARCHAR(5) NOT NULL CHECK (system IN ('S1', 'S2')),

    -- Entry details
    entry_price DECIMAL(14, 6) NOT NULL,
    entry_date TIMESTAMP WITH TIME ZONE NOT NULL,
    entry_contracts INTEGER NOT NULL CHECK (entry_contracts > 0),
    n_at_entry DECIMAL(12, 6) NOT NULL,

    -- Exit details
    exit_price DECIMAL(14, 6) NOT NULL,
    exit_date TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_reason VARCHAR(50) NOT NULL,

    -- P&L
    realized_pnl DECIMAL(14, 2) NOT NULL,
    commission DECIMAL(10, 2) DEFAULT 0,

    -- Pyramid info
    max_units INTEGER DEFAULT 1,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for S1 filter queries (get last S1 trade for symbol)
CREATE INDEX IF NOT EXISTS idx_trades_symbol_system_exit
    ON trades(symbol, system, exit_date DESC);

-- Index for getting trades by symbol
CREATE INDEX IF NOT EXISTS idx_trades_symbol_exit
    ON trades(symbol, exit_date DESC);

-- Index for performance analysis by exit reason
CREATE INDEX IF NOT EXISTS idx_trades_exit_reason
    ON trades(exit_reason, exit_date DESC);

-- Record this migration
INSERT INTO schema_migrations (version) VALUES ('003_create_trades_table')
ON CONFLICT (version) DO NOTHING;
