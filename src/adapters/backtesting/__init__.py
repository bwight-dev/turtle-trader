"""Backtesting infrastructure for Turtle Trading Bot."""

from src.adapters.backtesting.data_loader import (
    ETF_UNIVERSE,
    FUTURES_POINT_VALUES,
    FUTURES_UNIVERSE,
    MEDIUM_FUTURES_UNIVERSE,
    MICRO_CURRENCY_UNIVERSE,
    MICRO_FUTURES_UNIVERSE,
    SMALL_ACCOUNT_CORRELATION_GROUPS,
    SMALL_ACCOUNT_ETF_UNIVERSE,
    SMALL_FUTURES_UNIVERSE,
    HistoricalDataLoader,
    get_correlation_group,
    get_point_value,
)
from src.adapters.backtesting.engine import BacktestEngine, run_backtest
from src.adapters.backtesting.models import (
    BacktestConfig,
    BacktestResult,
    PerformanceMetrics,
    TradeRecord,
)
from src.adapters.backtesting.tracker import OpenPosition, StateTracker

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "ETF_UNIVERSE",
    "FUTURES_POINT_VALUES",
    "FUTURES_UNIVERSE",
    "MEDIUM_FUTURES_UNIVERSE",
    "MICRO_CURRENCY_UNIVERSE",
    "MICRO_FUTURES_UNIVERSE",
    "HistoricalDataLoader",
    "OpenPosition",
    "PerformanceMetrics",
    "SMALL_ACCOUNT_CORRELATION_GROUPS",
    "SMALL_ACCOUNT_ETF_UNIVERSE",
    "SMALL_FUTURES_UNIVERSE",
    "StateTracker",
    "TradeRecord",
    "get_correlation_group",
    "get_point_value",
    "run_backtest",
]
