"""ETF correlation group mapping for position limits.

Maps ETF symbols to CorrelationGroup enum values for enforcing
the 6-unit correlated market limit (Turtle Rule).
"""

from src.domain.models.enums import CorrelationGroup

# ETF to CorrelationGroup mapping
# Based on SMALL_ACCOUNT_ETF_UNIVERSE in data_loader.py
ETF_CORRELATION_GROUPS: dict[str, CorrelationGroup] = {
    # Equity - US (correlated)
    "SPY": CorrelationGroup.EQUITY_US,
    "QQQ": CorrelationGroup.EQUITY_US,
    "IWM": CorrelationGroup.EQUITY_US,

    # Equity - International
    "EFA": CorrelationGroup.EQUITY_INTL,
    "EEM": CorrelationGroup.EQUITY_INTL,

    # Energy sector
    "XLE": CorrelationGroup.ENERGY,
    "USO": CorrelationGroup.ENERGY,

    # Metals
    "GLD": CorrelationGroup.METALS,
    "SLV": CorrelationGroup.METALS,

    # Rates/Bonds
    "TLT": CorrelationGroup.RATES,
    "IEF": CorrelationGroup.RATES,

    # Utilities (sector, correlated with equities)
    "XLU": CorrelationGroup.EQUITY_US,

    # Agriculture/Commodities
    "DBA": CorrelationGroup.GRAINS,

    # Real Estate (correlated with equities and rates)
    "VNQ": CorrelationGroup.EQUITY_US,

    # Currency
    "FXE": CorrelationGroup.CURRENCIES,
}


def get_etf_correlation_group(symbol: str) -> CorrelationGroup | None:
    """Get correlation group for an ETF symbol.

    Args:
        symbol: ETF symbol (e.g., 'SPY', 'GLD')

    Returns:
        CorrelationGroup if symbol is mapped, None otherwise
    """
    return ETF_CORRELATION_GROUPS.get(symbol)
