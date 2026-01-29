"""Query to get trading universe from database.

This loads the list of active markets to scan/trade.
"""

from dataclasses import dataclass
from decimal import Decimal

from src.infrastructure.database import fetch


@dataclass
class MarketInfo:
    """Information about a tradable market."""

    symbol: str
    name: str
    exchange: str
    asset_class: str  # futures, etf, stock
    correlation_group: str
    point_value: Decimal
    tick_size: Decimal


async def get_active_universe() -> list[str]:
    """Get list of all active symbols.

    Returns:
        List of symbols like ['/MGC', '/MES', 'SPY', 'AAPL', ...]
    """
    rows = await fetch(
        "SELECT symbol FROM markets WHERE is_active = TRUE ORDER BY symbol"
    )
    return [row["symbol"] for row in rows]


async def get_futures_universe() -> list[str]:
    """Get only futures symbols.

    Returns:
        List of futures symbols like ['/MGC', '/MES', '/CL', ...]
    """
    rows = await fetch(
        """
        SELECT symbol FROM markets
        WHERE is_active = TRUE AND asset_class = 'futures'
        ORDER BY symbol
        """
    )
    return [row["symbol"] for row in rows]


async def get_micro_futures_universe() -> list[str]:
    """Get only micro futures symbols (for live trading with smaller account).

    Returns:
        List of micro futures like ['/MGC', '/MES', '/MCL', ...]
    """
    rows = await fetch(
        """
        SELECT symbol FROM markets
        WHERE is_active = TRUE
          AND asset_class = 'futures'
          AND (symbol LIKE '/M%' OR symbol LIKE '/SIL')
        ORDER BY symbol
        """
    )
    return [row["symbol"] for row in rows]


async def get_etf_universe() -> list[str]:
    """Get only ETF symbols.

    Returns:
        List of ETFs like ['SPY', 'QQQ', 'GLD', ...]
    """
    rows = await fetch(
        """
        SELECT symbol FROM markets
        WHERE is_active = TRUE AND asset_class = 'etf'
        ORDER BY symbol
        """
    )
    return [row["symbol"] for row in rows]


async def get_stock_universe() -> list[str]:
    """Get only individual stock symbols.

    Returns:
        List of stocks like ['AAPL', 'MSFT', 'NVDA', ...]
    """
    rows = await fetch(
        """
        SELECT symbol FROM markets
        WHERE is_active = TRUE AND asset_class = 'stock'
        ORDER BY symbol
        """
    )
    return [row["symbol"] for row in rows]


async def get_small_account_universe() -> list[str]:
    """Get the 15-ETF small account universe.

    This universe was validated via backtesting for $50k accounts:
    - $50k -> $1.08M (2068% return) over 2020-2025
    - 15 ETFs across 8 distinct sectors
    - Same drawdown profile as larger universe

    Returns:
        List of 15 ETFs: ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM', 'XLE', 'XLU',
                          'TLT', 'IEF', 'GLD', 'SLV', 'USO', 'DBA', 'VNQ', 'FXE']
    """
    rows = await fetch(
        """
        SELECT symbol FROM markets
        WHERE is_active = TRUE AND small_account = TRUE
        ORDER BY symbol
        """
    )
    return [row["symbol"] for row in rows]


async def get_universe_by_correlation_group(group: str) -> list[str]:
    """Get symbols in a specific correlation group.

    Args:
        group: Correlation group like 'metals_precious', 'equity_us_tech'

    Returns:
        List of symbols in that group
    """
    rows = await fetch(
        """
        SELECT symbol FROM markets
        WHERE is_active = TRUE AND correlation_group = $1
        ORDER BY symbol
        """,
        group,
    )
    return [row["symbol"] for row in rows]


async def get_market_info(symbol: str) -> MarketInfo | None:
    """Get full info for a single market.

    Args:
        symbol: Market symbol like '/MGC' or 'AAPL'

    Returns:
        MarketInfo or None if not found
    """
    from src.infrastructure.database import fetchrow

    row = await fetchrow(
        """
        SELECT symbol, name, exchange, asset_class, correlation_group,
               point_value, tick_size
        FROM markets
        WHERE symbol = $1
        """,
        symbol,
    )

    if not row:
        return None

    return MarketInfo(
        symbol=row["symbol"],
        name=row["name"],
        exchange=row["exchange"],
        asset_class=row["asset_class"],
        correlation_group=row["correlation_group"] or "uncorrelated",
        point_value=Decimal(str(row["point_value"])),
        tick_size=Decimal(str(row["tick_size"])),
    )


async def get_all_markets() -> list[MarketInfo]:
    """Get full info for all active markets.

    Returns:
        List of MarketInfo for all active markets
    """
    rows = await fetch(
        """
        SELECT symbol, name, exchange, asset_class, correlation_group,
               point_value, tick_size
        FROM markets
        WHERE is_active = TRUE
        ORDER BY asset_class, correlation_group, symbol
        """
    )

    return [
        MarketInfo(
            symbol=row["symbol"],
            name=row["name"],
            exchange=row["exchange"],
            asset_class=row["asset_class"],
            correlation_group=row["correlation_group"] or "uncorrelated",
            point_value=Decimal(str(row["point_value"])),
            tick_size=Decimal(str(row["tick_size"])),
        )
        for row in rows
    ]


async def get_correlation_groups() -> dict[str, list[str]]:
    """Get all symbols organized by correlation group.

    Returns:
        Dict like {'metals_precious': ['/GC', '/MGC', 'GLD'], ...}
    """
    rows = await fetch(
        """
        SELECT correlation_group, symbol FROM markets
        WHERE is_active = TRUE AND correlation_group IS NOT NULL
        ORDER BY correlation_group, symbol
        """
    )

    groups: dict[str, list[str]] = {}
    for row in rows:
        group = row["correlation_group"]
        if group not in groups:
            groups[group] = []
        groups[group].append(row["symbol"])

    return groups


async def count_markets() -> dict[str, int]:
    """Get count of markets by asset class.

    Returns:
        Dict like {'futures': 82, 'etf': 41, 'stock': 105}
    """
    rows = await fetch(
        """
        SELECT asset_class, COUNT(*) as count
        FROM markets
        WHERE is_active = TRUE
        GROUP BY asset_class
        """
    )

    return {row["asset_class"]: row["count"] for row in rows}
