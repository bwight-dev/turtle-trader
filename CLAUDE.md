# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Turtle Trading Bot is a Python algorithmic trading system implementing classic Turtle Trading rules with modern adaptations. The project is currently in **active implementation** phase.

## Implementation Progress (as of 2026-01-29)

**454 tests passing** (451 unit, 3 integration for alerts)

| Phase | Milestones | Status |
|-------|------------|--------|
| Foundation | M1-M4 | ✓ Complete |
| Market Data | M5-M8 | ✓ Complete |
| Strategy | M9-M11 | ✓ Complete |
| Portfolio | M12-M17 | ✓ Complete |
| Execution | M18-M21 | ✓ Complete |
| Integration | M22-M25 | ✓ Complete |
| **Live Testing** | Paper trading | ✓ Active |

**All 25 milestones complete!** Now in live paper trading on IBKR.

### Current Status
- **Paper Account**: DUP318628 (IBKR)
- **Position Monitor**: Running via launchd (every 60s)
- **Daily Scanner**: Scheduled for 6:30 AM Mon-Fri
- **Test Position**: EFA long (134 shares @ $101.56)

### Completed Components:
- **M1**: Project setup + Neon PostgreSQL connection
- **M2**: IBKR TWS connection with ib_insync
- **M3**: Core Pydantic models (Position, Portfolio, Signal, Trade, etc.)
- **M4**: N (ATR) calculator with Wilder's smoothing
- **M5**: Donchian channel calculator (10/20/55-day)
- **M6**: Yahoo Finance backup feed
- **M7**: Composite feed with automatic failover
- **M8**: N value persistence (PostgresNValueRepository)
- **M9**: S1/S2 signal detector (breakout detection)
- **M10**: S1 filter with trade history (Rule 7)
- **M11**: Market scanner use case
- **M12**: LangGraph workflow skeleton
- **M13**: Position model with pyramid tracking (done in M3)
- **M14**: Unit size calculator + drawdown tracker (Rule 5)
- **M15**: Limit checker - 4/6/12 unit limits (21 tests)
- **M16**: Position monitor - stop hit detection (Rule 10)
- **M17**: Position monitor - breakout exits + pyramids (Rules 11-14)
- **M18**: Broker interface + Paper broker (29 tests)
- **M19**: IBKR broker adapter (integration tests)
- **M20**: ModifyStopCommand + SyncPortfolioQuery (18 tests)
- **M21**: ReconcileAccountQuery (15 tests)
- **M22**: TradeLogger command (15 tests)
- **M23**: DailyWorkflow LangGraph orchestration (17 tests)
- **M24**: MonitoringLoop continuous position monitor (19 tests)
- **M25**: Docker deployment (Dockerfile, docker-compose, deploy.sh - 21 tests)

**Core Principle**: Mechanical execution with zero discretion once rules are defined.

## Technology Stack

- **Python 3.12+** with Pydantic v2 for type safety
- **Interactive Brokers** (ib_insync) - primary data source and execution
- **Yahoo Finance** (yfinance) - backup data source with automatic failover
- **Neon PostgreSQL** (cloud) - trade history, audit logs, N value persistence
- **In-memory caching** (Redis deferred) - real-time price cache
- **LangGraph** - workflow orchestration from the start
- **Docker on Unraid** - deployment target

## Database

```bash
# Neon PostgreSQL (cloud-hosted)
DATABASE_URL=postgresql://neondb_owner:npg_ipM4O8DGaeBP@ep-autumn-morning-afn6oh1a-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require
```

### Dashboard Tables

Two additional tables support the website dashboard:

**`alerts`** - Immutable event log for trading signals and actions:
- `ENTRY_SIGNAL` - Breakout signal detected
- `POSITION_OPENED` - Order filled, position established
- `POSITION_CLOSED` - Position fully exited
- `EXIT_STOP` - 2N stop hit
- `EXIT_BREAKOUT` - Donchian exit triggered
- `PYRAMID_TRIGGER` - Pyramid level reached

**`open_positions`** - Current state of open positions (upserted on significant changes)

Query examples:
```sql
-- All open positions for dashboard
SELECT * FROM open_positions ORDER BY entry_date;

-- Recent alerts (last 24h)
SELECT * FROM alerts WHERE timestamp > NOW() - INTERVAL '24 hours' ORDER BY timestamp DESC;

-- Unacknowledged count for notification badge
SELECT COUNT(*) FROM alerts WHERE acknowledged = FALSE;
```

## Build & Development Commands

```bash
# Database setup
python scripts/setup_db.py

# Import TOS trading history
python scripts/import_tos.py

# Backfill existing position to alerts database
python scripts/backfill_position.py

# Daily run (signal scanner - logs to alerts table)
python scripts/daily_run.py

# Position monitor (single check - updates open_positions table)
python scripts/monitor_positions.py --once

# Backtest
python scripts/backtest.py --equity 50000 --symbols SPY QQQ IWM --start 2020-01-01

# Status dashboard
python scripts/status.py

# Tests
pytest tests/unit/
pytest tests/integration/
pytest tests/backtest/
```

## Scheduled Tasks (launchd)

Two scheduled tasks run on macOS via launchd. Full details in `docs/SCHEDULING.md`.

### Task Configuration

| Task | Schedule | Script | Log File |
|------|----------|--------|----------|
| Daily Scanner | 6:30 AM Mon-Fri | `scripts/daily_run.py` | `logs/daily.error.log` |
| Position Monitor | Every 60 seconds | `scripts/monitor_positions.py` | `logs/monitor.error.log` |

### Plist Locations
```
~/Library/LaunchAgents/com.turtle.daily.plist
~/Library/LaunchAgents/com.turtle.monitor.plist
```

### Quick Monitoring Commands

```bash
# Check job status
launchctl list | grep turtle

# Watch position monitor in real-time
tail -f logs/monitor.error.log

# Watch daily scanner
tail -f logs/daily.error.log

# Status dashboard (positions, jobs, logs)
python scripts/status.py

# Stop/start monitor
launchctl unload ~/Library/LaunchAgents/com.turtle.monitor.plist
launchctl load ~/Library/LaunchAgents/com.turtle.monitor.plist
```

### Monitor Output Example
```
[Cycle 5]
============================================================
MONITORING CYCLE - 2026-01-29 13:15:31
============================================================
Checking 1 position(s)...
  EFA: HOLD | Price $101.53 | Stop $99.73 | P&L $-4.35
------------------------------------------------------------
Next check in 60 seconds...
```

When action is needed:
```
  EFA: >>> EXIT_STOP <<< - 2N stop hit: price 99.70 at or below stop 99.73
```

## Architecture (Clean Architecture)

### Layer Structure

```
src/
├── domain/            # Core business logic (innermost, no dependencies)
│   ├── models/        # Pydantic models (Position, Portfolio, Signal, etc.)
│   ├── interfaces/    # Abstract ports (DataFeed ABC, Broker ABC, Repository ABCs)
│   ├── services/      # Pure domain logic (SignalDetector, PositionMonitor, LimitChecker)
│   └── rules.py       # TurtleRules configuration
│
├── application/       # Use cases (orchestration layer)
│   ├── commands/      # Write operations (PlaceEntry, ExecutePyramid, ClosePosition, AlertLogger)
│   ├── queries/       # Read operations (ScanMarkets, GetPortfolio)
│   └── workflows/     # LangGraph orchestration (DailyWorkflow, MonitoringLoop)
│
├── adapters/          # Interface implementations (infrastructure)
│   ├── data_feeds/    # IBKRDataFeed, YahooDataFeed, CompositeDataFeed
│   ├── brokers/       # PaperBroker, IBKRBroker
│   ├── repositories/  # PostgresNValueRepo, PostgresTradeRepo, PostgresAlertRepo, PostgresOpenPositionRepo
│   └── mappers/       # SymbolMapper, IBKRMapper
│
└── infrastructure/    # Frameworks & drivers (outermost)
    ├── database.py    # Neon connection pool
    ├── config.py      # Environment configuration
    └── logging.py     # Structured logging
```

**Dependency Rule:** Dependencies point INWARD. Domain knows nothing about outer layers.

### Critical Module: Position Monitor (`domain/services/position_monitor.py`)

The Position Monitor is the key module that was missing in v1. It continuously monitors positions with this priority order:

1. **Stop hit** (2N hard stop) → EXIT_STOP
2. **Breakout exit** (10/20-day) → EXIT_BREAKOUT
3. **Pyramid trigger** (+½N from last entry) → PYRAMID
4. **No action** → HOLD

### Data Flow

Market Data (IBKR primary, Yahoo backup) → N/Donchian calculations → Strategy Engine (signals) + Position Monitor (exits/pyramids) → Portfolio Manager → Execution Gateway → Audit Log

## Turtle Trading Rules Quick Reference

**Full verified rules:** See `docs/RULES.md` (17 rules from Faith/Covel/Parker sources)

### Entries
- **S1**: 20-day breakout (skip if last S1 was winner)
- **S2**: 55-day breakout (always take - failsafe)

### Exits
- **S1**: 10-day opposite breakout
- **S2**: 20-day opposite breakout
- **Hard stop**: 2N from entry (non-negotiable)

### Pyramiding
- Add 1 unit at +½N intervals from last entry (Rule 11)
- Move ALL stops to 2N below newest entry (Rule 12)
- Maximum 4 units per market

### Position Limits
- 4 units per market
- 6 units correlated (e.g., MGC + SIL = metals)
- **Modern mode (default):** 20% total portfolio risk cap (for 228+ markets)
- **Original mode:** 12 units total (for historical validation with ~20 markets)
- Mode controlled by `USE_RISK_CAP_MODE` in `rules.py`

### N Calculation
- N = 20-day ATR with Wilders smoothing
- Formula: `((19 × Prev_N) + Current_TR) / 20`
- TOS equivalent: `ATR(20, WILDERS)`

### Risk & Sizing
- Risk per unit: 0.5% of notional equity (Parker modern rule)
- Unit = (0.005 × Notional Equity) / (N × Point Value)

### Drawdown Rule (Rule 5)
- 10% drawdown → reduce notional equity by 20%
- Sizing uses notional equity, not actual

## IBKR Configuration

- **Paper Trading**: Port 7497, Account DUP318628
- **Live Trading**: Port 7496
- **Gateway**: Port 4002 (paper) / 4001 (live)
- TWS runs on Mac Mini (local)

## Implementation Plan

**25 testable milestones** (1-3 days each) with automated tests + manual TOS comparison.

See `docs/plans/2026-01-27-implementation-plan.md` for full details.

### Milestone Groups
- **Foundation (M1-M4)**: Project setup, IBKR connection, Pydantic models, N calculator
- **Market Data (M5-M8)**: Donchian, Yahoo backup, composite feed, N persistence
- **Strategy (M9-M12)**: Signal detector, S1 filter, scanner, LangGraph skeleton
- **Portfolio (M13-M17)**: Position model, sizing, limits, Position Monitor
- **Execution (M18-M21)**: Broker interface, IBKR orders, stop modification
- **Integration (M22-M25)**: Audit logging, workflow, monitoring loop, Docker

## Key Specifications

Original specs in `docs/bot/`:
- `01-overview-and-domain.md` - Domain model, bounded contexts
- `02-pydantic-models.md` - Complete model specifications
- `03-position-monitor.md` - Position monitoring logic
- `04-module-implementations.md` - Implementation details
- `05-implementation-and-reference.md` - Phases, file structure, DB schema
- `06-data-sources.md` - IBKR/Yahoo integration details

Implementation plans in `docs/plans/`:
- `2026-01-27-implementation-plan.md` - 25 testable milestones with Clean Architecture
- `2026-01-27-architecture-review.md` - DDD/Clean Architecture analysis
- `2026-01-29-alerts-logging-design.md` - Dashboard alerts/positions logging (implemented)

## Validation Criteria

- N calculations must match TOS ATR(20, WILDERS) within 0.5%
- Donchian channels must match TradingView exactly
- Signal generation must match manual tracking
- Pyramid triggers at correct +1N levels
