"""Event logging command for Turtle Trading audit trail.

This module provides the EventLogger class for capturing trading
events with full context. See docs/plans/2026-02-12-event-streaming-design.md.

Usage:
    event_logger = EventLogger(event_repo)
    run_id = event_logger.start_run("monitor")

    await event_logger.log(
        EventType.POSITION_CHECKED,
        OutcomeType.HOLD,
        symbol="QQQ",
        context={
            "market": build_market_context(...),
            "position": build_position_context(...),
        }
    )
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.interfaces.repositories import EventRepository
from src.domain.models.event import Event, EventType, OutcomeType
from src.domain.models.market import Bar, DonchianChannel, NValue
from src.domain.models.position import Position
from src.domain.rules import (
    DRAWDOWN_REDUCTION,
    DRAWDOWN_THRESHOLD,
    MAX_TOTAL_RISK,
    MAX_UNITS_CORRELATED,
    MAX_UNITS_PER_MARKET,
    MAX_UNITS_TOTAL,
    N_PERIOD,
    PYRAMID_INTERVAL_MULTIPLIER,
    RISK_PER_TRADE,
    STOP_MULTIPLIER,
    USE_RISK_CAP_MODE,
)


class EventLogger:
    """Logs trading events with full context capture.

    The EventLogger manages a run (scanner or monitor execution)
    and logs events with auto-incrementing sequence numbers.

    Attributes:
        run_id: Current run identifier (set by start_run)
        sequence: Current event sequence number
        source: "scanner" or "monitor"
    """

    def __init__(self, repo: EventRepository) -> None:
        """Initialize the event logger.

        Args:
            repo: Repository for event persistence
        """
        self._repo = repo
        self._run_id: UUID | None = None
        self._sequence: int = 0
        self._source: str = ""

    @property
    def run_id(self) -> UUID | None:
        """Get current run ID."""
        return self._run_id

    def start_run(self, source: str) -> UUID:
        """Start a new run.

        Args:
            source: "scanner" or "monitor"

        Returns:
            The new run_id
        """
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
        """Log an event with auto-incrementing sequence.

        Args:
            event_type: Type of event
            outcome: What happened
            symbol: Market symbol (None for system events)
            outcome_reason: Human-readable explanation
            context: Full state snapshot
            dry_run: True if this was a simulation

        Returns:
            The created Event
        """
        if self._run_id is None:
            raise RuntimeError("Must call start_run() before logging events")

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

    async def log_monitor_started(
        self,
        positions: list[str],
        dry_run: bool = False,
    ) -> Event:
        """Log monitor cycle start.

        Args:
            positions: List of symbols being monitored
            dry_run: True if this is a simulation

        Returns:
            The created Event
        """
        return await self.log(
            EventType.MONITOR_STARTED,
            OutcomeType.COMPLETED,
            context={"positions": positions, "count": len(positions)},
            dry_run=dry_run,
        )

    async def log_monitor_completed(
        self,
        positions_checked: int,
        exits: int = 0,
        pyramids: int = 0,
        errors: int = 0,
        dry_run: bool = False,
    ) -> Event:
        """Log monitor cycle completion.

        Args:
            positions_checked: Number of positions checked
            exits: Number of exits triggered
            pyramids: Number of pyramids triggered
            errors: Number of errors encountered
            dry_run: True if this is a simulation

        Returns:
            The created Event
        """
        outcome = OutcomeType.COMPLETED if errors == 0 else OutcomeType.COMPLETED_WITH_ERRORS
        return await self.log(
            EventType.MONITOR_COMPLETED,
            outcome,
            context={
                "positions_checked": positions_checked,
                "exits": exits,
                "pyramids": pyramids,
                "errors": errors,
            },
            dry_run=dry_run,
        )

    async def log_scanner_started(
        self,
        symbols: list[str],
        dry_run: bool = False,
    ) -> Event:
        """Log scanner run start.

        Args:
            symbols: List of symbols to scan
            dry_run: True if this is a simulation

        Returns:
            The created Event
        """
        return await self.log(
            EventType.SCANNER_STARTED,
            OutcomeType.COMPLETED,
            context={"symbols": symbols, "count": len(symbols)},
            dry_run=dry_run,
        )

    async def log_scanner_completed(
        self,
        symbols_scanned: int,
        signals_detected: int = 0,
        signals_approved: int = 0,
        positions_opened: int = 0,
        errors: int = 0,
        dry_run: bool = False,
    ) -> Event:
        """Log scanner run completion.

        Args:
            symbols_scanned: Number of symbols checked
            signals_detected: Number of breakouts found
            signals_approved: Number of signals that passed filters
            positions_opened: Number of new positions opened
            errors: Number of errors encountered
            dry_run: True if this is a simulation

        Returns:
            The created Event
        """
        outcome = OutcomeType.COMPLETED if errors == 0 else OutcomeType.COMPLETED_WITH_ERRORS
        return await self.log(
            EventType.SCANNER_COMPLETED,
            outcome,
            context={
                "symbols_scanned": symbols_scanned,
                "signals_detected": signals_detected,
                "signals_approved": signals_approved,
                "positions_opened": positions_opened,
                "errors": errors,
            },
            dry_run=dry_run,
        )


# =============================================================================
# Context Builders
# =============================================================================


def build_market_context(
    symbol: str,
    price: Decimal,
    n_value: NValue | None = None,
    dc10: DonchianChannel | None = None,
    dc20: DonchianChannel | None = None,
    dc55: DonchianChannel | None = None,
    bars: list[Bar] | None = None,
    source: str = "unknown",
) -> dict:
    """Build market context for events.

    Args:
        symbol: Market symbol
        price: Current price
        n_value: N (ATR) value with metadata
        dc10: 10-day Donchian channel
        dc20: 20-day Donchian channel
        dc55: 55-day Donchian channel
        bars: Recent bars (for OHLC)
        source: Data source (yahoo, ibkr, composite)

    Returns:
        Market context dict
    """
    context: dict = {
        "symbol": symbol,
        "price": float(price),
        "source": source,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Add OHLCV from most recent bar
    if bars and len(bars) > 0:
        bar = bars[-1]
        context.update({
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": bar.volume,
            "bar_date": bar.date.isoformat(),
        })

    # Add N (volatility) with calculation details
    if n_value:
        context["n"] = {
            "value": float(n_value.value),
            "calculated_at": n_value.calculated_at.isoformat() if n_value.calculated_at else None,
            "period": N_PERIOD,
            "smoothing": "wilders",
        }

    # Add Donchian channels
    if dc10:
        context["dc10"] = {"upper": float(dc10.upper), "lower": float(dc10.lower), "period": 10}
    if dc20:
        context["dc20"] = {"upper": float(dc20.upper), "lower": float(dc20.lower), "period": 20}
    if dc55:
        context["dc55"] = {"upper": float(dc55.upper), "lower": float(dc55.lower), "period": 55}

    return context


def build_position_context(
    position: Position,
    current_price: Decimal | None = None,
) -> dict:
    """Build position context for events.

    Args:
        position: Position model
        current_price: Current market price (for P&L calc)

    Returns:
        Position context dict
    """
    # Calculate P&L if we have current price
    unrealized_pnl = None
    unrealized_pnl_percent = None
    if current_price is not None:
        pnl_direction = 1 if position.direction.value == "LONG" else -1
        unrealized_pnl = float(
            (current_price - position.average_entry_price) * position.total_contracts * pnl_direction
        )
        if position.average_entry_price > 0:
            unrealized_pnl_percent = float(
                (current_price - position.average_entry_price) / position.average_entry_price * 100 * pnl_direction
            )

    # Calculate days held
    days_held = None
    if position.opened_at:
        days_held = (datetime.now().date() - position.opened_at.date()).days

    context = {
        "symbol": position.symbol,
        "direction": position.direction.value,
        "system": position.system.value,
        "initial_entry_price": float(position.initial_entry_price),
        "initial_entry_date": position.opened_at.isoformat() if position.opened_at else None,
        "initial_n": float(position.initial_n.value) if position.initial_n else None,
        "contracts": position.total_contracts,
        "units": position.total_units,
        "average_entry": float(position.average_entry_price),
        "current_stop": float(position.current_stop),
        "current_price": float(current_price) if current_price else None,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_pnl_percent": unrealized_pnl_percent,
        "days_held": days_held,
        "max_pyramids": MAX_UNITS_PER_MARKET,
        "can_pyramid": position.total_units < MAX_UNITS_PER_MARKET,
    }

    # Add pyramid levels
    if position.pyramid_levels:
        context["pyramid_levels"] = [
            {
                "level": p.level,
                "entry_price": float(p.entry_price),
                "contracts": p.contracts,
                "n_at_entry": float(p.n_at_entry),
            }
            for p in position.pyramid_levels
        ]

    # Add next pyramid trigger
    if position.total_units < MAX_UNITS_PER_MARKET:
        last_pyramid = position.pyramid_levels[-1] if position.pyramid_levels else None
        if last_pyramid:
            half_n = float(PYRAMID_INTERVAL_MULTIPLIER) * float(last_pyramid.n_at_entry)
            if position.direction.value == "LONG":
                trigger = float(last_pyramid.entry_price) + half_n
            else:
                trigger = float(last_pyramid.entry_price) - half_n
            context["next_pyramid"] = {
                "level": position.total_units + 1,
                "trigger_price": trigger,
                "trigger_calculation": f"{last_pyramid.entry_price} {'+'if position.direction.value == 'LONG' else '-'} (0.5 × {last_pyramid.n_at_entry}) = {trigger:.2f}",
            }

    return context


def build_account_context(
    equity: Decimal,
    buying_power: Decimal,
    notional_equity: Decimal | None = None,
    high_water: Decimal | None = None,
    units_total: int = 0,
    units_by_direction: dict | None = None,
    units_by_group: dict | None = None,
) -> dict:
    """Build account context for events.

    Args:
        equity: Actual account equity
        buying_power: Available buying power
        notional_equity: Notional equity for sizing (may differ due to Rule 5)
        high_water: High water mark for drawdown calculation
        units_total: Total units in portfolio
        units_by_direction: Units by direction (LONG/SHORT)
        units_by_group: Units by correlation group

    Returns:
        Account context dict
    """
    if notional_equity is None:
        notional_equity = equity

    context = {
        "equity_actual": float(equity),
        "equity_notional": float(notional_equity),
        "buying_power": float(buying_power),
    }

    # Add drawdown tracking if we have high water mark
    if high_water and high_water > 0:
        drawdown_pct = float((high_water - equity) / high_water * 100)
        context["equity_high_water"] = float(high_water)
        context["drawdown"] = {
            "current_percent": drawdown_pct,
            "threshold_percent": float(DRAWDOWN_THRESHOLD * 100),
            "reduction_percent": float(DRAWDOWN_REDUCTION * 100),
            "triggered": drawdown_pct >= float(DRAWDOWN_THRESHOLD * 100),
        }

    # Add position limits
    risk_pct = units_total * float(RISK_PER_TRADE) * 100
    context["limits"] = {
        "mode": "risk_cap" if USE_RISK_CAP_MODE else "unit_count",
        "units_total": units_total,
        "units_max": MAX_UNITS_TOTAL,
        "current_risk_percent": risk_pct,
        "max_risk_percent": float(MAX_TOTAL_RISK * 100),
        "max_per_market": MAX_UNITS_PER_MARKET,
        "max_correlated": MAX_UNITS_CORRELATED,
    }

    if units_by_direction:
        context["limits"]["units_by_direction"] = units_by_direction
    if units_by_group:
        context["limits"]["units_by_group"] = units_by_group

    return context


def build_sizing_context(
    price: Decimal,
    n_value: Decimal,
    equity_actual: Decimal,
    equity_notional: Decimal,
    direction: str,
    system: str,
    contracts: int,
    stop_price: Decimal,
) -> dict:
    """Build sizing context for entry/pyramid events.

    This context captures all inputs needed to replay the sizing calculation.

    Args:
        price: Entry price
        n_value: N (ATR) at entry
        equity_actual: Actual account equity
        equity_notional: Notional equity for sizing
        direction: "LONG" or "SHORT"
        system: "S1" or "S2"
        contracts: Calculated number of contracts
        stop_price: Calculated stop price

    Returns:
        Sizing context dict with full calculation details
    """
    risk_dollars = float(equity_notional * RISK_PER_TRADE)
    dollar_volatility = float(n_value)  # Point value = 1 for stocks
    raw_unit_size = risk_dollars / dollar_volatility if dollar_volatility > 0 else 0
    stop_distance = float(n_value * STOP_MULTIPLIER)
    position_value = float(price * contracts)

    return {
        # === INPUTS (The Five Questions) ===
        "price": float(price),
        "n_value": float(n_value),
        "equity_actual": float(equity_actual),
        "equity_notional": float(equity_notional),
        "system": system,
        "direction": direction,

        # === RULE PARAMETERS ===
        "risk_percent": float(RISK_PER_TRADE),
        "stop_multiplier": float(STOP_MULTIPLIER),
        "point_value": 1.0,
        "atr_period": N_PERIOD,

        # === INTERMEDIATE CALCULATIONS ===
        "risk_dollars": risk_dollars,
        "dollar_volatility": dollar_volatility,
        "raw_unit_size": raw_unit_size,
        "stop_distance": stop_distance,

        # === OUTPUTS ===
        "contracts": contracts,
        "position_value": position_value,
        "initial_stop": float(stop_price),

        # === VERIFICATION ===
        "formula": "contracts = floor((equity_notional × risk_percent) / (n_value × point_value))",
        "calculation": f"floor(({equity_notional} × {RISK_PER_TRADE}) / ({n_value} × 1)) = floor({raw_unit_size:.2f}) = {contracts}",
    }


def build_exit_context(
    reason: str,
    rule: str,
    trigger_type: str,
    trigger_price: Decimal,
    current_price: Decimal,
    position: Position,
    fill_price: Decimal | None = None,
) -> dict:
    """Build exit context for exit events.

    Args:
        reason: "stop_hit" or "breakout_exit"
        rule: "Rule 10", "Rule 13", or "Rule 14"
        trigger_type: "stop", "donchian_10", or "donchian_20"
        trigger_price: The stop or channel level that triggered
        current_price: Price when exit triggered
        position: The position being exited
        fill_price: Actual fill price (if filled)

    Returns:
        Exit context dict
    """
    pnl_direction = 1 if position.direction.value == "LONG" else -1

    context = {
        "reason": reason,
        "rule": rule,
        "trigger_type": trigger_type,
        "trigger_price": float(trigger_price),
        "current_price": float(current_price),
        "direction": position.direction.value,
        "contracts": position.total_contracts,
        "units": position.total_units,
        "entry_price": float(position.average_entry_price),
        "entry_date": position.opened_at.isoformat() if position.opened_at else None,
    }

    # Calculate P&L
    if fill_price:
        gross_pnl = float((fill_price - position.average_entry_price) * position.total_contracts * pnl_direction)
        context["fill_price"] = float(fill_price)
        context["pnl"] = {
            "gross_pnl": gross_pnl,
            "slippage": float(fill_price - current_price) * (-1 if position.direction.value == "SHORT" else 1),
            "calculation": f"({position.average_entry_price} - {fill_price}) × {position.total_contracts} = {gross_pnl:.2f}",
        }

    # Calculate hold duration
    if position.opened_at:
        context["hold_duration_days"] = (datetime.now().date() - position.opened_at.date()).days

    return context


def build_pyramid_context(
    level: int,
    position: Position,
    trigger_price: Decimal,
    current_price: Decimal,
    n_current: Decimal,
    new_contracts: int,
    new_stop: Decimal,
) -> dict:
    """Build pyramid context for pyramid events.

    Args:
        level: Pyramid level (2, 3, or 4)
        position: Current position before pyramid
        trigger_price: Price that triggered pyramid
        current_price: Current market price
        n_current: Current N value
        new_contracts: Additional contracts being added
        new_stop: New stop price after pyramid

    Returns:
        Pyramid context dict
    """
    last_pyramid = position.pyramid_levels[-1] if position.pyramid_levels else None

    context = {
        "level": level,
        "direction": position.direction.value,
        "trigger_price": float(trigger_price),
        "current_price": float(current_price),
        "n_current": float(n_current),
        "new_contracts": new_contracts,
        "contracts_before": position.total_contracts,
        "contracts_after": position.total_contracts + new_contracts,
        "units_after": level,
        "max_units": MAX_UNITS_PER_MARKET,
        "stop_before": float(position.current_stop),
        "stop_after": float(new_stop),
        "pyramid_interval": float(PYRAMID_INTERVAL_MULTIPLIER),
    }

    if last_pyramid:
        context["last_entry_price"] = float(last_pyramid.entry_price)
        context["n_at_last_entry"] = float(last_pyramid.n_at_entry)
        half_n = float(PYRAMID_INTERVAL_MULTIPLIER * last_pyramid.n_at_entry)
        op = "+" if position.direction.value == "LONG" else "-"
        context["trigger_calculation"] = f"{last_pyramid.entry_price} {op} (0.5 × {last_pyramid.n_at_entry}) = {trigger_price:.2f}"

    # Stop calculation
    stop_op = "-" if position.direction.value == "LONG" else "+"
    context["stop_calculation"] = f"{current_price} {stop_op} (2 × {n_current}) = {new_stop:.2f}"

    return context


def build_signal_context(
    direction: str,
    system: str,
    trigger_price: Decimal,
    signal_price: Decimal,
    channel_period: int,
    correlation_group: str | None = None,
) -> dict:
    """Build signal context for signal detection events.

    Args:
        direction: "LONG" or "SHORT"
        system: "S1" or "S2"
        trigger_price: Donchian level that triggered
        signal_price: Price when signal detected
        channel_period: 20 for S1, 55 for S2
        correlation_group: Correlation group for limit checking

    Returns:
        Signal context dict
    """
    return {
        "direction": direction,
        "system": system,
        "trigger_price": float(trigger_price),
        "signal_price": float(signal_price),
        "channel_period": channel_period,
        "correlation_group": correlation_group,
        "breakout": {
            "type": "high" if direction == "LONG" else "low",
            "channel_value": float(trigger_price),
        },
    }


def build_filter_context(
    s1_filter_applied: bool = False,
    s1_filter_passed: bool = True,
    s1_filter_reason: str | None = None,
    last_s1_trade: dict | None = None,
    limit_market_current: int = 0,
    limit_market_passed: bool = True,
    limit_correlated_group: str | None = None,
    limit_correlated_current: int = 0,
    limit_correlated_passed: bool = True,
    limit_total_current: int = 0,
    limit_total_passed: bool = True,
    limit_mode: str = "risk_cap",
    current_risk_percent: float = 0,
) -> dict:
    """Build filter context for signal evaluation events.

    Args:
        s1_filter_applied: Whether S1 filter was checked
        s1_filter_passed: Whether S1 filter passed
        s1_filter_reason: Reason if S1 filter failed
        last_s1_trade: Details of last S1 trade if filter applied
        limit_market_current: Current units in this market
        limit_market_passed: Whether market limit passed
        limit_correlated_group: Correlation group name
        limit_correlated_current: Current units in group
        limit_correlated_passed: Whether correlated limit passed
        limit_total_current: Total units in portfolio
        limit_total_passed: Whether total limit passed
        limit_mode: "risk_cap" or "unit_count"
        current_risk_percent: Current total risk as percentage

    Returns:
        Filter context dict
    """
    # Determine which filter blocked (if any)
    all_passed = s1_filter_passed and limit_market_passed and limit_correlated_passed and limit_total_passed
    blocking_filter = None
    if not s1_filter_passed:
        blocking_filter = "s1_filter"
    elif not limit_market_passed:
        blocking_filter = "limit_market"
    elif not limit_correlated_passed:
        blocking_filter = "limit_correlated"
    elif not limit_total_passed:
        blocking_filter = "limit_total"

    context = {
        "s1_filter": {
            "applied": s1_filter_applied,
            "passed": s1_filter_passed,
            "reason": s1_filter_reason,
        },
        "limit_market": {
            "current": limit_market_current,
            "max": MAX_UNITS_PER_MARKET,
            "passed": limit_market_passed,
        },
        "limit_correlated": {
            "group": limit_correlated_group,
            "current": limit_correlated_current,
            "max": MAX_UNITS_CORRELATED,
            "passed": limit_correlated_passed,
        },
        "limit_total": {
            "mode": limit_mode,
            "current_units": limit_total_current,
            "max_units": MAX_UNITS_TOTAL,
            "current_risk_percent": current_risk_percent,
            "max_risk_percent": float(MAX_TOTAL_RISK * 100),
            "passed": limit_total_passed,
        },
        "all_passed": all_passed,
        "blocking_filter": blocking_filter,
    }

    if last_s1_trade:
        context["s1_filter"]["last_s1_trade"] = last_s1_trade

    return context
