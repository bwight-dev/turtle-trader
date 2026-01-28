# Backtesting Infrastructure Plan

**Created:** 2026-01-28
**Status:** Planning
**Target:** Backtest Turtle Trading Bot on 2024-2025 data

---

## Executive Summary

Build backtesting infrastructure to validate the Turtle Trading Bot against historical data before live deployment. Goal: run simulations on 2024-2025 market data and validate against known Turtle Trading performance characteristics.

---

## Part 1: How Other Bot Traders Test Their Bots

### Industry Best Practices

Based on research from [QuantStart](https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-I/), [3Commas](https://3commas.io/blog/comprehensive-2025-guide-to-backtesting-ai-trading), and [ForexTester](https://forextester.com/blog/algo-strategies/):

#### 1. Data Quality First
- Use high-quality OHLC data from reliable sources
- Clean data: adjust for splits, dividends, delisted symbols
- Include realistic commissions and slippage
- Source venue-specific data when possible

#### 2. Testing Methodology
- **In-Sample / Out-of-Sample Split**: Fit parameters on first segment, validate on second
- **Walk-Forward Analysis**: Re-calibrate on rolling window, test on next period
- **Minimum Duration**: Run simulations over 2+ years
- **Multi-Phase**: Backtest → Paper Trade → Small Live → Scale Up

#### 3. Avoiding Overfitting
- Prefer simple rules with clear rationale (Turtle rules qualify!)
- Use parameter ranges rather than "magic numbers"
- Stress test: degrade signals, widen spreads, insert data gaps
- Out-of-sample validation is mandatory

#### 4. Key Metrics to Track
| Metric | Target | Notes |
|--------|--------|-------|
| Sharpe Ratio | > 1.5 | Risk-adjusted returns |
| Max Drawdown | < 30% | Turtle systems historically ~25% |
| Win Rate | 35-45% | Trend following is low win rate, high R:R |
| Expectancy | Positive | (Win% × Avg Win) - (Loss% × Avg Loss) |
| Profit Factor | > 1.5 | Gross Profit / Gross Loss |

#### 5. Risk Management Validation
- Verify position sizing limits work (4/6/12 unit caps)
- Confirm stops trigger at 2N levels
- Test drawdown rule (10% DD → 20% equity reduction)
- Validate pyramid behavior (+½N intervals)

---

### Python Backtesting Frameworks Comparison

Research from [AutoTradeLab](https://autotradelab.com/blog/backtrader-vs-nautilusttrader-vs-vectorbt-vs-zipline-reloaded) and [Medium](https://medium.com/@trading.dude/battle-tested-backtesters-comparing-vectorbt-zipline-and-backtrader-for-financial-strategy-dee33d33a9e0):

| Framework | Speed | Live Trading | Learning Curve | Status |
|-----------|-------|--------------|----------------|--------|
| **VectorBT** | Fastest (vectorized) | Limited | Steeper | Active (Pro features paywalled) |
| **Backtrader** | Moderate | Strong IB integration | Easiest | Community-maintained |
| **Zipline** | Slow (event-driven) | Limited | Moderate | Forks only (Zipline-reloaded) |
| **NautilusTrader** | Fast (Rust core) | Production-grade | Steep | Active development |

#### Option A: Use Existing Framework
**Pros:**
- Battle-tested, community support
- Built-in analytics and reporting
- Handles edge cases

**Cons:**
- May not match our Clean Architecture
- Learning curve for framework idioms
- Dependency on external maintenance

#### Option B: Build Custom Engine
**Pros:**
- Perfect fit with existing domain services
- Full control over simulation logic
- Matches our Clean Architecture
- Can leverage existing PaperBroker, SignalDetector, PositionMonitor

**Cons:**
- More development time
- Need to handle edge cases ourselves
- No community support

#### Recommendation: **Option B (Custom Engine)**

Rationale:
1. We already have 70% of the components built
2. Turtle rules are specific and well-defined
3. Our domain services are pure functions - easy to test
4. PaperBroker already simulates execution
5. Avoids framework lock-in

---

### Turtle Trading Specific Validation

From [QuantifiedStrategies](https://www.quantifiedstrategies.com/turtle-trading-strategy/) and [academic research](https://lbms03.cityu.edu.hk/oaps/ef2021-4001-ctl580.pdf):

#### Historical Benchmarks
- **1996-2006 (Curtis Faith backtest)**: All 6 turtle strategies performed "fantastically"
- **2001-2021 on Index ETFs (QQQ, SPY, DIA)**: ~40% win rate, 200%+ returns
- **Forex (20-year)**: 30%+ win rate, 100-600% returns, MDD ~30%

#### Known Characteristics
- Low win rate (35-45%) is normal for trend-following
- Large drawdowns (20-30%) are expected
- Profits come from few big winners
- Performance varies by market regime (trending vs. choppy)

#### Validation Criteria for Our Backtest
- [ ] Win rate in 35-45% range
- [ ] Max drawdown under 35%
- [ ] Profit factor > 1.2
- [ ] S1 filter reduces whipsaws vs. no filter
- [ ] Pyramiding increases returns (with higher volatility)
- [ ] 2N stops prevent catastrophic losses

---

## Part 2: Current State Analysis

### What We Have (Ready to Use)

```
✅ Domain Services (Pure Logic)
   ├── SignalDetector - S1/S2 breakout detection
   ├── PositionMonitor - Exits, pyramids, stops
   ├── Channels - Donchian 10/20/55
   ├── Volatility - N (ATR) calculation
   ├── Sizing - Unit calculation
   ├── LimitChecker - 4/6/12 limits
   └── S1Filter - Rule 7 implementation

✅ Data Feeds
   ├── YahooDataFeed - Historical bars (no IBKR needed!)
   └── CompositeDataFeed - Failover support

✅ Execution Simulation
   └── PaperBroker - Fills, commissions, slippage, P&L

✅ Models
   ├── Bar, DonchianChannel, NValue
   ├── Position (with pyramids)
   ├── Portfolio, Signal, Trade
   └── All frozen/immutable
```

### What We Need to Build

```
❌ Backtesting Engine
   ├── Day-by-day simulation loop
   ├── State management across days
   └── Event scheduling

❌ Results & Analytics
   ├── TradeRecord model
   ├── EquityCurve tracking
   ├── Performance metrics calculation
   └── Drawdown tracking

❌ Reporting
   ├── Summary statistics
   ├── Monthly/yearly breakdown
   └── Trade log export

❌ CLI Interface
   └── scripts/backtest.py
```

---

## Part 3: Design Decisions (To Discuss)

### Decision 1: Simulation Granularity

**Option A: Daily Bars Only**
- Simpler implementation
- Matches Turtle's original daily timeframe
- Yahoo data is reliable at daily level
- Faster backtests

**Option B: Intraday Bars**
- More realistic fill simulation
- Can model intraday stop hits
- More complex, more data needed
- IBKR historical data required

**Recommendation:** Start with Daily Bars (Option A)

---

### Decision 2: Data Source for Backtesting

**Option A: Yahoo Finance (Live Fetch)**
- Always current data
- No storage needed
- Rate limits may slow large backtests
- Network dependency

**Option B: Local Cache (CSV/Parquet)**
- Fast, repeatable backtests
- Works offline
- Need to build data pipeline
- Storage requirements

**Option C: Hybrid (Cache with Yahoo Fallback)**
- Best of both worlds
- Cache for speed, Yahoo for missing data

**Recommendation:** Start with Yahoo (Option A), add caching later

---

### Decision 3: Universe of Instruments

What symbols to include in 2024-2025 backtest?

**Core Micro Futures (Our Target):**
- MGC (Micro Gold)
- MNQ (Micro Nasdaq)
- MES (Micro S&P)
- MCL (Micro Crude)
- SIL (Micro Silver)

**Extended Universe (Optional):**
- M2K (Micro Russell)
- MYM (Micro Dow)
- 6E, 6J (Currency futures via ETF proxies?)

**Data Availability Check Needed:**
- [ ] Verify Yahoo has data for micro futures
- [ ] If not, use full-size contract data (ES, NQ, GC, CL, SI)
- [ ] Or use ETF proxies (GLD, QQQ, SPY, USO, SLV)

---

### Decision 4: Initial Equity & Position Sizing

**Realistic Micro Account:**
- Starting equity: $25,000 - $100,000
- Risk per unit: 0.5% of notional equity
- Allows testing of drawdown rule

**Scaled Test:**
- Starting equity: $1,000,000 (original Turtle scale)
- More positions possible
- Better statistical significance

**Recommendation:** Test both - $50K micro account AND $1M scaled

---

### Decision 5: What to Validate First

**Phase 1: Core Rules Only**
- S1 system entries/exits
- 2N stops
- No pyramiding
- No correlation limits
- Single instrument

**Phase 2: Full Rules**
- S1 + S2 systems
- Pyramiding with stop adjustment
- 4/6/12 unit limits
- Multi-instrument portfolio

**Recommendation:** Phase 1 first (simpler validation)

---

## Part 4: Proposed Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     BacktestRunner (CLI)                     │
│                    scripts/backtest.py                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     BacktestEngine                           │
│              src/adapters/backtesting/engine.py              │
│                                                              │
│  - run(config) → BacktestResult                              │
│  - iterate through date range                                │
│  - coordinate all components                                 │
└─────────────────────────────────────────────────────────────┘
          │              │              │              │
          ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  DataLoader  │ │ DaySimulator │ │   Tracker    │ │   Reporter   │
│              │ │              │ │              │ │              │
│ - fetch bars │ │ - run 1 day  │ │ - equity     │ │ - metrics    │
│ - cache      │ │ - signals    │ │ - positions  │ │ - charts     │
│ - validate   │ │ - execution  │ │ - trades     │ │ - export     │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
                        │
                        ▼
        ┌───────────────────────────────────┐
        │     Existing Domain Services       │
        │                                    │
        │  SignalDetector  PositionMonitor   │
        │  Channels        Volatility        │
        │  LimitChecker    S1Filter          │
        │  Sizing          PaperBroker       │
        └───────────────────────────────────┘
```

### New Files to Create

```
src/adapters/backtesting/
├── __init__.py
├── engine.py           # BacktestEngine - main orchestrator
├── data_loader.py      # HistoricalDataLoader - fetch & cache
├── day_simulator.py    # DaySimulator - single day logic
├── tracker.py          # StateTracker - equity, positions, trades
└── reporter.py         # BacktestReporter - metrics & output

src/domain/models/
├── backtest_config.py  # BacktestConfig model
└── backtest_result.py  # BacktestResult, TradeRecord models

scripts/
└── backtest.py         # CLI entry point

tests/backtest/
├── test_engine.py
├── test_data_loader.py
├── test_day_simulator.py
└── test_reporter.py
```

### Key Interfaces

```python
@dataclass
class BacktestConfig:
    start_date: date
    end_date: date
    symbols: list[str]
    initial_equity: Decimal
    risk_per_unit: Decimal = Decimal("0.005")  # 0.5%
    use_s2: bool = True
    use_pyramiding: bool = True
    use_correlation_limits: bool = True
    commission_per_contract: Decimal = Decimal("2.25")
    slippage_ticks: int = 1

@dataclass
class BacktestResult:
    config: BacktestConfig
    trades: list[TradeRecord]
    equity_curve: list[EquityPoint]
    metrics: PerformanceMetrics

@dataclass
class PerformanceMetrics:
    total_return_pct: Decimal
    annualized_return_pct: Decimal
    max_drawdown_pct: Decimal
    sharpe_ratio: Decimal
    win_rate: Decimal
    profit_factor: Decimal
    total_trades: int
    avg_trade_pnl: Decimal
    avg_winner: Decimal
    avg_loser: Decimal
    largest_winner: Decimal
    largest_loser: Decimal

@dataclass
class TradeRecord:
    symbol: str
    system: Literal["S1", "S2"]
    direction: Literal["LONG", "SHORT"]
    entry_date: date
    entry_price: Decimal
    exit_date: date
    exit_price: Decimal
    exit_reason: Literal["STOP", "BREAKOUT", "MANUAL"]
    units: int
    pyramid_levels: int
    gross_pnl: Decimal
    commission: Decimal
    net_pnl: Decimal
```

---

## Part 5: Implementation Phases

### Phase 1: Minimal Viable Backtest (MVP)
**Goal:** Single instrument, S1 only, no pyramiding

**Tasks:**
- [ ] Create `BacktestConfig` and `BacktestResult` models
- [ ] Implement `HistoricalDataLoader` (Yahoo fetch)
- [ ] Implement `DaySimulator` (basic day loop)
- [ ] Implement `BacktestEngine` (coordinate components)
- [ ] Create `scripts/backtest.py` CLI
- [ ] Test with single symbol (e.g., GLD ETF for gold)

**Validation:**
- Can run end-to-end on 2024 data
- Produces trade list and basic metrics
- Results are reproducible

**Estimated Effort:** 3-4 days

---

### Phase 2: Full Turtle Rules
**Goal:** All rules, single instrument

**Tasks:**
- [ ] Add S2 system support
- [ ] Implement pyramiding logic in simulation
- [ ] Add S1 filter (Rule 7 - skip if last winner)
- [ ] Track pyramid levels per position
- [ ] Adjust stops on pyramid (Rule 12)

**Validation:**
- S1 filter reduces trade count
- Pyramids trigger at +½N levels
- All stops move to 2N below newest entry

**Estimated Effort:** 2-3 days

---

### Phase 3: Multi-Instrument Portfolio
**Goal:** Full portfolio with position limits

**Tasks:**
- [ ] Multi-symbol simulation loop
- [ ] Integrate LimitChecker (4/6/12 limits)
- [ ] Add correlation groups
- [ ] Portfolio-level equity tracking
- [ ] Capital allocation across instruments

**Validation:**
- Position limits enforced correctly
- Capital allocated appropriately
- No over-concentration

**Estimated Effort:** 2-3 days

---

### Phase 4: Analytics & Reporting
**Goal:** Professional-grade output

**Tasks:**
- [ ] Calculate all performance metrics
- [ ] Generate equity curve chart
- [ ] Monthly/yearly breakdown tables
- [ ] Drawdown analysis
- [ ] Trade log export (CSV)
- [ ] Compare to benchmark (buy & hold)

**Validation:**
- Metrics match manual calculation
- Charts are readable
- Export works for external analysis

**Estimated Effort:** 2 days

---

### Phase 5: Walk-Forward Validation
**Goal:** Robust out-of-sample testing

**Tasks:**
- [ ] Split data: 2024 in-sample, 2025 out-of-sample
- [ ] Implement walk-forward framework
- [ ] Compare IS vs OOS performance
- [ ] Parameter sensitivity analysis

**Validation:**
- OOS performance within acceptable range of IS
- No signs of overfitting

**Estimated Effort:** 2-3 days

---

## Part 6: Open Questions

1. **Data for Micro Futures**: Does Yahoo have /MGC, /MNQ, etc.? Or do we need to use ETF proxies (GLD, QQQ)?

2. **Futures Roll Handling**: How do we handle contract expiration in backtest? Use continuous contracts? Back-adjusted data?

3. **Intraday Stops**: With daily bars, how do we simulate intraday stop hits? Use daily high/low?

4. **Position Sizing Edge Cases**: What if unit size < 1 contract? Skip trade or round up?

5. **Short Positions**: Original Turtles traded both sides. Do we include shorts in backtest?

6. **Benchmark Comparison**: What benchmark to compare against? Buy & hold index? Other trend-following systems?

---

## Part 7: Success Criteria

### Minimum Viable
- [ ] Backtest runs on 2024-2025 data without errors
- [ ] Produces reproducible results
- [ ] Trade log can be manually verified
- [ ] Basic metrics: return, drawdown, win rate

### Full Success
- [ ] All Turtle rules correctly implemented
- [ ] Multi-instrument portfolio simulation
- [ ] Performance within expected Turtle ranges (35-45% win rate, <35% MDD)
- [ ] Walk-forward validation shows no overfitting
- [ ] Results exportable for external analysis
- [ ] Documentation of methodology

---

## Next Steps

1. **Discuss this plan** - Review design decisions, answer open questions
2. **Verify data availability** - Check Yahoo/IBKR for required symbols
3. **Start Phase 1** - Build MVP backtest engine
4. **Validate on simple case** - Single symbol, known behavior
5. **Iterate** - Add features phase by phase

---

## References

- [QuantStart: Successful Backtesting Part I](https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-I/)
- [3Commas: 2025 Guide to Backtesting](https://3commas.io/blog/comprehensive-2025-guide-to-backtesting-ai-trading)
- [AutoTradeLab: Backtesting Framework Comparison](https://autotradelab.com/blog/backtrader-vs-nautilusttrader-vs-vectorbt-vs-zipline-reloaded)
- [QuantifiedStrategies: Turtle Trading Strategy](https://www.quantifiedstrategies.com/turtle-trading-strategy/)
- [Curtis Faith: Way of the Turtle](https://www.amazon.com/Way-Turtle-Methods-Ordinary-Legendary/dp/007148664X) (original source)
