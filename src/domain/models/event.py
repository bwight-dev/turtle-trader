"""Event models for Turtle Trading audit trail.

This module defines the event streaming architecture for capturing
every trading decision with full context. Events are immutable
records that enable:

1. Complete audit trail - know exactly what happened and when
2. Full state capture - snapshot all variables at decision time
3. Causal chain - link events to understand how we got here
4. Math replay - verify any calculation from captured inputs

See docs/plans/2026-02-12-event-streaming-design.md for full design.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """All possible event types in the trading system.

    Scanner Events:
        SCANNER_STARTED: Scanner run begins
        SIGNAL_DETECTED: Raw breakout found
        SIGNAL_EVALUATED: Filters applied, decision made
        ENTRY_ATTEMPTED: Order submitted for new position
        ENTRY_FILLED: Entry order filled
        SCANNER_COMPLETED: Scanner run ends

    Monitor Events:
        MONITOR_STARTED: Monitor cycle begins
        POSITION_CHECKED: Position evaluated against rules
        EXIT_ATTEMPTED: Exit order submitted
        EXIT_FILLED: Exit order filled
        PYRAMID_ATTEMPTED: Pyramid order submitted
        PYRAMID_FILLED: Pyramid order filled
        STOP_MODIFIED: Stop price changed (Rule 12)
        MONITOR_COMPLETED: Monitor cycle ends

    System Events:
        CONNECTION_LOST: Broker connection dropped
        CONNECTION_RESTORED: Broker connection restored
        ERROR_OCCURRED: Unexpected error
    """

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
    """All possible outcomes for events.

    Each event has an outcome indicating what happened.
    Outcomes are grouped by the event types they apply to.
    """

    # === Signal Detection Outcomes ===
    BREAKOUT_20 = "breakout_20"      # S1 20-day breakout (Rule 6)
    BREAKOUT_55 = "breakout_55"      # S2 55-day breakout (Rule 8)
    NO_BREAKOUT = "no_breakout"      # No signal detected

    # === Signal Evaluation Outcomes ===
    APPROVED = "approved"            # Signal passed all filters
    FILTERED_S1 = "filtered_s1"      # Rule 7: last S1 was winner
    FILTERED_S2_REDUNDANT = "filtered_s2_redundant"  # S2 suppressed by S1
    LIMIT_MARKET = "limit_market"    # 4 units per market max
    LIMIT_CORRELATED = "limit_correlated"  # 6 units in group max
    LIMIT_TOTAL = "limit_total"      # 12 units total (original mode)
    LIMIT_RISK_CAP = "limit_risk_cap"  # 20% risk cap (Rule 17)
    ALREADY_IN_POSITION = "already_in_position"  # Already have position
    CAPITAL_CAP_EXCEEDED = "capital_cap_exceeded"  # Position would exceed max capital %

    # === Order Submission Outcomes ===
    SUBMITTED = "submitted"          # Order sent to broker
    INSUFFICIENT_CASH = "insufficient_cash"  # Not enough buying power
    INSUFFICIENT_SHARES = "insufficient_shares"  # Can't borrow for short
    REJECTED = "rejected"            # Broker rejected order
    MARKET_CLOSED = "market_closed"  # Market not open
    DELAYED_FAST_MARKET = "delayed_fast_market"  # Rule 16b: waited for stability

    # === Order Fill Outcomes ===
    FILLED = "filled"                # Full fill
    FILLED_AT_GAP = "filled_at_gap"  # Rule 16a: executed at gap open
    PARTIAL_FILL = "partial_fill"    # Partial fill
    CANCELLED = "cancelled"          # Order cancelled
    EXPIRED = "expired"              # Order expired

    # === Position Check Outcomes ===
    HOLD = "hold"                    # No action needed
    EXIT_STOP_TRIGGERED = "exit_stop_triggered"  # Rule 10: 2N stop hit
    EXIT_BREAKOUT_TRIGGERED = "exit_breakout_triggered"  # Rule 13/14: exit channel
    PYRAMID_TRIGGERED = "pyramid_triggered"  # Rule 11: +1/2N level reached

    # === Stop Modification Outcomes ===
    EXECUTED = "executed"            # Rule 12: stops moved successfully
    FAILED = "failed"                # Stop modification failed

    # === Connection Outcomes ===
    RECONNECTED = "reconnected"      # Successfully reconnected
    RECONNECT_FAILED = "reconnect_failed"  # Reconnect attempt failed

    # === Error Outcomes ===
    RECOVERED = "recovered"          # Error handled, continuing
    FATAL = "fatal"                  # Unrecoverable, stopping

    # === Run Completion Outcomes ===
    COMPLETED = "completed"          # Run finished successfully
    COMPLETED_WITH_ERRORS = "completed_with_errors"  # Finished with some errors


class Event(BaseModel):
    """An immutable event record capturing a trading decision.

    Events form the audit trail for the trading system. Each event
    captures the full state at decision time, enabling:

    - Replay of any calculation
    - Understanding causal chains
    - Debugging trading decisions
    - Performance analysis

    Attributes:
        id: Unique event identifier
        timestamp: When the event occurred (UTC)
        event_type: Type of event (see EventType)
        outcome: What happened (see OutcomeType)
        outcome_reason: Human-readable explanation
        run_id: Links all events in a single run
        sequence: Order within run (1, 2, 3, ...)
        symbol: Market symbol (None for system events)
        context: Full state snapshot as JSON
        source: "scanner" or "monitor"
        dry_run: True if this was a simulation
    """

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

    class Config:
        """Pydantic config."""

        frozen = True  # Events are immutable


# =============================================================================
# Context Type Hints (for documentation and IDE support)
# =============================================================================

class MarketContext(BaseModel):
    """Market data context for events.

    Captures price, volatility (N), and Donchian channels.
    """

    symbol: str
    price: Decimal
    bid: Decimal | None = None
    ask: Decimal | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    volume: int | None = None
    bar_date: str | None = None

    # N (volatility)
    n_value: Decimal | None = None
    n_period: int = 20
    n_smoothing: str = "wilders"
    n_prev: Decimal | None = None
    n_true_range: Decimal | None = None
    n_calculation: str | None = None

    # Donchian channels
    dc10_high: Decimal | None = None
    dc10_low: Decimal | None = None
    dc20_high: Decimal | None = None
    dc20_low: Decimal | None = None
    dc55_high: Decimal | None = None
    dc55_low: Decimal | None = None

    # Data source
    source: str | None = None  # yahoo, ibkr, composite


class SizingContext(BaseModel):
    """Position sizing context for events.

    Captures all inputs needed to replay the sizing calculation.
    The Five Questions: Price, N, Equity, System, Risk
    """

    # === INPUTS (The Five Questions) ===
    price: Decimal
    n_value: Decimal
    equity_actual: Decimal
    equity_notional: Decimal
    system: str  # S1 or S2
    direction: str  # LONG or SHORT

    # === RULE PARAMETERS ===
    risk_percent: Decimal = Decimal("0.005")
    stop_multiplier: Decimal = Decimal("2")
    point_value: Decimal = Decimal("1")
    atr_period: int = 20

    # === INTERMEDIATE CALCULATIONS ===
    risk_dollars: Decimal | None = None
    dollar_volatility: Decimal | None = None
    raw_unit_size: Decimal | None = None
    stop_distance: Decimal | None = None

    # === OUTPUTS ===
    contracts: int | None = None
    position_value: Decimal | None = None
    initial_stop: Decimal | None = None

    # === VERIFICATION ===
    formula: str | None = None
    calculation: str | None = None


class PositionContext(BaseModel):
    """Position state context for events."""

    symbol: str
    direction: str
    system: str
    initial_entry_price: Decimal
    initial_entry_date: str
    initial_n: Decimal
    contracts: int
    units: int
    average_entry: Decimal
    current_stop: Decimal
    stop_calculation: str | None = None
    current_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_pnl_percent: Decimal | None = None
    days_held: int | None = None
    next_pyramid_trigger: Decimal | None = None
    next_pyramid_calculation: str | None = None


class AccountContext(BaseModel):
    """Account state context for events."""

    equity_actual: Decimal
    equity_high_water: Decimal | None = None
    buying_power: Decimal
    equity_notional: Decimal

    # Drawdown (Rule 5)
    drawdown_current_percent: Decimal | None = None
    drawdown_threshold_percent: Decimal = Decimal("10")
    drawdown_reduction_percent: Decimal = Decimal("20")
    drawdown_triggered: bool = False

    # Position limits
    limits_mode: str = "risk_cap"  # risk_cap or unit_count
    units_total: int = 0
    units_max: int = 12
    current_risk_percent: Decimal | None = None
    max_risk_percent: Decimal = Decimal("20")


class PyramidContext(BaseModel):
    """Pyramid event context."""

    level: int
    direction: str
    last_entry_price: Decimal
    n_at_last_entry: Decimal
    pyramid_interval: Decimal = Decimal("0.5")
    trigger_price: Decimal
    trigger_calculation: str | None = None
    current_price: Decimal
    n_current: Decimal
    new_contracts: int
    contracts_before: int
    contracts_after: int
    units_after: int
    max_units: int = 4
    stop_before: Decimal
    stop_after: Decimal
    stop_calculation: str | None = None


class ExitContext(BaseModel):
    """Exit event context."""

    reason: str  # stop_hit, breakout_exit
    rule: str  # Rule 10, Rule 13, Rule 14
    trigger_type: str  # stop, donchian_10, donchian_20
    trigger_price: Decimal
    current_price: Decimal
    direction: str
    contracts: int
    units: int
    entry_price: Decimal
    entry_date: str
    fill_price: Decimal | None = None
    gross_pnl: Decimal | None = None
    net_pnl: Decimal | None = None
    pnl_percent: Decimal | None = None
    pnl_in_n: Decimal | None = None  # R-multiple
    hold_duration_days: int | None = None
    pnl_calculation: str | None = None
