-- Migration 007: Create events table for audit trail
--
-- Events capture every trading decision with full context.
-- See docs/plans/2026-02-12-event-streaming-design.md for design.

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Event classification
    event_type VARCHAR(50) NOT NULL,
    outcome VARCHAR(50) NOT NULL,
    outcome_reason TEXT,

    -- Identifiers
    run_id UUID NOT NULL,
    sequence INTEGER NOT NULL,
    symbol VARCHAR(20),

    -- Full context snapshot (JSONB for querying)
    context JSONB NOT NULL DEFAULT '{}',

    -- Metadata
    source VARCHAR(20) NOT NULL,  -- 'scanner' or 'monitor'
    dry_run BOOLEAN DEFAULT FALSE,

    -- Ensure unique sequence within each run
    CONSTRAINT events_run_sequence UNIQUE (run_id, sequence)
);

-- Index for timestamp-based queries (most common)
CREATE INDEX IF NOT EXISTS idx_events_timestamp
ON events(timestamp DESC);

-- Index for symbol queries
CREATE INDEX IF NOT EXISTS idx_events_symbol
ON events(symbol, timestamp DESC)
WHERE symbol IS NOT NULL;

-- Index for event type queries
CREATE INDEX IF NOT EXISTS idx_events_type
ON events(event_type, timestamp DESC);

-- Index for run queries (get all events in a run)
CREATE INDEX IF NOT EXISTS idx_events_run
ON events(run_id, sequence);

-- Index for non-HOLD events (trading activity)
CREATE INDEX IF NOT EXISTS idx_events_non_hold
ON events(timestamp DESC)
WHERE outcome != 'hold';

-- Index for source filtering (scanner vs monitor)
CREATE INDEX IF NOT EXISTS idx_events_source
ON events(source, timestamp DESC);

-- GIN index for JSONB context queries
CREATE INDEX IF NOT EXISTS idx_events_context
ON events USING GIN (context);

-- Comments for documentation
COMMENT ON TABLE events IS 'Immutable audit trail of all trading decisions';
COMMENT ON COLUMN events.event_type IS 'Type: scanner_started, signal_detected, position_checked, etc.';
COMMENT ON COLUMN events.outcome IS 'Result: approved, hold, exit_stop_triggered, etc.';
COMMENT ON COLUMN events.run_id IS 'Links all events within a single scanner/monitor run';
COMMENT ON COLUMN events.sequence IS 'Order of event within run (1, 2, 3, ...)';
COMMENT ON COLUMN events.context IS 'Full state snapshot: market, position, account, sizing, etc.';
