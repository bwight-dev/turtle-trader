"""Data validation services for market data quality checks."""

from decimal import Decimal

from src.domain.models.market import Bar


class BarValidationError(Exception):
    """Raised when bar data fails validation."""

    pass


def validate_bar(bar: Bar) -> tuple[bool, str]:
    """Validate a single bar for data quality.

    Checks:
    - High >= Low
    - High >= Open, Close
    - Low <= Open, Close
    - All prices positive
    - No extreme outliers (price not 0)

    Args:
        bar: Bar to validate

    Returns:
        Tuple of (is_valid, reason)
    """
    # Check positivity
    if bar.open <= 0:
        return False, f"Open price <= 0: {bar.open}"
    if bar.high <= 0:
        return False, f"High price <= 0: {bar.high}"
    if bar.low <= 0:
        return False, f"Low price <= 0: {bar.low}"
    if bar.close <= 0:
        return False, f"Close price <= 0: {bar.close}"

    # Check OHLC relationships
    if bar.high < bar.low:
        return False, f"High ({bar.high}) < Low ({bar.low})"
    if bar.high < bar.open:
        return False, f"High ({bar.high}) < Open ({bar.open})"
    if bar.high < bar.close:
        return False, f"High ({bar.high}) < Close ({bar.close})"
    if bar.low > bar.open:
        return False, f"Low ({bar.low}) > Open ({bar.open})"
    if bar.low > bar.close:
        return False, f"Low ({bar.low}) > Close ({bar.close})"

    return True, "OK"


def validate_bars(bars: list[Bar]) -> tuple[bool, list[str]]:
    """Validate a list of bars.

    Args:
        bars: List of bars to validate

    Returns:
        Tuple of (all_valid, list of error messages)
    """
    errors: list[str] = []

    for i, bar in enumerate(bars):
        valid, reason = validate_bar(bar)
        if not valid:
            errors.append(f"Bar {i} ({bar.date}): {reason}")

    return len(errors) == 0, errors


def compare_bars(
    bar1: Bar,
    bar2: Bar,
    max_deviation_pct: Decimal = Decimal("2.0"),
) -> tuple[bool, str]:
    """Compare two bars from different sources for consistency.

    Used to validate data between IBKR and Yahoo.

    Args:
        bar1: First bar (e.g., from IBKR)
        bar2: Second bar (e.g., from Yahoo)
        max_deviation_pct: Maximum allowed price deviation percentage

    Returns:
        Tuple of (is_consistent, reason)
    """
    if bar1.date != bar2.date:
        return False, f"Dates don't match: {bar1.date} vs {bar2.date}"

    # Compare close prices (most reliable comparison point)
    if bar1.close == 0 or bar2.close == 0:
        return False, "Zero close price"

    deviation = abs(bar1.close - bar2.close) / bar1.close * 100

    if deviation > max_deviation_pct:
        return False, (
            f"Close price deviation {deviation:.2f}% exceeds {max_deviation_pct}%: "
            f"{bar1.close} vs {bar2.close}"
        )

    return True, f"Deviation {deviation:.2f}% within tolerance"


def filter_valid_bars(bars: list[Bar]) -> list[Bar]:
    """Filter out invalid bars from a list.

    Args:
        bars: List of bars to filter

    Returns:
        List of valid bars only
    """
    return [bar for bar in bars if validate_bar(bar)[0]]
