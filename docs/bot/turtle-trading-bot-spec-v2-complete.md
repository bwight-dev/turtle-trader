# Turtle Trading Bot System Specification v2

> **Note:** This is a compiled document. For the most up-to-date specifications, refer to the individual doc files:
> - `01-overview-and-domain.md` - System overview and domain model
> - `02-pydantic-models.md` - All data models
> - `03-position-monitor.md` - Position monitoring module
> - `04-module-implementations.md` - Module code specifications
> - `05-implementation-and-reference.md` - Phases, structure, quick reference
> - `06-data-sources.md` - **IBKR (primary) + Yahoo Finance (backup) integration**

---

## Data Source Architecture (Updated)

**Primary:** Interactive Brokers (TWS/Gateway on Mac Mini, port 7497)
- Paper Trading Account: DUP318628
- Real-time prices and historical bars
- Order execution

**Backup:** Yahoo Finance (automatic failover)
- Used when IBKR is unavailable
- Free, reliable for daily bars

See `06-data-sources.md` for complete implementation details.

---

## Part 1: Overview and Domain Model

---

## 1. System Overview

### 1.1 Vision

Build a fully mechanical trading system that:
- Executes Turtle Trading rules without discretionary intervention
- Scales from paper trading → live micro futures → managed accounts
- Provides AI assistance for rule clarification and decision validation
- Maintains auditable trade records for future CTA registration

### 1.2 Core Principles

| Principle | Implementation |
|-----------|---------------|
| **Price Only** | No fundamental data, news, or external signals |
| **Mechanical Execution** | Zero discretion once rules are defined |
| **Volatility-Based Sizing** | N (ATR) drives all position calculations |
| **Let Winners Run** | No profit targets; exit only on opposite breakout (S1=10-day, S2=20-day) or hard stop |
| **Cut Losses** | Hard 2N stops, no exceptions |

### 1.3 Modern Adaptations (Parker Rules)

| Original 1983 | Modern 2025 | Rationale |
|---------------|-------------|-----------|
| ~20 commodities | 300+ markets | Capture rare outliers |
| 20/55-day breakouts | 55-200 day emphasis | Reduce whipsaws |
| 1-2% risk/trade | 0.25-0.5% risk/trade | Support larger universe |
| 12 unit limit | Portfolio heat cap | Dynamic risk management |

---

## 2. Domain Model

### 2.1 Ubiquitous Language

```
Market          := Tradeable instrument (futures, ETF, stock)
N (Volatility)  := 20-day ATR (Wilders smoothing)
Unit            := Position sized to risk X% of equity at 2N stop
Signal          := Breakout event (S1=20-day, S2=55-day)
Filter          := S1 skip rule (last S1 was winner)
Pyramid         := Adding units at +1N intervals
Stop            := Hard exit at 2N from entry (moves only on pyramid)
Breakout Exit   := Exit on opposite N-day breakout (S1=10-day, S2=20-day)
Correlation     := Market grouping for unit limits
Heat            := Total portfolio risk exposure
```

### 2.2 Core Aggregates

```
┌─────────────────────────────────────────────────────────────┐
│                        AGGREGATES                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  Portfolio  │    │   Market    │    │    Trade    │     │
│  │  (Root)     │    │  (Root)     │    │   (Root)    │     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘     │
│         │                  │                  │             │
│    ┌────┴────┐        ┌────┴────┐        ┌────┴────┐       │
│    │Position │        │  OHLCV  │        │  Entry  │       │
│    │Pyramid  │        │   Bar   │        │  Exit   │       │
│    │  Level  │        │    N    │        │ Pyramid │       │
│    │  Stop   │        │ Signal  │        │  Level  │       │
│    └─────────┘        │Donchian │        └─────────┘       │
│                       └─────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Bounded Contexts

```
┌──────────────────────────────────────────────────────────────────────┐
│                          TURTLE TRADING SYSTEM                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                │
│  │   MARKET    │   │  STRATEGY   │   │  PORTFOLIO  │                │
│  │   DATA      │──▶│   ENGINE    │──▶│  MANAGER    │                │
│  │             │   │             │   │             │                │
│  └─────────────┘   └─────────────┘   └──────┬──────┘                │
│        │                 │                  │                        │
│        │                 │           ┌──────┴──────┐                 │
│        │                 │           │  POSITION   │                 │
│        │                 │           │  MONITOR    │ ◀── KEY MODULE │
│        │                 │           └──────┬──────┘                 │
│        ▼                 ▼                  ▼                        │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                │
│  │   AI        │   │  EXECUTION  │   │   AUDIT     │                │
│  │  ADVISOR    │◀─▶│   GATEWAY   │──▶│   LOG       │                │
│  │             │   │             │   │             │                │
│  └─────────────┘   └─────────────┘   └─────────────┘                │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

#### Context Responsibilities

| Context | Responsibility |
|---------|---------------|
| **Market Data** | Ingest, normalize, serve price data; calculate N and Donchian |
| **Strategy Engine** | Generate entry signals, apply S1 filter |
| **Portfolio Manager** | Track positions, units, enforce limits |
| **Position Monitor** | **Monitor open positions for pyramids, exits, stops** |
| **Execution Gateway** | Interface with broker APIs |
| **AI Advisor** | Rule clarification, decision validation |
| **Audit Log** | Immutable trade history for compliance |
# Turtle Trading Bot - Part 2: Pydantic Models

## Core Enums and Base Types

```python
# turtle_core/models/enums.py
from enum import Enum

class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class System(str, Enum):
    S1 = "S1"  # 20-day breakout, 10-day exit
    S2 = "S2"  # 55-day breakout, 20-day exit

class PositionAction(str, Enum):
    HOLD = "HOLD"
    PYRAMID = "PYRAMID"
    EXIT_BREAKOUT = "EXIT_BREAKOUT"
    EXIT_STOP = "EXIT_STOP"

class ExitReason(str, Enum):
    STOP_HIT = "STOP_HIT"
    BREAKOUT_EXIT = "BREAKOUT_EXIT"
    MANUAL = "MANUAL"
    ROLLOVER = "ROLLOVER"

class CorrelationGroup(str, Enum):
    RATES_LONG = "RATES_LONG"
    RATES_MID = "RATES_MID"
    RATES_SHORT = "RATES_SHORT"
    CURRENCY_EUR = "CURRENCY_EUR"
    CURRENCY_GBP = "CURRENCY_GBP"
    CURRENCY_JPY = "CURRENCY_JPY"
    CURRENCY_CHF = "CURRENCY_CHF"
    CURRENCY_CAD = "CURRENCY_CAD"
    CURRENCY_AUD = "CURRENCY_AUD"
    METALS_PRECIOUS = "METALS_PRECIOUS"
    METALS_INDUSTRIAL = "METALS_INDUSTRIAL"
    ENERGY_OIL = "ENERGY_OIL"
    ENERGY_REFINED = "ENERGY_REFINED"
    ENERGY_GAS = "ENERGY_GAS"
    EQUITY_US = "EQUITY_US"
    EQUITY_TECH = "EQUITY_TECH"
    EQUITY_SMALL = "EQUITY_SMALL"
    GRAINS_FEED = "GRAINS_FEED"
    GRAINS_OILSEED = "GRAINS_OILSEED"
    GRAINS_WHEAT = "GRAINS_WHEAT"
    SOFTS = "SOFTS"
    LIVESTOCK = "LIVESTOCK"
    CRYPTO = "CRYPTO"
```

## Market Data Models

```python
# turtle_core/models/market.py
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from datetime import datetime, date
from typing import Literal

class NValue(BaseModel):
    """Volatility measure - 20-day ATR with Wilders smoothing"""
    value: Decimal = Field(..., gt=0, description="ATR value in price units")
    calculated_at: datetime
    period: int = Field(default=20)
    method: Literal["WILDERS", "SMA"] = "WILDERS"
    
    def to_dollars(self, point_value: Decimal) -> Decimal:
        """Convert N to dollar risk"""
        return self.value * point_value
    
    model_config = {"frozen": True}


class DonchianChannel(BaseModel):
    """N-day high/low channel"""
    upper: Decimal = Field(..., description="Highest high over period")
    lower: Decimal = Field(..., description="Lowest low over period")
    period: int
    calculated_at: datetime
    
    model_config = {"frozen": True}


class Bar(BaseModel):
    """OHLCV price bar"""
    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = 0
    
    @field_validator('high')
    @classmethod
    def high_gte_low(cls, v, info):
        if 'low' in info.data and v < info.data['low']:
            raise ValueError('high must be >= low')
        return v


class MarketSpec(BaseModel):
    """Market specification and metadata"""
    symbol: str = Field(..., description="Trading symbol (e.g., /MGC, /M2K)")
    name: str
    point_value: Decimal = Field(..., gt=0)
    tick_size: Decimal = Field(..., gt=0)
    correlation_group: CorrelationGroup
    exchange: str
    contract_month: str | None = None
    is_micro: bool = False
    full_size_equivalent: str | None = None
    
    model_config = {"frozen": True}


class MarketData(BaseModel):
    """Complete market state for trading decisions"""
    spec: MarketSpec
    current_price: Decimal
    n_value: NValue
    donchian_10: DonchianChannel  # For S1 exits
    donchian_20: DonchianChannel  # For S1 entries, S2 exits
    donchian_55: DonchianChannel  # For S2 entries
    bars: list[Bar] = Field(default_factory=list, exclude=True)
    updated_at: datetime
```

## Signal Models

```python
# turtle_core/models/signals.py
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime

class Signal(BaseModel):
    """Breakout signal"""
    symbol: str
    system: System
    direction: Direction
    breakout_price: Decimal
    triggered_at: datetime
    donchian_period: int
    
    model_config = {"frozen": True}


class FilterResult(BaseModel):
    """S1 filter decision"""
    take_signal: bool
    reason: str
    last_s1_trade_id: str | None = None
    last_s1_was_winner: bool | None = None


class SignalWithFilter(BaseModel):
    """Signal after filter application"""
    signal: Signal
    filter_result: FilterResult
    should_trade: bool = Field(..., description="Final decision after filter")
```

## Position Sizing Models

```python
# turtle_core/models/sizing.py
from pydantic import BaseModel, Field
from decimal import Decimal

class UnitSize(BaseModel):
    """Calculated position size for one unit"""
    contracts: int = Field(..., ge=0)
    risk_per_unit: Decimal
    equity_at_calculation: Decimal
    n_value_used: Decimal
    point_value: Decimal
    risk_pct_used: Decimal
    
    @property
    def is_tradeable(self) -> bool:
        return self.contracts > 0
    
    model_config = {"frozen": True}


class StopLevel(BaseModel):
    """Hard stop price calculation"""
    price: Decimal
    n_at_entry: Decimal
    entry_price: Decimal
    direction: Direction
    
    model_config = {"frozen": True}
```

## Position Models

```python
# turtle_core/models/positions.py
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime

class PyramidLevel(BaseModel):
    """Individual pyramid entry within a position"""
    unit_number: int = Field(..., ge=1, le=4)
    entry_price: Decimal
    entry_timestamp: datetime
    n_at_entry: Decimal
    contracts: int = Field(..., ge=1)
    original_stop: Decimal = Field(..., description="2N stop at time of this entry")
    
    model_config = {"frozen": True}


class Position(BaseModel):
    """Open position with full pyramid tracking"""
    id: str = Field(..., description="Unique position identifier")
    symbol: str
    direction: Direction
    system: System
    correlation_group: CorrelationGroup
    point_value: Decimal
    
    # Pyramid tracking
    pyramid_levels: list[PyramidLevel] = Field(default_factory=list)
    
    # Current state - this is the key field that changes
    current_stop: Decimal = Field(..., description="2N below most recent entry")
    opened_at: datetime
    
    @property
    def total_units(self) -> int:
        return len(self.pyramid_levels)
    
    @property
    def total_contracts(self) -> int:
        return sum(p.contracts for p in self.pyramid_levels)
    
    @property
    def average_entry(self) -> Decimal:
        if not self.pyramid_levels:
            return Decimal("0")
        total_value = sum(p.entry_price * p.contracts for p in self.pyramid_levels)
        return total_value / self.total_contracts
    
    @property
    def latest_entry(self) -> PyramidLevel | None:
        return self.pyramid_levels[-1] if self.pyramid_levels else None
    
    @property
    def next_pyramid_trigger(self) -> Decimal | None:
        """Price level to add next unit (+1N from last entry)"""
        if not self.can_pyramid or not self.latest_entry:
            return None
        
        n = self.latest_entry.n_at_entry
        if self.direction == Direction.LONG:
            return self.latest_entry.entry_price + n
        return self.latest_entry.entry_price - n
    
    @property
    def can_pyramid(self) -> bool:
        return self.total_units < 4  # Max per market
    
    def calculate_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Calculate open P&L"""
        if self.direction == Direction.LONG:
            price_diff = current_price - self.average_entry
        else:
            price_diff = self.average_entry - current_price
        
        return price_diff * self.total_contracts * self.point_value
```

## Portfolio Model

```python
# turtle_core/models/portfolio.py
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime

class Portfolio(BaseModel):
    """Complete portfolio state"""
    id: str
    equity: Decimal = Field(..., gt=0)
    peak_equity: Decimal = Field(..., gt=0)
    cash_balance: Decimal
    
    positions: dict[str, Position] = Field(default_factory=dict)
    
    # Settings
    risk_per_trade: Decimal = Field(default=Decimal("0.02"))
    max_units_per_market: int = Field(default=4)
    max_units_correlated: int = Field(default=6)
    max_units_total: int = Field(default=12)
    
    updated_at: datetime
    
    @property
    def total_units(self) -> int:
        return sum(p.total_units for p in self.positions.values())
    
    @property
    def drawdown(self) -> Decimal:
        if self.peak_equity == 0:
            return Decimal("0")
        return (self.peak_equity - self.equity) / self.peak_equity
    
    @property
    def drawdown_pct(self) -> Decimal:
        return self.drawdown * 100
    
    def get_adjusted_equity(self) -> Decimal:
        """
        Apply drawdown reduction rule:
        Every 10% drawdown → reduce notional equity by 20%
        """
        reductions = int(self.drawdown / Decimal("0.10"))
        adjustment = Decimal("1") - (reductions * Decimal("0.20"))
        return self.equity * max(adjustment, Decimal("0.40"))
    
    def units_in_correlation_group(self, group: CorrelationGroup) -> int:
        return sum(
            p.total_units for p in self.positions.values()
            if p.correlation_group == group
        )
    
    def get_open_positions(self) -> list[Position]:
        return list(self.positions.values())
```

## Monitoring Models (For Pyramids/Exits)

```python
# turtle_core/models/monitoring.py
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from typing import Literal

class PositionCheck(BaseModel):
    """Result of checking a single position"""
    position_id: str
    symbol: str
    action: PositionAction
    current_price: Decimal
    
    # Context for the action
    stop_price: Decimal | None = None
    pyramid_trigger: Decimal | None = None
    exit_trigger: Decimal | None = None
    
    reason: str
    checked_at: datetime


class PyramidOpportunity(BaseModel):
    """Detected pyramid opportunity"""
    position_id: str
    symbol: str
    direction: Direction
    current_unit_count: int
    trigger_price: Decimal
    current_price: Decimal
    
    # New unit details
    new_n_value: Decimal
    new_contracts: int
    new_stop_price: Decimal  # 2N below new entry - applies to ALL units
    
    # Limit check
    within_limits: bool
    limit_reason: str | None = None


class ExitSignal(BaseModel):
    """Detected exit condition"""
    position_id: str
    symbol: str
    exit_type: Literal["STOP", "BREAKOUT"]
    trigger_price: Decimal
    current_price: Decimal
    
    # Position details for closing
    direction: Direction
    total_contracts: int
    estimated_pnl: Decimal
    
    reason: str
    detected_at: datetime


class MonitoringResult(BaseModel):
    """Complete result of monitoring cycle"""
    cycle_timestamp: datetime
    positions_checked: int
    
    holds: list[PositionCheck] = Field(default_factory=list)
    pyramid_opportunities: list[PyramidOpportunity] = Field(default_factory=list)
    exit_signals: list[ExitSignal] = Field(default_factory=list)
    
    @property
    def has_actions(self) -> bool:
        return bool(self.pyramid_opportunities or self.exit_signals)
```

## Order Models

```python
# turtle_core/models/orders.py
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from typing import Literal

class BracketOrder(BaseModel):
    """Entry order with attached stop"""
    symbol: str
    direction: Direction
    quantity: int = Field(..., gt=0)
    entry_type: Literal["MARKET", "LIMIT", "STOP"] = "MARKET"
    entry_price: Decimal | None = None  # None for market orders
    stop_price: Decimal
    time_in_force: Literal["DAY", "GTC"] = "GTC"
    
    # Metadata
    system: System
    unit_number: int
    n_at_entry: Decimal


class OrderFill(BaseModel):
    """Execution confirmation"""
    order_id: str
    symbol: str
    direction: Direction
    quantity: int
    fill_price: Decimal
    filled_at: datetime
    commission: Decimal = Decimal("0")


class StopModification(BaseModel):
    """Stop price update (after pyramid)"""
    position_id: str
    old_stop: Decimal
    new_stop: Decimal
    reason: str
    modified_at: datetime
```

## Trade Record Model (Audit)

```python
# turtle_core/models/trades.py
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime

class Trade(BaseModel):
    """Completed trade record for audit"""
    id: str
    symbol: str
    direction: Direction
    system: System
    
    # Entry details
    entry_date: datetime
    entry_price: Decimal
    n_at_entry: Decimal
    initial_stop: Decimal
    initial_units: int
    initial_contracts: int
    
    # Pyramid history
    pyramid_levels: list[PyramidLevel] = Field(default_factory=list)
    max_units: int = 1
    max_contracts: int = 1
    
    # Exit details
    exit_date: datetime | None = None
    exit_price: Decimal | None = None
    exit_reason: ExitReason | None = None
    final_stop: Decimal | None = None
    
    # P&L
    realized_pnl: Decimal | None = None
    commission_total: Decimal = Decimal("0")
    net_pnl: Decimal | None = None
    
    @property
    def was_winner(self) -> bool | None:
        """For S1 filter - was this trade profitable?"""
        if self.net_pnl is None:
            return None
        return self.net_pnl > 0
    
    @property
    def was_2n_loss(self) -> bool | None:
        """Did trade hit the 2N stop?"""
        return self.exit_reason == ExitReason.STOP_HIT
```

## Limit Check Models

```python
# turtle_core/models/limits.py
from pydantic import BaseModel

class LimitCheckResult(BaseModel):
    """Result of checking unit limits"""
    allowed: bool
    
    # Individual checks
    total_units_ok: bool
    total_units_current: int
    total_units_max: int
    
    per_market_ok: bool
    per_market_current: int
    per_market_max: int
    
    correlation_ok: bool
    correlation_group: CorrelationGroup
    correlation_current: int
    correlation_max: int
    
    # If not allowed, why
    denial_reason: str | None = None
```

## Rules Configuration

```python
# turtle_core/rules.py
from decimal import Decimal
from pydantic import BaseModel

class TurtleRules(BaseModel):
    """
    Immutable Turtle Trading rules
    """
    
    # Risk management
    risk_per_trade: Decimal = Decimal("0.02")           # 2% original
    risk_per_trade_modern: Decimal = Decimal("0.005")   # 0.5% Parker
    stop_multiplier: int = 2                             # 2N stop
    
    # Pyramiding
    pyramid_interval_n: int = 1                          # Add at +1N
    max_units_per_market: int = 4
    max_units_correlated: int = 6
    max_units_total: int = 12
    
    # Entry signals (Donchian periods)
    s1_entry_days: int = 20
    s1_exit_days: int = 10
    s2_entry_days: int = 55
    s2_exit_days: int = 20
    
    # N calculation
    atr_period: int = 20
    atr_method: str = "WILDERS"
    
    # Drawdown management
    drawdown_reduction_threshold: Decimal = Decimal("0.10")
    drawdown_equity_reduction: Decimal = Decimal("0.20")
    
    model_config = {"frozen": True}


# Default rules instance
RULES = TurtleRules()
```
# Turtle Trading Bot - Part 3: Position Monitor

## Overview

The Position Monitor is responsible for **continuously monitoring open positions** for:
1. **Stop hits** - Price touches 2N stop → immediate exit
2. **Breakout exits** - Price touches 10-day (S1) or 20-day (S2) opposite breakout → exit
3. **Pyramid triggers** - Price reaches +1N from last entry → add unit if within limits

This is the module you identified was missing from v1.

---

## Position Monitor Service

```python
# portfolio/monitor/position_monitor.py
from decimal import Decimal
from datetime import datetime
from turtle_core.models import (
    Position, PositionAction, PositionCheck, Direction, System,
    DonchianChannel, MarketData, PyramidOpportunity, ExitSignal,
    MonitoringResult, NValue, LimitCheckResult,
)
from turtle_core.rules import RULES
from portfolio.limits.checker import LimitChecker
from portfolio.sizing.calculator import calculate_unit_size
from portfolio.sizing.stop_calculator import calculate_stop


class PositionMonitor:
    """
    Continuous monitoring of open positions.
    
    Check order (priority):
    1. Stop hit → EXIT_STOP (capital preservation first)
    2. Breakout exit → EXIT_BREAKOUT
    3. Pyramid trigger → PYRAMID
    4. None → HOLD
    """
    
    def __init__(self, limit_checker: LimitChecker):
        self.limit_checker = limit_checker
    
    def check_position(
        self,
        position: Position,
        market: MarketData,
    ) -> PositionCheck:
        """
        Check single position for required actions.
        """
        current_price = market.current_price
        now = datetime.now()
        
        # 1. CHECK STOP (highest priority - capital preservation)
        if self._is_stop_hit(position, current_price):
            return PositionCheck(
                position_id=position.id,
                symbol=position.symbol,
                action=PositionAction.EXIT_STOP,
                current_price=current_price,
                stop_price=position.current_stop,
                reason=f"Stop hit: price {current_price} crossed stop {position.current_stop}",
                checked_at=now,
            )
        
        # 2. CHECK BREAKOUT EXIT
        exit_channel = self._get_exit_channel(position, market)
        if self._is_breakout_exit(position, current_price, exit_channel):
            exit_price = (
                exit_channel.lower if position.direction == Direction.LONG 
                else exit_channel.upper
            )
            return PositionCheck(
                position_id=position.id,
                symbol=position.symbol,
                action=PositionAction.EXIT_BREAKOUT,
                current_price=current_price,
                exit_trigger=exit_price,
                reason=f"Breakout exit: price {current_price} crossed {exit_channel.period}-day {'low' if position.direction == Direction.LONG else 'high'} at {exit_price}",
                checked_at=now,
            )
        
        # 3. CHECK PYRAMID OPPORTUNITY
        if self._is_pyramid_triggered(position, current_price):
            return PositionCheck(
                position_id=position.id,
                symbol=position.symbol,
                action=PositionAction.PYRAMID,
                current_price=current_price,
                pyramid_trigger=position.next_pyramid_trigger,
                stop_price=position.current_stop,
                reason=f"Pyramid trigger: price {current_price} reached +1N level {position.next_pyramid_trigger}",
                checked_at=now,
            )
        
        # 4. NO ACTION NEEDED
        return PositionCheck(
            position_id=position.id,
            symbol=position.symbol,
            action=PositionAction.HOLD,
            current_price=current_price,
            stop_price=position.current_stop,
            pyramid_trigger=position.next_pyramid_trigger,
            reason="No action required - monitoring continues",
            checked_at=now,
        )
    
    def _is_stop_hit(self, position: Position, price: Decimal) -> bool:
        """
        Check if price has hit the 2N stop.
        
        LONG: price <= stop (price fell to stop)
        SHORT: price >= stop (price rose to stop)
        """
        if position.direction == Direction.LONG:
            return price <= position.current_stop
        return price >= position.current_stop
    
    def _get_exit_channel(
        self, 
        position: Position, 
        market: MarketData
    ) -> DonchianChannel:
        """
        Get appropriate exit channel based on system.
        
        S1 → 10-day breakout exit
        S2 → 20-day breakout exit
        """
        if position.system == System.S1:
            return market.donchian_10
        return market.donchian_20
    
    def _is_breakout_exit(
        self,
        position: Position,
        price: Decimal,
        exit_channel: DonchianChannel,
    ) -> bool:
        """
        Check for breakout exit.
        
        S1 long exits on 10-day low
        S1 short exits on 10-day high
        S2 long exits on 20-day low
        S2 short exits on 20-day high
        """
        if position.direction == Direction.LONG:
            return price <= exit_channel.lower
        return price >= exit_channel.upper
    
    def _is_pyramid_triggered(self, position: Position, price: Decimal) -> bool:
        """
        Check if price has reached +1N from last entry.
        
        Can only pyramid if:
        - Position has < 4 units
        - Price has moved +1N in favorable direction
        """
        if not position.can_pyramid:
            return False
        
        trigger = position.next_pyramid_trigger
        if trigger is None:
            return False
        
        if position.direction == Direction.LONG:
            return price >= trigger
        return price <= trigger
    
    def build_pyramid_opportunity(
        self,
        position: Position,
        market: MarketData,
        portfolio_equity: Decimal,
        portfolio,  # Full portfolio for limit check
    ) -> PyramidOpportunity:
        """
        Build complete pyramid opportunity with:
        - New unit sizing
        - New stop price (applies to ALL units)
        - Limit check result
        """
        # Calculate new unit size with CURRENT N value
        unit_size = calculate_unit_size(
            equity=portfolio_equity,
            n_value=market.n_value,
            point_value=position.point_value,
        )
        
        # Calculate new stop (2N below CURRENT price)
        # CRITICAL: This stop applies to ALL existing units too
        new_stop = calculate_stop(
            entry_price=market.current_price,
            n_value=market.n_value,
            direction=position.direction,
        )
        
        # Check all limits
        limit_result = self.limit_checker.can_add_position(
            portfolio=portfolio,
            symbol=position.symbol,
            units_to_add=1,
            correlation_group=position.correlation_group,
        )
        
        return PyramidOpportunity(
            position_id=position.id,
            symbol=position.symbol,
            direction=position.direction,
            current_unit_count=position.total_units,
            trigger_price=position.next_pyramid_trigger,
            current_price=market.current_price,
            new_n_value=market.n_value.value,
            new_contracts=unit_size.contracts,
            new_stop_price=new_stop.price,
            within_limits=limit_result.allowed,
            limit_reason=limit_result.denial_reason,
        )
    
    def build_exit_signal(
        self,
        position: Position,
        market: MarketData,
        exit_type: str,
        trigger_price: Decimal,
    ) -> ExitSignal:
        """Build exit signal with P&L estimate"""
        estimated_pnl = position.calculate_unrealized_pnl(market.current_price)
        
        return ExitSignal(
            position_id=position.id,
            symbol=position.symbol,
            exit_type=exit_type,
            trigger_price=trigger_price,
            current_price=market.current_price,
            direction=position.direction,
            total_contracts=position.total_contracts,
            estimated_pnl=estimated_pnl,
            reason=f"{exit_type} exit triggered at {trigger_price}",
            detected_at=datetime.now(),
        )
```

---

## Monitor Service (Orchestration Layer)

```python
# portfolio/monitor/monitor_service.py
from datetime import datetime
from turtle_core.models import Portfolio, MonitoringResult, PositionAction, Direction
from .position_monitor import PositionMonitor


class MonitorService:
    """
    Service layer for position monitoring.
    Runs monitoring cycle across all open positions.
    """
    
    def __init__(
        self,
        position_monitor: PositionMonitor,
        data_feed,  # DataFeed instance
    ):
        self.monitor = position_monitor
        self.data_feed = data_feed
    
    async def run_monitoring_cycle(
        self,
        portfolio: Portfolio,
    ) -> MonitoringResult:
        """
        Check all open positions for required actions.
        
        Returns structured result containing:
        - Positions to hold (no action)
        - Pyramid opportunities
        - Exit signals
        """
        result = MonitoringResult(
            cycle_timestamp=datetime.now(),
            positions_checked=len(portfolio.positions),
        )
        
        for position in portfolio.get_open_positions():
            # Get current market data for this position
            market = await self.data_feed.get_market_data_by_symbol(position.symbol)
            
            # Check position
            check = self.monitor.check_position(position, market)
            
            # Route to appropriate list based on action
            match check.action:
                case PositionAction.HOLD:
                    result.holds.append(check)
                
                case PositionAction.PYRAMID:
                    # Build full pyramid opportunity
                    opportunity = self.monitor.build_pyramid_opportunity(
                        position=position,
                        market=market,
                        portfolio_equity=portfolio.get_adjusted_equity(),
                        portfolio=portfolio,
                    )
                    result.pyramid_opportunities.append(opportunity)
                
                case PositionAction.EXIT_STOP:
                    signal = self.monitor.build_exit_signal(
                        position=position,
                        market=market,
                        exit_type="STOP",
                        trigger_price=position.current_stop,
                    )
                    result.exit_signals.append(signal)
                
                case PositionAction.EXIT_BREAKOUT:
                    exit_channel = self.monitor._get_exit_channel(position, market)
                    trigger = (
                        exit_channel.lower if position.direction == Direction.LONG 
                        else exit_channel.upper
                    )
                    signal = self.monitor.build_exit_signal(
                        position=position,
                        market=market,
                        exit_type="BREAKOUT",
                        trigger_price=trigger,
                    )
                    result.exit_signals.append(signal)
        
        return result
```

---

## Continuous Monitoring Loop

```python
# orchestrator/monitoring_loop.py
import asyncio
from datetime import datetime
from turtle_core.models import Portfolio, MonitoringResult
from portfolio.monitor import MonitorService
from execution.brokers import Broker
from audit.logger import TradeLogger


class MonitoringLoop:
    """
    Continuous position monitoring during market hours.
    
    Runs every N seconds to check for:
    - Stop hits
    - Breakout exits
    - Pyramid opportunities
    """
    
    def __init__(
        self,
        monitor_service: MonitorService,
        broker: Broker,
        logger: TradeLogger,
        interval_seconds: int = 60,
    ):
        self.monitor = monitor_service
        self.broker = broker
        self.logger = logger
        self.interval = interval_seconds
        self._running = False
    
    async def start(self, portfolio: Portfolio):
        """Start the monitoring loop"""
        self._running = True
        print(f"Starting position monitor (interval: {self.interval}s)")
        
        while self._running:
            try:
                # Run monitoring cycle
                result = await self.monitor.run_monitoring_cycle(portfolio)
                
                # Log cycle
                self._log_cycle(result)
                
                # Process any required actions
                if result.has_actions:
                    await self._process_actions(portfolio, result)
                
                # Wait for next cycle
                await asyncio.sleep(self.interval)
                
            except Exception as e:
                print(f"Monitoring error: {e}")
                # Keep running despite errors
                await asyncio.sleep(self.interval)
    
    def stop(self):
        """Stop the monitoring loop"""
        self._running = False
        print("Stopping position monitor")
    
    def _log_cycle(self, result: MonitoringResult):
        """Log monitoring cycle summary"""
        if result.has_actions:
            print(f"[{result.cycle_timestamp}] Monitoring: "
                  f"{len(result.exit_signals)} exits, "
                  f"{len(result.pyramid_opportunities)} pyramids")
    
    async def _process_actions(
        self, 
        portfolio: Portfolio, 
        result: MonitoringResult
    ):
        """Process exits and pyramids from monitoring"""
        
        # EXITS FIRST (free up units, preserve capital)
        for exit_signal in result.exit_signals:
            print(f"Processing exit: {exit_signal.symbol} ({exit_signal.exit_type})")
            await self._execute_exit(portfolio, exit_signal)
        
        # THEN PYRAMIDS
        for pyramid in result.pyramid_opportunities:
            if pyramid.within_limits:
                print(f"Processing pyramid: {pyramid.symbol} (unit {pyramid.current_unit_count + 1})")
                await self._execute_pyramid(portfolio, pyramid)
            else:
                print(f"Skipping pyramid {pyramid.symbol}: {pyramid.limit_reason}")
    
    async def _execute_exit(self, portfolio: Portfolio, exit_signal):
        """Close position and update portfolio"""
        position = portfolio.positions[exit_signal.symbol]
        
        # Close via broker
        fill = await self.broker.close_position(
            position_id=position.id,
            quantity=position.total_contracts,
        )
        
        # Log trade exit
        await self.logger.log_exit(
            position=position,
            exit_price=fill.fill_price,
            exit_reason=exit_signal.exit_type,
        )
        
        # Remove from portfolio
        del portfolio.positions[exit_signal.symbol]
        
        print(f"  Closed {exit_signal.symbol} at {fill.fill_price}, "
              f"P&L: ${exit_signal.estimated_pnl:,.2f}")
    
    async def _execute_pyramid(self, portfolio: Portfolio, pyramid):
        """Add unit to position and update ALL stops"""
        position = portfolio.positions[pyramid.symbol]
        
        # Place new entry order
        from turtle_core.models import BracketOrder
        order = BracketOrder(
            symbol=pyramid.symbol,
            direction=pyramid.direction,
            quantity=pyramid.new_contracts,
            entry_type="MARKET",
            stop_price=pyramid.new_stop_price,
            time_in_force="GTC",
            system=position.system,
            unit_number=pyramid.current_unit_count + 1,
            n_at_entry=pyramid.new_n_value,
        )
        
        fill = await self.broker.place_bracket_order(order)
        
        # CRITICAL: Update ALL stops to new level
        await self.broker.modify_stop(
            position_id=position.id,
            new_stop_price=pyramid.new_stop_price,
        )
        
        # Update position model
        from turtle_core.models import PyramidLevel
        new_level = PyramidLevel(
            unit_number=pyramid.current_unit_count + 1,
            entry_price=fill.fill_price,
            entry_timestamp=fill.filled_at,
            n_at_entry=pyramid.new_n_value,
            contracts=pyramid.new_contracts,
            original_stop=pyramid.new_stop_price,
        )
        position.pyramid_levels.append(new_level)
        position.current_stop = pyramid.new_stop_price  # All stops move
        
        # Log pyramid
        await self.logger.log_pyramid(position, fill)
        
        print(f"  Added unit {pyramid.current_unit_count + 1} to {pyramid.symbol} "
              f"at {fill.fill_price}, new stop: {pyramid.new_stop_price}")
```

---

## Stop Update Rule Diagram

```
CRITICAL: When pyramiding, ALL unit stops move to 2N below newest entry

═══════════════════════════════════════════════════════════════════════
EXAMPLE: Long Position in /MGC (Micro Gold)
═══════════════════════════════════════════════════════════════════════

INITIAL ENTRY (Unit 1):
┌────────────────────────────────────────────────────────────────────┐
│ Unit 1: Entry $2800, N=$20, Stop = $2800 - (2×$20) = $2760        │
│                                                                    │
│ Price: $2800 ────────────────────────────────────                 │
│ Stop:  $2760 ════════════════════════════════════                 │
└────────────────────────────────────────────────────────────────────┘

PYRAMID AT +1N (Unit 2 at $2820):
┌────────────────────────────────────────────────────────────────────┐
│ Unit 1: Entry $2800, Stop moves to $2780 (was $2760)              │
│ Unit 2: Entry $2820, N=$20, Stop = $2820 - (2×$20) = $2780        │
│                                                                    │
│ Price: $2820 ────────────────────────────────────                 │
│ Unit1: $2800 ....................................................  │
│ Stop:  $2780 ════════════════════════════════════ (ALL units)     │
│ Old:   $2760 ---- (no longer valid)                               │
└────────────────────────────────────────────────────────────────────┘

PYRAMID AT +2N (Unit 3 at $2840):
┌────────────────────────────────────────────────────────────────────┐
│ Unit 1: Entry $2800, Stop moves to $2800 (breakeven!)             │
│ Unit 2: Entry $2820, Stop moves to $2800                          │
│ Unit 3: Entry $2840, N=$20, Stop = $2840 - (2×$20) = $2800        │
│                                                                    │
│ Price: $2840 ────────────────────────────────────                 │
│ Unit3: $2840 ....................................................  │
│ Unit2: $2820 ....................................................  │
│ Unit1: $2800 ════════════════════════════════════ ← Stop = Entry! │
│ Stop:  $2800 ════════════════════════════════════ (ALL units)     │
└────────────────────────────────────────────────────────────────────┘

PYRAMID AT +3N (Unit 4 at $2860):
┌────────────────────────────────────────────────────────────────────┐
│ Unit 1: Entry $2800, Stop at $2820 → LOCKED IN $20 PROFIT         │
│ Unit 2: Entry $2820, Stop at $2820 → BREAKEVEN                    │
│ Unit 3: Entry $2840, Stop at $2820 → $20 risk                     │
│ Unit 4: Entry $2860, Stop = $2860 - (2×$20) = $2820               │
│                                                                    │
│ Price: $2860 ────────────────────────────────────                 │
│ Unit4: $2860 ....................................................  │
│ Unit3: $2840 ....................................................  │
│ Unit2: $2820 ════════════════════════════════════ ← Stop here     │
│ Unit1: $2800 ....................................................  │
│ Stop:  $2820 ════════════════════════════════════ (ALL units)     │
│                                                                    │
│ If stopped out at $2820:                                          │
│   Unit 1: +$20 profit ($2820 - $2800)                            │
│   Unit 2: $0 (breakeven)                                          │
│   Unit 3: -$20 loss ($2820 - $2840)                              │
│   Unit 4: -$40 loss ($2820 - $2860)                              │
│   NET: -$40 loss (vs -$200 if stops hadn't moved)                │
└────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Position Monitoring

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     POSITION MONITORING LOOP                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  For each open position:                                                 │
│                                                                          │
│  ┌──────────────┐                                                       │
│  │ Get Current  │                                                       │
│  │ Market Data  │ (price, N, Donchian channels)                         │
│  └──────┬───────┘                                                       │
│         │                                                                │
│         ▼                                                                │
│  ┌──────────────┐     YES    ┌──────────────┐                          │
│  │ Stop Hit?    │───────────▶│ EXIT_STOP    │──▶ Close All + Log       │
│  │ (price≤stop) │            └──────────────┘                          │
│  └──────┬───────┘                                                       │
│         │ NO                                                            │
│         ▼                                                                │
│  ┌──────────────┐     YES    ┌──────────────┐                          │
│  │ Exit Brkout? │───────────▶│EXIT_BREAKOUT │──▶ Close All + Log       │
│  │(S1:10d/S2:20d)│           └──────────────┘                          │
│  └──────┬───────┘                                                       │
│         │ NO                                                            │
│         ▼                                                                │
│  ┌──────────────┐     YES    ┌──────────────┐     ┌──────────────┐     │
│  │ Pyramid?     │───────────▶│ Check Limits │────▶│ Add Unit     │     │
│  │ (price≥+1N)  │            │              │ OK  │ Update ALL   │     │
│  │              │            │              │     │ Stops        │     │
│  └──────┬───────┘            └──────┬───────┘     └──────────────┘     │
│         │ NO                        │ FAIL                              │
│         │                           ▼                                   │
│         │                    ┌──────────────┐                          │
│         │                    │ Log Skipped  │                          │
│         │                    │ (limit hit)  │                          │
│         │                    └──────────────┘                          │
│         ▼                                                                │
│  ┌──────────────┐                                                       │
│  │    HOLD      │ ──▶ Continue monitoring                               │
│  └──────────────┘                                                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```
# Turtle Trading Bot - Part 4: Module Implementations

## Market Data Module

### N (ATR) Calculator

```python
# market_data/calc/volatility.py
from decimal import Decimal
from datetime import datetime
from turtle_core.models import Bar, NValue


def calculate_true_range(
    high: Decimal,
    low: Decimal,
    prev_close: Decimal
) -> Decimal:
    """
    TR = max(H-L, |H-PDC|, |PDC-L|)
    
    Three components:
    1. High - Low (today's range)
    2. |High - Previous Close| (gap up captured)
    3. |Previous Close - Low| (gap down captured)
    """
    return max(
        high - low,
        abs(high - prev_close),
        abs(prev_close - low)
    )


def calculate_n(
    bars: list[Bar],
    period: int = 20,
    method: str = "WILDERS"
) -> NValue:
    """
    Calculate N (ATR with Wilders smoothing)
    
    Wilders Smoothing (used by TOS):
        N = ((period - 1) * Previous_N + Current_TR) / period
    
    This is equivalent to EMA with alpha = 1/period
    """
    if len(bars) < period + 1:
        raise ValueError(f"Need at least {period + 1} bars, got {len(bars)}")
    
    # Calculate all true ranges
    true_ranges: list[Decimal] = []
    for i in range(1, len(bars)):
        tr = calculate_true_range(
            bars[i].high,
            bars[i].low,
            bars[i - 1].close
        )
        true_ranges.append(tr)
    
    if method == "WILDERS":
        # Seed with SMA of first `period` true ranges
        n_value = sum(true_ranges[:period]) / period
        
        # Apply Wilders smoothing for remaining
        for tr in true_ranges[period:]:
            n_value = ((period - 1) * n_value + tr) / period
    else:
        # Simple moving average of last `period` true ranges
        n_value = sum(true_ranges[-period:]) / period
    
    return NValue(
        value=n_value,
        calculated_at=datetime.now(),
        period=period,
        method=method,
    )
```

### Donchian Calculator

```python
# market_data/calc/channels.py
from decimal import Decimal
from datetime import datetime
from turtle_core.models import Bar, DonchianChannel


def calculate_donchian(bars: list[Bar], period: int) -> DonchianChannel:
    """
    Donchian Channel:
        Upper = Highest High over N days
        Lower = Lowest Low over N days
    
    Used for:
        - 20-day: S1 entries
        - 55-day: S2 entries
        - 10-day: S1 exits
        - 20-day: S2 exits
    """
    if len(bars) < period:
        raise ValueError(f"Need at least {period} bars, got {len(bars)}")
    
    recent_bars = bars[-period:]
    
    return DonchianChannel(
        upper=max(b.high for b in recent_bars),
        lower=min(b.low for b in recent_bars),
        period=period,
        calculated_at=datetime.now(),
    )
```

### Data Feed Interface

```python
# market_data/feeds/base.py
from abc import ABC, abstractmethod
from turtle_core.models import Bar, MarketData, MarketSpec


class DataFeed(ABC):
    """Abstract base for market data providers"""
    
    @abstractmethod
    async def get_bars(self, symbol: str, days: int) -> list[Bar]:
        """Fetch historical OHLCV bars"""
        pass
    
    @abstractmethod
    async def get_current_price(self, symbol: str) -> Decimal:
        """Get latest price"""
        pass
    
    async def get_market_data(self, spec: MarketSpec) -> MarketData:
        """Get complete market state with all indicators"""
        from .calc.volatility import calculate_n
        from .calc.channels import calculate_donchian
        from datetime import datetime
        
        # Fetch enough bars for all calculations
        bars = await self.get_bars(spec.symbol, days=70)
        current_price = await self.get_current_price(spec.symbol)
        
        return MarketData(
            spec=spec,
            current_price=current_price,
            n_value=calculate_n(bars, period=20, method="WILDERS"),
            donchian_10=calculate_donchian(bars, period=10),
            donchian_20=calculate_donchian(bars, period=20),
            donchian_55=calculate_donchian(bars, period=55),
            bars=bars,
            updated_at=datetime.now(),
        )
```

---

## Strategy Module

### Signal Detector

```python
# strategy/signals/detector.py
from decimal import Decimal
from datetime import datetime
from turtle_core.models import Signal, Direction, System, MarketData, DonchianChannel


class SignalDetector:
    """Detect breakout entry signals per Turtle rules"""
    
    def detect_s1_signal(self, market: MarketData) -> Signal | None:
        """
        S1: 20-day breakout
        
        Long if price > 20-day high
        Short if price < 20-day low
        """
        return self._detect_breakout(
            market=market,
            channel=market.donchian_20,
            system=System.S1,
        )
    
    def detect_s2_signal(self, market: MarketData) -> Signal | None:
        """
        S2: 55-day breakout (failsafe - always take)
        
        Long if price > 55-day high
        Short if price < 55-day low
        """
        return self._detect_breakout(
            market=market,
            channel=market.donchian_55,
            system=System.S2,
        )
    
    def _detect_breakout(
        self,
        market: MarketData,
        channel: DonchianChannel,
        system: System,
    ) -> Signal | None:
        """Generic breakout detection"""
        price = market.current_price
        
        # Long breakout
        if price > channel.upper:
            return Signal(
                symbol=market.spec.symbol,
                system=system,
                direction=Direction.LONG,
                breakout_price=channel.upper,
                triggered_at=datetime.now(),
                donchian_period=channel.period,
            )
        
        # Short breakout
        if price < channel.lower:
            return Signal(
                symbol=market.spec.symbol,
                system=system,
                direction=Direction.SHORT,
                breakout_price=channel.lower,
                triggered_at=datetime.now(),
                donchian_period=channel.period,
            )
        
        return None
```

### S1 Filter

```python
# strategy/filters/s1_filter.py
from turtle_core.models import Signal, FilterResult, System


class S1Filter:
    """
    S1 Filter Rule:
    
    - Last S1 trade in this market was WINNER → SKIP signal
    - Last S1 trade in this market was LOSER (2N stop) → TAKE signal
    - No S1 history for this market → TAKE signal
    
    S2 signals are NEVER filtered (failsafe system)
    """
    
    def __init__(self, trade_repository):
        self.trade_repo = trade_repository
    
    async def should_take_signal(
        self,
        symbol: str,
        signal: Signal
    ) -> FilterResult:
        
        # S2 is never filtered
        if signal.system == System.S2:
            return FilterResult(
                take_signal=True,
                reason="S2 signals always taken (failsafe system)",
            )
        
        # Look up last S1 trade for this market
        last_s1 = await self.trade_repo.get_last_s1_trade(symbol)
        
        # No history → take signal
        if last_s1 is None:
            return FilterResult(
                take_signal=True,
                reason="No S1 history for this market - taking signal",
            )
        
        # Last S1 was winner → skip
        if last_s1.was_winner:
            return FilterResult(
                take_signal=False,
                reason=f"Last S1 trade (ID: {last_s1.id}) was winner - skipping per filter rule",
                last_s1_trade_id=last_s1.id,
                last_s1_was_winner=True,
            )
        
        # Last S1 was loser → take
        return FilterResult(
            take_signal=True,
            reason=f"Last S1 trade (ID: {last_s1.id}) was loser - taking signal",
            last_s1_trade_id=last_s1.id,
            last_s1_was_winner=False,
        )
```

---

## Portfolio Module

### Position Sizing

```python
# portfolio/sizing/calculator.py
from decimal import Decimal, ROUND_DOWN
from turtle_core.models import UnitSize, NValue
from turtle_core.rules import RULES


def calculate_unit_size(
    equity: Decimal,
    n_value: NValue,
    point_value: Decimal,
    risk_pct: Decimal = None,
) -> UnitSize:
    """
    Calculate number of contracts for one unit.
    
    Formula:
        Risk Amount = Equity × Risk%
        Dollar Volatility = N × Point Value
        Stop Risk = Dollar Volatility × 2 (2N stop)
        Contracts = Risk Amount / Stop Risk
    
    ALWAYS round DOWN - never risk more than intended.
    """
    if risk_pct is None:
        risk_pct = RULES.risk_per_trade
    
    risk_amount = equity * risk_pct
    dollar_volatility = n_value.value * point_value
    stop_risk = dollar_volatility * RULES.stop_multiplier  # 2N
    
    if stop_risk == 0:
        contracts = 0
    else:
        # CRITICAL: Round DOWN
        contracts = int((risk_amount / stop_risk).to_integral_value(ROUND_DOWN))
    
    actual_risk = stop_risk * contracts if contracts > 0 else Decimal("0")
    
    return UnitSize(
        contracts=contracts,
        risk_per_unit=actual_risk,
        equity_at_calculation=equity,
        n_value_used=n_value.value,
        point_value=point_value,
        risk_pct_used=risk_pct,
    )
```

### Stop Calculator

```python
# portfolio/sizing/stop_calculator.py
from decimal import Decimal
from turtle_core.models import StopLevel, Direction, NValue
from turtle_core.rules import RULES


def calculate_stop(
    entry_price: Decimal,
    n_value: NValue,
    direction: Direction,
) -> StopLevel:
    """
    Calculate 2N stop price.
    
    LONG:  Stop = Entry - 2N
    SHORT: Stop = Entry + 2N
    
    Note: Stop only moves when pyramiding (to 2N below new entry).
    Stop does NOT trail automatically with price movement.
    """
    stop_distance = n_value.value * RULES.stop_multiplier
    
    if direction == Direction.LONG:
        stop_price = entry_price - stop_distance
    else:
        stop_price = entry_price + stop_distance
    
    return StopLevel(
        price=stop_price,
        n_at_entry=n_value.value,
        entry_price=entry_price,
        direction=direction,
    )
```

### Limit Checker

```python
# portfolio/limits/checker.py
from turtle_core.models import Portfolio, LimitCheckResult, CorrelationGroup
from turtle_core.rules import RULES


class LimitChecker:
    """
    Enforce all unit limits before adding positions.
    
    Limits:
    1. Max 12 units total
    2. Max 4 units per market
    3. Max 6 units per correlation group
    """
    
    def can_add_position(
        self,
        portfolio: Portfolio,
        symbol: str,
        units_to_add: int,
        correlation_group: CorrelationGroup,
    ) -> LimitCheckResult:
        """Check all limits before adding position or pyramid"""
        
        # Current state
        total_units = portfolio.total_units
        
        # Per-market current
        existing = portfolio.positions.get(symbol)
        per_market_current = existing.total_units if existing else 0
        
        # Correlation group current
        correlation_current = portfolio.units_in_correlation_group(correlation_group)
        
        # Projected after addition
        total_after = total_units + units_to_add
        per_market_after = per_market_current + units_to_add
        correlation_after = correlation_current + units_to_add
        
        # Check each limit
        total_ok = total_after <= RULES.max_units_total
        per_market_ok = per_market_after <= RULES.max_units_per_market
        correlation_ok = correlation_after <= RULES.max_units_correlated
        
        allowed = total_ok and per_market_ok and correlation_ok
        
        # Determine denial reason
        denial_reason = None
        if not allowed:
            if not total_ok:
                denial_reason = f"Total units ({total_after}) exceeds max ({RULES.max_units_total})"
            elif not per_market_ok:
                denial_reason = f"Per-market units ({per_market_after}) exceeds max ({RULES.max_units_per_market})"
            elif not correlation_ok:
                denial_reason = f"{correlation_group.value} units ({correlation_after}) exceeds max ({RULES.max_units_correlated})"
        
        return LimitCheckResult(
            allowed=allowed,
            total_units_ok=total_ok,
            total_units_current=total_units,
            total_units_max=RULES.max_units_total,
            per_market_ok=per_market_ok,
            per_market_current=per_market_current,
            per_market_max=RULES.max_units_per_market,
            correlation_ok=correlation_ok,
            correlation_group=correlation_group,
            correlation_current=correlation_current,
            correlation_max=RULES.max_units_correlated,
            denial_reason=denial_reason,
        )
```

---

## Execution Module

### Broker Interface

```python
# execution/brokers/base.py
from abc import ABC, abstractmethod
from decimal import Decimal
from turtle_core.models import BracketOrder, OrderFill, StopModification


class Broker(ABC):
    """Abstract broker interface"""
    
    @abstractmethod
    async def place_bracket_order(self, order: BracketOrder) -> OrderFill:
        """Place entry with attached stop"""
        pass
    
    @abstractmethod
    async def modify_stop(
        self,
        position_id: str,
        new_stop_price: Decimal,
    ) -> StopModification:
        """Update stop price for all units in position"""
        pass
    
    @abstractmethod
    async def close_position(
        self,
        position_id: str,
        quantity: int,
    ) -> OrderFill:
        """Close all or part of position at market"""
        pass
    
    @abstractmethod
    async def cancel_all_orders(self, symbol: str) -> int:
        """Cancel all pending orders for symbol"""
        pass
```

### Paper Broker

```python
# execution/brokers/paper.py
import uuid
from decimal import Decimal
from datetime import datetime
from .base import Broker
from turtle_core.models import BracketOrder, OrderFill, StopModification, Direction


class PaperBroker(Broker):
    """Simulated broker for testing and paper trading"""
    
    def __init__(self):
        self.orders: dict[str, BracketOrder] = {}
        self.fills: list[OrderFill] = []
        self.positions: dict[str, dict] = {}
    
    async def place_bracket_order(self, order: BracketOrder) -> OrderFill:
        order_id = str(uuid.uuid4())
        self.orders[order_id] = order
        
        # Simulate fill at entry price
        fill_price = order.entry_price or Decimal("0")
        
        fill = OrderFill(
            order_id=order_id,
            symbol=order.symbol,
            direction=order.direction,
            quantity=order.quantity,
            fill_price=fill_price,
            filled_at=datetime.now(),
            commission=Decimal("2.25") * order.quantity,  # Typical micro futures
        )
        
        self.fills.append(fill)
        
        # Track position
        self.positions[order.symbol] = {
            "order_id": order_id,
            "stop_price": order.stop_price,
            "direction": order.direction,
            "quantity": order.quantity,
        }
        
        return fill
    
    async def modify_stop(
        self,
        position_id: str,
        new_stop_price: Decimal,
    ) -> StopModification:
        # Find position by ID
        for symbol, pos in self.positions.items():
            if pos.get("order_id") == position_id:
                old_stop = pos["stop_price"]
                pos["stop_price"] = new_stop_price
                
                return StopModification(
                    position_id=position_id,
                    old_stop=old_stop,
                    new_stop=new_stop_price,
                    reason="Pyramid adjustment - all stops updated",
                    modified_at=datetime.now(),
                )
        
        raise ValueError(f"Position {position_id} not found")
    
    async def close_position(
        self,
        position_id: str,
        quantity: int,
    ) -> OrderFill:
        # Simulate market close
        return OrderFill(
            order_id=str(uuid.uuid4()),
            symbol="",
            direction=Direction.LONG,  # Opposite of position
            quantity=quantity,
            fill_price=Decimal("0"),  # Would be current market
            filled_at=datetime.now(),
            commission=Decimal("2.25") * quantity,
        )
    
    async def cancel_all_orders(self, symbol: str) -> int:
        cancelled = 0
        to_remove = []
        for order_id, order in self.orders.items():
            if order.symbol == symbol:
                to_remove.append(order_id)
                cancelled += 1
        
        for order_id in to_remove:
            del self.orders[order_id]
        
        return cancelled
```

---

## Audit Module

### Trade Logger

```python
# audit/logger/trade_logger.py
from datetime import datetime
from decimal import Decimal
from turtle_core.models import (
    Trade, Position, Signal, UnitSize, OrderFill, 
    ExitReason, Direction, PyramidLevel
)


class TradeLogger:
    """Immutable trade logging for compliance and S1 filter"""
    
    def __init__(self, repository):
        self.repo = repository
    
    async def log_entry(
        self,
        position: Position,
        signal: Signal,
        unit_size: UnitSize,
        fill: OrderFill,
    ) -> Trade:
        """Log new position entry"""
        trade = Trade(
            id=position.id,
            symbol=position.symbol,
            direction=position.direction,
            system=signal.system,
            entry_date=fill.filled_at,
            entry_price=fill.fill_price,
            n_at_entry=position.pyramid_levels[0].n_at_entry,
            initial_stop=position.current_stop,
            initial_units=1,
            initial_contracts=fill.quantity,
            pyramid_levels=list(position.pyramid_levels),
            max_units=1,
            max_contracts=fill.quantity,
            commission_total=fill.commission,
        )
        
        await self.repo.save_trade(trade)
        return trade
    
    async def log_pyramid(
        self,
        position: Position,
        fill: OrderFill,
    ) -> Trade:
        """Update trade record with pyramid addition"""
        trade = await self.repo.get_trade(position.id)
        
        # Update pyramid tracking
        trade.pyramid_levels = list(position.pyramid_levels)
        trade.max_units = max(trade.max_units, position.total_units)
        trade.max_contracts = max(trade.max_contracts, position.total_contracts)
        trade.commission_total += fill.commission
        
        await self.repo.save_trade(trade)
        return trade
    
    async def log_exit(
        self,
        position: Position,
        exit_price: Decimal,
        exit_reason: str,
    ) -> Trade:
        """Finalize trade record with exit details"""
        trade = await self.repo.get_trade(position.id)
        
        trade.exit_date = datetime.now()
        trade.exit_price = exit_price
        trade.exit_reason = ExitReason(exit_reason)
        trade.final_stop = position.current_stop
        
        # Calculate P&L
        if position.direction == Direction.LONG:
            price_diff = exit_price - position.average_entry
        else:
            price_diff = position.average_entry - exit_price
        
        trade.realized_pnl = price_diff * position.total_contracts * position.point_value
        trade.net_pnl = trade.realized_pnl - trade.commission_total
        
        await self.repo.save_trade(trade)
        
        # Update S1 filter history
        if trade.system == "S1":
            await self.repo.record_s1_result(
                symbol=trade.symbol,
                trade_id=trade.id,
                was_winner=trade.was_winner,
            )
        
        return trade
```
# Turtle Trading Bot - Part 5: Implementation Phases & Reference

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Language** | Python 3.12+ | Your stack, rich trading libs |
| **Models** | Pydantic v2 | Type safety, validation, serialization |
| **Async** | asyncio | Concurrent market monitoring |
| **State Machine** | LangGraph | Workflow orchestration |
| **AI Integration** | LangChain | Gemini + NotebookLM bridge |
| **Broker API** | ib_insync | IBKR integration |
| **Database** | PostgreSQL | Trade history, audit log |
| **Cache** | Redis | Real-time price cache |
| **Deployment** | Docker on Unraid | Your home lab |

---

## Implementation Phases

### Phase 1: Core Foundation (Week 1-2)

**Modules:** `turtle_core`, `market_data`

```
Deliverables:
├── All Pydantic models (Part 2 of this spec)
├── TurtleRules configuration
├── Yahoo Finance data feed
├── N (ATR) calculator with Wilders smoothing
├── Donchian channel calculator (10, 20, 55-day)
├── CLI tool to test calculations
└── Unit tests comparing to TOS values

Validation Criteria:
- N calculations match TOS ATR(20, WILDERS) within 0.5%
- Donchian channels match TradingView exactly
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
└── Export tools for compliance

Validation Criteria:
- Import your TOS history successfully
- Generate report matching manual tracking
- S1 filter lookups return correct results
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
├── Paper broker (simulation)
├── IBKR broker integration
├── Bracket order builder
├── Stop modification handler
└── Fill reconciliation

Validation Criteria:
- Paper trade for 2 weeks
- Bracket orders match TOS setup
- Stop updates work correctly
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
│   │   └── config.py
│   │
│   ├── market_data/
│   │   ├── __init__.py
│   │   ├── feeds/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── yahoo.py
│   │   │   └── ibkr.py
│   │   ├── calc/
│   │   │   ├── __init__.py
│   │   │   ├── volatility.py
│   │   │   └── channels.py
│   │   └── store/
│   │       └── repository.py
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
