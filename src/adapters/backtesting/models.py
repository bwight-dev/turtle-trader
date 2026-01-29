"""Models for backtesting configuration and results."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True)
class BacktestConfig:
    """Configuration for a backtest run."""

    start_date: date
    end_date: date
    initial_equity: Decimal = Decimal("50000")
    risk_per_unit: Decimal = Decimal("0.005")  # 0.5% per unit

    # Systems
    use_s1: bool = True
    use_s2: bool = True
    allow_short: bool = True

    # Position management
    use_pyramiding: bool = True
    max_pyramid_units: int = 4
    use_correlation_limits: bool = True

    # Limit mode
    use_risk_cap_mode: bool = True  # Modern risk cap vs original 12-unit
    max_total_risk: Decimal = Decimal("0.15")  # 15% of equity (optimal per backtest)
    max_units_per_market: int = 4
    max_units_correlated: int = 6
    max_units_total: int = 12  # Only used if use_risk_cap_mode=False

    # Execution simulation
    # For ETFs: commission per trade (most brokers = $0)
    # For futures: commission per contract (~$2.25)
    commission_per_trade: Decimal = Decimal("1.00")  # $1 per trade (nominal)
    commission_per_contract: Decimal = Decimal("0")  # $0 per share for ETFs
    slippage_ticks: int = 1

    # Point values (multipliers)
    # - For ETFs: default 1.0 (1 share = $1 per point)
    # - For futures: use FUTURES_POINT_VALUES or provide custom dict
    # If point_values dict is provided, it overrides default_point_value
    default_point_value: Decimal = Decimal("1.0")
    point_values: dict[str, float] | None = None  # Per-symbol multipliers

    # Deprecated: use default_point_value instead
    point_value: Decimal = Decimal("1.0")

    # Signal priority
    signal_priority: Literal["strength", "fifo"] = "strength"

    def get_point_value(self, symbol: str) -> Decimal:
        """Get point value for a specific symbol.

        Args:
            symbol: The trading symbol

        Returns:
            Point value (multiplier) for the symbol
        """
        if self.point_values and symbol in self.point_values:
            return Decimal(str(self.point_values[symbol]))
        return self.default_point_value


@dataclass
class TradeRecord:
    """Record of a completed trade."""

    symbol: str
    system: Literal["S1", "S2"]
    direction: Literal["LONG", "SHORT"]

    entry_date: date
    entry_price: Decimal
    entry_n: Decimal

    exit_date: date
    exit_price: Decimal
    exit_reason: Literal["STOP", "BREAKOUT", "END_OF_TEST"]

    units: int  # Number of units (may include pyramids)
    contracts: int  # Total contracts

    gross_pnl: Decimal
    commission: Decimal
    slippage: Decimal
    net_pnl: Decimal

    # Pyramid tracking
    pyramid_levels: int = 1
    avg_entry_price: Decimal | None = None

    @property
    def pnl_r(self) -> Decimal:
        """P&L in R-multiples (risk units)."""
        initial_risk = self.entry_n * 2  # 2N stop
        if initial_risk == 0:
            return Decimal("0")
        return self.net_pnl / (initial_risk * self.contracts)


@dataclass
class EquityPoint:
    """Single point on the equity curve."""

    date: date
    equity: Decimal
    cash: Decimal
    positions_value: Decimal
    drawdown_pct: Decimal
    high_water_mark: Decimal


@dataclass
class PerformanceMetrics:
    """Performance statistics for a backtest."""

    # Returns
    total_return_pct: Decimal
    annualized_return_pct: Decimal
    final_equity: Decimal

    # Risk
    max_drawdown_pct: Decimal
    avg_drawdown_pct: Decimal
    max_drawdown_duration_days: int

    # Risk-adjusted
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal

    # P&L
    gross_profit: Decimal
    gross_loss: Decimal
    profit_factor: Decimal
    expectancy: Decimal

    avg_winner: Decimal
    avg_loser: Decimal
    largest_winner: Decimal
    largest_loser: Decimal
    avg_trade_pnl: Decimal

    # Exposure
    avg_positions_held: Decimal
    max_positions_held: int
    time_in_market_pct: Decimal

    # By system
    s1_trades: int = 0
    s2_trades: int = 0
    long_trades: int = 0
    short_trades: int = 0


@dataclass
class BacktestResult:
    """Complete results of a backtest run."""

    config: BacktestConfig
    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: list[EquityPoint] = field(default_factory=list)
    metrics: PerformanceMetrics | None = None

    # Diagnostics
    signals_generated: int = 0
    signals_filtered: int = 0
    signals_skipped_size: int = 0  # Size < 1 contract
    signals_skipped_limits: int = 0
    pyramid_triggers: int = 0
    stop_exits: int = 0
    breakout_exits: int = 0

    @property
    def summary(self) -> str:
        """Generate a text summary of results."""
        if not self.metrics:
            return "No metrics calculated"

        m = self.metrics
        return f"""
BACKTEST RESULTS
================
Period: {self.config.start_date} to {self.config.end_date}
Initial Equity: ${self.config.initial_equity:,.0f}
Final Equity: ${m.final_equity:,.0f}

RETURNS
-------
Total Return: {m.total_return_pct:.1f}%
Annualized Return: {m.annualized_return_pct:.1f}%
Max Drawdown: {m.max_drawdown_pct:.1f}%

RISK-ADJUSTED
-------------
Sharpe Ratio: {m.sharpe_ratio:.2f}
Sortino Ratio: {m.sortino_ratio:.2f}
Calmar Ratio: {m.calmar_ratio:.2f}

TRADES
------
Total Trades: {m.total_trades}
Win Rate: {m.win_rate:.1f}%
Profit Factor: {m.profit_factor:.2f}
Expectancy: ${m.expectancy:.2f}

Avg Winner: ${m.avg_winner:,.2f}
Avg Loser: ${m.avg_loser:,.2f}
Largest Winner: ${m.largest_winner:,.2f}
Largest Loser: ${m.largest_loser:,.2f}

BREAKDOWN
---------
S1 Trades: {m.s1_trades}
S2 Trades: {m.s2_trades}
Long Trades: {m.long_trades}
Short Trades: {m.short_trades}
"""
