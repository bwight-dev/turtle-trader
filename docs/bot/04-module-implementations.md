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
from decimal import Decimal
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

        # Fetch enough bars for all calculations (70 days for 55-day Donchian + buffer)
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

### Data Feed Implementations

The system uses a **dual data source architecture**:

| Feed | Class | Purpose |
|------|-------|---------|
| **IBKR** | `IBKRDataFeed` | Primary - connects to TWS/Gateway on Mac Mini |
| **Yahoo** | `YahooDataFeed` | Backup - free, reliable for daily bars |
| **Composite** | `CompositeDataFeed` | Wrapper with automatic failover |

**See `06-data-sources.md` for complete implementations including:**
- IBKR connection management and configuration
- Symbol mapping (internal ↔ IBKR ↔ Yahoo formats)
- Continuous contract handling for futures (back-adjustment)
- Data validation and cross-source verification
- N value persistence for statefulness

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
