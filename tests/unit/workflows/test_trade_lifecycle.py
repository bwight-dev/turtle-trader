"""Unit tests for Turtle Trading workflow."""

import pytest

from src.application.workflows.trade_lifecycle import (
    WorkflowState,
    WorkflowStatus,
    create_workflow,
    get_compiled_workflow,
    run_workflow,
    scan_markets,
    validate_signals,
    size_positions,
    execute_orders,
    monitor_positions,
)


class TestWorkflowStates:
    """Tests for workflow state definitions."""

    def test_workflow_states_defined(self):
        """Verify all required states are in the workflow."""
        workflow = create_workflow()
        nodes = workflow.nodes.keys()

        assert "scan" in nodes
        assert "validate" in nodes
        assert "size" in nodes
        assert "execute" in nodes
        assert "monitor" in nodes

    def test_workflow_compiles(self):
        """Verify workflow can be compiled."""
        compiled = get_compiled_workflow()
        assert compiled is not None


class TestScanNode:
    """Tests for scan_markets node."""

    def test_scan_returns_state(self):
        """Scan node returns valid state."""
        state: WorkflowState = {
            "universe": ["/MGC", "/MES"],
            "dry_run": True,
            "signals": [],
        }

        result = scan_markets(state)

        assert "signals" in result
        assert "scan_errors" in result
        assert isinstance(result["scan_errors"], list)

    def test_scan_preserves_existing_signals(self):
        """Scan preserves signals already in state."""
        state: WorkflowState = {
            "signals": [{"symbol": "/MGC", "direction": "long"}],
        }

        result = scan_markets(state)

        assert len(result["signals"]) == 1


class TestValidateNode:
    """Tests for validate_signals node."""

    def test_validate_filters_signals(self):
        """Validate filters signals based on should_take."""
        state: WorkflowState = {
            "signals": [
                {"symbol": "/MGC", "should_take": True},
                {"symbol": "/MES", "should_take": False},
            ],
        }

        result = validate_signals(state)

        assert len(result["validated_signals"]) == 1
        assert result["validated_signals"][0]["symbol"] == "/MGC"

    def test_validate_empty_signals(self):
        """Validate handles empty signals list."""
        state: WorkflowState = {"signals": []}

        result = validate_signals(state)

        assert result["validated_signals"] == []
        assert result["validation_errors"] == []


class TestSizeNode:
    """Tests for size_positions node."""

    def test_size_creates_orders(self):
        """Size node creates sized orders for validated signals."""
        state: WorkflowState = {
            "validated_signals": [
                {"symbol": "/MGC", "direction": "long"},
            ],
        }

        result = size_positions(state)

        assert len(result["sized_orders"]) == 1
        assert result["sized_orders"][0]["symbol"] == "/MGC"

    def test_size_empty_signals(self):
        """Size handles empty validated signals."""
        state: WorkflowState = {"validated_signals": []}

        result = size_positions(state)

        assert result["sized_orders"] == []


class TestExecuteNode:
    """Tests for execute_orders node."""

    def test_execute_dry_run(self):
        """Execute in dry-run mode simulates orders."""
        state: WorkflowState = {
            "dry_run": True,
            "sized_orders": [{"symbol": "/MGC", "contracts": 2}],
        }

        result = execute_orders(state)

        assert len(result["executions"]) == 1
        assert result["executions"][0]["status"] == "simulated"
        assert result["executions"][0]["order_id"] == "DRY_RUN"
        assert result["status"] == WorkflowStatus.DRY_RUN.value

    def test_execute_empty_orders(self):
        """Execute handles empty orders list."""
        state: WorkflowState = {
            "dry_run": True,
            "sized_orders": [],
        }

        result = execute_orders(state)

        assert result["executions"] == []


class TestMonitorNode:
    """Tests for monitor_positions node."""

    def test_monitor_completes_workflow(self):
        """Monitor node marks workflow as completed."""
        state: WorkflowState = {}

        result = monitor_positions(state)

        assert result["status"] == WorkflowStatus.COMPLETED.value
        assert result["completed_at"] != ""

    def test_monitor_returns_actions(self):
        """Monitor returns monitor actions list."""
        state: WorkflowState = {}

        result = monitor_positions(state)

        assert "monitor_actions" in result
        assert "monitor_errors" in result


class TestWorkflowExecution:
    """Tests for full workflow execution."""

    async def test_workflow_dry_run(self):
        """Test complete workflow in dry-run mode."""
        result = await run_workflow(
            universe=["/MGC", "/MES"],
            dry_run=True,
        )

        assert result["status"] in [
            WorkflowStatus.COMPLETED.value,
            WorkflowStatus.DRY_RUN.value,
        ]
        assert result["started_at"] != ""

    async def test_workflow_empty_universe(self):
        """Test workflow with empty universe."""
        result = await run_workflow(universe=[], dry_run=True)

        assert result["status"] == WorkflowStatus.COMPLETED.value

    async def test_workflow_default_dry_run(self):
        """Test workflow defaults to dry-run."""
        result = await run_workflow()

        assert result["dry_run"] is True


class TestWorkflowTransitions:
    """Tests for workflow state transitions."""

    async def test_no_signals_skips_to_monitor(self):
        """When no signals, workflow skips to monitor."""
        result = await run_workflow(universe=[], dry_run=True)

        # Should have empty intermediate states
        assert result["signals"] == []
        assert result["status"] == WorkflowStatus.COMPLETED.value

    async def test_workflow_flow_complete(self):
        """Test that workflow flows through all states."""
        compiled = get_compiled_workflow()

        initial_state: WorkflowState = {
            "universe": ["/MGC"],
            "dry_run": True,
            "signals": [{"symbol": "/MGC", "direction": "long", "should_take": True}],
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
            "started_at": "",
            "completed_at": "",
            "error": "",
        }

        result = compiled.invoke(initial_state)

        # Should have flowed through all states
        assert len(result["validated_signals"]) == 1
        assert len(result["sized_orders"]) == 1
        assert len(result["executions"]) == 1
        assert result["status"] in [
            WorkflowStatus.COMPLETED.value,
            WorkflowStatus.DRY_RUN.value,
        ]


class TestWorkflowStatus:
    """Tests for WorkflowStatus enum."""

    def test_status_values(self):
        """Verify all status values exist."""
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.DRY_RUN.value == "dry_run"
