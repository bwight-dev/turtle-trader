"""Unit tests for DailyWorkflow."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.application.workflows.daily_workflow import (
    DailyWorkflow,
    DailyWorkflowResult,
    DailyWorkflowStatus,
    SignalCandidate,
    SizedOrder,
    create_daily_workflow,
    get_compiled_daily_workflow,
    run_daily_workflow,
)
from src.domain.models.enums import Direction, System
from src.domain.models.portfolio import Portfolio


class TestWorkflowCreation:
    """Tests for workflow graph creation."""

    def test_create_workflow_returns_graph(self):
        """create_daily_workflow returns a StateGraph."""
        workflow = create_daily_workflow()
        assert workflow is not None

    def test_workflow_compiles(self):
        """Workflow compiles without errors."""
        compiled = get_compiled_daily_workflow()
        assert compiled is not None

    def test_workflow_has_expected_nodes(self):
        """Workflow has all expected nodes."""
        workflow = create_daily_workflow()
        nodes = workflow.nodes
        expected_nodes = ["reconcile", "scan", "validate", "size", "execute", "complete"]
        for node in expected_nodes:
            assert node in nodes


class TestDryRunExecution:
    """Tests for dry-run workflow execution."""

    async def test_workflow_dry_run_completes(self):
        """Workflow completes in dry-run mode."""
        workflow = DailyWorkflow()

        result = await workflow.run(
            universe=["/MGC", "/MES"],
            dry_run=True,
        )

        assert result.status in [
            DailyWorkflowStatus.COMPLETED,
            DailyWorkflowStatus.DRY_RUN,
        ]
        assert result.started_at is not None
        assert result.completed_at is not None

    async def test_workflow_dry_run_no_real_orders(self):
        """Dry-run mode doesn't execute real orders."""
        workflow = DailyWorkflow()

        result = await workflow.run(
            universe=["/MGC"],
            dry_run=True,
        )

        # In dry-run, any executions should be marked as simulated
        for execution in result.orders_executed:
            assert execution.status == "simulated" or execution.order_id == "DRY_RUN"

    async def test_workflow_empty_universe(self):
        """Workflow handles empty universe."""
        workflow = DailyWorkflow()

        result = await workflow.run(
            universe=[],
            dry_run=True,
        )

        assert result.status in [
            DailyWorkflowStatus.COMPLETED,
            DailyWorkflowStatus.DRY_RUN,
        ]
        assert len(result.signals_detected) == 0


class TestWorkflowResults:
    """Tests for workflow result structure."""

    async def test_result_has_timestamps(self):
        """Result includes proper timestamps."""
        workflow = DailyWorkflow()

        result = await workflow.run(dry_run=True)

        assert isinstance(result.started_at, datetime)
        assert result.completed_at is None or isinstance(result.completed_at, datetime)

    async def test_result_counts_executions(self):
        """Result correctly counts executed orders."""
        workflow = DailyWorkflow()

        result = await workflow.run(dry_run=True)

        # With no signals, should have 0 executions
        assert result.orders_executed_count == 0

    def test_result_status_enum(self):
        """DailyWorkflowStatus has expected values."""
        assert DailyWorkflowStatus.PENDING.value == "pending"
        assert DailyWorkflowStatus.DRY_RUN.value == "dry_run"
        assert DailyWorkflowStatus.COMPLETED.value == "completed"
        assert DailyWorkflowStatus.FAILED.value == "failed"


class TestSignalCandidate:
    """Tests for SignalCandidate dataclass."""

    def test_signal_candidate_creation(self):
        """Can create SignalCandidate."""
        signal = SignalCandidate(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            breakout_price=Decimal("2800"),
            channel_value=Decimal("2800"),
            n_value=Decimal("20"),
        )

        assert signal.symbol == "/MGC"
        assert signal.direction == Direction.LONG
        assert signal.system == System.S1
        assert signal.should_take is True

    def test_signal_candidate_filter_reason(self):
        """SignalCandidate tracks filter reason."""
        signal = SignalCandidate(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            breakout_price=Decimal("2800"),
            channel_value=Decimal("2800"),
            n_value=Decimal("20"),
            should_take=False,
            filter_reason="Last S1 was winner",
        )

        assert signal.should_take is False
        assert signal.filter_reason == "Last S1 was winner"


class TestSizedOrder:
    """Tests for SizedOrder dataclass."""

    def test_sized_order_creation(self):
        """Can create SizedOrder."""
        order = SizedOrder(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            contracts=4,
            entry_price=Decimal("2800"),
            stop_price=Decimal("2760"),
            risk_amount=Decimal("1600"),
        )

        assert order.symbol == "/MGC"
        assert order.contracts == 4
        assert order.stop_price == Decimal("2760")


class TestWorkflowWithPortfolio:
    """Tests for workflow with existing portfolio."""

    async def test_workflow_accepts_portfolio(self):
        """Workflow accepts existing portfolio."""
        workflow = DailyWorkflow()
        portfolio = Portfolio()

        result = await workflow.run(
            universe=["/MGC"],
            dry_run=True,
            portfolio=portfolio,
        )

        assert result.status in [
            DailyWorkflowStatus.COMPLETED,
            DailyWorkflowStatus.DRY_RUN,
        ]

    async def test_workflow_accepts_equity(self):
        """Workflow accepts account equity."""
        workflow = DailyWorkflow()

        result = await workflow.run(
            universe=["/MGC"],
            dry_run=True,
            account_equity=Decimal("50000"),
        )

        assert result.status in [
            DailyWorkflowStatus.COMPLETED,
            DailyWorkflowStatus.DRY_RUN,
        ]


class TestConvenienceFunction:
    """Tests for run_daily_workflow convenience function."""

    async def test_run_daily_workflow_function(self):
        """Convenience function works."""
        result = await run_daily_workflow(
            universe=["/MGC"],
            dry_run=True,
        )

        assert result.status in [
            DailyWorkflowStatus.COMPLETED,
            DailyWorkflowStatus.DRY_RUN,
        ]


class TestWorkflowTransitions:
    """Tests for workflow state transitions."""

    async def test_no_signals_skips_to_complete(self):
        """Empty signals skips directly to complete."""
        workflow = DailyWorkflow()

        result = await workflow.run(
            universe=[],  # No symbols = no signals
            dry_run=True,
        )

        # Should complete without going through size/execute
        assert len(result.orders_sized) == 0
        assert len(result.orders_executed) == 0

    async def test_workflow_status_progression(self):
        """Workflow progresses through expected states."""
        workflow = DailyWorkflow()

        result = await workflow.run(
            universe=["/MGC"],
            dry_run=True,
        )

        # Final status should be completed or dry_run
        assert result.status in [
            DailyWorkflowStatus.COMPLETED,
            DailyWorkflowStatus.DRY_RUN,
        ]
