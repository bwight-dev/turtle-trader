"""Backtest engine for Turtle Trading system.

Simulates day-by-day trading using historical data and Turtle rules.
Coordinates data loading, signal detection, position management,
and performance tracking.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from src.adapters.backtesting.data_loader import (
    ETF_UNIVERSE,
    FUTURES_POINT_VALUES,
    HistoricalDataLoader,
    get_correlation_group,
    get_point_value,
)
from src.adapters.backtesting.models import BacktestConfig, BacktestResult
from src.adapters.backtesting.tracker import OpenPosition, StateTracker
from src.domain.models.market import Bar, DonchianChannel
from src.domain.services.channels import calculate_donchian
from src.domain.services.sizing import calculate_unit_size
from src.domain.services.volatility import calculate_n


class BacktestEngine:
    """Main backtest engine for Turtle Trading simulation.

    Iterates through historical data day-by-day, applying Turtle rules:
    1. Check stops on existing positions
    2. Check breakout exits
    3. Check pyramid opportunities
    4. Detect new entry signals
    5. Apply S1 filter
    6. Check position limits
    7. Size and execute entries
    8. Record equity
    """

    def __init__(
        self,
        config: BacktestConfig,
        data_loader: HistoricalDataLoader | None = None,
        symbols: list[str] | None = None,
    ):
        """Initialize the backtest engine.

        Args:
            config: Backtest configuration
            data_loader: Data loader (creates default if None)
            symbols: Symbols to trade (defaults to ETF_UNIVERSE)
        """
        self.config = config
        self.loader = data_loader or HistoricalDataLoader()
        self.symbols = symbols or ETF_UNIVERSE

        # Build point values map: use config values if provided, else use defaults
        self._point_values = self._build_point_values_map()

        # State
        self.tracker = StateTracker(
            initial_equity=config.initial_equity,
            commission_per_trade=config.commission_per_trade,
            commission_per_contract=config.commission_per_contract,
            point_values=self._point_values,
        )

        # Results tracking
        self.signals_generated = 0
        self.signals_filtered = 0
        self.signals_skipped_size = 0
        self.signals_skipped_limits = 0
        self.pyramid_triggers = 0
        self.stop_exits = 0
        self.breakout_exits = 0

        # Data cache for the run
        self._bars_by_symbol: dict[str, list[Bar]] = {}
        self._bar_index: dict[str, dict[date, int]] = {}

    def _build_point_values_map(self) -> dict[str, Decimal]:
        """Build the point values map for all symbols.

        Priority:
        1. Config point_values dict (if provided)
        2. FUTURES_POINT_VALUES (for known futures)
        3. Config default_point_value
        """
        result = {}
        default = self.config.default_point_value

        for symbol in self.symbols:
            if self.config.point_values and symbol in self.config.point_values:
                # Config override takes precedence
                result[symbol] = Decimal(str(self.config.point_values[symbol]))
            elif symbol in FUTURES_POINT_VALUES:
                # Use known futures multiplier
                result[symbol] = Decimal(str(FUTURES_POINT_VALUES[symbol]))
            else:
                # Default (typically 1.0 for ETFs/stocks)
                result[symbol] = default

        return result

    def _get_point_value(self, symbol: str) -> Decimal:
        """Get point value for a specific symbol."""
        return self._point_values.get(symbol, self.config.default_point_value)

    def run(self, show_progress: bool = True) -> BacktestResult:
        """Run the backtest.

        Args:
            show_progress: Print progress messages

        Returns:
            BacktestResult with all trades and metrics
        """
        if show_progress:
            print(f"\nLoading data for {len(self.symbols)} symbols...")

        # Load all data upfront
        self._load_all_data()

        if show_progress:
            print(f"Running backtest from {self.config.start_date} to {self.config.end_date}...")

        # Get trading days from SPY (or first symbol with data)
        trading_days = self._get_trading_days()

        if show_progress:
            print(f"  {len(trading_days)} trading days")

        # Main simulation loop
        for i, current_date in enumerate(trading_days):
            self._simulate_day(current_date)

            if show_progress and (i + 1) % 50 == 0:
                equity = self.tracker.equity_curve[-1].equity if self.tracker.equity_curve else self.config.initial_equity
                print(f"  Day {i+1}/{len(trading_days)}: {current_date} | Equity: ${equity:,.0f} | Positions: {len(self.tracker.positions)}")

        # Close any remaining positions at end of test
        self._close_all_positions(trading_days[-1], "END_OF_TEST")

        # Calculate final metrics
        metrics = self.tracker.calculate_metrics()

        return BacktestResult(
            config=self.config,
            trades=self.tracker.trades,
            equity_curve=self.tracker.equity_curve,
            metrics=metrics,
            signals_generated=self.signals_generated,
            signals_filtered=self.signals_filtered,
            signals_skipped_size=self.signals_skipped_size,
            signals_skipped_limits=self.signals_skipped_limits,
            pyramid_triggers=self.pyramid_triggers,
            stop_exits=self.stop_exits,
            breakout_exits=self.breakout_exits,
        )

    def _load_all_data(self) -> None:
        """Load all historical data into memory."""
        # Add buffer before start for indicator warmup (need 55+ bars)
        buffer_start = self.config.start_date - timedelta(days=100)

        for symbol in self.symbols:
            bars = self.loader.get_bars(symbol, buffer_start, self.config.end_date)
            if bars:
                self._bars_by_symbol[symbol] = bars
                # Build date index for fast lookup
                self._bar_index[symbol] = {
                    bar.date: i for i, bar in enumerate(bars)
                }

    def _get_trading_days(self) -> list[date]:
        """Get list of trading days from the data."""
        # Use first symbol with data as reference
        for symbol in self.symbols:
            if symbol in self._bars_by_symbol:
                bars = self._bars_by_symbol[symbol]
                return [
                    bar.date for bar in bars
                    if self.config.start_date <= bar.date <= self.config.end_date
                ]
        return []

    def _get_bars_up_to(self, symbol: str, current_date: date, lookback: int = 60) -> list[Bar]:
        """Get bars up to and including current date.

        Args:
            symbol: Symbol to get bars for
            current_date: Current simulation date
            lookback: Number of bars to return

        Returns:
            List of bars ending at current_date
        """
        if symbol not in self._bar_index:
            return []

        idx_map = self._bar_index[symbol]
        if current_date not in idx_map:
            return []

        end_idx = idx_map[current_date]
        start_idx = max(0, end_idx - lookback + 1)

        return self._bars_by_symbol[symbol][start_idx:end_idx + 1]

    def _get_bar_for_date(self, symbol: str, current_date: date) -> Bar | None:
        """Get single bar for a date."""
        if symbol not in self._bar_index:
            return None
        idx_map = self._bar_index[symbol]
        if current_date not in idx_map:
            return None
        return self._bars_by_symbol[symbol][idx_map[current_date]]

    def _simulate_day(self, current_date: date) -> None:
        """Simulate a single trading day.

        Order of operations:
        1. Check stops (using day's low/high)
        2. Check breakout exits
        3. Check pyramid opportunities
        4. Detect new signals
        5. Filter and size signals
        6. Execute entries
        7. Record equity
        """
        # Get current prices for all symbols
        prices: dict[str, Decimal] = {}
        bars_today: dict[str, Bar] = {}

        for symbol in self.symbols:
            bar = self._get_bar_for_date(symbol, current_date)
            if bar:
                prices[symbol] = bar.close
                bars_today[symbol] = bar

        if not prices:
            return

        # 1. Check stops on existing positions
        self._check_stops(current_date, bars_today)

        # 2. Check breakout exits
        self._check_breakout_exits(current_date, bars_today)

        # 3. Check pyramid opportunities
        if self.config.use_pyramiding:
            self._check_pyramids(current_date, bars_today)

        # 4-6. Detect and process new signals
        self._process_new_signals(current_date, bars_today)

        # 7. Record equity
        self.tracker.record_equity(current_date, prices)

    def _check_stops(self, current_date: date, bars_today: dict[str, Bar]) -> None:
        """Check if any positions hit their stops."""
        positions_to_close = []

        for symbol, position in self.tracker.positions.items():
            bar = bars_today.get(symbol)
            if not bar:
                continue

            stop_hit = False
            exit_price = position.stop_price

            if position.direction == "LONG":
                # Long stop hit if day's low <= stop
                if bar.low <= position.stop_price:
                    stop_hit = True
                    exit_price = position.stop_price  # Assume filled at stop
            else:
                # Short stop hit if day's high >= stop
                if bar.high >= position.stop_price:
                    stop_hit = True
                    exit_price = position.stop_price

            if stop_hit:
                positions_to_close.append((symbol, exit_price))

        for symbol, exit_price in positions_to_close:
            self.tracker.close_position(symbol, current_date, exit_price, "STOP")
            self.stop_exits += 1

    def _check_breakout_exits(self, current_date: date, bars_today: dict[str, Bar]) -> None:
        """Check if positions should exit via opposite channel breakout."""
        positions_to_close = []

        for symbol, position in self.tracker.positions.items():
            bar = bars_today.get(symbol)
            if not bar:
                continue

            # Get bars for channel calculation
            bars = self._get_bars_up_to(symbol, current_date, 60)
            if len(bars) < 20:
                continue

            # S1 uses 10-day exit, S2 uses 20-day exit
            exit_period = 10 if position.system == "S1" else 20

            try:
                exit_channel = calculate_donchian(bars[:-1], exit_period)  # Exclude today
            except ValueError:
                continue

            should_exit = False
            exit_price = bar.close

            if position.direction == "LONG":
                # Exit long when price touches exit channel low
                if bar.low <= exit_channel.lower:
                    should_exit = True
                    exit_price = exit_channel.lower
            else:
                # Exit short when price touches exit channel high
                if bar.high >= exit_channel.upper:
                    should_exit = True
                    exit_price = exit_channel.upper

            if should_exit:
                positions_to_close.append((symbol, exit_price))

        for symbol, exit_price in positions_to_close:
            self.tracker.close_position(symbol, current_date, exit_price, "BREAKOUT")
            self.breakout_exits += 1

    def _check_pyramids(self, current_date: date, bars_today: dict[str, Bar]) -> None:
        """Check if positions should add pyramid units."""
        for symbol, position in list(self.tracker.positions.items()):
            # Check unit limits
            if position.units >= self.config.max_pyramid_units:
                continue

            bar = bars_today.get(symbol)
            if not bar:
                continue

            # Get current N
            bars = self._get_bars_up_to(symbol, current_date, 25)
            if len(bars) < 20:
                continue

            try:
                n_value = calculate_n(bars[-20:])
            except ValueError:
                continue

            # Pyramid trigger: price moves +½N from last entry
            half_n = n_value.value / 2
            last_price = position.last_pyramid_price

            should_pyramid = False
            pyramid_price = bar.close

            if position.direction == "LONG":
                trigger_price = last_price + half_n
                if bar.high >= trigger_price:
                    should_pyramid = True
                    pyramid_price = trigger_price
            else:
                trigger_price = last_price - half_n
                if bar.low <= trigger_price:
                    should_pyramid = True
                    pyramid_price = trigger_price

            if should_pyramid:
                # Check limits before pyramiding
                if not self._check_limits_for_add(symbol, position.correlation_group):
                    continue

                # Calculate size for pyramid (using notional equity per Rule 5)
                point_value = self._get_point_value(symbol)
                size = calculate_unit_size(
                    equity=self.tracker.sizing_equity,
                    n_value=n_value.value,
                    point_value=point_value,
                    risk_pct=self.config.risk_per_unit,
                )

                if size.contracts < 1:
                    continue

                # Calculate new stop (2N from newest entry)
                if position.direction == "LONG":
                    new_stop = pyramid_price - (2 * n_value.value)
                else:
                    new_stop = pyramid_price + (2 * n_value.value)

                self.tracker.add_pyramid(
                    symbol=symbol,
                    pyramid_date=current_date,
                    price=pyramid_price,
                    contracts=size.contracts,
                    new_stop=new_stop,
                )
                self.pyramid_triggers += 1

    def _process_new_signals(self, current_date: date, bars_today: dict[str, Bar]) -> None:
        """Detect, filter, and execute new entry signals."""
        signals = []

        for symbol in self.symbols:
            # Skip if already have position
            if symbol in self.tracker.positions:
                continue

            bar = bars_today.get(symbol)
            if not bar:
                continue

            # Get historical bars for indicators
            bars = self._get_bars_up_to(symbol, current_date, 60)
            if len(bars) < 55:
                continue

            # Calculate indicators (excluding today's bar for channels)
            try:
                n_value = calculate_n(bars[-20:])
                dc_20 = calculate_donchian(bars[:-1], 20)
                dc_55 = calculate_donchian(bars[:-1], 55)
            except ValueError:
                continue

            current_price = bar.close

            # Detect S1 signal (20-day breakout)
            if self.config.use_s1:
                s1_signal = self._detect_signal(
                    symbol, current_price, dc_20, "S1", bar, n_value.value
                )
                if s1_signal:
                    # Apply S1 filter (Rule 7)
                    if self.tracker.was_last_s1_winner(symbol):
                        self.signals_filtered += 1
                    else:
                        signals.append(s1_signal)
                        self.signals_generated += 1

            # Detect S2 signal (55-day breakout) - always take (failsafe)
            if self.config.use_s2:
                s2_signal = self._detect_signal(
                    symbol, current_price, dc_55, "S2", bar, n_value.value
                )
                if s2_signal:
                    signals.append(s2_signal)
                    self.signals_generated += 1

        # Sort by strength if configured
        if self.config.signal_priority == "strength":
            signals.sort(key=lambda s: s["strength"], reverse=True)

        # Execute signals respecting limits
        for signal in signals:
            self._try_enter_position(current_date, signal)

    def _detect_signal(
        self,
        symbol: str,
        price: Decimal,
        channel: DonchianChannel,
        system: Literal["S1", "S2"],
        bar: Bar,
        n_value: Decimal,
    ) -> dict | None:
        """Detect a breakout signal.

        Returns signal dict with strength metric for prioritization.
        """
        direction = None
        channel_value = None

        # Check for long breakout (price > channel upper)
        if bar.high > channel.upper:
            direction = "LONG"
            channel_value = channel.upper
            # Use high as entry price if breakout
            entry_price = max(channel.upper, bar.open)  # Gap handling

        # Check for short breakout (price < channel lower)
        elif bar.low < channel.lower and self.config.allow_short:
            direction = "SHORT"
            channel_value = channel.lower
            entry_price = min(channel.lower, bar.open)

        if not direction:
            return None

        # Calculate strength: (price - breakout) / N
        # Higher = stronger breakout
        if direction == "LONG":
            strength = (entry_price - channel_value) / n_value if n_value > 0 else Decimal("0")
        else:
            strength = (channel_value - entry_price) / n_value if n_value > 0 else Decimal("0")

        return {
            "symbol": symbol,
            "direction": direction,
            "system": system,
            "entry_price": entry_price,
            "channel_value": channel_value,
            "n_value": n_value,
            "strength": strength,
            "correlation_group": get_correlation_group(symbol),
        }

    def _try_enter_position(self, current_date: date, signal: dict) -> bool:
        """Try to enter a position, respecting limits.

        Returns True if position was entered.
        """
        symbol = signal["symbol"]
        direction = signal["direction"]
        n_value = signal["n_value"]
        entry_price = signal["entry_price"]
        correlation_group = signal["correlation_group"]

        # Check if we already have a position (may have entered earlier this day)
        if symbol in self.tracker.positions:
            return False

        # Check limits
        if not self._check_limits_for_add(symbol, correlation_group):
            self.signals_skipped_limits += 1
            return False

        # Get point value for this symbol
        point_value = self._get_point_value(symbol)

        # Calculate size based on risk (using notional equity per Rule 5)
        size = calculate_unit_size(
            equity=self.tracker.sizing_equity,
            n_value=n_value,
            point_value=point_value,
            risk_pct=self.config.risk_per_unit,
        )

        if size.contracts < 1:
            self.signals_skipped_size += 1
            return False

        contracts = size.contracts

        # Limit position value to 25% of notional equity (basic diversification)
        # This uses notional equity (which reduces during drawdowns per Rule 5)
        max_position_value = self.tracker.sizing_equity * Decimal("0.25")
        position_value = entry_price * contracts * point_value

        if position_value > max_position_value:
            # Scale down to max allowed
            contracts = int(max_position_value / (entry_price * point_value))
            if contracts < 1:
                self.signals_skipped_size += 1
                return False

        # Calculate stop (2N from entry)
        if direction == "LONG":
            stop_price = entry_price - (2 * n_value)
        else:
            stop_price = entry_price + (2 * n_value)

        # Enter position
        self.tracker.open_position(
            symbol=symbol,
            direction=direction,
            system=signal["system"],
            entry_date=current_date,
            entry_price=entry_price,
            entry_n=n_value,
            contracts=contracts,
            stop_price=stop_price,
            correlation_group=correlation_group,
        )

        return True

    def _check_limits_for_add(self, symbol: str, correlation_group: str | None) -> bool:
        """Check if we can add a position given current limits."""
        # Per-market limit
        current_units = self.tracker.units_for_symbol(symbol)
        if current_units >= self.config.max_units_per_market:
            return False

        # Correlation limit
        if correlation_group and self.config.use_correlation_limits:
            corr_units = self.tracker.units_for_correlation_group(correlation_group)
            if corr_units >= self.config.max_units_correlated:
                return False

        # Total limit (risk cap mode or unit count)
        if self.config.use_risk_cap_mode:
            total_risk = self.tracker.total_risk
            if total_risk >= self.config.max_total_risk:
                return False
        else:
            if self.tracker.total_units >= self.config.max_units_total:
                return False

        return True

    def _close_all_positions(self, current_date: date, reason: Literal["STOP", "BREAKOUT", "END_OF_TEST"]) -> None:
        """Close all open positions."""
        for symbol in list(self.tracker.positions.keys()):
            bar = self._get_bar_for_date(symbol, current_date)
            if bar:
                self.tracker.close_position(symbol, current_date, bar.close, reason)


def run_backtest(
    start_date: date | None = None,
    end_date: date | None = None,
    initial_equity: Decimal = Decimal("50000"),
    symbols: list[str] | None = None,
    show_progress: bool = True,
) -> BacktestResult:
    """Convenience function to run a backtest.

    Args:
        start_date: Start date (default: 2024-01-01)
        end_date: End date (default: 2025-12-31)
        initial_equity: Starting equity
        symbols: Symbols to trade (default: ETF universe)
        show_progress: Print progress

    Returns:
        BacktestResult
    """
    config = BacktestConfig(
        start_date=start_date or date(2024, 1, 1),
        end_date=end_date or date(2025, 12, 31),
        initial_equity=initial_equity,
    )

    engine = BacktestEngine(config=config, symbols=symbols)
    return engine.run(show_progress=show_progress)
