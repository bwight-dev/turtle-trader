# Turtle Trading Bot - Implementation Plan

**Created:** 2026-01-27
**Status:** Draft - Awaiting approval
**Methodology:** 25 testable milestones, 1-3 days each

---

## Design Decisions

Based on brainstorming session:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Milestone size | 1-3 days | Fast feedback, easier debugging |
| Testing approach | Automated + manual TOS comparison | Balance speed with accuracy validation |
| Caching | In-memory (skip Redis) | Simpler stack, add Redis later if needed |
| Starting point | IBKR connection first | Validate infrastructure early |
| DDD strictness | Clean Architecture | Layered structure with domain at center |
| AI/Workflow | LangGraph from start | Build target architecture early |
| Execution scope | Paper-first with live architecture | Config change for live, no refactoring |

---

## Infrastructure

### Database
```bash
# Neon PostgreSQL (cloud)
DATABASE_URL=postgresql://neondb_owner:npg_ipM4O8DGaeBP@ep-autumn-morning-afn6oh1a-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require
```

### IBKR
- TWS on Mac Mini (local)
- Paper: Port 7497, Account DUP318628
- Live: Port 7496 (future)

---

## File Structure (Clean Architecture)

Based on architecture review, using layered Clean Architecture:

```
src/
├── domain/                         # Core domain (innermost layer)
│   ├── models/                     # Entities and Value Objects
│   │   ├── __init__.py
│   │   ├── enums.py               # Direction, System, PositionAction
│   │   ├── market.py              # NValue, DonchianChannel, Bar, MarketSpec
│   │   ├── position.py            # Position, PyramidLevel (aggregate)
│   │   ├── portfolio.py           # Portfolio (aggregate root)
│   │   ├── signal.py              # Signal, FilterResult
│   │   ├── order.py               # BracketOrder, OrderFill
│   │   ├── trade.py               # Trade (audit record)
│   │   └── limits.py              # LimitCheckResult
│   ├── interfaces/                 # Ports (abstract interfaces)
│   │   ├── __init__.py
│   │   ├── data_feed.py           # DataFeed ABC
│   │   ├── broker.py              # Broker ABC
│   │   └── repositories.py        # Repository ABCs
│   ├── services/                   # Domain services (pure business logic)
│   │   ├── __init__.py
│   │   ├── signal_detector.py     # S1/S2 breakout detection
│   │   ├── s1_filter.py           # S1 filter logic
│   │   ├── position_monitor.py    # Stop/exit/pyramid detection
│   │   ├── limit_checker.py       # Position limit validation
│   │   ├── sizing.py              # Unit size calculator
│   │   └── stop_calculator.py     # Stop price calculator
│   └── rules.py                    # TurtleRules configuration
│
├── application/                    # Use cases (application layer)
│   ├── __init__.py
│   ├── commands/                   # Write operations
│   │   ├── __init__.py
│   │   ├── place_entry.py
│   │   ├── execute_pyramid.py
│   │   ├── close_position.py
│   │   └── modify_stop.py
│   ├── queries/                    # Read operations
│   │   ├── __init__.py
│   │   ├── scan_markets.py
│   │   ├── get_portfolio.py
│   │   └── get_market_data.py
│   └── workflows/                  # LangGraph orchestration
│       ├── __init__.py
│       ├── daily_workflow.py
│       ├── monitoring_loop.py
│       └── trade_lifecycle.py
│
├── adapters/                       # Interface adapters (infrastructure)
│   ├── __init__.py
│   ├── data_feeds/                 # DataFeed implementations
│   │   ├── __init__.py
│   │   ├── ibkr_feed.py           # IBKR via ib_insync
│   │   ├── yahoo_feed.py          # Yahoo Finance backup
│   │   └── composite_feed.py      # Failover wrapper
│   ├── brokers/                    # Broker implementations
│   │   ├── __init__.py
│   │   ├── paper_broker.py
│   │   └── ibkr_broker.py
│   ├── repositories/               # Database implementations
│   │   ├── __init__.py
│   │   ├── n_repository.py        # N value persistence
│   │   ├── trade_repository.py    # Trade audit log
│   │   └── portfolio_repository.py
│   └── mappers/                    # Data transformation
│       ├── __init__.py
│       ├── symbol_mapper.py       # Internal ↔ IBKR ↔ Yahoo
│       └── ibkr_mapper.py         # IBKR data → domain models
│
├── infrastructure/                 # Frameworks & drivers (outermost)
│   ├── __init__.py
│   ├── database.py                # Neon connection pool
│   ├── config.py                  # Environment configuration
│   ├── logging.py                 # Structured logging
│   └── migrations/                # Database migrations
│       └── ...
│
└── scripts/                        # CLI entry points
    ├── setup_db.py
    ├── test_neon.py
    ├── test_ibkr.py
    ├── import_tos.py
    └── daily_run.py

tests/
├── unit/                           # Domain + services (no I/O)
│   ├── domain/
│   └── services/
├── integration/                    # Adapters + real connections
│   ├── data_feeds/
│   ├── brokers/
│   └── repositories/
├── e2e/                            # Full workflows
└── fixtures/                       # Test data
    └── mgc_bars.json
```

**Layer Dependencies (Clean Architecture):**
```
infrastructure → adapters → application → domain
     ↓              ↓            ↓           ↓
  (outer)                                 (inner)

Dependencies point INWARD. Domain knows nothing about outer layers.
```

---

## Milestone Overview

```
Foundation (M1-M4)        ~1 week
├── M1: Project setup + Neon connection
├── M2: IBKR TWS connection
├── M3: Core Pydantic models
└── M4: N (ATR) calculator with TOS validation

Market Data (M5-M8)       ~1.5 weeks
├── M5: Donchian channel calculator
├── M6: Yahoo Finance backup feed
├── M7: Composite feed with failover
├── M7.5: Contract rollover logic (Rule 15)
└── M8: N value persistence (Neon)

Strategy Engine (M9-M12)  ~1 week
├── M9: S1/S2 signal detector
├── M10: S1 filter with trade history
├── M11: Market scanner
└── M12: LangGraph workflow skeleton

Portfolio (M13-M17)       ~1.5 weeks
├── M13: Position model + pyramid tracking
├── M14: Unit size calculator + drawdown tracker (Rule 5)
├── M15: Limit checker
├── M16: Position Monitor (stops)
└── M17: Position Monitor (pyramids + exits)

Execution (M18-M21)       ~1.5 weeks
├── M18: Broker interface + Paper broker
├── M19: IBKR bracket orders
├── M20: Stop modification + position sync
└── M21: Account reconciliation

Integration (M22-M25)     ~1 week
├── M22: Audit logging + trade history
├── M23: Daily workflow (LangGraph)
├── M24: Monitoring loop integration
└── M25: Docker deployment
```

---

## Milestone Details

### Foundation Phase

#### M1: Project Setup + Neon Connection

**Deliverables:**
- `pyproject.toml` with dependencies
- `.env.example` with Neon connection template
- `src/` directory structure (domain, application, adapters, infrastructure)
- `src/infrastructure/database.py` - Neon connection pool
- `src/infrastructure/config.py` - Environment configuration
- `scripts/test_neon.py`
- Database migrations for `markets` table

**Dependencies:** None

**Acceptance Tests:**
```python
async def test_neon_connection():
    pool = await get_pool()
    result = await pool.fetchval("SELECT 1")
    assert result == 1

async def test_markets_table_exists():
    pool = await get_pool()
    exists = await pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'markets')"
    )
    assert exists
```

**Manual Verification:**
- `scripts/test_neon.py` prints "Connected to Neon successfully"
- Check Neon dashboard shows connection

---

#### M2: IBKR TWS Connection

**Deliverables:**
- `src/infrastructure/config.py` - add IBKRConfig
- `src/domain/interfaces/data_feed.py` - DataFeed ABC (port)
- `src/adapters/data_feeds/ibkr_feed.py` - IBKRDataFeed (connection only)
- `scripts/test_ibkr.py`

**Dependencies:** M1

**Acceptance Tests:**
```python
@pytest.mark.asyncio
async def test_ibkr_connects():
    feed = IBKRDataFeed()
    connected = await feed.connect()
    assert connected
    assert feed.is_connected
    await feed.disconnect()

@pytest.mark.asyncio
async def test_ibkr_account_summary():
    feed = IBKRDataFeed()
    await feed.connect()
    summary = await feed.get_account_summary()
    assert 'NetLiquidation' in summary
    await feed.disconnect()
```

**Manual Verification:**
- TWS running on Mac Mini with paper account DUP318628
- `scripts/test_ibkr.py` prints account equity

---

#### M3: Core Pydantic Models

**Deliverables:**
- `src/domain/models/enums.py` - Direction, System, PositionAction, CorrelationGroup
- `src/domain/models/market.py` - NValue, DonchianChannel, Bar, MarketSpec, MarketData
- `src/domain/models/signal.py` - Signal, FilterResult
- `src/domain/models/order.py` - BracketOrder, OrderFill, StopModification
- `src/domain/models/trade.py` - Trade (audit record)
- `src/domain/models/limits.py` - LimitCheckResult
- `src/domain/rules.py` - TurtleRules configuration

**Dependencies:** M1

**Acceptance Tests:**
```python
def test_nvalue_to_dollars():
    n = NValue(value=Decimal("20"), calculated_at=datetime.now())
    dollar_risk = n.to_dollars(Decimal("10"))
    assert dollar_risk == Decimal("200")

def test_bar_validation():
    with pytest.raises(ValidationError):
        Bar(symbol="/MGC", date=date.today(),
            open=Decimal("100"), high=Decimal("90"),
            low=Decimal("95"), close=Decimal("98"))

def test_position_pyramid_trigger():
    pos = Position(...)
    assert pos.next_pyramid_trigger == Decimal("2820")
```

**Manual Verification:**
- Import all models in REPL
- Verify frozen=True prevents mutation

---

#### M4: N (ATR) Calculator with TOS Validation

**Deliverables:**
- `src/domain/services/volatility.py` - calculate_true_range(), calculate_n()
- `tests/fixtures/mgc_bars.json` (30 days from TOS export)

**Dependencies:** M2, M3

**Acceptance Tests:**
```python
def test_true_range_gap_up():
    tr = calculate_true_range(
        high=Decimal("105"), low=Decimal("102"),
        prev_close=Decimal("100")
    )
    assert tr == Decimal("5")

def test_n_matches_tos():
    bars = load_fixture("mgc_bars.json")
    n = calculate_n(bars, period=20, method="WILDERS")

    tos_value = Decimal("91.42")  # From TOS 1-22-2026
    deviation = abs(n.value - tos_value) / tos_value
    assert deviation < Decimal("0.005")
```

**Manual Verification:**
- Open TOS, check ATR(20, WILDERS) for /MGC
- Compare to test output, should match within 0.5%

---

### Market Data Phase

#### M5: Donchian Channel Calculator

**Deliverables:**
- `src/domain/services/channels.py` - calculate_donchian()

**Dependencies:** M4

**Acceptance Tests:**
```python
def test_donchian_20_matches_tradingview():
    bars = load_fixture("mgc_bars.json")
    dc = calculate_donchian(bars, period=20)
    # Verify against TradingView values
    assert dc.upper == Decimal("2850.00")
    assert dc.lower == Decimal("2740.00")
```

**Manual Verification:**
- Open TradingView, add Donchian(20) to /MGC
- Compare upper/lower to test output

---

#### M6: Yahoo Finance Backup Feed

**Deliverables:**
- `src/infrastructure/config.py` - add YahooConfig
- `src/adapters/data_feeds/yahoo_feed.py` - YahooDataFeed
- `src/adapters/mappers/symbol_mapper.py` - SymbolMapper (internal ↔ Yahoo)

**Dependencies:** M3

**Acceptance Tests:**
```python
@pytest.mark.asyncio
async def test_yahoo_fetches_bars():
    feed = YahooDataFeed()
    bars = await feed.get_bars("/MGC", days=30)
    assert len(bars) >= 20
    assert all(b.high >= b.low for b in bars)

def test_symbol_mapper_to_yahoo():
    mapper = SymbolMapper()
    assert mapper.to_yahoo("/MGC") == "MGC=F"
```

**Manual Verification:**
- Fetch /MGC from Yahoo, compare close to TOS

---

#### M7: Composite Feed with Failover

**Deliverables:**
- `src/infrastructure/config.py` - add DataSourceConfig
- `src/adapters/data_feeds/composite_feed.py` - CompositeDataFeed with failover
- `src/domain/services/validation.py` - validate_bar() function

**Dependencies:** M2, M6

**Acceptance Tests:**
```python
@pytest.mark.asyncio
async def test_uses_ibkr_when_available():
    feed = CompositeDataFeed()
    bars = await feed.get_bars("/MGC", days=20)
    assert feed.last_source == "ibkr"

@pytest.mark.asyncio
async def test_falls_back_to_yahoo():
    config = DataSourceConfig()
    config.ibkr.port = 9999  # Invalid
    feed = CompositeDataFeed(config)
    bars = await feed.get_bars("/MGC", days=20)
    assert feed.last_source == "yahoo"
```

**Manual Verification:**
- Stop TWS, run feed - should use Yahoo
- Start TWS, run feed - should use IBKR

---

#### M7.5: Contract Rollover Logic (Futures)

**Deliverables:**
- `src/domain/services/rollover_detector.py` - RolloverDetector (Rule 15)
- `src/adapters/data_feeds/continuous_contract.py` - ContinuousContractBuilder
- `src/infrastructure/config.py` - add rollover thresholds

**Dependencies:** M7

**Rule 15 Implementation:** The Rollover Logic rule:
- Detect when to roll: volume shifts to new month OR X weeks before expiry
- Roll the position: exit old contract, enter new contract simultaneously
- Do NOT exit a trend just because contract expires
- Handle back-adjustment for historical data (optional for live trading)

**Acceptance Tests:**
```python
def test_rollover_detected_by_volume():
    """Detect rollover when front month volume drops"""
    detector = RolloverDetector()
    # Front month has less volume than next month
    result = detector.should_roll(
        front_month_volume=5000,
        next_month_volume=15000,
        days_to_expiry=10,
    )
    assert result.should_roll is True
    assert "volume" in result.reason.lower()

def test_rollover_detected_by_expiry():
    """Detect rollover when near expiry"""
    detector = RolloverDetector(days_before_expiry=14)
    result = detector.should_roll(
        front_month_volume=15000,
        next_month_volume=5000,  # Volume still in front
        days_to_expiry=7,  # But only 7 days left
    )
    assert result.should_roll is True
    assert "expiry" in result.reason.lower()

def test_continuous_contract_builds():
    """Build continuous contract from multiple expirations"""
    builder = ContinuousContractBuilder()
    continuous = builder.build("/MGC", start_date=date(2025, 1, 1))

    # Should have no gaps
    assert len(continuous.bars) > 200
    assert all(b.date for b in continuous.bars)
```

**Manual Verification:**
- Check IBKR contract expiration dates for /MGC
- Verify rollover detection triggers appropriately
- Test manual roll: exit G26, enter J26

---

#### M8: N Value Persistence (Neon)

**Deliverables:**
- `src/domain/interfaces/repositories.py` - add NValueRepository ABC (port)
- `src/adapters/repositories/n_repository.py` - PostgresNValueRepository (adapter)
- Database migrations for `calculated_indicators` table
- `src/application/commands/update_indicators.py` - DailyUpdateCommand (partial)

**Dependencies:** M1, M4, M5, M7

**Acceptance Tests:**
```python
@pytest.mark.asyncio
async def test_save_and_retrieve_n():
    repo = NValueRepository(pool)
    await repo.save_n(symbol="/MGC", calc_date=date(2026, 1, 22), ...)
    indicators = await repo.get_latest_indicators("/MGC")
    assert indicators["n_value"] == Decimal("91.42")

@pytest.mark.asyncio
async def test_n_calculation_uses_previous():
    await repo.save_n(symbol="/MGC", calc_date=date(2026, 1, 21), n_value=Decimal("90.00"), ...)
    prev_n = await repo.get_previous_n("/MGC", date(2026, 1, 22))
    assert prev_n == Decimal("90.00")
```

**Manual Verification:**
- Run daily update for /MGC
- Check Neon dashboard - row in calculated_indicators
- Restart bot, verify previous N loaded from DB

---

### Strategy Engine Phase

#### M9: S1/S2 Signal Detector

**Deliverables:**
- `src/domain/services/signal_detector.py` - SignalDetector (pure domain logic)

**Dependencies:** M3, M7

**Acceptance Tests:**
```python
def test_s1_long_breakout():
    market = make_market_data(
        current_price=Decimal("2860"),
        donchian_20_upper=Decimal("2850"),
    )
    detector = SignalDetector()
    signal = detector.detect_s1_signal(market)
    assert signal.direction == Direction.LONG

def test_no_signal_inside_channel():
    market = make_market_data(current_price=Decimal("2800"), ...)
    detector = SignalDetector()
    assert detector.detect_s1_signal(market) is None
```

**Manual Verification:**
- Check TOS for markets you're tracking
- Run detector, confirm matching results

---

#### M10: S1 Filter with Trade History

**Deliverables:**
- `src/domain/services/s1_filter.py` - S1Filter (domain service)
- `src/domain/interfaces/repositories.py` - add TradeRepository ABC (port)
- `src/adapters/repositories/trade_repository.py` - PostgresTradeRepository (partial)
- Database migrations for `s1_filter_history` table

**Dependencies:** M1, M9

**Acceptance Tests:**
```python
@pytest.mark.asyncio
async def test_skip_after_winner():
    repo.set_last_s1_trade("/MGC", was_winner=True)
    filter = S1Filter(repo)
    result = await filter.should_take_signal("/MGC", signal)
    assert result.take_signal is False

@pytest.mark.asyncio
async def test_s2_never_filtered():
    repo.set_last_s1_trade("/MGC", was_winner=True)
    filter = S1Filter(repo)
    signal = make_signal(system=System.S2)
    result = await filter.should_take_signal("/MGC", signal)
    assert result.take_signal is True
```

**Manual Verification:**
- Check your TOS history for /MGC
- Verify filter matches your manual decision

---

#### M11: Market Scanner

**Deliverables:**
- `src/application/queries/scan_markets.py` - MarketScanner (use case)
- `src/infrastructure/config.py` - add universe configuration

**Dependencies:** M9, M10

**Acceptance Tests:**
```python
@pytest.mark.asyncio
async def test_scans_universe():
    universe = ["/MGC", "/M2K", "/MES", "/SIL"]
    scanner = MarketScanner(...)
    results = await scanner.scan(universe)
    assert len(results) == 4
```

**Manual Verification:**
- Run scanner against your universe
- Compare to daily TOS scan

---

#### M12: LangGraph Workflow Skeleton

**Deliverables:**
- `src/application/workflows/trade_lifecycle.py` - LangGraph state machine
- State definitions: SCAN → VALIDATE → SIZE → EXECUTE → MONITOR

**Dependencies:** M11

**Acceptance Tests:**
```python
def test_workflow_states_defined():
    states = workflow.nodes.keys()
    assert "scan" in states
    assert "validate_signal" in states

async def test_workflow_dry_run():
    result = await workflow.run({"dry_run": True})
    assert result.status == "completed"
```

**Manual Verification:**
- Run workflow in dry-run
- Verify state transitions logged correctly

---

### Portfolio Phase

#### M13: Position Model + Pyramid Tracking

**Deliverables:**
- `src/domain/models/position.py` - Position, PyramidLevel (entity with identity)
- `src/domain/models/portfolio.py` - Portfolio (aggregate root)

**Dependencies:** M3

**Architecture Note:** Per architecture review, Portfolio should use aggregate methods:
- `portfolio.add_position(position)` - enforces limits
- `portfolio.close_position(symbol)` - returns closed position
- `portfolio.update_stop(symbol, new_stop)` - modifies position stop

This protects invariants (limits, stops) and makes the aggregate the single source of truth.

**Acceptance Tests:**
```python
def test_position_total_contracts():
    pos = make_position_with_pyramids(...)
    assert pos.total_contracts == 7
    assert pos.total_units == 3

def test_next_pyramid_trigger_long():
    pos = make_position(
        direction=Direction.LONG,
        latest_entry_price=Decimal("2800"),
        latest_n_at_entry=Decimal("20"),
    )
    # ½N = 10, so trigger at 2810 (Rule 11: pyramid at ½N intervals)
    assert pos.next_pyramid_trigger == Decimal("2810")
```

**Manual Verification:**
- Model your /MGC position (4 units)
- Verify `can_pyramid == False`

---

#### M14: Unit Size Calculator + Drawdown Tracker

**Deliverables:**
- `src/domain/services/sizing.py` - calculate_unit_size() (pure function)
- `src/domain/services/stop_calculator.py` - calculate_stop() (pure function)
- `src/domain/services/drawdown_tracker.py` - DrawdownTracker (Rule 5)
- `src/domain/models/equity.py` - EquityState (actual vs notional)

**Dependencies:** M3

**Rule 5 Implementation:** The Drawdown Reduction rule:
- Track peak equity (starting or annual high)
- When equity drops 10% from peak → reduce notional equity by 20%
- All sizing calculations use notional equity, not actual
- When equity recovers to peak → restore notional = actual

**Acceptance Tests:**
```python
def test_unit_size_rounds_down():
    # Rule 4: Risk Factor = 0.5% (Parker modern for 300+ markets)
    # $100k × 0.005 = $500 risk budget
    # Dollar volatility = N × point_value = 20 × 10 = $200
    # Unit size = 500 / 200 = 2.5, rounds down to 2
    size = calculate_unit_size(
        equity=Decimal("100000"),
        n_value=NValue(value=Decimal("20"), ...),
        point_value=Decimal("10"),
        risk_pct=Decimal("0.005"),  # 0.5% Parker rule
    )
    assert size.contracts == 2

def test_stop_calculation_long():
    stop = calculate_stop(
        entry_price=Decimal("2800"),
        n_value=NValue(value=Decimal("20"), ...),
        direction=Direction.LONG,
    )
    assert stop.price == Decimal("2760")

def test_drawdown_reduces_notional_equity():
    """Rule 5: 10% drawdown → 20% notional reduction"""
    tracker = DrawdownTracker(peak_equity=Decimal("100000"))
    tracker.update_equity(Decimal("89000"))  # 11% drawdown

    # Notional should be reduced by 20%
    assert tracker.notional_equity == Decimal("80000")  # 100k × 0.8
    assert tracker.actual_equity == Decimal("89000")

def test_drawdown_recovery_restores_notional():
    """Rule 5: Recovery restores notional to actual"""
    tracker = DrawdownTracker(peak_equity=Decimal("100000"))
    tracker.update_equity(Decimal("89000"))  # Draw down
    assert tracker.notional_equity == Decimal("80000")

    tracker.update_equity(Decimal("100000"))  # Recover
    assert tracker.notional_equity == Decimal("100000")

def test_sizing_uses_notional_not_actual():
    """Sizing must use notional equity during drawdown"""
    equity_state = EquityState(actual=Decimal("89000"), notional=Decimal("80000"))
    size = calculate_unit_size(
        equity=equity_state.notional,  # Use notional!
        n_value=NValue(value=Decimal("20"), ...),
        point_value=Decimal("10"),
        risk_pct=Decimal("0.005"),
    )
    # $80k × 0.005 / 200 = 2 contracts (not 2.225 if using actual)
    assert size.contracts == 2
```

**Manual Verification:**
- Calculate manually for /M2K
- Compare to function output
- Test drawdown scenario: if account drops to $89k from $100k, notional should be $80k

---

#### M15: Limit Checker

**Deliverables:**
- `src/domain/services/limit_checker.py` - LimitChecker (domain service)

**Dependencies:** M13

**Acceptance Tests:**
```python
def test_total_units_limit():
    portfolio = make_portfolio(total_units=11)
    checker = LimitChecker()
    result = checker.can_add_position(
        portfolio, symbol="/MES", units_to_add=2, ...
    )
    assert result.allowed is False

def test_your_current_portfolio():
    # 10 units, metals at 6
    portfolio = make_portfolio(...)
    checker = LimitChecker()

    # Can add non-metals
    result = checker.can_add_position(
        portfolio, symbol="/MES", units_to_add=1,
        correlation_group=CorrelationGroup.EQUITY_US,
    )
    assert result.allowed is True
```

**Manual Verification:**
- Your portfolio: 10/12 total, Metals 6/6
- Verify checker blocks new metals

---

#### M16: Position Monitor (Stops)

**Deliverables:**
- `src/domain/services/position_monitor.py` - PositionMonitor (stop detection only)

**Dependencies:** M13, M14

**Acceptance Tests:**
```python
def test_stop_hit_long():
    pos = make_position(direction=Direction.LONG, current_stop=Decimal("2760"))
    market = make_market_data(current_price=Decimal("2760"))

    monitor = PositionMonitor(...)
    check = monitor.check_position(pos, market)
    assert check.action == PositionAction.EXIT_STOP

def test_no_stop_when_safe():
    pos = make_position(direction=Direction.LONG, current_stop=Decimal("2760"))
    market = make_market_data(current_price=Decimal("2800"))

    monitor = PositionMonitor(...)
    check = monitor.check_position(pos, market)
    assert check.action != PositionAction.EXIT_STOP
```

**Manual Verification:**
- /M2K stop at $2,648.50
- Run monitor with current price
- Simulate price at $2,648 - should EXIT_STOP

---

#### M17: Position Monitor (Pyramids + Exits)

**Deliverables:**
- `src/domain/services/position_monitor.py` - PositionMonitor (complete)
- `src/application/commands/execute_pyramid.py` - PyramidHandler (use case)
- `src/application/commands/close_position.py` - ExitHandler (use case)

**Dependencies:** M15, M16

**Architecture Note:** Per architecture review, use separation of concerns:
- `PositionMonitor` (domain) - **only detects** what action is needed (HOLD/PYRAMID/EXIT)
- `PyramidHandler` (application) - **handles pyramid execution** (sizing, stop calc, order)
- `ExitHandler` (application) - **handles exit execution** (close order, P&L calc)

This reduces coupling and makes the monitor testable without mocking execution.

**Acceptance Tests:**
```python
def test_s1_long_exit_on_10day_low():
    pos = make_position(system=System.S1, ...)
    market = make_market_data(
        current_price=Decimal("2780"),
        donchian_10_lower=Decimal("2785"),
    )
    check = monitor.check_position(pos, market)
    assert check.action == PositionAction.EXIT_BREAKOUT

def test_pyramid_triggered_at_plus_1n():
    pos = make_position(total_units=2, ...)
    market = make_market_data(current_price=Decimal("2825"), ...)
    check = monitor.check_position(pos, market)
    assert check.action == PositionAction.PYRAMID

def test_stop_checked_before_exit():
    # Both stop AND breakout triggered
    pos = make_position(current_stop=Decimal("2760"), ...)
    market = make_market_data(
        current_price=Decimal("2755"),
        donchian_10_lower=Decimal("2758"),
    )
    check = monitor.check_position(pos, market)
    assert check.action == PositionAction.EXIT_STOP  # Priority
```

**Manual Verification:**
- Run monitor against your positions
- Verify correct hold/pyramid/exit decisions

---

### Execution Phase

#### M18: Broker Interface + Paper Broker

**Deliverables:**
- `src/domain/interfaces/broker.py` - Broker ABC (port in domain layer)
- `src/adapters/brokers/paper_broker.py` - PaperBroker simulation (adapter)

**Dependencies:** M3

**Acceptance Tests:**
```python
@pytest.mark.asyncio
async def test_bracket_order_execution():
    broker = PaperBroker()
    order = BracketOrder(...)
    fill = await broker.place_bracket_order(order)
    assert fill.quantity == 2
    assert fill.commission > 0

@pytest.mark.asyncio
async def test_stop_modification():
    broker = PaperBroker()
    # Open position, then modify stop
    mod = await broker.modify_stop(position_id, Decimal("2780"))
    assert mod.new_stop == Decimal("2780")
```

**Manual Verification:**
- Run paper broker in REPL
- Place order, modify stop, close

---

#### M19: IBKR Bracket Orders

**Deliverables:**
- `src/adapters/brokers/ibkr_broker.py` - IBKRBroker (adapter)
- `src/adapters/mappers/ibkr_mapper.py` - Order/fill mapping

**Dependencies:** M2, M18

**Acceptance Tests:**
```python
@pytest.mark.asyncio
@pytest.mark.ibkr
async def test_place_bracket_order_paper():
    broker = IBKRBroker(paper=True)
    await broker.connect()
    order = BracketOrder(symbol="/MES", ...)
    fill = await broker.place_bracket_order(order)
    assert fill.quantity == 1
    # Clean up
    await broker.close_position(fill.order_id, 1)
```

**Manual Verification:**
- Place bracket order on paper account
- Check TWS - verify stop visible
- Cancel test position

---

#### M20: Stop Modification + Position Sync

**Deliverables:**
- `src/adapters/brokers/ibkr_broker.py` - add modify_stop(), get_positions()
- `src/application/commands/modify_stop.py` - ModifyStopCommand (use case)
- `src/application/queries/sync_portfolio.py` - SyncPortfolioQuery (use case)

**Dependencies:** M19

**Acceptance Tests:**
```python
@pytest.mark.asyncio
@pytest.mark.ibkr
async def test_modify_stop():
    # Open position, modify stop
    mod = await broker.modify_stop(position_id, Decimal("5950"))
    assert mod.new_stop == Decimal("5950")
    # Verify in IBKR
    orders = await broker.get_open_orders("/MES")
    assert orders[0].stop_price == Decimal("5950")

@pytest.mark.asyncio
@pytest.mark.ibkr
async def test_position_sync():
    positions = await broker.get_positions()
    assert isinstance(positions, list)
```

**Manual Verification:**
- Open manual position in TWS
- Run sync - should see position
- Modify stop in code - verify TWS updated

---

#### M21: Account Reconciliation

**Deliverables:**
- `src/application/queries/reconcile_account.py` - Reconciler (use case)

**Dependencies:** M20

**Acceptance Tests:**
```python
@pytest.mark.asyncio
async def test_reconciliation_matches():
    result = reconciler.compare(portfolio, ibkr_positions)
    assert result.matches is True

@pytest.mark.asyncio
async def test_reconciliation_detects_mismatch():
    portfolio = make_portfolio(positions={"/MES": make_position(total_contracts=999)})
    result = reconciler.compare(portfolio, ibkr_positions)
    assert result.matches is False
```

**Manual Verification:**
- Run against paper account
- Create mismatch, verify detection

---

### Integration Phase

#### M22: Audit Logging + Trade History

**Deliverables:**
- `src/application/commands/log_trade.py` - TradeLogger (use case)
- `src/adapters/repositories/trade_repository.py` - PostgresTradeRepository (complete)
- Database migrations for `trades` table

**Dependencies:** M1, M13

**Acceptance Tests:**
```python
@pytest.mark.asyncio
async def test_log_entry():
    trade = await logger.log_entry(position, signal, unit_size, fill)
    saved = await repo.get_trade(trade.id)
    assert saved.symbol == trade.symbol

@pytest.mark.asyncio
async def test_log_exit_updates_pnl():
    trade = await logger.log_exit(position, exit_price=Decimal("2850"), ...)
    assert trade.realized_pnl == Decimal("2000")
```

**Manual Verification:**
- Import TOS history
- Query database
- Run S1 filter lookup

---

#### M23: Daily Workflow (LangGraph)

**Deliverables:**
- `src/application/workflows/daily_workflow.py` - DailyWorkflow (LangGraph)

**Dependencies:** M12, M17, M21, M22

**Acceptance Tests:**
```python
@pytest.mark.asyncio
async def test_workflow_dry_run():
    result = await workflow.run()
    assert result.status == "completed"
    assert result.orders_executed == 0  # Dry run
```

**Manual Verification:**
- Run in dry-run mode
- Compare signals to manual TOS scan

---

#### M24: Monitoring Loop Integration

**Deliverables:**
- `src/application/workflows/monitoring_loop.py` - MonitoringLoop (continuous)

**Dependencies:** M17, M21, M22

**Acceptance Tests:**
```python
@pytest.mark.asyncio
async def test_monitoring_loop_checks_positions():
    for _ in range(3):
        result = await loop.monitor.run_monitoring_cycle(portfolio)
    assert all(r.positions_checked == 2 for r in results)

@pytest.mark.asyncio
async def test_monitoring_executes_exit():
    mock_feed.set_price("/MGC", Decimal("2758"))  # Below stop
    await loop._process_cycle(portfolio)
    assert "/MGC" not in portfolio.positions
```

**Manual Verification:**
- Run with your positions
- Verify correct decisions
- Test simulated stop hit

---

#### M25: Docker Deployment

**Deliverables:**
- `Dockerfile` - Production image
- `docker-compose.yml` - Full stack configuration
- `scripts/deploy.sh` - Deploy to Unraid
- Health check endpoints

**Dependencies:** M23, M24

**Acceptance Tests:**
```python
def test_docker_builds():
    result = subprocess.run(["docker", "build", "-t", "turtle-bot", "."])
    assert result.returncode == 0

def test_container_starts():
    # Check health status
    assert b"healthy" in result.stdout
```

**Manual Verification:**
- Deploy to Unraid
- Check logs
- Verify Neon + IBKR connections

---

## Dependency Graph

```
M1 (Neon) ─────────────────────────────────────────────────┐
    │                                                       │
    ├──► M2 (IBKR) ──► M4 (N calc) ──► M5 (Donchian)      │
    │         │                              │              │
    │         │                              ▼              │
    │         └───────────► M7 (Composite) ──► M8 (Persist)│
    │                              ▲                        │
    │                              │                        │
    ├──► M3 (Models) ──────────────┘                       │
    │         │                                             │
    │         ├──► M6 (Yahoo)                              │
    │         │                                             │
    │         ├──► M9 (Signals) ──► M10 (S1 Filter) ◄──────┤
    │         │         │               │                   │
    │         │         └───────────────┴──► M11 (Scanner) │
    │         │                                    │        │
    │         │                                    ▼        │
    │         │                              M12 (LangGraph)│
    │         │                                    │        │
    │         ├──► M13 (Position) ──► M15 (Limits)         │
    │         │         │                  │                │
    │         │         ▼                  ▼                │
    │         ├──► M14 (Sizing) ──► M16 (Monitor-Stop)     │
    │         │                           │                 │
    │         │                           ▼                 │
    │         │                    M17 (Monitor-Full)      │
    │         │                           │                 │
    │         └──► M18 (Broker) ──► M19 (IBKR Orders)      │
    │                   │              │                    │
    │                   │              ▼                    │
    │                   │        M20 (Stop Mod)            │
    │                   │              │                    │
    │                   │              ▼                    │
    │                   │        M21 (Reconcile)           │
    │                   │              │                    │
    │                   ▼              │                    │
    └──► M22 (Audit) ◄─┴──────────────┘                    │
              │                                             │
              ▼                                             │
         M23 (Workflow) ◄──────────────────────────────────┘
              │
              ▼
         M24 (Monitor Loop)
              │
              ▼
         M25 (Docker)
```

---

## Current Portfolio Reference (1-22-2026)

For validation testing:

| Market | Qty | Entry | Stop | System | N Value |
|--------|-----|-------|------|--------|---------|
| /MGCG26 | 4 | $4,790.25 | $4,770.00 | S2 | $91.42 |
| /M2KH26 | 4 | $2,731.10 | $2,648.50 | S1 | $40.44 |
| /SILH26 | 2 | $96.58 | $87.50 | S1 | $4.56 |

**Total Units:** 10/12
**Metals Correlation:** 6/6 (at limit)

---

## Next Steps

1. Review and approve this plan
2. Run architecture-patterns skill to validate DDD design
3. Create project structure (M1)
4. Begin implementation

---

## Changelog

- 2026-01-27: Verified against RULES.md - Fixed pyramid interval to ½N, risk to 0.5%
- 2026-01-27: Added M7.5 (Rollover Logic) for Rule 15
- 2026-01-27: Added Drawdown Tracker to M14 for Rule 5
- 2026-01-27: Applied Clean Architecture file structure from architecture review
- 2026-01-27: Added architecture notes to M13 (aggregate methods) and M17 (separation of concerns)
- 2026-01-27: Initial draft created from brainstorming session
