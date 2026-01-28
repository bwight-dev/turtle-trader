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
