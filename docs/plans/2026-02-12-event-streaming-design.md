# Event Streaming Architecture Design

**Date:** 2026-02-12
**Status:** Draft
**Purpose:** Capture every trading decision with full context for audit, replay, and debugging

## Design Principles

1. **Complete Audit Trail** - Know exactly what happened, when, and why
2. **Full State Capture** - Snapshot all relevant variables at decision time
3. **Causal Chain** - Link events to understand how we got here
4. **Immutable Log** - Events are append-only, never modified

---

## Event Types

### Scanner Events (Daily Run)

| Event Type | Description | When Logged |
|------------|-------------|-------------|
| `SCANNER_STARTED` | Scanner run begins | Start of daily_run.py |
| `SIGNAL_DETECTED` | Raw breakout found | Donchian breakout detected |
| `SIGNAL_EVALUATED` | Filters applied, decision made | After S1/limit checks |
| `ENTRY_ATTEMPTED` | Order submitted for new position | Order placed with broker |
| `ENTRY_FILLED` | Entry order filled | Fill confirmed |
| `SCANNER_COMPLETED` | Scanner run ends | End of daily_run.py |

### Monitor Events (Continuous)

| Event Type | Description | When Logged |
|------------|-------------|-------------|
| `MONITOR_STARTED` | Monitor cycle begins | Start of monitoring cycle |
| `POSITION_CHECKED` | Position evaluated against rules | Each position check |
| `EXIT_ATTEMPTED` | Exit order submitted | Stop hit or breakout exit |
| `EXIT_FILLED` | Exit order filled | Fill confirmed |
| `PYRAMID_ATTEMPTED` | Pyramid order submitted | +½N level reached |
| `PYRAMID_FILLED` | Pyramid order filled | Fill confirmed |
| `STOP_MODIFIED` | Stop price changed | After pyramid fill |
| `MONITOR_COMPLETED` | Monitor cycle ends | End of monitoring cycle |

### System Events

| Event Type | Description | When Logged |
|------------|-------------|-------------|
| `CONNECTION_LOST` | Broker connection dropped | IBKR disconnect detected |
| `CONNECTION_RESTORED` | Broker connection restored | IBKR reconnect success |
| `ERROR_OCCURRED` | Unexpected error | Exception caught |

---

## Outcome Types

Each event has an outcome indicating what happened:

### Signal Outcomes
```python
# SIGNAL_DETECTED outcomes
BREAKOUT_20 = "breakout_20"      # S1 20-day breakout
BREAKOUT_55 = "breakout_55"      # S2 55-day breakout (failsafe)
NO_BREAKOUT = "no_breakout"      # No signal

# SIGNAL_EVALUATED outcomes
APPROVED = "approved"            # Signal passed all filters
FILTERED_S1 = "filtered_s1"      # S1 skipped (last S1 was winner) - Rule 7
FILTERED_S2_REDUNDANT = "filtered_s2_redundant"  # S2 suppressed by S1 same direction
LIMIT_MARKET = "limit_market"    # 4 units max per market
LIMIT_CORRELATED = "limit_correlated"  # 6 units in correlated group
LIMIT_TOTAL = "limit_total"      # 12 units total (original mode)
LIMIT_RISK_CAP = "limit_risk_cap"  # 20% total risk (modern mode) - Rule 17
ALREADY_IN_POSITION = "already_in_position"  # Already have position
```

### Order Outcomes
```python
# *_ATTEMPTED outcomes
SUBMITTED = "submitted"          # Order sent to broker
INSUFFICIENT_CASH = "insufficient_cash"  # Not enough buying power
INSUFFICIENT_SHARES = "insufficient_shares"  # Can't borrow for short
REJECTED = "rejected"            # Broker rejected order
MARKET_CLOSED = "market_closed"  # Market not open

# *_FILLED outcomes
FILLED = "filled"                # Full fill
PARTIAL_FILL = "partial_fill"    # Partial fill (rare for our size)
CANCELLED = "cancelled"          # Order cancelled
EXPIRED = "expired"              # Order expired
```

### Position Check Outcomes
```python
# POSITION_CHECKED outcomes
HOLD = "hold"                    # No action needed
EXIT_STOP_TRIGGERED = "exit_stop_triggered"      # 2N stop hit
EXIT_BREAKOUT_TRIGGERED = "exit_breakout_triggered"  # 10/20-day exit
PYRAMID_TRIGGERED = "pyramid_triggered"  # +½N level reached
```

### System Outcomes
```python
# CONNECTION outcomes
RECONNECTED = "reconnected"      # Successfully reconnected
RECONNECT_FAILED = "reconnect_failed"  # Reconnect attempt failed

# ERROR outcomes
RECOVERED = "recovered"          # Error handled, continuing
FATAL = "fatal"                  # Unrecoverable, stopping
```

---

## Context Schemas

### The Five Questions (Must Be Answerable)

Every sizing/entry/pyramid event MUST capture enough context to answer:

| Question | Field | Example |
|----------|-------|---------|
| **1. Price** | `sizing.price` or `market.price` | 523.45 |
| **2. Volatility (N)** | `market.n.value` + `market.n.period` | 8.52 (20-day Wilder's ATR) |
| **3. Equity** | `account.equity_actual` + `account.equity_notional` | $50,000 (no drawdown reduction) |
| **4. System** | `signal.system` or `position.system` | S2 (55-day breakout) |
| **5. Risk** | `sizing.risk_percent` + `sizing.risk_dollars` | 0.5% = $250 per unit |

**Plus sizing outputs:**
- Contracts: `sizing.contracts` (29)
- Stop: `sizing.initial_stop` (540.49)
- Position value: `sizing.position_value` ($15,180)

**Replay test:** Given the five inputs, can you recalculate every output?

```
Unit Size = floor((Notional Equity × Risk%) / (N × Point Value))
         = floor((50000 × 0.005) / (8.52 × 1))
         = floor(250 / 8.52)
         = floor(29.34)
         = 29 contracts ✓

Stop = Entry Price + (Stop Multiplier × N)   [for SHORT]
     = 523.45 + (2 × 8.52)
     = 523.45 + 17.04
     = 540.49 ✓
```

---

### Common Context (All Events)

```python
{
    "run_id": "uuid",           # Links all events in a run
    "sequence": 1,              # Order within run
    "source": "scanner|monitor", # Which script
    "dry_run": false,           # Was this a dry run?
}
```

### Market Context

```python
{
    "market": {
        "symbol": "QQQ",

        # === PRICE DATA ===
        "price": 523.45,               # Current/close price
        "bid": 523.40,
        "ask": 523.50,
        "open": 522.00,
        "high": 525.00,
        "low": 521.50,
        "volume": 1234567,
        "bar_date": "2026-02-12",

        # === VOLATILITY (N) ===
        "n": {
            "value": 8.52,
            "date": "2026-02-12",
            "period": 20,              # ATR period
            "smoothing": "wilders",    # Wilder's smoothing
            "prev_n": 8.48,            # Previous N (for verification)
            "true_range": 9.32,        # Today's TR
            # Formula: ((19 × prev_n) + tr) / 20
            "calculation": "((19 × 8.48) + 9.32) / 20 = 8.52"
        },

        # === DONCHIAN CHANNELS ===
        "donchian": {
            "dc10": {"high": 530.00, "low": 510.00, "period": 10},
            "dc20": {"high": 540.00, "low": 500.00, "period": 20},
            "dc55": {"high": 550.00, "low": 480.00, "period": 55},
            "exclude_current_bar": true,  # Critical: excludes today
        },

        # === DATA SOURCE ===
        "source": "yahoo",             # yahoo, ibkr, composite
        "source_timestamp": "2026-02-12T16:00:00Z",
    }
}
```

### Position Context

```python
{
    "position": {
        "symbol": "QQQ",
        "direction": "SHORT",
        "system": "S2",

        # === ENTRY INFO ===
        "initial_entry_price": 525.00, # First entry price
        "initial_entry_date": "2026-02-04",
        "initial_n": 8.26,             # N at first entry

        # === CURRENT STATE ===
        "contracts": 26,
        "units": 1,
        "average_entry": 525.00,       # Weighted average if pyramided
        "position_value": 13650.00,    # current_price × contracts

        # === STOP (Rule 10) ===
        "current_stop": 541.52,
        "stop_distance": 16.52,        # 2N at most recent entry
        "stop_calculation": "525.00 + (2 × 8.26) = 541.52",

        # === P&L ===
        "current_price": 523.45,
        "unrealized_pnl": 40.30,       # (entry - current) × contracts [SHORT]
        "unrealized_pnl_percent": 0.3,
        "pnl_in_n": 0.19,              # P&L / (N × contracts)

        # === PYRAMID TRACKING ===
        "pyramid_levels": [
            {
                "level": 1,
                "entry_price": 525.00,
                "entry_date": "2026-02-04",
                "contracts": 26,
                "n_at_entry": 8.26
            }
        ],
        "max_pyramids": 4,             # Rule 13
        "can_pyramid": true,           # units < max_pyramids

        # === NEXT PYRAMID (Rule 11) ===
        "next_pyramid": {
            "level": 2,
            "trigger_price": 520.87,   # last_entry - (0.5 × n_at_last_entry) [SHORT]
            "trigger_calculation": "525.00 - (0.5 × 8.26) = 520.87",
            "distance_to_trigger": 2.58, # current_price - trigger [SHORT]
        },

        # === TIME IN TRADE ===
        "days_held": 8,
        "trading_days_held": 6,
    }
}
```

### Account Context

```python
{
    "account": {
        # === EQUITY ===
        "equity_actual": 50000.00,     # Real account value
        "equity_high_water": 55000.00, # Peak equity (for drawdown calc)
        "buying_power": 45000.00,      # Available for new positions

        # === DRAWDOWN RULE (Rule 5) ===
        "drawdown": {
            "current_percent": 9.1,    # (high_water - actual) / high_water
            "threshold_percent": 10.0, # Trigger level
            "reduction_percent": 20.0, # How much to reduce
            "triggered": false,        # Is drawdown rule active?
        },
        "equity_notional": 50000.00,   # Used for sizing (may be reduced)
        # If triggered: notional = actual × (1 - reduction_percent)

        # === POSITION LIMITS ===
        "limits": {
            "mode": "risk_cap",        # "risk_cap" (modern) or "original"
            "units_total": 3,
            "units_max": 12,           # Or 20% risk cap in modern mode
            "units_long": 2,
            "units_short": 1,
            "units_by_market": {
                "QQQ": 1,
                "XLE": 2,
            },
            "units_by_group": {
                "equity_index": 2,
                "energy": 1,
            },
        },

        # === MARGIN ===
        "margin_used": 5000.00,
        "margin_available": 45000.00,
    }
}
```

### Order Context

```python
{
    "order": {
        "order_id": "12345",
        "order_type": "MARKET",
        "action": "SELL",          # BUY or SELL
        "quantity": 26,
        "limit_price": null,       # For limit orders
        "submitted_at": "2026-02-12T14:30:00Z",
        "filled_at": "2026-02-12T14:30:01Z",
        "fill_price": 523.45,
        "expected_price": 523.40,  # Price when signal triggered
        "commission": 0.65,
        "slippage": 0.05,          # fill_price - expected_price

        # === RULE 16a: GAP OPEN HANDLING ===
        "gap": {
            "is_gap_open": false,      # Did market gap through our level?
            "gap_direction": null,     # "up" or "down"
            "previous_close": 521.00,
            "open_price": 523.50,
            "gap_size": 2.50,
            "gap_percent": 0.48,
            "signal_price": 522.00,    # Our breakout/stop level
            "gapped_through": false,   # Did open gap past signal_price?
            "executed_at_open": false, # Did we execute at market open?
        },

        # === RULE 16b: FAST MARKET HANDLING ===
        "fast_market": {
            "detected": false,         # Was fast market detected?
            "spread_at_signal": 0.05,  # Bid-ask spread when signal fired
            "spread_threshold": 0.50,  # Our threshold for "fast market"
            "spread_percent": 0.01,    # Spread as % of price
            "execution_delayed": false,# Did we delay execution?
            "delay_reason": null,      # Why we delayed
            "delay_duration_sec": 0,   # How long we waited
            "stabilization_price": null, # Price after stabilization
        },
    }
}
```

### Signal Context

```python
{
    "signal": {
        "direction": "SHORT",
        "system": "S2",                # S1 or S2
        "trigger_price": 500.00,       # Donchian level that triggered
        "signal_price": 499.50,        # Price when signal detected
        "channel_period": 55,          # 20 for S1, 55 for S2
        "correlation_group": "equity_index",  # For limit checking (Rule 17)

        # === BREAKOUT DETAILS ===
        "breakout": {
            "type": "low",             # "high" (long) or "low" (short)
            "channel_value": 500.00,   # The 55-day low
            "channel_start_date": "2025-12-01",  # When channel period started
            "bars_since_breakout": 0,  # 0 = just broke out
        },
    }
}
```

### Filter Context (SIGNAL_EVALUATED)

```python
{
    "filters": {
        # === RULE 7: S1 FILTER ===
        "s1_filter": {
            "applied": true,           # Only applies to S1 signals
            "system": "S1",
            "last_s1_trade": {
                "symbol": "QQQ",
                "direction": "LONG",
                "entry_date": "2025-12-01",
                "exit_date": "2026-01-15",
                "entry_price": 500.00,
                "exit_price": 525.00,
                "result": "winner",    # "winner" or "loser" (2N stop hit)
                "pnl": 1250.00,
                "pnl_in_n": 1.5,       # How many N it moved
            },
            "passed": false,
            "reason": "Last S1 trade was winner, skipping per Rule 7"
        },

        # === POSITION LIMITS ===
        "limit_market": {              # Max 4 units per market
            "symbol": "QQQ",
            "current": 0,
            "max": 4,
            "passed": true
        },
        "limit_correlated": {          # Max 6 units in correlated group
            "group": "equity_index",
            "symbols_in_group": ["SPY", "QQQ", "IWM"],
            "current": 2,
            "max": 6,
            "passed": true
        },
        "limit_total": {               # Mode-dependent total limit
            "mode": "risk_cap",        # "risk_cap" or "unit_count"
            # Unit count mode (original):
            "current_units": 3,
            "max_units": 12,
            # Risk cap mode (modern - Rule 17):
            "current_risk_percent": 1.5,  # 3 units × 0.5%
            "max_risk_percent": 20.0,
            "passed": true,
            "reason": "Within 20% risk cap (1.5% current + 0.5% new = 2.0%)"
        },

        # === SUMMARY ===
        "all_passed": false,
        "blocking_filter": "s1_filter",
        "evaluation_order": ["s1_filter", "limit_market", "limit_correlated", "limit_total"]
    }
}
```

### Sizing Context (ENTRY_ATTEMPTED)

This context must contain ALL inputs needed to replay the calculation.

```python
{
    "sizing": {
        # === INPUTS (The Five Questions) ===
        "price": 523.45,               # Expected entry price (for sizing)
        "n_value": 8.52,               # ATR/volatility
        "equity_actual": 50000.00,     # Actual account equity
        "equity_notional": 50000.00,   # Notional (may differ due to Rule 5)
        "system": "S2",                # S1 or S2
        "direction": "SHORT",

        # === RULE PARAMETERS (from TurtleRules) ===
        "risk_percent": 0.005,         # 0.5% per unit (Parker rule)
        "stop_multiplier": 2.0,        # 2N stop distance
        "point_value": 1.0,            # 1 for stocks, varies for futures
        "atr_period": 20,              # N calculation period

        # === INTERMEDIATE CALCULATIONS ===
        "risk_dollars": 250.00,        # equity_notional × risk_percent
        "dollar_volatility": 8.52,     # n_value × point_value
        "raw_unit_size": 29.34,        # risk_dollars / dollar_volatility
        "stop_distance": 17.04,        # n_value × stop_multiplier

        # === OUTPUTS ===
        "contracts": 29,               # floor(raw_unit_size)
        "position_value": 15180.05,    # price × contracts
        "initial_stop": 540.49,        # price + stop_distance (for SHORT)
        "risk_per_contract": 17.04,    # stop_distance × point_value

        # === VERIFICATION (for replay) ===
        "formula": "contracts = floor((equity_notional × risk_percent) / (n_value × point_value))",
        "calculation": "floor((50000 × 0.005) / (8.52 × 1)) = floor(29.34) = 29"
    }
}
```

**Replay verification:** Anyone reading this event can plug the inputs into the formula and get the same outputs.

### Exit Context (EXIT_ATTEMPTED, EXIT_FILLED)

```python
{
    "exit": {
        # === WHY ARE WE EXITING? ===
        "reason": "stop_hit",          # stop_hit, breakout_exit
        "rule": "Rule 10: 2N stop",    # Which turtle rule triggered

        # === TRIGGER DETAILS ===
        "trigger_type": "stop",        # stop, donchian_10, donchian_20
        "trigger_price": 541.52,       # Stop level or channel level
        "current_price": 542.00,       # Price when exit triggered
        "breach_amount": 0.48,         # How far past trigger

        # === POSITION AT EXIT ===
        "direction": "SHORT",
        "contracts": 26,
        "units": 1,
        "entry_price": 525.00,         # Average entry
        "entry_date": "2026-02-04",

        # === P&L CALCULATION ===
        "pnl": {
            "expected_price": 541.52,  # Trigger price
            "fill_price": 542.10,      # Actual fill
            "slippage": 0.58,          # fill - expected (cost for SHORT)
            "gross_pnl": -444.60,      # (entry - fill) × contracts × direction
            "commission": 0.65,
            "net_pnl": -445.25,
            "pnl_percent": -3.4,       # net_pnl / position_value
            "pnl_in_n": -2.07,         # net_pnl / (n × contracts) - "R-multiple"
            "calculation": "(525.00 - 542.10) × 26 = -444.60"
        },

        # === TRADE STATISTICS ===
        "hold_duration_days": 8,
        "max_favorable_excursion": 50.00,   # Best unrealized P&L
        "max_adverse_excursion": -500.00,   # Worst unrealized P&L
        "exit_efficiency": 0.89,            # How much of MFE we captured
    }
}
```

### Pyramid Context (PYRAMID_ATTEMPTED, PYRAMID_FILLED)

```python
{
    "pyramid": {
        # === TRIGGER CALCULATION ===
        "level": 2,                    # Which pyramid (2, 3, or 4)
        "direction": "LONG",
        "last_entry_price": 50.25,     # Previous pyramid entry
        "n_at_last_entry": 1.24,       # N when last entry was made
        "pyramid_interval": 0.5,       # ½N interval (Rule 11)
        "trigger_price": 50.87,        # last_entry + (0.5 × n_at_last)
        "current_price": 50.90,
        "trigger_calculation": "50.25 + (0.5 × 1.24) = 50.87",

        # === SIZING (same formula as entry) ===
        "n_current": 1.26,             # Current N for new unit
        "equity_notional": 50000.00,
        "risk_percent": 0.005,
        "new_contracts": 198,          # Additional contracts this pyramid
        "contracts_before": 243,
        "contracts_after": 441,        # Total after pyramid
        "units_after": 2,
        "max_units": 4,                # Rule 13: max 4 per market

        # === STOP ADJUSTMENT (Rule 12) ===
        "stop_before": 47.77,          # 2N from original entry
        "new_entry_price": 50.90,      # Fill price for pyramid
        "n_at_new_entry": 1.26,        # N at pyramid fill
        "stop_after": 48.38,           # new_entry - (2 × n_at_new_entry)
        "stop_calculation": "50.90 - (2 × 1.26) = 48.38",
        "stop_moved_by": 0.61,         # stop_after - stop_before
    }
}
```

---

## Example Event Sequences

### Successful Entry Flow

```
1. SCANNER_STARTED
   context: {run_id: "abc", symbols: ["SPY", "QQQ", "IWM", ...]}

2. SIGNAL_DETECTED
   symbol: QQQ, outcome: BREAKOUT_55
   context: {market: {...}, signal: {direction: SHORT, system: S2, trigger: 500.00}}

3. SIGNAL_EVALUATED
   symbol: QQQ, outcome: APPROVED
   context: {market: {...}, account: {...}, filters: {all passed}}

4. ENTRY_ATTEMPTED
   symbol: QQQ, outcome: SUBMITTED
   context: {market: {...}, account: {...}, order: {...}, sizing: {...}}

5. ENTRY_FILLED
   symbol: QQQ, outcome: FILLED
   context: {market: {...}, order: {fill_price: 499.50}, position: {...}}

6. SCANNER_COMPLETED
   context: {run_id: "abc", signals_found: 1, positions_opened: 1, duration_sec: 45}
```

### Filtered Signal Flow

```
1. SCANNER_STARTED

2. SIGNAL_DETECTED
   symbol: SPY, outcome: BREAKOUT_20

3. SIGNAL_EVALUATED
   symbol: SPY, outcome: FILTERED_S1
   context: {filters: {s1_filter: {passed: false, reason: "Last S1 was winner"}}}

4. SCANNER_COMPLETED
```

### Stop Hit Exit Flow

```
1. MONITOR_STARTED
   context: {run_id: "xyz", positions: ["QQQ", "XLE"]}

2. POSITION_CHECKED
   symbol: QQQ, outcome: EXIT_STOP_TRIGGERED
   context: {market: {price: 542.00}, position: {stop: 541.52}, exit: {reason: "stop_hit"}}

3. EXIT_ATTEMPTED
   symbol: QQQ, outcome: SUBMITTED
   context: {order: {action: "BUY", quantity: 26}}  # Buy to cover short

4. EXIT_FILLED
   symbol: QQQ, outcome: FILLED
   context: {order: {fill_price: 542.10}, exit: {realized_pnl: -455.00}}

5. POSITION_CHECKED
   symbol: XLE, outcome: HOLD
   context: {market: {...}, position: {...}}

6. MONITOR_COMPLETED
   context: {positions_checked: 2, exits: 1, pyramids: 0}
```

### Pyramid Flow

```
1. MONITOR_STARTED

2. POSITION_CHECKED
   symbol: XLE, outcome: PYRAMID_TRIGGERED
   context: {market: {price: 52.50}, position: {next_pyramid: 52.38}}

3. PYRAMID_ATTEMPTED
   symbol: XLE, outcome: SUBMITTED
   context: {pyramid: {level: 2, new_contracts: 240}, sizing: {...}}

4. PYRAMID_FILLED
   symbol: XLE, outcome: FILLED
   context: {pyramid: {fill_price: 52.52, total_contracts: 483}}

5. STOP_MODIFIED
   symbol: XLE, outcome: EXECUTED
   context: {pyramid: {old_stop: 50.75, new_stop: 51.25}}

6. MONITOR_COMPLETED
```

### Insufficient Cash Flow

```
1. POSITION_CHECKED
   symbol: XLE, outcome: PYRAMID_TRIGGERED

2. PYRAMID_ATTEMPTED
   symbol: XLE, outcome: INSUFFICIENT_CASH
   context: {
       account: {buying_power: 2000.00},
       sizing: {position_value: 12500.00},
       reason: "Buying power $2,000 < required $12,500"
   }

3. MONITOR_COMPLETED
```

---

## Database Schema

```sql
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Event classification
    event_type VARCHAR(50) NOT NULL,
    outcome VARCHAR(50) NOT NULL,
    outcome_reason TEXT,           -- Human-readable explanation

    -- Identifiers
    run_id UUID NOT NULL,          -- Links events in same run
    sequence INTEGER NOT NULL,     -- Order within run
    symbol VARCHAR(20),            -- NULL for system events

    -- Full context snapshot
    context JSONB NOT NULL,

    -- Denormalized for common queries
    source VARCHAR(20) NOT NULL,   -- 'scanner' or 'monitor'
    dry_run BOOLEAN DEFAULT FALSE,

    -- Indexes
    CONSTRAINT events_run_sequence UNIQUE (run_id, sequence)
);

-- Indexes for common queries
CREATE INDEX idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX idx_events_symbol ON events(symbol, timestamp DESC);
CREATE INDEX idx_events_type ON events(event_type, timestamp DESC);
CREATE INDEX idx_events_run ON events(run_id, sequence);
CREATE INDEX idx_events_outcome ON events(outcome) WHERE outcome != 'hold';
```

---

## Python Models

```python
from enum import Enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """All possible event types in the trading system."""

    # Scanner events
    SCANNER_STARTED = "scanner_started"
    SIGNAL_DETECTED = "signal_detected"
    SIGNAL_EVALUATED = "signal_evaluated"
    ENTRY_ATTEMPTED = "entry_attempted"
    ENTRY_FILLED = "entry_filled"
    SCANNER_COMPLETED = "scanner_completed"

    # Monitor events
    MONITOR_STARTED = "monitor_started"
    POSITION_CHECKED = "position_checked"
    EXIT_ATTEMPTED = "exit_attempted"
    EXIT_FILLED = "exit_filled"
    PYRAMID_ATTEMPTED = "pyramid_attempted"
    PYRAMID_FILLED = "pyramid_filled"
    STOP_MODIFIED = "stop_modified"
    MONITOR_COMPLETED = "monitor_completed"

    # System events
    CONNECTION_LOST = "connection_lost"
    CONNECTION_RESTORED = "connection_restored"
    ERROR_OCCURRED = "error_occurred"


class OutcomeType(str, Enum):
    """All possible outcomes for events."""

    # Signal detection
    BREAKOUT_20 = "breakout_20"      # S1 20-day breakout (Rule 6)
    BREAKOUT_55 = "breakout_55"      # S2 55-day breakout (Rule 8)
    NO_BREAKOUT = "no_breakout"

    # Signal evaluation
    APPROVED = "approved"
    FILTERED_S1 = "filtered_s1"      # Rule 7: last S1 was winner
    FILTERED_S2_REDUNDANT = "filtered_s2_redundant"  # S2 suppressed by S1
    LIMIT_MARKET = "limit_market"    # 4 units per market
    LIMIT_CORRELATED = "limit_correlated"  # 6 units in group
    LIMIT_TOTAL = "limit_total"      # 12 units (original mode)
    LIMIT_RISK_CAP = "limit_risk_cap"  # 20% risk cap (Rule 17)
    ALREADY_IN_POSITION = "already_in_position"

    # Order submission
    SUBMITTED = "submitted"
    INSUFFICIENT_CASH = "insufficient_cash"
    INSUFFICIENT_SHARES = "insufficient_shares"
    REJECTED = "rejected"
    MARKET_CLOSED = "market_closed"
    DELAYED_FAST_MARKET = "delayed_fast_market"  # Rule 16b

    # Order fills
    FILLED = "filled"
    FILLED_AT_GAP = "filled_at_gap"  # Rule 16a: executed at gap open
    PARTIAL_FILL = "partial_fill"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

    # Position checks
    HOLD = "hold"
    EXIT_STOP_TRIGGERED = "exit_stop_triggered"      # Rule 10: 2N stop
    EXIT_BREAKOUT_TRIGGERED = "exit_breakout_triggered"  # Rule 13/14
    PYRAMID_TRIGGERED = "pyramid_triggered"          # Rule 11

    # Stop modifications
    EXECUTED = "executed"            # Rule 12: stops moved
    FAILED = "failed"

    # System
    RECONNECTED = "reconnected"
    RECONNECT_FAILED = "reconnect_failed"
    RECOVERED = "recovered"
    FATAL = "fatal"


class Event(BaseModel):
    """An immutable event record capturing a trading decision."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Classification
    event_type: EventType
    outcome: OutcomeType
    outcome_reason: str | None = None

    # Identifiers
    run_id: UUID
    sequence: int
    symbol: str | None = None

    # Full state snapshot
    context: dict = Field(default_factory=dict)

    # Metadata
    source: str  # "scanner" or "monitor"
    dry_run: bool = False
```

---

## Query Examples

```sql
-- What happened to QQQ today?
SELECT timestamp, event_type, outcome, outcome_reason
FROM events
WHERE symbol = 'QQQ'
  AND timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp;

-- Why did we exit this position?
SELECT e.*, e.context->'exit' as exit_details
FROM events e
WHERE symbol = 'QQQ'
  AND event_type IN ('position_checked', 'exit_attempted', 'exit_filled')
  AND timestamp > '2026-02-10'
ORDER BY timestamp;

-- All rejected/failed entries this week
SELECT timestamp, symbol, outcome, outcome_reason,
       context->'account'->'buying_power' as buying_power,
       context->'sizing'->'position_value' as required
FROM events
WHERE event_type = 'entry_attempted'
  AND outcome NOT IN ('submitted', 'filled')
  AND timestamp > NOW() - INTERVAL '7 days';

-- Pyramid success rate
SELECT outcome, COUNT(*),
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
FROM events
WHERE event_type = 'pyramid_attempted'
GROUP BY outcome;

-- Full audit trail for a specific run
SELECT sequence, event_type, symbol, outcome, outcome_reason
FROM events
WHERE run_id = 'abc-123'
ORDER BY sequence;

-- Market state when we entered QQQ
SELECT context->'market' as market_state,
       context->'sizing' as sizing_calc,
       context->'account' as account_state
FROM events
WHERE symbol = 'QQQ'
  AND event_type = 'entry_filled'
ORDER BY timestamp DESC
LIMIT 1;
```

---

## Implementation Notes

### Event Logger Interface

```python
class EventLogger:
    """Logs trading events with full context capture."""

    def __init__(self, repo: EventRepository):
        self._repo = repo
        self._run_id: UUID | None = None
        self._sequence: int = 0
        self._source: str = ""

    def start_run(self, source: str) -> UUID:
        """Start a new run, returns run_id."""
        self._run_id = uuid4()
        self._sequence = 0
        self._source = source
        return self._run_id

    async def log(
        self,
        event_type: EventType,
        outcome: OutcomeType,
        symbol: str | None = None,
        outcome_reason: str | None = None,
        context: dict | None = None,
        dry_run: bool = False,
    ) -> Event:
        """Log an event with auto-incrementing sequence."""
        self._sequence += 1
        event = Event(
            event_type=event_type,
            outcome=outcome,
            outcome_reason=outcome_reason,
            run_id=self._run_id,
            sequence=self._sequence,
            symbol=symbol,
            context=context or {},
            source=self._source,
            dry_run=dry_run,
        )
        await self._repo.save(event)
        return event
```

### Context Builders

```python
def build_market_context(symbol: str, bars: list[Bar], n_value: NValue) -> dict:
    """Build market context from current data."""
    ...

def build_position_context(position: Position) -> dict:
    """Build position context from Position model."""
    ...

def build_account_context(account: Account, portfolio: Portfolio) -> dict:
    """Build account context from current state."""
    ...
```

---

## Migration from Alerts

The existing `alerts` table serves a different purpose (user notifications) and should remain.

Events are for **system audit** (what happened, full detail).
Alerts are for **user notification** (important events, summarized).

Events table will be the source of truth; alerts can be derived from events.

---

## Rules Cross-Reference

Every Turtle Trading rule must be traceable in the event stream.

| Rule | Description | Where Captured | Verification |
|------|-------------|----------------|--------------|
| **Rule 3** | N = 20-day Wilder's ATR | `market.n` | period=20, smoothing="wilders", calculation string |
| **Rule 4** | Unit sizing formula | `sizing` | All inputs explicit, formula shown |
| **Rule 5** | 10% drawdown → 20% reduction | `account.drawdown` | threshold, reduction, triggered flag |
| **Rule 6** | S1 = 20-day breakout | `signal` | system="S1", channel_period=20 |
| **Rule 7** | S1 filter (skip if winner) | `filters.s1_filter` | last_trade details, passed/reason |
| **Rule 8** | S2 = 55-day breakout | `signal` | system="S2", channel_period=55 |
| **Rule 9** | S2 failsafe | Event sequence | FILTERED_S1 → later BREAKOUT_55 |
| **Rule 10** | 2N hard stop | `sizing`, `position` | stop_multiplier=2, calculation string |
| **Rule 11** | Pyramid at +½N | `pyramid` | interval=0.5, trigger_calculation |
| **Rule 12** | Move ALL stops on pyramid | `STOP_MODIFIED` event | stop_before, stop_after, all positions |
| **Rule 13** | S1 exit = 10-day | `exit` | trigger_type="donchian_10" |
| **Rule 14** | S2 exit = 20-day | `exit` | trigger_type="donchian_20" |
| **Rule 15** | Futures rollover | N/A | Stocks only |
| **Rule 16a** | Gap open execution | `order.gap` | is_gap_open, executed_at_open |
| **Rule 16b** | Fast market delay | `order.fast_market` | detected, execution_delayed |
| **Rule 17** | 20% portfolio risk cap | `account.limits` | mode="risk_cap", current/max risk |

### Audit Queries by Rule

```sql
-- Rule 5: When was drawdown reduction triggered?
SELECT timestamp, context->'account'->'drawdown' as drawdown
FROM events
WHERE (context->'account'->'drawdown'->>'triggered')::boolean = true
ORDER BY timestamp;

-- Rule 7: All S1 signals that were filtered
SELECT timestamp, symbol, outcome_reason,
       context->'filters'->'s1_filter'->'last_s1_trade' as last_trade
FROM events
WHERE event_type = 'signal_evaluated'
  AND outcome = 'filtered_s1';

-- Rule 11: All pyramid triggers
SELECT timestamp, symbol,
       context->'pyramid'->>'level' as level,
       context->'pyramid'->>'trigger_calculation' as calculation
FROM events
WHERE event_type = 'pyramid_attempted';

-- Rule 16a: All gap open executions
SELECT timestamp, symbol,
       context->'order'->'gap'->>'gap_percent' as gap_pct,
       context->'order'->>'fill_price' as fill
FROM events
WHERE (context->'order'->'gap'->>'executed_at_open')::boolean = true;

-- Rule 17: Risk cap violations
SELECT timestamp, symbol, outcome_reason,
       context->'filters'->'limit_total' as limit_details
FROM events
WHERE outcome = 'limit_risk_cap';
```
