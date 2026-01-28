# Backtesting Infrastructure Plan

**Created:** 2026-01-28
**Status:** Planning
**Target:** Backtest Turtle Trading Bot on 2024-2025 data

---

## Executive Summary

Build backtesting infrastructure to validate the Turtle Trading Bot against historical data before live deployment. Goal: run simulations on 2024-2025 market data across a **228-market universe** (Jerry Parker diversified approach) and validate against known Turtle Trading performance characteristics.

---

## Confirmed Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Data Source** | Yahoo Finance (primary) | Simple, free, no IBKR needed for backtest |
| **Universe Size** | 228 markets (full database) | Jerry Parker diversified approach |
| **Short Positions** | Yes, both long and short | Original Turtle rules |
| **Starting Equity** | **Configurable** (default $50K) | Test with $10K, $50K, $200K, etc. |
| **Systems** | S1 + S2 (full system) | No point testing partial rules |
| **Pyramiding** | Yes | Core Turtle rule |
| **Position Limits** | 4/6/12 units | Full rule enforcement |

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

### Decision 3: Universe of Instruments ✅ DECIDED

**Full 228-Market Universe** (from `004_seed_full_universe.sql`):

| Asset Class | Count | Examples |
|-------------|-------|----------|
| **Full-Size Futures** | 58 | /ES, /GC, /CL, /ZC, /6E |
| **Micro Futures** | 24 | /MES, /MGC, /MCL, /M6E |
| **ETFs** | 41 | SPY, GLD, TLT, XLE |
| **Stocks** | 105 | AAPL, NVDA, XOM, JPM |
| **Total** | **228** | |

**Correlation Groups** (for 6-unit limit):
- `equity_us`, `equity_us_tech`, `equity_us_small`
- `metals_precious`, `metals_industrial`
- `energy_oil`, `energy_gas`, `energy_refined`
- `grains_feed`, `grains_oilseed`, `grains_wheat`
- `currency_eur`, `currency_jpy`, `currency_gbp`, etc.
- `rates_long`, `rates_mid`, `rates_short`
- `softs`, `livestock`, `dairy`, `crypto`

**Data Considerations for 228 Markets:**
- Yahoo Finance has good coverage for ETFs and stocks
- Futures use full-size contract symbols (ES=F, GC=F, CL=F)
- Micro futures → fall back to full-size Yahoo data (same price, different sizing)
- ~500 trading days (2024-2025) × 228 symbols = ~114,000 bar fetches
- Need caching strategy for performance

---

### Decision 4: Initial Equity & Position Sizing ✅ DECIDED

**Configurable Starting Equity** - run multiple backtests with different sizes:

| Account Size | Risk per Unit (0.5%) | Use Case |
|--------------|----------------------|----------|
| $10,000 | $50 | Minimum viable micro account |
| $50,000 | $250 | **Default** - realistic micro trader |
| $100,000 | $500 | Larger retail account |
| $200,000 | $1,000 | Semi-professional |
| $1,000,000 | $5,000 | Original Turtle scale |

**Position sizing formula:**
- Unit size = Risk per Unit / (N × Point Value)
- Example at $50K: $250 / ($2 × $5) = 25 contracts of /MES

**Why test multiple sizes:**
- $10K may have too few tradeable markets (size < 1 contract issues)
- $50K is realistic for most users
- $200K+ shows scaling behavior
- Compare results across equity levels

**Drawdown Rule Testing:**
- 10% DD → Notional equity drops by 20%
- Example at $50K: $5K loss → notional becomes $40K

---

### Decision 5: What to Validate ✅ DECIDED

**Full System from Day 1** - no phased approach

Test everything together:
- S1 + S2 systems (both entries)
- Long AND short positions
- Pyramiding with stop adjustment (Rules 11-12)
- 4/6/12 unit limits
- 228-market portfolio
- Drawdown rule (Rule 5)

Rationale: Testing partial rules doesn't validate the real system behavior. Interactions between rules matter.

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

### Phase 1: Data Infrastructure
**Goal:** Reliable historical data for 228 markets

**Tasks:**
- [ ] Extend `SymbolMapper` to handle all 228 symbols → Yahoo format
- [ ] Implement `HistoricalDataLoader` with caching (avoid re-fetching)
- [ ] Handle futures symbol mapping (micro → full-size for Yahoo)
- [ ] Validate data quality (no gaps, correct OHLC)
- [ ] Build data cache (~114K bars for 2024-2025)

**Considerations:**
- Yahoo rate limits: may need throttling or batch fetching
- Cache format: SQLite or Parquet for fast reads
- Handle stock splits, dividends in ETF/stock data

**Estimated Effort:** 2-3 days

---

### Phase 2: Backtesting Engine Core
**Goal:** Day-by-day simulation with full Turtle rules

**Tasks:**
- [ ] Create `BacktestConfig` and `BacktestResult` models
- [ ] Implement `BacktestEngine` main loop
- [ ] Implement `DaySimulator`:
  - Calculate N values for all 228 markets
  - Calculate Donchian channels (10/20/55)
  - Detect S1/S2 signals (both long and short)
  - Apply S1 filter (Rule 7)
  - Check position limits (4/6/12)
  - Execute entries via PaperBroker
- [ ] Implement position monitoring:
  - Check stops (2N)
  - Check breakout exits (10/20-day)
  - Check pyramid opportunities (+½N)
  - Move stops on pyramid (Rule 12)
- [ ] Track equity curve and drawdown
- [ ] Implement drawdown rule (Rule 5: 10% → 20% reduction)

**Key Integration Points:**
```
Existing services to use:
├── SignalDetector.detect_s1_signal()
├── SignalDetector.detect_s2_signal()
├── PositionMonitor.check_position()
├── LimitChecker.can_add_position()
├── S1Filter.should_take_trade()
├── UnitCalculator.calculate_unit_size()
├── PaperBroker.place_bracket_order()
└── PaperBroker.modify_stop()
```

**Estimated Effort:** 4-5 days

---

### Phase 3: Results & Analytics
**Goal:** Professional-grade output and analysis

**Tasks:**
- [ ] Implement `TradeRecord` model with full trade details
- [ ] Calculate performance metrics:
  - Total return, annualized return
  - Max drawdown, average drawdown
  - Sharpe ratio, Sortino ratio
  - Win rate, profit factor
  - Average winner/loser, largest winner/loser
  - Expectancy
- [ ] Generate equity curve data
- [ ] Monthly/yearly breakdown tables
- [ ] Trade log export (CSV)
- [ ] Breakdown by:
  - Asset class (futures vs ETF vs stocks)
  - System (S1 vs S2)
  - Direction (long vs short)
  - Correlation group

**Estimated Effort:** 2-3 days

---

### Phase 4: CLI & Automation
**Goal:** Easy-to-run backtest command

**Tasks:**
- [ ] Create `scripts/backtest.py` with argparse
- [ ] Support command-line options:
  ```
  --start DATE        Start date (default: 2024-01-01)
  --end DATE          End date (default: 2025-12-31)
  --equity AMOUNT     Starting equity (default: 50000)
  --universe TYPE     all|futures|etf|stock (default: all)
  --output FILE       Results output file
  --verbose           Show progress
  ```
- [ ] Progress bar for long backtests
- [ ] Save results to JSON/CSV
- [ ] Generate summary report

**Example Usage:**
```bash
# Full 2024-2025 backtest
python scripts/backtest.py --start 2024-01-01 --end 2025-12-31 --equity 50000

# Futures only
python scripts/backtest.py --universe futures --output results/futures_2024.json

# Quick test on ETFs
python scripts/backtest.py --universe etf --start 2024-01-01 --end 2024-06-30
```

**Estimated Effort:** 1-2 days

---

### Phase 5: Validation & Analysis
**Goal:** Verify results make sense

**Tasks:**
- [ ] Spot-check individual trades manually
- [ ] Compare metrics to historical Turtle benchmarks
- [ ] Run 2024 in-sample, 2025 out-of-sample comparison
- [ ] Analyze by market regime (trending vs. choppy periods)
- [ ] Identify best/worst performing asset classes
- [ ] Document any anomalies or unexpected results

**Expected Results (based on historical Turtle performance):**
- Win rate: 35-45%
- Max drawdown: 20-35%
- Profit factor: > 1.2
- Most profits from few big winners

**Estimated Effort:** 2-3 days

---

### Total Estimated Effort: 11-16 days

---

## Part 6: Open Questions

### Resolved ✅

| Question | Resolution |
|----------|------------|
| Short positions? | Yes, include both long and short |
| Starting equity? | **Configurable** ($10K, $50K, $200K, etc.) |
| Which systems? | S1 + S2 (full system) |
| Universe size? | Full 228 markets |
| Data source? | Yahoo Finance primary, IBKR as fallback |
| Intraday stops? | Use daily H/L to check stop triggers |
| Benchmark? | SPY buy & hold |

### Still Open ❓

1. **Futures Data Source** ✅ RESOLVED:
   - Yahoo Finance has futures data (e.g., `GC=F` for gold, `ES=F` for S&P)
   - IBKR data feed CAN work but requires TWS running and has rate limits
   - **Decision:** Use Yahoo for simplicity; IBKR available as fallback if needed
   - Need to verify: Run `yfinance.download("GC=F", period="2y")` for all 58 futures

2. **Futures Roll Handling** ⏳ TO VERIFY:
   - Yahoo provides continuous front-month data (auto-rolls)
   - Question: Does this cause price jumps that affect stop calculations?
   - **Action:** Check Yahoo data around roll dates for /ES, /GC to see if there are gaps
   - If problematic, may need back-adjusted data from IBKR

3. **Intraday Stop Simulation** ✅ RESOLVED:
   - **Problem:** With daily bars, a stop might be hit intraday but we only see OHLC
   - **Example:** Long at $100, stop at $98. Day's range: Open $101, High $102, Low $97, Close $100
     - Reality: Stop at $98 was hit (Low went to $97)
     - Naive backtest using Close: Would miss this stop hit
   - **Solution:** Check daily Low (for longs) or High (for shorts) against stop price
   - This is more realistic and avoids overly optimistic results

4. **Position Sizing Edge Cases** ❓ ASK EXPERT:
   - What if calculated unit size < 1 contract?
   - Options:
     - a) Skip the trade (not enough equity for this market)
     - b) Round up to 1 (violates risk rules but takes the trade)

   **🔮 Question for Turtle Expert:**
   > "In the original Turtle system, what happened when calculated position size was less than 1 contract? Did the Turtles skip that market, round up to 1 contract, or handle it another way? What did Richard Dennis or the rules specify for minimum position sizes?"

5. **Benchmark Comparison** ✅ RESOLVED:
   - Primary: Buy & hold SPY
   - Secondary: SG Trend Index (if available)
   - This allows comparing to both passive investing and professional trend followers

6. **Signal Priority When Capital Limited** ❓ ASK EXPERT:
   - If multiple signals fire on same day but capital only allows some trades:
   - How to prioritize?

   **🔮 Question for Turtle Expert:**
   > "When multiple entry signals occurred on the same day and the Turtles couldn't take all of them due to position limits or capital constraints, how did they prioritize? Did the original rules specify a method - random selection, strongest breakout, volatility-adjusted ranking, or some other approach? What did Curtis Faith or Jerry Parker describe as the standard practice?"

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
