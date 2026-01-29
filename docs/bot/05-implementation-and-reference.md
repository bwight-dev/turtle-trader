# Turtle Trading Bot - Part 5: Implementation Phases & Reference

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Language** | Python 3.12+ | Your stack, rich trading libs |
| **Models** | Pydantic v2 | Type safety, validation, serialization |
| **Async** | asyncio | Concurrent market monitoring |
| **State Machine** | LangGraph | Workflow orchestration |
| **AI Integration** | LangChain | Gemini + NotebookLM bridge |
| **Broker API** | ib_insync | IBKR integration (execution + data) |
| **Database** | PostgreSQL | Trade history, audit log, N persistence |
| **Cache** | Redis | Real-time price cache |
| **Deployment** | Docker on Unraid | Your home lab |

### Data Sources (Priority Order)

| Priority | Source | Use Case | Library |
|----------|--------|----------|---------|
| **Primary** | Interactive Brokers | Real-time prices, historical bars, execution | `ib_insync` |
| **Backup** | Yahoo Finance | Fallback when IBKR unavailable | `yfinance` |

**IBKR Configuration:**
- TWS/Gateway running on Mac Mini (local)
- Paper Trading: Port 7497, Account DUP318628
- Live Trading: Port 7496 (when ready)

See `06-data-sources.md` for complete IBKR integration details.

---

## Implementation Phases

### Phase 1: Core Foundation (Week 1-2)

**Modules:** `turtle_core`, `market_data`

```
Deliverables:
├── All Pydantic models (Part 2 of this spec)
├── TurtleRules configuration
├── Data source configuration (IBKRConfig, YahooConfig, DataSourceConfig)
├── IBKR data feed (primary) - connects to TWS on Mac Mini
├── Yahoo Finance data feed (backup)
├── Composite data feed with automatic failover
├── Symbol mapper (internal ↔ IBKR ↔ Yahoo formats)
├── N (ATR) calculator with Wilders smoothing
├── N value persistence (PostgreSQL) - statefulness per spec
├── Donchian channel calculator (10, 20, 55-day)
├── Data validation (OHLC sanity checks, bad tick detection)
├── CLI tool to test calculations
└── Unit tests comparing to TOS values

Validation Criteria:
- IBKR connection established to TWS on Mac Mini
- N calculations match TOS ATR(20, WILDERS) within 0.5%
- Donchian channels match TradingView exactly
- Failover to Yahoo works when IBKR unavailable
- N values persist across restarts (database)
```

### Phase 2: Strategy Engine (Week 3-4)

**Modules:** `strategy`

```
Deliverables:
├── Signal detector (S1/S2 breakouts)
├── S1 filter with trade history lookup
├── Market scanner across universe
├── Test harness for signal generation
└── Integration tests

Validation Criteria:
- Generate signals for your existing TOS positions
- Filter rule matches manual tracking
```

### Phase 3: Portfolio & Position Monitor (Week 5-7)

**Modules:** `portfolio` (including `monitor` submodule)

```
Deliverables:
├── Position tracker with pyramid levels
├── Unit size calculator
├── Limit checker (per-market, correlation, total)
├── Drawdown tracker with equity adjustment
├── *** Position Monitor *** (pyramids, exits, stops)
├── Stop calculator
└── Integration tests

Validation Criteria:
- Match calculations to your 1-22-2026 portfolio state
- Verify pyramid triggers at correct +1N levels
- Verify exit triggers on 10/20-day breakouts
- Verify stops move correctly on pyramid
```

### Phase 4: Audit & Logging (Week 8-9)

**Modules:** `audit`

```
Deliverables:
├── Trade logger (PostgreSQL)
├── S1 filter history tracking
├── TOS CSV import (from existing skill)
├── Monthly report generator
├── Portfolio snapshot system
├── Export tools for compliance
├── AlertLogger command (dashboard integration) ✓ Added 2026-01-29
│   ├── alerts table (immutable event log)
│   └── open_positions table (current state)
└── Significant change detection (0.5% price, $50 P&L)

Validation Criteria:
- Import your TOS history successfully
- Generate report matching manual tracking
- S1 filter lookups return correct results
- Dashboard tables populated by monitor/scanner
```

### Phase 5: AI Integration (Week 10-11)

**Modules:** `ai_advisor`

```
Deliverables:
├── Gemini Pro validation client
├── NotebookLM bridge (MCP if available)
├── Decision validator
├── Rule query interface
└── Integration with workflows

Validation Criteria:
- Edge-case questions match book answers
- Validate sample trades correctly
```

### Phase 6: Execution Layer (Week 12-13)

**Modules:** `execution`

```
Deliverables:
├── Paper broker (simulation for testing)
├── IBKR broker integration (extends existing data feed connection)
│   ├── Order placement (bracket orders with stops)
│   ├── Position management
│   ├── Stop modification
│   └── Fill reconciliation
├── Bracket order builder
├── Stop modification handler
└── Account sync (positions, equity from IBKR)

Validation Criteria:
- Paper trade for 2 weeks on IB paper account (DUP318628)
- Bracket orders match expected setup
- Stop updates work correctly
- Position sync matches IBKR account state
```

### Phase 7: Orchestration (Week 14-16)

**Modules:** `orchestrator`

```
Deliverables:
├── Daily workflow runner
├── Continuous monitoring loop
├── LangGraph state machine
├── Docker deployment on Unraid
├── n8n scheduling integration
└── Alerting system

Validation Criteria:
- Run parallel with manual trading
- Compare automated decisions to yours
- No missed pyramids or exits
```

---

## File Structure

```
turtle-trading-bot/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
│
├── src/
│   ├── turtle_core/
│   │   ├── __init__.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── enums.py
│   │   │   ├── market.py
│   │   │   ├── signals.py
│   │   │   ├── sizing.py
│   │   │   ├── positions.py
│   │   │   ├── portfolio.py
│   │   │   ├── monitoring.py
│   │   │   ├── orders.py
│   │   │   ├── trades.py
│   │   │   └── limits.py
│   │   ├── rules.py
│   │   └── config.py              # IBKRConfig, YahooConfig, DataSourceConfig
│   │
│   ├── market_data/
│   │   ├── __init__.py
│   │   ├── feeds/
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # Abstract DataFeed interface
│   │   │   ├── ibkr.py            # PRIMARY: Interactive Brokers feed
│   │   │   ├── yahoo.py           # BACKUP: Yahoo Finance feed
│   │   │   └── composite.py       # Failover wrapper
│   │   ├── symbols/
│   │   │   ├── __init__.py
│   │   │   └── mapper.py          # Symbol format translation
│   │   ├── futures/
│   │   │   ├── __init__.py
│   │   │   └── continuous.py      # Back-adjusted continuous contracts
│   │   ├── calc/
│   │   │   ├── __init__.py
│   │   │   ├── volatility.py
│   │   │   └── channels.py
│   │   ├── validation.py          # OHLC sanity checks
│   │   └── store/
│   │       ├── repository.py
│   │       └── n_repository.py    # N value persistence
│   │
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── signals/
│   │   │   ├── __init__.py
│   │   │   └── detector.py
│   │   ├── filters/
│   │   │   ├── __init__.py
│   │   │   └── s1_filter.py
│   │   └── scanner/
│   │       └── market_scanner.py
│   │
│   ├── portfolio/
│   │   ├── __init__.py
│   │   ├── tracker/
│   │   │   └── portfolio_tracker.py
│   │   ├── sizing/
│   │   │   ├── __init__.py
│   │   │   ├── calculator.py
│   │   │   └── stop_calculator.py
│   │   ├── limits/
│   │   │   ├── __init__.py
│   │   │   └── checker.py
│   │   └── monitor/           # ← THE KEY MODULE
│   │       ├── __init__.py
│   │       ├── position_monitor.py
│   │       └── monitor_service.py
│   │
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── brokers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── paper.py
│   │   │   └── ibkr.py
│   │   └── orders/
│   │       └── bracket.py
│   │
│   ├── ai_advisor/
│   │   ├── __init__.py
│   │   ├── gemini/
│   │   │   ├── __init__.py
│   │   │   └── client.py
│   │   ├── notebook/
│   │   │   └── bridge.py
│   │   └── validate/
│   │       └── decision_validator.py
│   │
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── logger/
│   │   │   └── trade_logger.py
│   │   └── reports/
│   │       └── generator.py
│   │
│   └── orchestrator/
│       ├── __init__.py
│       ├── daily_workflow.py
│       ├── monitoring_loop.py
│       └── workflows/
│           └── trade_lifecycle.py
│
├── tests/
│   ├── unit/
│   │   ├── test_n_calculation.py
│   │   ├── test_donchian.py
│   │   ├── test_sizing.py
│   │   ├── test_limits.py
│   │   └── test_monitor.py
│   ├── integration/
│   │   ├── test_signal_flow.py
│   │   └── test_position_lifecycle.py
│   └── backtest/
│       └── runner.py
│
├── scripts/
│   ├── setup_db.py
│   ├── import_tos.py
│   └── daily_run.py
│
└── docs/
    ├── 01-overview-and-domain.md
    ├── 02-pydantic-models.md
    ├── 03-position-monitor.md
    ├── 04-module-implementations.md
    ├── 05-implementation-and-reference.md
    ├── 06-data-sources.md          # IBKR + Yahoo integration
    ├── RULES.md
    ├── DEPLOYMENT.md
    └── API.md
```

---

## Database Schema

```sql
-- Markets
CREATE TABLE markets (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100),
    point_value DECIMAL(10,4) NOT NULL,
    tick_size DECIMAL(10,6) NOT NULL,
    correlation_group VARCHAR(50) NOT NULL,
    exchange VARCHAR(20),
    is_micro BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true
);

-- Price History
CREATE TABLE price_bars (
    id SERIAL PRIMARY KEY,
    market_id INT REFERENCES markets(id),
    bar_date DATE NOT NULL,
    open DECIMAL(12,4),
    high DECIMAL(12,4),
    low DECIMAL(12,4),
    close DECIMAL(12,4),
    volume BIGINT,
    UNIQUE(market_id, bar_date)
);

-- Calculated Indicators
CREATE TABLE calculated_indicators (
    id SERIAL PRIMARY KEY,
    market_id INT REFERENCES markets(id),
    calc_date DATE NOT NULL,
    n_value DECIMAL(12,6),
    donchian_20_high DECIMAL(12,4),
    donchian_20_low DECIMAL(12,4),
    donchian_55_high DECIMAL(12,4),
    donchian_55_low DECIMAL(12,4),
    donchian_10_high DECIMAL(12,4),
    donchian_10_low DECIMAL(12,4),
    UNIQUE(market_id, calc_date)
);

-- Trades (Audit Log)
CREATE TABLE trades (
    id VARCHAR(36) PRIMARY KEY,
    market_id INT REFERENCES markets(id),
    direction VARCHAR(5) NOT NULL,
    system VARCHAR(2) NOT NULL,
    
    entry_date TIMESTAMP NOT NULL,
    entry_price DECIMAL(12,4) NOT NULL,
    n_at_entry DECIMAL(12,6) NOT NULL,
    initial_stop DECIMAL(12,4) NOT NULL,
    initial_units INT NOT NULL,
    initial_contracts INT NOT NULL,
    
    pyramid_levels JSONB DEFAULT '[]',
    max_units INT DEFAULT 1,
    max_contracts INT DEFAULT 1,
    
    exit_date TIMESTAMP,
    exit_price DECIMAL(12,4),
    exit_reason VARCHAR(20),
    final_stop DECIMAL(12,4),
    
    realized_pnl DECIMAL(14,2),
    commission_total DECIMAL(10,2) DEFAULT 0,
    net_pnl DECIMAL(14,2),
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- S1 Filter History
CREATE TABLE s1_filter_history (
    id SERIAL PRIMARY KEY,
    market_id INT REFERENCES markets(id),
    trade_id VARCHAR(36) REFERENCES trades(id),
    was_winner BOOLEAN NOT NULL,
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Portfolio Snapshots
CREATE TABLE portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    equity DECIMAL(14,2) NOT NULL,
    peak_equity DECIMAL(14,2) NOT NULL,
    total_units INT NOT NULL,
    open_pnl DECIMAL(14,2),
    positions JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_trades_market_system ON trades(market_id, system);
CREATE INDEX idx_trades_open ON trades(exit_date) WHERE exit_date IS NULL;
CREATE INDEX idx_s1_filter_market ON s1_filter_history(market_id, recorded_at DESC);
CREATE INDEX idx_price_bars_lookup ON price_bars(market_id, bar_date DESC);
```

---

## Quick Reference Card

```
┌────────────────────────────────────────────────────────────────┐
│                  TURTLE TRADING QUICK REFERENCE                 │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  N (ATR)                                                       │
│  ────────                                                      │
│  N = 20-day ATR (Wilders smoothing)                           │
│  Formula: ((19 × Prev_N) + Current_TR) / 20                   │
│  TOS: ATR(20, WILDERS)                                        │
│                                                                │
│  POSITION SIZING                                               │
│  ────────────────                                              │
│  Unit = (Equity × 2%) / (N × Point_Value × 2)                 │
│  Always round DOWN                                             │
│                                                                │
│  ENTRIES                                                       │
│  ───────                                                       │
│  S1: Price > 20-day high (long) or < 20-day low (short)       │
│  S2: Price > 55-day high (long) or < 55-day low (short)       │
│                                                                │
│  S1 FILTER                                                     │
│  ─────────                                                     │
│  Last S1 winner → SKIP                                         │
│  Last S1 loser  → TAKE                                         │
│  No history     → TAKE                                         │
│  S2 → ALWAYS TAKE (failsafe)                                  │
│                                                                │
│  EXITS                                                         │
│  ─────                                                         │
│  S1: Price touches 10-day opposite breakout                   │
│  S2: Price touches 20-day opposite breakout                   │
│  Hard stop: 2N from entry                                     │
│                                                                │
│  *** STOP DOES NOT TRAIL AUTOMATICALLY ***                    │
│  Stop only moves when pyramiding                              │
│                                                                │
│  PYRAMIDS                                                      │
│  ────────                                                      │
│  Trigger: Price reaches +1N from last entry                   │
│  Action:  Add 1 unit                                          │
│  CRITICAL: Move ALL stops to 2N below newest entry            │
│  Max: 4 units per market                                      │
│                                                                │
│  LIMITS                                                        │
│  ──────                                                        │
│  Per market:  4 units max                                     │
│  Correlated:  6 units max (e.g., MGC + SIL = metals)         │
│  Total:      12 units max                                     │
│                                                                │
│  DRAWDOWN RULE                                                 │
│  ─────────────                                                 │
│  Every 10% drawdown → reduce notional equity by 20%           │
│  Use adjusted equity for all sizing calculations              │
│                                                                │
│  MONITORING PRIORITY                                           │
│  ──────────────────                                            │
│  1. Stop hit      → EXIT immediately (capital preservation)   │
│  2. Breakout exit → EXIT (trend over)                         │
│  3. Pyramid       → ADD if within limits                      │
│  4. Hold          → Continue monitoring                       │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Your Current Portfolio (1-22-2026)

For reference when validating:

| Market | Qty | Entry | Stop | System | N Value |
|--------|-----|-------|------|--------|---------|
| /MGCG26 | 4 | $4,790.25 | $4,770.00 | S2 | $91.42 |
| /M2KH26 | 4 | $2,731.10 | $2,648.50 | S1 | $40.44 |
| /SILH26 | 2 | $96.58 | $87.50 | S1 | $4.56 |

**Total Units:** 10/12  
**Metals Correlation:** 6/6 (at limit)

---

## Next Steps

1. **Review this spec** - Any corrections needed?
2. **Choose starting module** - Recommend `turtle_core` + `market_data`
3. **Set up repo** - Create project structure
4. **Build Phase 1** - Get N calculations matching TOS

Which module do you want to build first?
