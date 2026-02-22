"""Run logging command for Turtle Trading system.

This command logs run events for the scanner and monitor tasks,
capturing what was checked and what decisions were made.
"""

from datetime import date, datetime

from src.domain.interfaces.repositories import RunRepository
from src.domain.models.run import Run, RunStatus, TaskType


class RunLogger:
    """Command to log run events for scanner and monitor tasks.

    This command:
    1. Creates run records at task start
    2. Accumulates per-symbol/position details during execution
    3. Finalizes runs with summary and status at completion
    """

    def __init__(self, run_repo: RunRepository) -> None:
        """Initialize the run logger.

        Args:
            run_repo: Repository for run persistence
        """
        self._run_repo = run_repo

    def start_scanner_run(self, universe_size: int) -> Run:
        """Begin a scanner run.

        Args:
            universe_size: Number of symbols to be scanned

        Returns:
            Run object to be updated during execution
        """
        return Run(
            task_type=TaskType.SCANNER,
            details={
                "universe_size": universe_size,
                "market_date": str(date.today()),
                "symbols": [],
            },
        )

    def start_monitor_run(self) -> Run:
        """Begin a monitor run.

        Returns:
            Run object to be updated during execution
        """
        return Run(
            task_type=TaskType.MONITOR,
            details={
                "positions": [],
                "ibkr_connected": False,
            },
        )

    def add_scanner_check(
        self,
        run: Run,
        symbol: str,
        price: float | None,
        n_value: float | None,
        dc20_upper: float | None,
        dc20_lower: float | None,
        dc55_upper: float | None,
        dc55_lower: float | None,
        signals: list[dict],
        error: str | None,
    ) -> None:
        """Add a symbol check result to the scanner run.

        Args:
            run: The run being updated
            symbol: Symbol that was checked
            price: Current price
            n_value: Calculated N (ATR) value
            dc20_upper: 20-day Donchian upper
            dc20_lower: 20-day Donchian lower
            dc55_upper: 55-day Donchian upper
            dc55_lower: 55-day Donchian lower
            signals: List of detected signals
            error: Error message if check failed
        """
        run.details["symbols"].append({
            "symbol": symbol,
            "price": price,
            "n_value": n_value,
            "dc20_upper": dc20_upper,
            "dc20_lower": dc20_lower,
            "dc55_upper": dc55_upper,
            "dc55_lower": dc55_lower,
            "signals": signals,
            "decision": "error" if error else ("signal_detected" if signals else "no_signal"),
            "error": error,
        })

        if error:
            run.errors_count += 1
        else:
            run.symbols_checked += 1
            run.signals_found += len(signals)

    def add_monitor_check(
        self,
        run: Run,
        symbol: str,
        quantity: int,
        entry_price: float,
        current_price: float,
        stop_price: float,
        exit_channel: float | None,
        pyramid_trigger: float | None,
        action: str,
        reason: str,
        pnl: float,
        error: str | None = None,
    ) -> None:
        """Add a position check result to the monitor run.

        Args:
            run: The run being updated
            symbol: Position symbol
            quantity: Position quantity (negative for short)
            entry_price: Average entry price
            current_price: Current market price
            stop_price: Current stop price
            exit_channel: Exit channel level (DC10/DC20 low/high)
            pyramid_trigger: Next pyramid trigger price
            action: Action determined (hold, exit_stop, exit_breakout, pyramid)
            reason: Human-readable reason for action
            pnl: Unrealized P&L
            error: Error message if check failed
        """
        run.details["positions"].append({
            "symbol": symbol,
            "quantity": quantity,
            "entry_price": entry_price,
            "current_price": current_price,
            "stop_price": stop_price,
            "exit_channel": exit_channel,
            "pyramid_trigger": pyramid_trigger,
            "action": action,
            "reason": reason,
            "pnl": pnl,
            "error": error,
        })

        if error:
            run.errors_count += 1
        else:
            run.symbols_checked += 1
            if action.lower() not in ("hold", "no_action"):
                run.actions_needed += 1

    def set_ibkr_connected(self, run: Run, connected: bool) -> None:
        """Set IBKR connection status for monitor run.

        Args:
            run: The run being updated
            connected: Whether IBKR is connected
        """
        run.details["ibkr_connected"] = connected

    async def complete_run(self, run: Run) -> None:
        """Finalize and save a completed run.

        Automatically determines status based on error count
        and generates a human-readable summary.

        Args:
            run: The run to finalize
        """
        run.completed_at = datetime.now()

        # Determine status
        if run.errors_count > 0 and run.symbols_checked > 0:
            run.status = RunStatus.PARTIAL
        elif run.errors_count > 0 and run.symbols_checked == 0:
            run.status = RunStatus.FAILED
        else:
            run.status = RunStatus.SUCCESS

        # Generate summary
        run.summary = self._generate_summary(run)

        await self._run_repo.save(run)

    async def fail_run(self, run: Run, error_message: str) -> None:
        """Mark a run as failed due to critical error.

        Args:
            run: The run to fail
            error_message: Description of the failure
        """
        run.completed_at = datetime.now()
        run.status = RunStatus.FAILED
        run.summary = f"Failed: {error_message}"
        run.details["critical_error"] = error_message

        await self._run_repo.save(run)

    def _generate_summary(self, run: Run) -> str:
        """Generate a human-readable summary of the run.

        Args:
            run: The completed run

        Returns:
            Summary string (e.g., "Scanned 15 ETFs, found 2 signals")
        """
        if run.task_type == TaskType.SCANNER:
            parts = [f"Scanned {run.symbols_checked} ETFs"]
            if run.signals_found > 0:
                parts.append(f"found {run.signals_found} signal(s)")
            else:
                parts.append("no signals")
            if run.errors_count > 0:
                parts.append(f"{run.errors_count} error(s)")
            return ", ".join(parts)
        else:  # MONITOR
            parts = [f"Checked {run.symbols_checked} position(s)"]
            if run.actions_needed > 0:
                parts.append(f"{run.actions_needed} action(s) needed")
            else:
                parts.append("all holding")
            if run.errors_count > 0:
                parts.append(f"{run.errors_count} error(s)")
            return ", ".join(parts)
