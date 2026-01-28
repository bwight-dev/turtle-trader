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
