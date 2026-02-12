-- Migration: 006_create_runs_table
-- Description: Create runs table for execution event logging
-- Created: 2026-02-12

-- Runs table: tracks each execution of scanner and monitor tasks
CREATE TABLE IF NOT EXISTS runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,

    -- Task identification
    task_type VARCHAR(20) NOT NULL,  -- 'scanner' or 'monitor'

    -- Summary fields (for list view)
    symbols_checked INTEGER NOT NULL DEFAULT 0,
    signals_found INTEGER NOT NULL DEFAULT 0,
    actions_needed INTEGER NOT NULL DEFAULT 0,
    errors_count INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- running/success/partial/failed
    summary TEXT,  -- Human-readable summary (e.g., "Scanned 15 ETFs, found 2 signals")

    -- Full detail in JSONB (for drill-down view)
    details JSONB NOT NULL DEFAULT '{}'
);

-- Index for listing runs by date (primary query)
CREATE INDEX IF NOT EXISTS idx_runs_started_at
    ON runs(started_at DESC);

-- Index for filtering by task type
CREATE INDEX IF NOT EXISTS idx_runs_task_type
    ON runs(task_type, started_at DESC);

-- Partial index for failed/partial runs (ops monitoring)
CREATE INDEX IF NOT EXISTS idx_runs_problems
    ON runs(status, started_at DESC)
    WHERE status IN ('failed', 'partial');

-- Record this migration
INSERT INTO schema_migrations (version) VALUES ('006_create_runs_table')
ON CONFLICT (version) DO NOTHING;
