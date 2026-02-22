"""State tracker for backtest simulation.

Tracks positions, equity curve, and completed trades throughout
the backtest simulation.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

from src.adapters.backtesting.models import EquityPoint, PerformanceMetrics, TradeRecord
from src.domain.services.drawdown_tracker import DrawdownTracker


@dataclass
class OpenPosition:
    """An open position during backtest."""

    symbol: str
    direction: Literal["LONG", "SHORT"]
    system: Literal["S1", "S2"]

    # Entry info
    entry_date: date
    entry_price: Decimal
    entry_n: Decimal
    contracts: int
    units: int = 1

    # Stop
    stop_price: Decimal = Decimal("0")

    # Pyramiding
    pyramid_entries: list[tuple[date, Decimal, int]] = field(default_factory=list)

    # Tracking
    correlation_group: str | None = None
    last_pyramid_price: Decimal | None = None

    def __post_init__(self):
        if not self.pyramid_entries:
            self.pyramid_entries = [(self.entry_date, self.entry_price, self.contracts)]
        if not self.last_pyramid_price:
            self.last_pyramid_price = self.entry_price

    @property
    def avg_entry_price(self) -> Decimal:
        """Calculate average entry price across all pyramids."""
        total_value = sum(p * c for _, p, c in self.pyramid_entries)
        total_contracts = sum(c for _, _, c in self.pyramid_entries)
        if total_contracts == 0:
            return self.entry_price
        return total_value / total_contracts

    @property
    def total_contracts(self) -> int:
        """Total contracts including pyramids."""
        return sum(c for _, _, c in self.pyramid_entries)

    def mark_to_market(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized P&L at current price."""
        if self.direction == "LONG":
            return (current_price - self.avg_entry_price) * self.total_contracts
        else:
            return (self.avg_entry_price - current_price) * self.total_contracts

    def add_pyramid(
        self,
        date: date,
        price: Decimal,
        contracts: int,
        new_stop: Decimal,
    ) -> None:
        """Add a pyramid entry."""
        self.pyramid_entries.append((date, price, contracts))
        self.units += 1
        self.contracts = self.total_contracts
        self.stop_price = new_stop
        self.last_pyramid_price = price


class StateTracker:
    """Tracks all state during backtest simulation.

    Manages:
    - Open positions
    - Cash and equity
    - Completed trades
    - Equity curve
    - Trade history for S1 filter
    """

    def __init__(
        self,
        initial_equity: Decimal,
        commission_per_trade: Decimal = Decimal("1.00"),
        commission_per_contract: Decimal = Decimal("0"),
        point_value: Decimal = Decimal("1.0"),
        point_values: dict[str, Decimal] | None = None,
        min_notional_floor: Decimal | None = None,
    ):
        """Initialize the state tracker.

        Args:
            initial_equity: Starting cash
            commission_per_trade: Fixed commission per trade (for ETFs)
            commission_per_contract: Commission per contract (for futures)
            point_value: Default dollar value per point (1.0 for ETFs)
            point_values: Per-symbol point values dict (overrides point_value)
            min_notional_floor: Minimum notional as fraction of starting equity.
                               Set to 0.60 for small accounts to prevent "death spiral".
        """
        self.initial_equity = initial_equity
        self.cash = initial_equity
        self.commission_per_trade = commission_per_trade
        self.commission_per_contract = commission_per_contract
        self._default_point_value = point_value
        self._point_values = point_values or {}
        self._min_notional_floor = min_notional_floor

        # Positions
        self.positions: dict[str, OpenPosition] = {}

        # History
        self.trades: list[TradeRecord] = []
        self.equity_curve: list[EquityPoint] = []

        # High water mark tracking (for metrics/reporting only)
        self.high_water_mark = initial_equity

        # Rule 5: Drawdown tracking via domain service
        # Uses yearly starting equity (not rolling HWM) with cascading reductions
        self._drawdown_tracker = DrawdownTracker(
            yearly_starting_equity=initial_equity,
            min_notional_floor=min_notional_floor,
        )

        # Trade history by symbol (for S1 filter)
        self.trade_history: dict[str, list[TradeRecord]] = {}

        # N value cache (symbol -> most recent N)
        self.n_values: dict[str, Decimal] = {}

        # Last known prices for mark-to-market
        self._last_prices: dict[str, Decimal] = {}

    def get_point_value(self, symbol: str) -> Decimal:
        """Get point value for a specific symbol.

        Args:
            symbol: The trading symbol

        Returns:
            Point value (multiplier) for the symbol
        """
        return self._point_values.get(symbol, self._default_point_value)

    @property
    def positions_value(self) -> Decimal:
        """Calculate total value of open positions at current prices.

        Note: Requires mark_to_market to be called with current prices.
        """
        total = Decimal("0")
        for pos in self.positions.values():
            price = self._last_prices.get(pos.symbol, pos.entry_price)
            point_value = self.get_point_value(pos.symbol)
            total += pos.mark_to_market(price) * point_value
        return total

    @property
    def equity(self) -> Decimal:
        """Current equity (cash + positions value)."""
        return self.cash + self.positions_value

    @property
    def sizing_equity(self) -> Decimal:
        """Equity used for position sizing (notional equity per Rule 5).

        This is reduced during drawdowns to prevent 'digging a deeper hole'.
        Uses cascading reductions per original Turtle rules.
        """
        return self._drawdown_tracker.notional_equity

    @property
    def total_units(self) -> int:
        """Total units across all positions."""
        return sum(pos.units for pos in self.positions.values())

    @property
    def total_risk(self) -> Decimal:
        """Total risk as fraction of initial equity."""
        # Each unit risks 0.5%
        return self.total_units * Decimal("0.005")

    def update_prices(self, prices: dict[str, Decimal]) -> None:
        """Update last known prices for mark-to-market."""
        if not hasattr(self, "_last_prices"):
            self._last_prices = {}
        self._last_prices.update(prices)

    def reset_year(self, new_starting_equity: Decimal | None = None) -> None:
        """Reset for a new year (Rule 5).

        Call at start of each year to reset the yearly starting equity
        to the current account value.

        Args:
            new_starting_equity: New yearly starting equity.
                                 If None, uses current equity.
        """
        equity = new_starting_equity if new_starting_equity is not None else self.equity
        self._drawdown_tracker.reset_year(equity)

    def open_position(
        self,
        symbol: str,
        direction: Literal["LONG", "SHORT"],
        system: Literal["S1", "S2"],
        entry_date: date,
        entry_price: Decimal,
        entry_n: Decimal,
        contracts: int,
        stop_price: Decimal,
        correlation_group: str | None = None,
    ) -> OpenPosition:
        """Open a new position.

        For backtesting simplicity, we track positions at cost basis.
        Cash is reduced by entry cost (long) or not changed (short).
        P&L is realized on close.

        Args:
            symbol: Symbol to trade
            direction: LONG or SHORT
            system: S1 or S2
            entry_date: Entry date
            entry_price: Entry price
            entry_n: N value at entry (for sizing/stops)
            contracts: Number of contracts
            stop_price: Initial stop price
            correlation_group: For limit tracking

        Returns:
            The opened position
        """
        # Commission = per-trade fee + per-contract fee
        commission = self.commission_per_trade + (self.commission_per_contract * contracts)

        # Deduct entry commission
        self.cash -= commission

        position = OpenPosition(
            symbol=symbol,
            direction=direction,
            system=system,
            entry_date=entry_date,
            entry_price=entry_price,
            entry_n=entry_n,
            contracts=contracts,
            stop_price=stop_price,
            correlation_group=correlation_group,
        )

        self.positions[symbol] = position
        self.n_values[symbol] = entry_n

        return position

    def add_pyramid(
        self,
        symbol: str,
        pyramid_date: date,
        price: Decimal,
        contracts: int,
        new_stop: Decimal,
    ) -> None:
        """Add pyramid to existing position."""
        if symbol not in self.positions:
            raise ValueError(f"No position for {symbol}")

        position = self.positions[symbol]

        # Deduct commission (P&L tracked on close)
        commission = self.commission_per_trade + (self.commission_per_contract * contracts)
        self.cash -= commission

        position.add_pyramid(pyramid_date, price, contracts, new_stop)

    def close_position(
        self,
        symbol: str,
        exit_date: date,
        exit_price: Decimal,
        exit_reason: Literal["STOP", "BREAKOUT", "END_OF_TEST"],
    ) -> TradeRecord:
        """Close a position and record the trade.

        Args:
            symbol: Symbol to close
            exit_date: Exit date
            exit_price: Exit price
            exit_reason: Why we're exiting

        Returns:
            TradeRecord of the completed trade
        """
        if symbol not in self.positions:
            raise ValueError(f"No position for {symbol}")

        position = self.positions[symbol]
        contracts = position.total_contracts
        direction = position.direction
        point_value = self.get_point_value(symbol)

        # Calculate P&L (price difference * contracts * point_value)
        if direction == "LONG":
            gross_pnl = (exit_price - position.avg_entry_price) * contracts * point_value
        else:
            gross_pnl = (position.avg_entry_price - exit_price) * contracts * point_value

        # Commission for exit (per-trade + per-contract)
        exit_commission = self.commission_per_trade + (self.commission_per_contract * contracts)

        # Total commission for trade record (entry was already paid)
        # Entry commission = per-trade for each pyramid entry + per-contract
        num_entries = len(position.pyramid_entries)
        entry_contracts = sum(c for _, _, c in position.pyramid_entries)
        entry_commission = (self.commission_per_trade * num_entries) + (self.commission_per_contract * entry_contracts)
        total_commission = entry_commission + exit_commission

        # Slippage estimate (already included in prices typically)
        slippage = Decimal("0")

        # Net P&L (commission already mostly deducted from cash)
        net_pnl = gross_pnl - exit_commission

        # Add net P&L to cash (this is the realized gain/loss)
        self.cash += net_pnl

        trade = TradeRecord(
            symbol=symbol,
            system=position.system,
            direction=direction,
            entry_date=position.entry_date,
            entry_price=position.entry_price,
            entry_n=position.entry_n,
            exit_date=exit_date,
            exit_price=exit_price,
            exit_reason=exit_reason,
            units=position.units,
            contracts=contracts,
            gross_pnl=gross_pnl,
            commission=total_commission,
            slippage=slippage,
            net_pnl=net_pnl,
            pyramid_levels=len(position.pyramid_entries),
            avg_entry_price=position.avg_entry_price,
        )

        self.trades.append(trade)

        # Track by symbol for S1 filter
        if symbol not in self.trade_history:
            self.trade_history[symbol] = []
        self.trade_history[symbol].append(trade)

        # Remove position
        del self.positions[symbol]

        return trade

    def record_equity(self, current_date: date, prices: dict[str, Decimal]) -> EquityPoint:
        """Record equity curve point for current date.

        Equity = Cash + Unrealized P&L from open positions

        Args:
            current_date: The date
            prices: Current prices for mark-to-market

        Returns:
            EquityPoint for this date
        """
        self.update_prices(prices)

        # Calculate unrealized P&L from open positions
        unrealized_pnl = Decimal("0")
        for symbol, position in self.positions.items():
            price = prices.get(symbol, position.entry_price)
            point_value = self.get_point_value(symbol)
            unrealized_pnl += position.mark_to_market(price) * point_value

        # Equity = cash (which includes realized P&L) + unrealized P&L
        equity = self.cash + unrealized_pnl

        # Update high water mark (for reporting/metrics only)
        if equity > self.high_water_mark:
            self.high_water_mark = equity

        # Rule 5: Update drawdown tracker (uses yearly starting equity, not HWM)
        # This applies cascading reductions per original Turtle rules
        self._drawdown_tracker.update_equity(equity)

        # Calculate drawdown from HWM for reporting (different from Rule 5 drawdown)
        if self.high_water_mark > 0:
            drawdown_pct = (self.high_water_mark - equity) / self.high_water_mark * 100
        else:
            drawdown_pct = Decimal("0")

        point = EquityPoint(
            date=current_date,
            equity=equity,
            cash=self.cash,
            positions_value=unrealized_pnl,
            drawdown_pct=drawdown_pct,
            high_water_mark=self.high_water_mark,
        )

        self.equity_curve.append(point)
        return point

    def get_last_s1_trade(self, symbol: str) -> TradeRecord | None:
        """Get the most recent S1 trade for a symbol (for S1 filter)."""
        if symbol not in self.trade_history:
            return None

        s1_trades = [t for t in self.trade_history[symbol] if t.system == "S1"]
        return s1_trades[-1] if s1_trades else None

    def was_last_s1_winner(self, symbol: str) -> bool:
        """Check if last S1 trade was a winner (for S1 filter, Rule 7)."""
        last_trade = self.get_last_s1_trade(symbol)
        if not last_trade:
            return False
        return last_trade.net_pnl > 0

    def units_for_symbol(self, symbol: str) -> int:
        """Get current units for a symbol."""
        if symbol not in self.positions:
            return 0
        return self.positions[symbol].units

    def units_for_correlation_group(self, group: str) -> int:
        """Get total units for a correlation group."""
        return sum(
            pos.units
            for pos in self.positions.values()
            if pos.correlation_group == group
        )

    def calculate_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics from completed trades and equity curve."""
        if not self.trades:
            return self._empty_metrics()

        trades = self.trades
        equity_curve = self.equity_curve

        # Basic trade stats
        total_trades = len(trades)
        winners = [t for t in trades if t.net_pnl > 0]
        losers = [t for t in trades if t.net_pnl <= 0]
        winning_trades = len(winners)
        losing_trades = len(losers)

        win_rate = Decimal(winning_trades) / Decimal(total_trades) * 100 if total_trades > 0 else Decimal("0")

        # P&L
        gross_profit = sum(t.net_pnl for t in winners) if winners else Decimal("0")
        gross_loss = abs(sum(t.net_pnl for t in losers)) if losers else Decimal("0")

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else Decimal("999")

        avg_winner = gross_profit / len(winners) if winners else Decimal("0")
        avg_loser = -gross_loss / len(losers) if losers else Decimal("0")

        largest_winner = max(t.net_pnl for t in winners) if winners else Decimal("0")
        largest_loser = min(t.net_pnl for t in losers) if losers else Decimal("0")

        total_pnl = sum(t.net_pnl for t in trades)
        avg_trade_pnl = total_pnl / total_trades if total_trades > 0 else Decimal("0")

        # Expectancy: (Win% × Avg Win) - (Loss% × Avg Loss)
        win_pct = Decimal(winning_trades) / Decimal(total_trades) if total_trades > 0 else Decimal("0")
        loss_pct = Decimal(losing_trades) / Decimal(total_trades) if total_trades > 0 else Decimal("0")
        expectancy = (win_pct * avg_winner) + (loss_pct * avg_loser)

        # Returns
        final_equity = equity_curve[-1].equity if equity_curve else self.initial_equity
        total_return_pct = (final_equity - self.initial_equity) / self.initial_equity * 100

        # Annualized return (assuming 252 trading days)
        if equity_curve and len(equity_curve) > 1:
            days = (equity_curve[-1].date - equity_curve[0].date).days
            years = Decimal(days) / Decimal("365")
            if years > 0 and final_equity > 0:
                annualized_return_pct = ((final_equity / self.initial_equity) ** (1 / years) - 1) * 100
            else:
                # Can't calculate annualized return with negative equity
                annualized_return_pct = total_return_pct
        else:
            annualized_return_pct = total_return_pct

        # Drawdown
        max_drawdown_pct = max(p.drawdown_pct for p in equity_curve) if equity_curve else Decimal("0")
        avg_drawdown_pct = sum(p.drawdown_pct for p in equity_curve) / len(equity_curve) if equity_curve else Decimal("0")

        # Max drawdown duration
        max_dd_duration = 0
        current_dd_duration = 0
        for point in equity_curve:
            if point.drawdown_pct > 0:
                current_dd_duration += 1
                max_dd_duration = max(max_dd_duration, current_dd_duration)
            else:
                current_dd_duration = 0

        # Sharpe ratio (simplified - using daily returns)
        if len(equity_curve) > 1:
            daily_returns = []
            for i in range(1, len(equity_curve)):
                prev_eq = equity_curve[i - 1].equity
                curr_eq = equity_curve[i].equity
                if prev_eq > 0:
                    daily_returns.append((curr_eq - prev_eq) / prev_eq)

            if daily_returns:
                avg_return = sum(daily_returns) / len(daily_returns)
                variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
                std_dev = variance ** Decimal("0.5")
                sharpe_ratio = (avg_return * Decimal("252") ** Decimal("0.5")) / std_dev if std_dev > 0 else Decimal("0")
            else:
                sharpe_ratio = Decimal("0")
        else:
            sharpe_ratio = Decimal("0")

        # Sortino (downside deviation)
        if len(equity_curve) > 1:
            negative_returns = [r for r in daily_returns if r < 0]
            if negative_returns:
                downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
                downside_dev = downside_variance ** Decimal("0.5")
                sortino_ratio = (avg_return * Decimal("252") ** Decimal("0.5")) / downside_dev if downside_dev > 0 else Decimal("0")
            else:
                sortino_ratio = sharpe_ratio * 2  # No downside = great
        else:
            sortino_ratio = Decimal("0")

        # Calmar ratio (return / max drawdown)
        calmar_ratio = annualized_return_pct / max_drawdown_pct if max_drawdown_pct > 0 else Decimal("0")

        # Exposure
        positions_held = [len(self.positions) for _ in equity_curve]  # Simplified
        avg_positions = sum(positions_held) / len(positions_held) if positions_held else Decimal("0")
        max_positions = max(positions_held) if positions_held else 0
        time_in_market = sum(1 for p in positions_held if p > 0) / len(positions_held) * 100 if positions_held else Decimal("0")

        # By system
        s1_trades = len([t for t in trades if t.system == "S1"])
        s2_trades = len([t for t in trades if t.system == "S2"])
        long_trades = len([t for t in trades if t.direction == "LONG"])
        short_trades = len([t for t in trades if t.direction == "SHORT"])

        return PerformanceMetrics(
            total_return_pct=total_return_pct,
            annualized_return_pct=annualized_return_pct,
            final_equity=final_equity,
            max_drawdown_pct=max_drawdown_pct,
            avg_drawdown_pct=avg_drawdown_pct,
            max_drawdown_duration_days=max_dd_duration,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            expectancy=expectancy,
            avg_winner=avg_winner,
            avg_loser=avg_loser,
            largest_winner=largest_winner,
            largest_loser=largest_loser,
            avg_trade_pnl=avg_trade_pnl,
            avg_positions_held=Decimal(str(avg_positions)),
            max_positions_held=max_positions,
            time_in_market_pct=Decimal(str(time_in_market)),
            s1_trades=s1_trades,
            s2_trades=s2_trades,
            long_trades=long_trades,
            short_trades=short_trades,
        )

    def _empty_metrics(self) -> PerformanceMetrics:
        """Return empty metrics when no trades."""
        return PerformanceMetrics(
            total_return_pct=Decimal("0"),
            annualized_return_pct=Decimal("0"),
            final_equity=self.initial_equity,
            max_drawdown_pct=Decimal("0"),
            avg_drawdown_pct=Decimal("0"),
            max_drawdown_duration_days=0,
            sharpe_ratio=Decimal("0"),
            sortino_ratio=Decimal("0"),
            calmar_ratio=Decimal("0"),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=Decimal("0"),
            gross_profit=Decimal("0"),
            gross_loss=Decimal("0"),
            profit_factor=Decimal("0"),
            expectancy=Decimal("0"),
            avg_winner=Decimal("0"),
            avg_loser=Decimal("0"),
            largest_winner=Decimal("0"),
            largest_loser=Decimal("0"),
            avg_trade_pnl=Decimal("0"),
            avg_positions_held=Decimal("0"),
            max_positions_held=0,
            time_in_market_pct=Decimal("0"),
        )
