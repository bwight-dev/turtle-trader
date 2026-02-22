"""Historical data loader with SQLite caching for backtesting.

Fetches OHLCV data from Yahoo Finance and caches locally in SQLite
for fast, repeatable backtests without hitting API limits.
"""

import sqlite3
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import yfinance as yf

from src.domain.models.market import Bar


# Default ETF universe for MVP backtesting
ETF_UNIVERSE = [
    # Broad market
    "SPY", "QQQ", "IWM", "DIA", "MDY",
    # Sectors
    "XLF", "XLE", "XLK", "XLV", "XLI", "XLU", "XLP", "XLY", "XLB",
    # International
    "EEM", "EFA", "VWO", "FXI",
    # Bonds
    "TLT", "IEF", "LQD", "HYG", "TIP",
    # Commodities (ETF proxies)
    "GLD", "SLV", "USO", "UNG", "DBA", "DBC",
    # Real Estate
    "VNQ", "IYR",
]

# ============================================================================
# SMALL ACCOUNT ETF UNIVERSE ($50k accounts)
# ============================================================================
# 15 diversified ETFs covering major asset classes and sectors.
# ETFs solve the "granularity problem" - can buy exact share amounts.
#
# Key insight: With $50k at 0.5% risk ($250/trade), you need instruments
# where position sizing math allows 1+ shares. ETFs with ~$1-2 daily ATR
# and prices under $500 work perfectly.
#
# Based on:
# - Tom Basso's diversification research (Market Wizards)
# - Jerry Parker's ETF advice for small accounts
# - Salem Abraham's approach (maximize opportunities within capital)
# ============================================================================

SMALL_ACCOUNT_ETF_UNIVERSE = [
    # === EQUITY INDEX (3) - broad market exposure ===
    "SPY",   # S&P 500 - large cap US
    "QQQ",   # Nasdaq 100 - tech-heavy growth
    "IWM",   # Russell 2000 - small cap US

    # === INTERNATIONAL EQUITY (2) ===
    "EFA",   # EAFE - developed international
    "EEM",   # Emerging Markets

    # === SECTORS (2) - uncorrelated to broad market ===
    "XLE",   # Energy sector
    "XLU",   # Utilities sector (defensive, uncorrelated)

    # === BONDS (2) ===
    "TLT",   # 20+ Year Treasury - long duration
    "IEF",   # 7-10 Year Treasury - intermediate

    # === COMMODITIES (4) - diversified real assets ===
    "GLD",   # Gold - precious metals
    "SLV",   # Silver - precious metals (higher beta)
    "USO",   # Crude Oil - energy
    "DBA",   # Agriculture - grains, softs, meats

    # === REAL ESTATE (1) ===
    "VNQ",   # US REITs - real estate exposure

    # === CURRENCY (1) ===
    "FXE",   # Euro Currency Trust - forex
]
# Total: 15 markets across 8 distinct sectors
# Provides broad diversification while remaining manageable for $50k

# Small account correlation groups
SMALL_ACCOUNT_CORRELATION_GROUPS = {
    # Equity - US (correlated)
    "equity_us_large": ["SPY"],
    "equity_us_tech": ["QQQ"],
    "equity_us_small": ["IWM"],
    # Equity - International
    "equity_developed": ["EFA"],
    "equity_emerging": ["EEM"],
    # Sectors
    "sector_energy": ["XLE"],
    "sector_utilities": ["XLU"],
    # Bonds
    "bonds_long": ["TLT"],
    "bonds_mid": ["IEF"],
    # Commodities
    "metals_precious": ["GLD", "SLV"],
    "energy_oil": ["USO"],
    "commodities_ag": ["DBA"],
    # Real Estate
    "real_estate": ["VNQ"],
    # Currency
    "currency_euro": ["FXE"],
}

# ============================================================================
# FUTURES UNIVERSES BY ACCOUNT SIZE
# ============================================================================
# Dollar volatility = ATR × point_value
# Max tradeable = (equity × risk%) / (2 × dollar_vol) >= 1 contract
#
# At $100k with 1% risk ($1000 budget, 2N stop): DolVol must be <= $500
# At $100k with 2% risk ($2000 budget, 2N stop): DolVol must be <= $1000
# ============================================================================

# SMALL ACCOUNT UNIVERSE: $50k-$100k at 1% risk
# 11 diversified markets with dollar volatility <= $500
SMALL_FUTURES_UNIVERSE = [
    # === EQUITY INDEX (3) ===
    "MES=F",  # Micro S&P 500: DolVol ~$340
    "MYM=F",  # Micro Dow: DolVol ~$270
    "M2K=F",  # Micro Russell: DolVol ~$200

    # === BONDS (2) ===
    "ZN=F",   # 10-Year Treasury: DolVol ~$350
    "ZF=F",   # 5-Year Treasury: DolVol ~$195

    # === GRAINS (3) ===
    "ZC=F",   # Corn: DolVol ~$300
    "ZW=F",   # Wheat: DolVol ~$450
    "ZO=F",   # Oats: DolVol ~$390

    # === SOFTS (2) ===
    "CT=F",   # Cotton: DolVol ~$325
    "SB=F",   # Sugar: DolVol ~$315

    # === MEATS (1) ===
    "HE=F",   # Lean Hogs: DolVol ~$470
]
# Total: 11 markets, 6 sectors

# MEDIUM ACCOUNT UNIVERSE: $100k-$250k at 2% risk (or $200k+ at 1%)
# 15 diversified markets with dollar volatility <= $1000
MEDIUM_FUTURES_UNIVERSE = [
    # === EQUITY INDEX (4) ===
    "MES=F",  # Micro S&P 500: DolVol ~$340
    "MNQ=F",  # Micro Nasdaq: DolVol ~$710
    "MYM=F",  # Micro Dow: DolVol ~$270
    "M2K=F",  # Micro Russell: DolVol ~$200

    # === BONDS (3) ===
    "ZB=F",   # 30-Year Treasury: DolVol ~$750
    "ZN=F",   # 10-Year Treasury: DolVol ~$350
    "ZF=F",   # 5-Year Treasury: DolVol ~$195

    # === ENERGY (1) ===
    "QM=F",   # E-mini Crude: DolVol ~$860

    # === GRAINS (4) ===
    "ZC=F",   # Corn: DolVol ~$300
    "ZW=F",   # Wheat: DolVol ~$450
    "ZS=F",   # Soybeans: DolVol ~$660
    "ZO=F",   # Oats: DolVol ~$390

    # === SOFTS (2) ===
    "CT=F",   # Cotton: DolVol ~$325
    "SB=F",   # Sugar: DolVol ~$315

    # === MEATS (1) ===
    "HE=F",   # Lean Hogs: DolVol ~$470
]
# Total: 15 markets, 6 sectors (no metals - too volatile for <$250k)

# DEPRECATED: Keep for backwards compatibility
# This was too ambitious - many markets have DolVol > $1000
MICRO_FUTURES_UNIVERSE = MEDIUM_FUTURES_UNIVERSE

# Currency micros - still have high multipliers ($6k-$12k/point)
# Only suitable for accounts $250k+ or with reduced risk settings
MICRO_CURRENCY_UNIVERSE = [
    "M6E=F",  # Micro Euro FX: $12,500/point
    "M6A=F",  # Micro Australian Dollar: $10,000/point
    "M6B=F",  # Micro British Pound: $6,250/point
    "MJY=F",  # Micro Japanese Yen: $12,500/point
]

# Standard futures universe for backtesting (Yahoo continuous contracts)
# Requires larger accounts ($500k+) for proper position sizing
FUTURES_UNIVERSE = [
    # Equity Index
    "ES=F",   # E-mini S&P 500
    "NQ=F",   # E-mini Nasdaq 100
    "YM=F",   # Mini Dow
    "RTY=F",  # E-mini Russell 2000
    # Metals
    "GC=F",   # Gold
    "SI=F",   # Silver
    "HG=F",   # Copper
    # Energy
    "CL=F",   # Crude Oil
    "NG=F",   # Natural Gas
    "RB=F",   # RBOB Gasoline
    # Bonds
    "ZB=F",   # 30-Year Treasury
    "ZN=F",   # 10-Year Treasury
    "ZF=F",   # 5-Year Treasury
    # Currencies
    "6E=F",   # Euro FX
    "6J=F",   # Japanese Yen
    "6B=F",   # British Pound
    "6A=F",   # Australian Dollar
    "6C=F",   # Canadian Dollar
    # Agriculturals
    "ZC=F",   # Corn
    "ZS=F",   # Soybeans
    "ZW=F",   # Wheat
    "KC=F",   # Coffee
    "CT=F",   # Cotton
    "SB=F",   # Sugar
]

# Point values (multipliers) for futures contracts
# These are the dollar value per 1-point move
FUTURES_POINT_VALUES = {
    # =========== MICRO/MINI FUTURES (for accounts $50k-$500k) ===========
    # Micro Equity Index
    "MES=F": 5,       # Micro E-mini S&P: $5/point (1/10th of ES)
    "MNQ=F": 2,       # Micro E-mini Nasdaq: $2/point (1/10th of NQ)
    "MYM=F": 0.5,     # Micro E-mini Dow: $0.50/point (1/10th of YM)
    "M2K=F": 5,       # Micro E-mini Russell: $5/point (1/10th of RTY)
    # Micro Metals
    "MGC=F": 10,      # Micro Gold: $10/oz (10 oz contract)
    "SIL=F": 1000,    # Micro Silver: $1000/dollar (1000 oz contract)
    # Mini Energy
    "QM=F": 500,      # E-mini Crude Oil: $500/point (half of CL)
    # Micro Currencies (high multipliers - need $250k+)
    "M6E=F": 12500,   # Micro Euro: $12,500/euro (1/10th of 6E)
    "M6A=F": 10000,   # Micro AUD: $10,000/AUD (1/10th of 6A)
    "M6B=F": 6250,    # Micro GBP: $6,250/pound (1/10th of 6B)
    "MJY=F": 12500,   # Micro JPY: $12,500/100 yen (1/10th of 6J)

    # =========== GRAINS (small multipliers, good for small accounts) ===========
    "ZC=F": 50,       # Corn: $50/cent (5000 bushels)
    "ZW=F": 50,       # Wheat: $50/cent (5000 bushels)
    "ZS=F": 50,       # Soybeans: $50/cent (5000 bushels)
    "ZO=F": 50,       # Oats: $50/cent (5000 bushels)
    "ZR=F": 50,       # Rice: $50/cent (2000 cwt)

    # =========== SOFTS ===========
    "CC=F": 10,       # Cocoa: $10/point (10 metric tons)
    "OJ=F": 150,      # Orange Juice: $150/point (15000 lbs)
    "KC=F": 375,      # Coffee: $375/cent (37,500 lbs)
    "CT=F": 500,      # Cotton: $500/cent (50,000 lbs)
    "SB=F": 1120,     # Sugar: $1120/cent (112,000 lbs)

    # =========== MEATS ===========
    "LE=F": 400,      # Live Cattle: $400/cent (40,000 lbs)
    "HE=F": 400,      # Lean Hogs: $400/cent (40,000 lbs)
    "GF=F": 500,      # Feeder Cattle: $500/cent (50,000 lbs)

    # =========== STANDARD FUTURES (require accounts $500k+) ===========
    # Equity Index
    "ES=F": 50,       # E-mini S&P: $50/point
    "NQ=F": 20,       # E-mini Nasdaq: $20/point
    "YM=F": 5,        # Mini Dow: $5/point
    "RTY=F": 50,      # E-mini Russell: $50/point
    # Metals
    "GC=F": 100,      # Gold: $100/oz (100 oz contract)
    "SI=F": 5000,     # Silver: $5000/dollar (5000 oz contract)
    "HG=F": 250,      # Copper: $250/cent (25000 lbs)
    # Energy
    "CL=F": 1000,     # Crude Oil: $1000/dollar (1000 bbls)
    "NG=F": 10000,    # Natural Gas: $10000/dollar (10000 mmBtu)
    "RB=F": 42000,    # RBOB Gasoline: $42000/dollar
    # Bonds (each point = $1000)
    "ZB=F": 1000,     # 30-Year Treasury: $1000/point
    "ZN=F": 1000,     # 10-Year Treasury: $1000/point
    "ZF=F": 1000,     # 5-Year Treasury: $1000/point
    # Currencies (each point = full contract value move)
    "6E=F": 125000,   # Euro FX: $125,000/euro
    "6J=F": 125000,   # Japanese Yen: $125,000/100 yen
    "6B=F": 62500,    # British Pound: $62,500/pound
    "6A=F": 100000,   # Australian Dollar: $100,000/AUD
    "6C=F": 100000,   # Canadian Dollar: $100,000/CAD
}

# Futures correlation groups for position limits
# Includes both standard and micro contracts in same groups
FUTURES_CORRELATION_GROUPS = {
    # Equity - US (standard and micro are correlated)
    "equity_us": ["ES=F", "NQ=F", "YM=F", "RTY=F", "MES=F", "MNQ=F", "MYM=F", "M2K=F"],
    # Metals
    "metals_precious": ["GC=F", "SI=F", "MGC=F", "SIL=F"],
    "metals_base": ["HG=F"],
    # Energy
    "energy_petroleum": ["CL=F", "RB=F", "QM=F"],
    "energy_gas": ["NG=F"],
    # Bonds
    "bonds_us": ["ZB=F", "ZN=F", "ZF=F"],
    # Currencies (standard and micro are correlated)
    "currencies_europe": ["6E=F", "6B=F", "M6E=F", "M6B=F"],
    "currencies_pacific": ["6J=F", "6A=F", "MJY=F", "M6A=F"],
    "currencies_americas": ["6C=F"],
    # Grains (corn, wheat, soybeans are correlated)
    "grains_corn": ["ZC=F"],
    "grains_wheat": ["ZW=F"],
    "grains_soybeans": ["ZS=F"],
    "grains_other": ["ZO=F", "ZR=F"],
    # Softs (each is fairly independent)
    "softs_coffee": ["KC=F"],
    "softs_cocoa": ["CC=F"],
    "softs_sugar": ["SB=F"],
    "softs_cotton": ["CT=F"],
    "softs_oj": ["OJ=F"],
    # Meats (cattle are correlated, hogs separate)
    "meats_cattle": ["LE=F", "GF=F"],
    "meats_hogs": ["HE=F"],
}


def get_point_value(symbol: str) -> float:
    """Get the point value (multiplier) for a symbol.

    Returns 1.0 for ETFs/stocks, contract multiplier for futures.
    """
    return FUTURES_POINT_VALUES.get(symbol, 1.0)


# Correlation groups for position limits
ETF_CORRELATION_GROUPS = {
    # Equity - US
    "equity_us": ["SPY", "DIA", "MDY"],
    "equity_us_tech": ["QQQ", "XLK"],
    "equity_us_small": ["IWM"],
    # Sectors (each its own group)
    "sector_financials": ["XLF"],
    "sector_energy": ["XLE"],
    "sector_healthcare": ["XLV"],
    "sector_industrials": ["XLI"],
    "sector_utilities": ["XLU"],
    "sector_staples": ["XLP"],
    "sector_discretionary": ["XLY"],
    "sector_materials": ["XLB"],
    # International
    "equity_emerging": ["EEM", "VWO"],
    "equity_developed": ["EFA"],
    "equity_china": ["FXI"],
    # Bonds
    "bonds_long": ["TLT"],
    "bonds_mid": ["IEF"],
    "bonds_corporate": ["LQD", "HYG"],
    "bonds_tips": ["TIP"],
    # Commodities
    "metals_precious": ["GLD", "SLV"],
    "energy_oil": ["USO"],
    "energy_gas": ["UNG"],
    "commodities_ag": ["DBA"],
    "commodities_broad": ["DBC"],
    # Real Estate
    "real_estate": ["VNQ", "IYR"],
}


def get_correlation_group(symbol: str) -> str | None:
    """Get correlation group for a symbol.

    Checks small account, ETF, and futures correlation groups.
    """
    # Check small account groups first (more specific)
    for group, symbols in SMALL_ACCOUNT_CORRELATION_GROUPS.items():
        if symbol in symbols:
            return group
    # Check futures
    for group, symbols in FUTURES_CORRELATION_GROUPS.items():
        if symbol in symbols:
            return group
    # Then ETFs
    for group, symbols in ETF_CORRELATION_GROUPS.items():
        if symbol in symbols:
            return group
    return None


class HistoricalDataLoader:
    """Loads and caches historical OHLCV data for backtesting.

    Uses SQLite for local caching to avoid repeated API calls.
    First fetch may take a while; subsequent loads are instant.
    """

    def __init__(
        self,
        cache_path: str | Path = "data/backtest_cache.db",
        requests_per_minute: int = 30,  # Conservative rate limit
    ):
        """Initialize the data loader.

        Args:
            cache_path: Path to SQLite cache file
            requests_per_minute: Max Yahoo requests per minute
        """
        self._cache_path = Path(cache_path)
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._rate_limit = requests_per_minute
        self._last_request_time = 0.0
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        with sqlite3.connect(self._cache_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bars (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (symbol, date)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bars_symbol
                ON bars(symbol)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fetch_log (
                    symbol TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    bar_count INTEGER NOT NULL,
                    PRIMARY KEY (symbol, start_date, end_date)
                )
            """)
            conn.commit()

    def _rate_limit_wait(self) -> None:
        """Wait if needed to respect rate limits."""
        min_interval = 60.0 / self._rate_limit
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    def get_bars(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        force_refresh: bool = False,
    ) -> list[Bar]:
        """Get historical bars for a symbol.

        Checks cache first, fetches from Yahoo if not cached.

        Args:
            symbol: Ticker symbol (e.g., "SPY")
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            force_refresh: If True, skip cache and re-fetch

        Returns:
            List of Bar objects, oldest first
        """
        if not force_refresh:
            cached = self._load_from_cache(symbol, start_date, end_date)
            if cached:
                return cached

        # Fetch from Yahoo
        bars = self._fetch_from_yahoo(symbol, start_date, end_date)

        if bars:
            self._save_to_cache(symbol, bars, start_date, end_date)

        return bars

    def _load_from_cache(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[Bar] | None:
        """Load bars from SQLite cache.

        Returns None if cache doesn't cover the full date range.
        """
        with sqlite3.connect(self._cache_path) as conn:
            # Check if we have data for this range
            cursor = conn.execute(
                """
                SELECT MIN(date), MAX(date), COUNT(*)
                FROM bars
                WHERE symbol = ? AND date >= ? AND date <= ?
                """,
                (symbol, start_date.isoformat(), end_date.isoformat()),
            )
            row = cursor.fetchone()

            if not row or not row[0]:
                return None

            cached_start, cached_end, count = row

            # Require at least 80% coverage (accounting for weekends/holidays)
            expected_days = (end_date - start_date).days
            expected_trading_days = int(expected_days * 5 / 7 * 0.95)  # ~95% for holidays

            if count < expected_trading_days * 0.8:
                return None

            # Load the bars
            cursor = conn.execute(
                """
                SELECT symbol, date, open, high, low, close, volume
                FROM bars
                WHERE symbol = ? AND date >= ? AND date <= ?
                ORDER BY date
                """,
                (symbol, start_date.isoformat(), end_date.isoformat()),
            )

            bars = []
            for row in cursor:
                bars.append(Bar(
                    symbol=row[0],
                    date=date.fromisoformat(row[1]),
                    open=Decimal(str(row[2])),
                    high=Decimal(str(row[3])),
                    low=Decimal(str(row[4])),
                    close=Decimal(str(row[5])),
                    volume=int(row[6]),
                ))

            return bars if bars else None

    def _fetch_from_yahoo(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[Bar]:
        """Fetch bars from Yahoo Finance."""
        self._rate_limit_wait()

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start_date,
                end=end_date + timedelta(days=1),  # end is exclusive
                auto_adjust=True,
            )

            if df is None or df.empty:
                return []

            bars = []
            for idx, row in df.iterrows():
                try:
                    bar = Bar(
                        symbol=symbol,
                        date=idx.date() if hasattr(idx, "date") else idx,
                        open=Decimal(str(round(row["Open"], 6))),
                        high=Decimal(str(round(row["High"], 6))),
                        low=Decimal(str(round(row["Low"], 6))),
                        close=Decimal(str(round(row["Close"], 6))),
                        volume=int(row["Volume"]) if row["Volume"] > 0 else 0,
                    )
                    bars.append(bar)
                except Exception:
                    continue

            return bars

        except Exception as e:
            print(f"  Error fetching {symbol}: {e}")
            return []

    def _save_to_cache(
        self,
        symbol: str,
        bars: list[Bar],
        start_date: date,
        end_date: date,
    ) -> None:
        """Save bars to SQLite cache."""
        if not bars:
            return

        now = date.today().isoformat()

        with sqlite3.connect(self._cache_path) as conn:
            # Insert bars (replace if exists)
            conn.executemany(
                """
                INSERT OR REPLACE INTO bars
                (symbol, date, open, high, low, close, volume, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        bar.symbol,
                        bar.date.isoformat(),
                        float(bar.open),
                        float(bar.high),
                        float(bar.low),
                        float(bar.close),
                        bar.volume,
                        now,
                    )
                    for bar in bars
                ],
            )

            # Log the fetch
            conn.execute(
                """
                INSERT OR REPLACE INTO fetch_log
                (symbol, start_date, end_date, fetched_at, bar_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (symbol, start_date.isoformat(), end_date.isoformat(), now, len(bars)),
            )

            conn.commit()

    def preload_universe(
        self,
        symbols: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        show_progress: bool = True,
    ) -> dict[str, int]:
        """Preload data for multiple symbols into cache.

        Args:
            symbols: List of symbols (defaults to ETF_UNIVERSE)
            start_date: Start date (defaults to 2 years ago)
            end_date: End date (defaults to today)
            show_progress: Print progress messages

        Returns:
            Dict of symbol -> bar count
        """
        symbols = symbols or ETF_UNIVERSE
        end_date = end_date or date.today()
        start_date = start_date or (end_date - timedelta(days=730))  # 2 years

        results = {}
        total = len(symbols)

        for i, symbol in enumerate(symbols, 1):
            if show_progress:
                print(f"  [{i}/{total}] Loading {symbol}...", end=" ", flush=True)

            bars = self.get_bars(symbol, start_date, end_date)
            results[symbol] = len(bars)

            if show_progress:
                if bars:
                    print(f"{len(bars)} bars")
                else:
                    print("FAILED")

        return results

    def get_cache_stats(self) -> dict:
        """Get statistics about the cache."""
        with sqlite3.connect(self._cache_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(DISTINCT symbol) as symbols,
                    COUNT(*) as total_bars,
                    MIN(date) as earliest,
                    MAX(date) as latest
                FROM bars
            """)
            row = cursor.fetchone()

            cursor2 = conn.execute("""
                SELECT symbol, COUNT(*) as bars, MIN(date), MAX(date)
                FROM bars
                GROUP BY symbol
                ORDER BY symbol
            """)
            by_symbol = {
                r[0]: {"bars": r[1], "start": r[2], "end": r[3]}
                for r in cursor2
            }

            return {
                "symbols": row[0] or 0,
                "total_bars": row[1] or 0,
                "earliest_date": row[2],
                "latest_date": row[3],
                "by_symbol": by_symbol,
            }

    def clear_cache(self, symbol: str | None = None) -> None:
        """Clear cache for a symbol or all symbols."""
        with sqlite3.connect(self._cache_path) as conn:
            if symbol:
                conn.execute("DELETE FROM bars WHERE symbol = ?", (symbol,))
                conn.execute("DELETE FROM fetch_log WHERE symbol = ?", (symbol,))
            else:
                conn.execute("DELETE FROM bars")
                conn.execute("DELETE FROM fetch_log")
            conn.commit()
