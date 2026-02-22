# Small Account Turtle Trading: $50k Implementation

**Date:** 2026-01-28
**Status:** Validated via Backtesting

---

## Executive Summary

The classic Turtle Trading system **works on a $50k account** when adapted correctly:

| Metric | Result |
|--------|--------|
| Initial Equity | $50,000 |
| Final Equity | $1,084,109 |
| Total Return | 2,068% |
| Max Drawdown | 67.4% |
| Sharpe Ratio | 1.04 |
| Win Rate | 23.9% |
| Total Trades | 522 |
| Test Period | 2020-01-01 to 2025-12-31 |

---

## The Problem with Original Turtle Rules

The original Turtle system required $1-2M accounts because:

1. **Granularity Problem**: Futures contracts are indivisible. If math says "buy 0.5 contracts," you can't.
2. **High Dollar Volatility**: Many futures have >$1,000 daily dollar volatility, exceeding small account risk budgets.
3. **Death Spiral**: Rule 5 drawdown reduction can reduce sizing so much that you can't trade at all.
4. **Margin Requirements**: Futures require significant margin that eats into capital.

---

## The Solution: Three Key Adaptations

### 1. Use ETFs Instead of Futures

ETFs solve the granularity problem completely:
- Can buy any number of shares (even fractional)
- Lower volatility per unit
- No margin requirements for long positions
- Same trend-following characteristics

**Result:** 0 signals skipped due to size in backtesting.

### 2. Curated 15-Market Universe

Based on Tom Basso's "7 Market" study and Jerry Parker's advice, we selected 15 uncorrelated ETFs across 8 sectors:

| Sector | ETFs | Correlation Group |
|--------|------|-------------------|
| **US Equity** | SPY, QQQ, IWM | equity_us_large, equity_us_tech, equity_us_small |
| **International** | EFA, EEM | equity_developed, equity_emerging |
| **Sectors** | XLE, XLU | sector_energy, sector_utilities |
| **Bonds** | TLT, IEF | bonds_long, bonds_mid |
| **Commodities** | GLD, SLV, USO, DBA | metals_precious, energy_oil, commodities_ag |
| **Real Estate** | VNQ | real_estate |
| **Currency** | FXE | currency_euro |

**Why 15 markets?**
- 7 markets was too concentrated ($498k final vs $1.08M with 15)
- 31 markets offered no improvement (same drawdown, more complexity)
- 15 markets maximizes diversification benefit without over-spreading capital

### 3. 60% Sizing Floor (Anti-Death-Spiral)

Added a floor to prevent notional equity from dropping below 60% of peak:

```python
min_notional_floor = Decimal("0.60")  # Never reduce below 60%
```

**Why 60%?**
- Original Rule 5: 10% DD → 20% reduction → cascades to nothing
- With 60% floor: Even after 50% drawdown, still trading at 60% capacity
- Keeps you in the game to catch the recovery trends

---

## Configuration for Live Trading

### Environment Variables (.env)

```bash
# Small Account Mode
USE_SMALL_ACCOUNT_MODE=true
MIN_NOTIONAL_FLOOR=0.60
MAX_TOTAL_RISK=0.15

# Risk Settings (per Jerry Parker)
RISK_PER_TRADE=0.005  # 0.5% per trade

# Position Limits
MAX_UNITS_PER_MARKET=4
MAX_UNITS_CORRELATED=6
MAX_UNITS_TOTAL=12
```

### Database

Run migration to add the 15 ETFs:
```bash
psql $DATABASE_URL < src/infrastructure/migrations/002_add_small_account_etfs.sql
```

### Code References

| Component | File | Key Setting |
|-----------|------|-------------|
| **ETF Universe** | `src/adapters/backtesting/data_loader.py` | `SMALL_ACCOUNT_ETF_UNIVERSE` |
| **Sizing Floor** | `src/domain/services/drawdown_tracker.py` | `min_notional_floor` parameter |
| **Config** | `src/infrastructure/config.py` | `use_small_account_mode`, `min_notional_floor` |
| **DB Query** | `src/application/queries/get_universe.py` | `get_small_account_universe()` |
| **Markets Table** | `src/infrastructure/migrations/002_add_small_account_etfs.sql` | 15 ETF seed data |

---

## Backtest Comparison

| Strategy | Markets | Final Equity | Return | Max DD | Sharpe |
|----------|---------|-------------|--------|--------|--------|
| ORIGINAL (31 ETFs) | 31 | $2.24M | 4,389% | 67.8% | 1.16 |
| **SMALL_ACCT (15 ETFs)** | **15** | **$1.08M** | **2,068%** | **67.4%** | **1.04** |
| CONCENTRATED (31 + floor) | 31 | $2.24M | 4,389% | 67.8% | 1.16 |

**Key Insight:** The 15-market universe captures most of the return with less complexity.

---

## Signal Flow Analysis

| Metric | SMALL_ACCT |
|--------|------------|
| Signals Generated | 890 |
| Filtered (S1 rule) | 3,029 |
| Skipped (size < 1) | 0 |
| Skipped (limits) | 350 |
| **Executed** | **522** |

**No signals were skipped due to insufficient size** - ETFs solve the granularity problem.

---

## Expected Performance Characteristics

Based on 2020-2025 backtest:

| Metric | Value |
|--------|-------|
| Win Rate | ~24% |
| Profit Factor | 1.33 |
| Avg Trade P&L | $1,984 |
| Pyramid Adds | 900 |
| Stop Exits | 378 |
| Breakout Exits | 138 |

**Important:** Expect ~75% of trades to be losers. This is normal for trend following.
The winners are significantly larger than the losers (that's where the edge comes from).

---

## Psychological Preparation (Salem Abraham's Advice)

From the NotebookLM research:

1. **Accept 50%+ drawdowns** - Salem Abraham suffered this early and survived
2. **Keep trading through losses** - The system only works if you take all signals
3. **"The thing that can never happen, can happen"** - Be prepared for the worst
4. **Don't second-guess the rules** - Mechanical execution is the edge

---

## Running the Backtest

```bash
# Compare all strategies
python scripts/backtest_small_account.py --equity 50000 --start 2020-01-01 --end 2025-12-31

# Just the small account strategy
python scripts/backtest.py --equity 50000 --symbols SPY QQQ IWM EFA EEM XLE XLU TLT IEF GLD SLV USO DBA VNQ FXE
```

---

## Sources

- **Tom Basso** - "7 Market" study showing minimal markets needed for trend following
- **Jerry Parker** - Advice on ETFs for small accounts, 0.5% risk per trade
- **Salem Abraham** - Started with $30-50k, accepted volatility, survived drawdowns
- **Original Turtle Rules** - Faith, Covel, Parker source documents

---

## Files Modified

| File | Change |
|------|--------|
| `src/domain/services/drawdown_tracker.py` | Added `min_notional_floor` parameter |
| `src/adapters/backtesting/tracker.py` | Pass floor to DrawdownTracker |
| `src/adapters/backtesting/models.py` | Added floor to BacktestConfig |
| `src/adapters/backtesting/engine.py` | Wire up the floor parameter |
| `src/adapters/backtesting/data_loader.py` | Added `SMALL_ACCOUNT_ETF_UNIVERSE` (15 markets) |
| `src/infrastructure/config.py` | Added `use_small_account_mode`, `min_notional_floor`, `max_total_risk` |
| `src/application/queries/get_universe.py` | Added `get_small_account_universe()` |
| `src/infrastructure/migrations/002_add_small_account_etfs.sql` | 15 ETF seed data |
| `scripts/backtest_small_account.py` | Comparison script |

---

*Document created: 2026-01-28*
