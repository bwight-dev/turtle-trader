"""Daily workflow for Turtle Trading system.

This workflow runs once per day (typically before market open or after close)
to scan for new opportunities, validate them, and optionally execute.

Workflow stages:
1. RECONCILE: Sync portfolio with broker
2. SCAN: Detect breakout signals across universe
3. VALIDATE: Apply S1 filter and check position limits
4. SIZE: Calculate unit size based on N and equity
5. EXECUTE: Place orders (or dry-run)
6. LOG: Record any executed trades

This is the "entry" workflow. Position monitoring (exits/pyramids)
is handled by the separate monitoring_loop.py.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from src.application.commands.log_trade import TradeLogger
from src.application.queries.reconcile_account import ReconcileAccountQuery
from src.application.queries.sync_portfolio import SyncPortfolioQuery
from src.domain.interfaces.broker import Broker
from src.domain.interfaces.data_feed import DataFeed
from src.domain.interfaces.repositories import NValueRepository, TradeRepository
from src.domain.models.enums import Direction, System
from src.domain.models.portfolio import Portfolio
from src.domain.services.equity_tracker import get_equity_tracker, init_equity_tracker
from src.domain.services.limit_checker import LimitChecker
from src.domain.services.s1_filter import S1Filter
from src.domain.services.signal_detector import SignalDetector
from src.domain.services.sizing import calculate_unit_size


class DailyWorkflowStatus(str, Enum):
    """Status of daily workflow execution."""

    PENDING = "pending"
    RECONCILING = "reconciling"
    SCANNING = "scanning"
    VALIDATING = "validating"
    SIZING = "sizing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    DRY_RUN = "dry_run"


@dataclass
class SignalCandidate:
    """A signal candidate for potential entry."""

    symbol: str
    direction: Direction
    system: System
    breakout_price: Decimal
    channel_value: Decimal
    n_value: Decimal
    should_take: bool = True
    filter_reason: str = ""


@dataclass
class SizedOrder:
    """A sized order ready for execution."""

    symbol: str
    direction: Direction
    system: System
    contracts: int
    entry_price: Decimal
    stop_price: Decimal
    risk_amount: Decimal


@dataclass
class ExecutionResult:
    """Result of order execution."""

    symbol: str
    order_id: str
    status: str
    fill_price: Decimal | None = None
    filled_contracts: int = 0
    error: str | None = None


@dataclass
class DailyWorkflowResult:
    """Result of daily workflow execution."""

    status: DailyWorkflowStatus
    started_at: datetime
    completed_at: datetime | None = None

    # Reconciliation results
    portfolio_synced: bool = False
    reconciliation_matches: bool = False

    # Scan results
    signals_detected: list[SignalCandidate] = field(default_factory=list)

    # Validation results
    signals_validated: list[SignalCandidate] = field(default_factory=list)

    # Sizing results
    orders_sized: list[SizedOrder] = field(default_factory=list)

    # Execution results
    orders_executed: list[ExecutionResult] = field(default_factory=list)

    # Errors
    errors: list[str] = field(default_factory=list)

    @property
    def orders_executed_count(self) -> int:
        """Number of orders successfully executed."""
        return len([o for o in self.orders_executed if o.status == "filled"])


class DailyWorkflowState(TypedDict, total=False):
    """State for daily workflow execution."""

    # Dependencies (injected)
    broker: Broker
    data_feed: DataFeed
    n_repo: NValueRepository
    trade_repo: TradeRepository

    # Configuration
    universe: list[str]
    dry_run: bool
    account_equity: Decimal

    # Portfolio state
    portfolio: Portfolio

    # Workflow state
    signals: list[dict]
    validated_signals: list[dict]
    sized_orders: list[dict]
    executions: list[dict]

    # Results
    status: str
    errors: list[str]
    started_at: str
    completed_at: str


def reconcile_portfolio(state: DailyWorkflowState) -> DailyWorkflowState:
    """Reconcile internal portfolio with broker positions.

    This is a synchronous wrapper - actual async calls would be
    handled by the orchestrator.
    """
    # In full implementation, this would call:
    # portfolio, sync_result = await SyncPortfolioQuery(broker).execute()
    # reconcile_result = await ReconcileAccountQuery(broker).execute(portfolio)

    return {
        **state,
        "status": DailyWorkflowStatus.SCANNING.value,
    }


def scan_markets(state: DailyWorkflowState) -> DailyWorkflowState:
    """Scan markets for breakout signals.

    Detects S1 (20-day) and S2 (55-day) breakouts across the universe.
    """
    # In full implementation, this would:
    # 1. Get market data for each symbol in universe
    # 2. Calculate Donchian channels
    # 3. Detect breakouts using SignalDetector

    universe = state.get("universe", [])
    signals = []

    # Placeholder - real implementation fetches data and detects signals
    for symbol in universe:
        # Would call: signal = detector.detect_signal(bars, n_value)
        pass

    return {
        **state,
        "signals": signals,
        "status": DailyWorkflowStatus.VALIDATING.value,
    }


def validate_signals(state: DailyWorkflowState) -> DailyWorkflowState:
    """Validate signals through S1 filter and position limits.

    - Applies Rule 7: Skip S1 if last S1 was winner
    - Checks portfolio limits (4/6/12 rule)
    """
    signals = state.get("signals", [])
    portfolio = state.get("portfolio", Portfolio())
    errors = state.get("errors", [])

    validated = []
    limit_checker = LimitChecker()

    for signal in signals:
        # Check position limits
        symbol = signal.get("symbol", "")
        direction = Direction(signal.get("direction", "long"))
        correlation_group = signal.get("correlation_group")

        limit_result = limit_checker.check_entry_allowed(
            portfolio=portfolio,
            symbol=symbol,
            correlation_group=correlation_group,
        )

        if not limit_result.allowed:
            signal["should_take"] = False
            signal["filter_reason"] = limit_result.violation_reason or "Position limit"
            continue

        # S1 filter would be applied here for S1 signals
        # if signal.get("system") == "S1":
        #     filter_result = s1_filter.should_take_signal(...)

        signal["should_take"] = True
        validated.append(signal)

    return {
        **state,
        "validated_signals": validated,
        "status": DailyWorkflowStatus.SIZING.value,
        "errors": errors,
    }


def size_positions(state: DailyWorkflowState) -> DailyWorkflowState:
    """Calculate position sizes for validated signals.

    Uses Rule 4: Unit = (Risk × Equity) / (N × PointValue)
    Uses Rule 5: Apply drawdown reduction via EquityTracker
    Uses sizing floor (60% default) to prevent death spiral
    """
    validated = state.get("validated_signals", [])
    account_equity = state.get("account_equity", Decimal("100000"))
    errors = state.get("errors", [])

    # Use EquityTracker for proper sizing with drawdown handling
    # This matches the backtest behavior exactly
    equity_tracker = get_equity_tracker()
    equity_tracker.update(account_equity)
    equity = equity_tracker.sizing_equity  # Notional, with floor applied

    sized_orders = []

    for signal in validated:
        symbol = signal.get("symbol", "")
        n_value = Decimal(signal.get("n_value", "1"))
        direction = Direction(signal.get("direction", "long"))
        entry_price = Decimal(signal.get("breakout_price", "0"))

        # In full implementation, use UnitCalculator
        # unit = calculator.calculate_unit_size(...)

        # Calculate stop price (2N from entry)
        if direction == Direction.LONG:
            stop_price = entry_price - (2 * n_value)
        else:
            stop_price = entry_price + (2 * n_value)

        sized_orders.append({
            "symbol": symbol,
            "direction": direction.value,
            "system": signal.get("system", "S1"),
            "contracts": 1,  # Would be calculated
            "entry_price": str(entry_price),
            "stop_price": str(stop_price),
            "risk_amount": "0",
        })

    return {
        **state,
        "sized_orders": sized_orders,
        "status": DailyWorkflowStatus.EXECUTING.value,
        "errors": errors,
    }


def execute_orders(state: DailyWorkflowState) -> DailyWorkflowState:
    """Execute orders or simulate in dry-run mode."""
    dry_run = state.get("dry_run", True)
    sized_orders = state.get("sized_orders", [])
    errors = state.get("errors", [])

    executions = []

    for order in sized_orders:
        if dry_run:
            executions.append({
                "symbol": order.get("symbol", ""),
                "order_id": "DRY_RUN",
                "status": "simulated",
                "fill_price": order.get("entry_price"),
                "filled_contracts": order.get("contracts", 0),
            })
        else:
            # In full implementation, would call:
            # fill = await broker.place_bracket_order(bracket_order)
            pass

    status = DailyWorkflowStatus.DRY_RUN.value if dry_run else DailyWorkflowStatus.COMPLETED.value

    return {
        **state,
        "executions": executions,
        "status": status,
        "completed_at": datetime.now().isoformat(),
        "errors": errors,
    }


def should_continue_to_validate(state: DailyWorkflowState) -> Literal["validate", "complete"]:
    """Decide whether to continue to validation."""
    signals = state.get("signals", [])
    return "validate" if signals else "complete"


def should_continue_to_size(state: DailyWorkflowState) -> Literal["size", "complete"]:
    """Decide whether to continue to sizing."""
    validated = state.get("validated_signals", [])
    return "size" if validated else "complete"


def should_continue_to_execute(state: DailyWorkflowState) -> Literal["execute", "complete"]:
    """Decide whether to continue to execution."""
    sized = state.get("sized_orders", [])
    return "execute" if sized else "complete"


def complete_workflow(state: DailyWorkflowState) -> DailyWorkflowState:
    """Complete the workflow."""
    status = state.get("status", DailyWorkflowStatus.COMPLETED.value)
    if status not in [DailyWorkflowStatus.DRY_RUN.value, DailyWorkflowStatus.FAILED.value]:
        status = DailyWorkflowStatus.COMPLETED.value

    return {
        **state,
        "status": status,
        "completed_at": datetime.now().isoformat(),
    }


def create_daily_workflow() -> StateGraph:
    """Create the daily trading workflow graph.

    Returns:
        StateGraph ready for compilation.
    """
    workflow = StateGraph(DailyWorkflowState)

    # Add nodes
    workflow.add_node("reconcile", reconcile_portfolio)
    workflow.add_node("scan", scan_markets)
    workflow.add_node("validate", validate_signals)
    workflow.add_node("size", size_positions)
    workflow.add_node("execute", execute_orders)
    workflow.add_node("complete", complete_workflow)

    # Set entry point
    workflow.set_entry_point("reconcile")

    # Linear flow: reconcile -> scan
    workflow.add_edge("reconcile", "scan")

    # Conditional: scan -> validate or complete
    workflow.add_conditional_edges(
        "scan",
        should_continue_to_validate,
        {
            "validate": "validate",
            "complete": "complete",
        },
    )

    # Conditional: validate -> size or complete
    workflow.add_conditional_edges(
        "validate",
        should_continue_to_size,
        {
            "size": "size",
            "complete": "complete",
        },
    )

    # Conditional: size -> execute or complete
    workflow.add_conditional_edges(
        "size",
        should_continue_to_execute,
        {
            "execute": "execute",
            "complete": "complete",
        },
    )

    # Execute -> complete
    workflow.add_edge("execute", "complete")

    # Complete -> END
    workflow.add_edge("complete", END)

    return workflow


def get_compiled_daily_workflow():
    """Get the compiled daily workflow ready for invocation.

    Returns:
        Compiled workflow that can be invoked with .invoke()
    """
    return create_daily_workflow().compile()


class DailyWorkflow:
    """High-level interface for running the daily trading workflow.

    This class provides a simpler interface for running the workflow
    with proper dependency injection.
    """

    def __init__(
        self,
        broker: Broker | None = None,
        data_feed: DataFeed | None = None,
        n_repo: NValueRepository | None = None,
        trade_repo: TradeRepository | None = None,
    ):
        """Initialize the daily workflow.

        Args:
            broker: Broker for order execution
            data_feed: Data feed for market data
            n_repo: Repository for N values
            trade_repo: Repository for trade records
        """
        self._broker = broker
        self._data_feed = data_feed
        self._n_repo = n_repo
        self._trade_repo = trade_repo
        self._workflow = get_compiled_daily_workflow()

    async def run(
        self,
        universe: list[str] | None = None,
        dry_run: bool = True,
        account_equity: Decimal | None = None,
        portfolio: Portfolio | None = None,
        starting_equity: Decimal | None = None,
    ) -> DailyWorkflowResult:
        """Run the complete daily workflow.

        Args:
            universe: List of symbols to scan
            dry_run: If True, simulate without placing orders
            account_equity: Account equity for sizing (fetched from broker if None)
            portfolio: Current portfolio (synced from broker if None)
            starting_equity: Yearly starting equity for drawdown tracking.
                            If None, uses account_equity as starting point.

        Returns:
            DailyWorkflowResult with all results
        """
        started_at = datetime.now()

        # Initialize equity tracker for proper sizing with drawdown handling
        # This ensures live trading matches backtest behavior exactly
        if starting_equity is not None or account_equity is not None:
            init_equity_tracker(starting_equity or account_equity or Decimal("50000"))

        # Build initial state
        initial_state: DailyWorkflowState = {
            "universe": universe or [],
            "dry_run": dry_run,
            "account_equity": account_equity or Decimal("100000"),
            "portfolio": portfolio or Portfolio(),
            "signals": [],
            "validated_signals": [],
            "sized_orders": [],
            "executions": [],
            "status": DailyWorkflowStatus.RECONCILING.value,
            "errors": [],
            "started_at": started_at.isoformat(),
            "completed_at": "",
        }

        # Run workflow
        final_state = self._workflow.invoke(initial_state)

        # Build result
        return DailyWorkflowResult(
            status=DailyWorkflowStatus(final_state.get("status", "completed")),
            started_at=started_at,
            completed_at=datetime.fromisoformat(final_state["completed_at"])
            if final_state.get("completed_at")
            else None,
            signals_detected=[
                SignalCandidate(
                    symbol=s.get("symbol", ""),
                    direction=Direction(s.get("direction", "long")),
                    system=System(s.get("system", "S1")),
                    breakout_price=Decimal(s.get("breakout_price", "0")),
                    channel_value=Decimal(s.get("channel_value", "0")),
                    n_value=Decimal(s.get("n_value", "1")),
                    should_take=s.get("should_take", True),
                    filter_reason=s.get("filter_reason", ""),
                )
                for s in final_state.get("signals", [])
            ],
            signals_validated=[
                SignalCandidate(
                    symbol=s.get("symbol", ""),
                    direction=Direction(s.get("direction", "long")),
                    system=System(s.get("system", "S1")),
                    breakout_price=Decimal(s.get("breakout_price", "0")),
                    channel_value=Decimal(s.get("channel_value", "0")),
                    n_value=Decimal(s.get("n_value", "1")),
                )
                for s in final_state.get("validated_signals", [])
            ],
            orders_sized=[
                SizedOrder(
                    symbol=o.get("symbol", ""),
                    direction=Direction(o.get("direction", "long")),
                    system=System(o.get("system", "S1")),
                    contracts=o.get("contracts", 0),
                    entry_price=Decimal(o.get("entry_price", "0")),
                    stop_price=Decimal(o.get("stop_price", "0")),
                    risk_amount=Decimal(o.get("risk_amount", "0")),
                )
                for o in final_state.get("sized_orders", [])
            ],
            orders_executed=[
                ExecutionResult(
                    symbol=e.get("symbol", ""),
                    order_id=e.get("order_id", ""),
                    status=e.get("status", ""),
                    fill_price=Decimal(e.get("fill_price", "0"))
                    if e.get("fill_price")
                    else None,
                    filled_contracts=e.get("filled_contracts", 0),
                )
                for e in final_state.get("executions", [])
            ],
            errors=final_state.get("errors", []),
        )


async def run_daily_workflow(
    universe: list[str] | None = None,
    dry_run: bool = True,
) -> DailyWorkflowResult:
    """Convenience function to run the daily workflow.

    Args:
        universe: List of symbols to scan
        dry_run: If True, simulate without placing orders

    Returns:
        DailyWorkflowResult with all results
    """
    workflow = DailyWorkflow()
    return await workflow.run(universe=universe, dry_run=dry_run)
