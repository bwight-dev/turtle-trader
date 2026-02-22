"""LangGraph workflow for Turtle Trading lifecycle.

This workflow orchestrates the trading process:
SCAN → VALIDATE → SIZE → EXECUTE → MONITOR

Each state performs a specific function:
- SCAN: Detect breakout signals across universe
- VALIDATE: Apply S1 filter and check position limits
- SIZE: Calculate unit size based on N and equity
- EXECUTE: Place orders (or dry-run)
- MONITOR: Check stops and pyramid triggers
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph


class WorkflowStatus(str, Enum):
    """Status of workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DRY_RUN = "dry_run"


class SignalInfo(TypedDict, total=False):
    """Information about a detected signal."""

    symbol: str
    direction: str
    system: str
    breakout_price: str
    channel_value: str
    should_take: bool
    filter_reason: str


class SizeInfo(TypedDict, total=False):
    """Information about position sizing."""

    symbol: str
    contracts: int
    stop_price: str
    risk_amount: str


class ExecutionInfo(TypedDict, total=False):
    """Information about order execution."""

    symbol: str
    order_id: str
    status: str
    filled_price: str
    filled_contracts: int


class MonitorAction(TypedDict, total=False):
    """Action from position monitoring."""

    symbol: str
    action: str  # hold, pyramid, exit_stop, exit_breakout
    reason: str


class WorkflowState(TypedDict, total=False):
    """State for the Turtle Trading workflow."""

    # Configuration
    universe: list[str]
    dry_run: bool

    # Scan state
    signals: list[SignalInfo]
    scan_errors: list[str]

    # Validation state
    validated_signals: list[SignalInfo]
    validation_errors: list[str]

    # Sizing state
    sized_orders: list[SizeInfo]
    sizing_errors: list[str]

    # Execution state
    executions: list[ExecutionInfo]
    execution_errors: list[str]

    # Monitor state
    monitor_actions: list[MonitorAction]
    monitor_errors: list[str]

    # Workflow metadata
    status: str
    started_at: str
    completed_at: str
    error: str


def scan_markets(state: WorkflowState) -> WorkflowState:
    """Scan markets for breakout signals.

    Detects S1 (20-day) and S2 (55-day) breakouts across the universe.
    """
    # In real implementation, this would use MarketScanner
    # For skeleton, we just pass through

    return {
        **state,
        "signals": state.get("signals", []),
        "scan_errors": [],
    }


def validate_signals(state: WorkflowState) -> WorkflowState:
    """Validate signals through S1 filter and position limits.

    - Applies Rule 7: Skip S1 if last S1 was winner
    - Checks portfolio limits (4/6/12 rule)
    """
    signals = state.get("signals", [])

    # In real implementation, apply S1Filter and LimitChecker
    validated = [s for s in signals if s.get("should_take", True)]

    return {
        **state,
        "validated_signals": validated,
        "validation_errors": [],
    }


def size_positions(state: WorkflowState) -> WorkflowState:
    """Calculate position sizes for validated signals.

    Uses Rule 4: Unit = (Risk × Equity) / (N × PointValue)
    Uses Rule 5: Apply drawdown reduction if applicable
    """
    validated = state.get("validated_signals", [])

    # In real implementation, use calculate_unit_size
    sized = []
    for signal in validated:
        sized.append(
            SizeInfo(
                symbol=signal.get("symbol", ""),
                contracts=0,  # Would be calculated
                stop_price="0",
                risk_amount="0",
            )
        )

    return {
        **state,
        "sized_orders": sized,
        "sizing_errors": [],
    }


def execute_orders(state: WorkflowState) -> WorkflowState:
    """Execute orders or simulate in dry-run mode.

    In dry-run mode, logs what would happen without placing orders.
    """
    dry_run = state.get("dry_run", True)
    sized = state.get("sized_orders", [])

    executions = []
    for order in sized:
        if dry_run:
            executions.append(
                ExecutionInfo(
                    symbol=order.get("symbol", ""),
                    order_id="DRY_RUN",
                    status="simulated",
                    filled_price="0",
                    filled_contracts=0,
                )
            )
        else:
            # In real implementation, use Broker interface
            pass

    status = WorkflowStatus.DRY_RUN.value if dry_run else WorkflowStatus.RUNNING.value

    return {
        **state,
        "executions": executions,
        "execution_errors": [],
        "status": status,
    }


def monitor_positions(state: WorkflowState) -> WorkflowState:
    """Monitor open positions for stops and pyramid triggers.

    Priority order (Rule from Position Monitor spec):
    1. Stop hit (2N hard stop) → EXIT_STOP
    2. Breakout exit (10/20-day) → EXIT_BREAKOUT
    3. Pyramid trigger (+½N level) → PYRAMID
    4. No action → HOLD
    """
    # In real implementation, use PositionMonitor

    return {
        **state,
        "monitor_actions": [],
        "monitor_errors": [],
        "status": WorkflowStatus.COMPLETED.value,
        "completed_at": datetime.now().isoformat(),
    }


def should_continue_to_validate(state: WorkflowState) -> Literal["validate", "end"]:
    """Decide whether to continue to validation."""
    signals = state.get("signals", [])
    if not signals:
        return "end"
    return "validate"


def should_continue_to_size(state: WorkflowState) -> Literal["size", "monitor"]:
    """Decide whether to continue to sizing."""
    validated = state.get("validated_signals", [])
    if not validated:
        return "monitor"
    return "size"


def should_continue_to_execute(state: WorkflowState) -> Literal["execute", "monitor"]:
    """Decide whether to continue to execution."""
    sized = state.get("sized_orders", [])
    if not sized:
        return "monitor"
    return "execute"


def create_workflow() -> StateGraph:
    """Create the Turtle Trading workflow graph.

    Returns:
        Compiled StateGraph ready for execution.
    """
    # Create the graph
    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("scan", scan_markets)
    workflow.add_node("validate", validate_signals)
    workflow.add_node("size", size_positions)
    workflow.add_node("execute", execute_orders)
    workflow.add_node("monitor", monitor_positions)

    # Set entry point
    workflow.set_entry_point("scan")

    # Add conditional edges
    workflow.add_conditional_edges(
        "scan",
        should_continue_to_validate,
        {
            "validate": "validate",
            "end": "monitor",
        },
    )

    workflow.add_conditional_edges(
        "validate",
        should_continue_to_size,
        {
            "size": "size",
            "monitor": "monitor",
        },
    )

    workflow.add_conditional_edges(
        "size",
        should_continue_to_execute,
        {
            "execute": "execute",
            "monitor": "monitor",
        },
    )

    # Execute always goes to monitor
    workflow.add_edge("execute", "monitor")

    # Monitor is the end
    workflow.add_edge("monitor", END)

    return workflow


def get_compiled_workflow():
    """Get the compiled workflow ready for invocation.

    Returns:
        Compiled workflow that can be invoked with .invoke()
    """
    return create_workflow().compile()


# Convenience function for running the workflow
async def run_workflow(
    universe: list[str] | None = None,
    dry_run: bool = True,
) -> WorkflowState:
    """Run the complete trading workflow.

    Args:
        universe: List of symbols to scan (default: empty)
        dry_run: If True, simulate without placing orders

    Returns:
        Final workflow state with results
    """
    compiled = get_compiled_workflow()

    initial_state: WorkflowState = {
        "universe": universe or [],
        "dry_run": dry_run,
        "signals": [],
        "scan_errors": [],
        "validated_signals": [],
        "validation_errors": [],
        "sized_orders": [],
        "sizing_errors": [],
        "executions": [],
        "execution_errors": [],
        "monitor_actions": [],
        "monitor_errors": [],
        "status": WorkflowStatus.PENDING.value,
        "started_at": datetime.now().isoformat(),
        "completed_at": "",
        "error": "",
    }

    result = compiled.invoke(initial_state)
    return result
