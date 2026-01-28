# Turtle Trading Bot - Part 6: Data Sources & IBKR Integration

## Overview

The system uses a **dual data source architecture** with automatic failover:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA SOURCE PRIORITY                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐                                               │
│  │  PRIMARY: IBKR   │ ◀── Interactive Brokers TWS/Gateway          │
│  │  (Mac Mini Local)│     Running locally on Mac Mini               │
│  └────────┬─────────┘                                               │
│           │                                                          │
│           │ Connection failed?                                       │
│           │ Data validation failed?                                  │
│           │ Market closed?                                           │
│           ▼                                                          │
│  ┌──────────────────┐                                               │
│  │  BACKUP: Yahoo   │ ◀── yfinance library                          │
│  │  Finance         │     Free, reliable for daily bars             │
│  └──────────────────┘                                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## IBKR Configuration

### Connection Settings

```python
# turtle_core/config.py
from pydantic_settings import BaseSettings
from pydantic import Field


class IBKRConfig(BaseSettings):
    """Interactive Brokers connection configuration"""

    # Connection
    host: str = Field(default="127.0.0.1", description="TWS/Gateway host")
    port: int = Field(default=7497, description="7497=TWS Paper, 7496=TWS Live, 4002=Gateway Paper, 4001=Gateway Live")
    client_id: int = Field(default=1, description="Unique client ID for this connection")

    # Timeouts
    connection_timeout: int = Field(default=30, description="Seconds to wait for connection")
    request_timeout: int = Field(default=60, description="Seconds to wait for data requests")

    # Paper Trading Account
    account_id: str = Field(default="DUP318628", description="IB Account ID")

    # Retry settings
    max_retries: int = Field(default=3)
    retry_delay: float = Field(default=2.0, description="Seconds between retries")

    # Data settings
    use_rth: bool = Field(default=True, description="Regular Trading Hours only")

    model_config = {
        "env_prefix": "IBKR_",
        "env_file": ".env",
    }


class YahooConfig(BaseSettings):
    """Yahoo Finance backup configuration"""

    # Rate limiting
    requests_per_minute: int = Field(default=60)

    # Data settings
    auto_adjust: bool = Field(default=True, description="Auto-adjust for splits/dividends")

    model_config = {
        "env_prefix": "YAHOO_",
        "env_file": ".env",
    }


class DataSourceConfig(BaseSettings):
    """Combined data source configuration"""

    ibkr: IBKRConfig = Field(default_factory=IBKRConfig)
    yahoo: YahooConfig = Field(default_factory=YahooConfig)

    # Failover settings
    primary_source: str = Field(default="ibkr", description="Primary data source")
    enable_fallback: bool = Field(default=True, description="Fall back to Yahoo if IBKR fails")

    # Validation
    validate_against_secondary: bool = Field(default=False, description="Cross-check data between sources")
    max_price_deviation_pct: float = Field(default=2.0, description="Max allowed deviation between sources")

    model_config = {
        "env_file": ".env",
    }
```

### Environment Variables (.env)

```bash
# Interactive Brokers Configuration
IBKR_HOST=127.0.0.1
IBKR_PORT=7497                    # Paper trading port (TWS)
IBKR_CLIENT_ID=1
IBKR_ACCOUNT_ID=DUP318628
IBKR_CONNECTION_TIMEOUT=30
IBKR_REQUEST_TIMEOUT=60
IBKR_USE_RTH=true

# Yahoo Finance Configuration (backup)
YAHOO_REQUESTS_PER_MINUTE=60
YAHOO_AUTO_ADJUST=true

# Data Source Configuration
DATA_PRIMARY_SOURCE=ibkr
DATA_ENABLE_FALLBACK=true
DATA_VALIDATE_AGAINST_SECONDARY=false
```

---

## Symbol Mapping

IBKR uses different symbol formats than your internal representation. The system maintains a mapping table:

```python
# market_data/symbols/mapper.py
from dataclasses import dataclass
from typing import Optional
from turtle_core.models import CorrelationGroup


@dataclass(frozen=True)
class SymbolMapping:
    """Maps between internal symbols and broker-specific formats"""
    internal: str           # Your format: /MGC, /M2K, SPY
    ibkr_symbol: str        # IB format: MGC, M2K, SPY
    ibkr_sec_type: str      # STK, FUT, OPT, etc.
    ibkr_exchange: str      # SMART, COMEX, GLOBEX, etc.
    ibkr_currency: str      # USD, EUR, etc.
    yahoo_symbol: str       # Yahoo format: MGC=F, M2K=F, SPY
    point_value: float      # Dollar value per point
    tick_size: float        # Minimum price increment
    correlation_group: CorrelationGroup
    is_micro: bool = False
    full_size_equivalent: Optional[str] = None


# Micro Futures Mapping
MICRO_FUTURES_MAP = {
    # Metals
    "/MGC": SymbolMapping(
        internal="/MGC",
        ibkr_symbol="MGC",
        ibkr_sec_type="FUT",
        ibkr_exchange="COMEX",
        ibkr_currency="USD",
        yahoo_symbol="MGC=F",
        point_value=10.0,
        tick_size=0.10,
        correlation_group=CorrelationGroup.METALS_PRECIOUS,
        is_micro=True,
        full_size_equivalent="/GC",
    ),
    "/SIL": SymbolMapping(
        internal="/SIL",
        ibkr_symbol="SIL",
        ibkr_sec_type="FUT",
        ibkr_exchange="COMEX",
        ibkr_currency="USD",
        yahoo_symbol="SIL=F",
        point_value=50.0,
        tick_size=0.005,
        correlation_group=CorrelationGroup.METALS_PRECIOUS,
        is_micro=True,
        full_size_equivalent="/SI",
    ),
    "/MHG": SymbolMapping(
        internal="/MHG",
        ibkr_symbol="MHG",
        ibkr_sec_type="FUT",
        ibkr_exchange="COMEX",
        ibkr_currency="USD",
        yahoo_symbol="MHG=F",
        point_value=2500.0,
        tick_size=0.0005,
        correlation_group=CorrelationGroup.METALS_INDUSTRIAL,
        is_micro=True,
        full_size_equivalent="/HG",
    ),

    # Stock Indices
    "/MES": SymbolMapping(
        internal="/MES",
        ibkr_symbol="MES",
        ibkr_sec_type="FUT",
        ibkr_exchange="CME",
        ibkr_currency="USD",
        yahoo_symbol="MES=F",
        point_value=5.0,
        tick_size=0.25,
        correlation_group=CorrelationGroup.EQUITY_US,
        is_micro=True,
        full_size_equivalent="/ES",
    ),
    "/MNQ": SymbolMapping(
        internal="/MNQ",
        ibkr_symbol="MNQ",
        ibkr_sec_type="FUT",
        ibkr_exchange="CME",
        ibkr_currency="USD",
        yahoo_symbol="MNQ=F",
        point_value=2.0,
        tick_size=0.25,
        correlation_group=CorrelationGroup.EQUITY_TECH,
        is_micro=True,
        full_size_equivalent="/NQ",
    ),
    "/M2K": SymbolMapping(
        internal="/M2K",
        ibkr_symbol="M2K",
        ibkr_sec_type="FUT",
        ibkr_exchange="CME",
        ibkr_currency="USD",
        yahoo_symbol="M2K=F",
        point_value=5.0,
        tick_size=0.10,
        correlation_group=CorrelationGroup.EQUITY_SMALL,
        is_micro=True,
        full_size_equivalent="/RTY",
    ),
    "/MYM": SymbolMapping(
        internal="/MYM",
        ibkr_symbol="MYM",
        ibkr_sec_type="FUT",
        ibkr_exchange="CBOT",
        ibkr_currency="USD",
        yahoo_symbol="MYM=F",
        point_value=0.50,
        tick_size=1.0,
        correlation_group=CorrelationGroup.EQUITY_US,
        is_micro=True,
        full_size_equivalent="/YM",
    ),

    # Energy
    "/MCL": SymbolMapping(
        internal="/MCL",
        ibkr_symbol="MCL",
        ibkr_sec_type="FUT",
        ibkr_exchange="NYMEX",
        ibkr_currency="USD",
        yahoo_symbol="MCL=F",
        point_value=100.0,
        tick_size=0.01,
        correlation_group=CorrelationGroup.ENERGY_OIL,
        is_micro=True,
        full_size_equivalent="/CL",
    ),

    # Grains
    "/MZC": SymbolMapping(
        internal="/MZC",
        ibkr_symbol="MZC",
        ibkr_sec_type="FUT",
        ibkr_exchange="CBOT",
        ibkr_currency="USD",
        yahoo_symbol="MZC=F",
        point_value=10.0,
        tick_size=0.125,
        correlation_group=CorrelationGroup.GRAINS_FEED,
        is_micro=True,
        full_size_equivalent="/ZC",
    ),
    "/MZS": SymbolMapping(
        internal="/MZS",
        ibkr_symbol="MZS",
        ibkr_sec_type="FUT",
        ibkr_exchange="CBOT",
        ibkr_currency="USD",
        yahoo_symbol="MZS=F",
        point_value=10.0,
        tick_size=0.125,
        correlation_group=CorrelationGroup.GRAINS_OILSEED,
        is_micro=True,
        full_size_equivalent="/ZS",
    ),
    "/MZW": SymbolMapping(
        internal="/MZW",
        ibkr_symbol="MZW",
        ibkr_sec_type="FUT",
        ibkr_exchange="CBOT",
        ibkr_currency="USD",
        yahoo_symbol="MZW=F",
        point_value=10.0,
        tick_size=0.125,
        correlation_group=CorrelationGroup.GRAINS_WHEAT,
        is_micro=True,
        full_size_equivalent="/ZW",
    ),

    # Currencies
    "/M6E": SymbolMapping(
        internal="/M6E",
        ibkr_symbol="M6E",
        ibkr_sec_type="FUT",
        ibkr_exchange="CME",
        ibkr_currency="USD",
        yahoo_symbol="M6E=F",
        point_value=12500.0,
        tick_size=0.0001,
        correlation_group=CorrelationGroup.CURRENCY_EUR,
        is_micro=True,
        full_size_equivalent="/6E",
    ),
    "/M6B": SymbolMapping(
        internal="/M6B",
        ibkr_symbol="M6B",
        ibkr_sec_type="FUT",
        ibkr_exchange="CME",
        ibkr_currency="USD",
        yahoo_symbol="M6B=F",
        point_value=6250.0,
        tick_size=0.0001,
        correlation_group=CorrelationGroup.CURRENCY_GBP,
        is_micro=True,
        full_size_equivalent="/6B",
    ),

    # Crypto
    "/MBT": SymbolMapping(
        internal="/MBT",
        ibkr_symbol="MBT",
        ibkr_sec_type="FUT",
        ibkr_exchange="CME",
        ibkr_currency="USD",
        yahoo_symbol="MBT=F",
        point_value=0.10,
        tick_size=5.0,
        correlation_group=CorrelationGroup.CRYPTO,
        is_micro=True,
        full_size_equivalent="/BTC",
    ),
    "/MET": SymbolMapping(
        internal="/MET",
        ibkr_symbol="MET",
        ibkr_sec_type="FUT",
        ibkr_exchange="CME",
        ibkr_currency="USD",
        yahoo_symbol="MET=F",
        point_value=0.10,
        tick_size=0.25,
        correlation_group=CorrelationGroup.CRYPTO,
        is_micro=True,
        full_size_equivalent="/ETH",
    ),
}


class SymbolMapper:
    """Translate between internal and broker symbol formats"""

    def __init__(self):
        self._internal_map = {**MICRO_FUTURES_MAP}
        self._ibkr_map = {m.ibkr_symbol: m for m in self._internal_map.values()}
        self._yahoo_map = {m.yahoo_symbol: m for m in self._internal_map.values()}

    def get_mapping(self, internal_symbol: str) -> SymbolMapping:
        """Get mapping for internal symbol"""
        # Handle contract month suffix (e.g., /MGCG26 -> /MGC)
        base_symbol = self._strip_contract_month(internal_symbol)
        if base_symbol not in self._internal_map:
            raise ValueError(f"Unknown symbol: {internal_symbol}")
        return self._internal_map[base_symbol]

    def to_ibkr(self, internal_symbol: str) -> tuple[str, str, str, str]:
        """Convert to IBKR format: (symbol, secType, exchange, currency)"""
        mapping = self.get_mapping(internal_symbol)
        # Extract contract month if present
        contract_month = self._extract_contract_month(internal_symbol)
        symbol = mapping.ibkr_symbol
        return (symbol, mapping.ibkr_sec_type, mapping.ibkr_exchange, mapping.ibkr_currency)

    def to_yahoo(self, internal_symbol: str) -> str:
        """Convert to Yahoo Finance format"""
        mapping = self.get_mapping(internal_symbol)
        return mapping.yahoo_symbol

    def from_ibkr(self, ibkr_symbol: str) -> str:
        """Convert from IBKR format to internal"""
        if ibkr_symbol not in self._ibkr_map:
            raise ValueError(f"Unknown IBKR symbol: {ibkr_symbol}")
        return self._ibkr_map[ibkr_symbol].internal

    def _strip_contract_month(self, symbol: str) -> str:
        """Remove contract month suffix: /MGCG26 -> /MGC"""
        # Micro futures have 3-letter base + optional month code
        if symbol.startswith("/M") and len(symbol) > 4:
            return symbol[:4]
        elif symbol.startswith("/") and len(symbol) > 3:
            return symbol[:3]
        return symbol

    def _extract_contract_month(self, symbol: str) -> str | None:
        """Extract contract month: /MGCG26 -> G26"""
        base = self._strip_contract_month(symbol)
        if len(symbol) > len(base):
            return symbol[len(base):]
        return None
```

---

## Continuous Contract Handling (Futures)

For futures trading, raw historical data can have gaps at contract rollovers. The system handles this with back-adjustment:

```python
# market_data/futures/continuous.py
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional
from turtle_core.models import Bar


@dataclass
class ContractInfo:
    """Futures contract details"""
    symbol: str              # e.g., MGCG26
    expiration: date
    first_notice: Optional[date]
    last_trade: date


@dataclass
class RollEvent:
    """Contract roll information"""
    from_contract: str
    to_contract: str
    roll_date: date
    price_adjustment: Decimal  # Gap between contracts


class ContinuousContractBuilder:
    """
    Build continuous (back-adjusted) price series for futures.

    Why this matters:
    - When a futures contract rolls (e.g., March -> June),
      there's often a price gap
    - Without adjustment, your system sees false breakouts
    - Back-adjustment ensures your N values and Donchian
      channels are calculated on clean, continuous data
    """

    def __init__(self, roll_method: str = "volume"):
        """
        roll_method:
            "volume" - Roll when front month volume < back month
            "open_interest" - Roll when OI shifts
            "days_before_expiry" - Roll N days before expiration
        """
        self.roll_method = roll_method
        self.days_before_expiry = 5  # Default for time-based roll

    def build_continuous_series(
        self,
        contracts: dict[str, list[Bar]],  # contract_symbol -> bars
        contract_info: dict[str, ContractInfo],
    ) -> tuple[list[Bar], list[RollEvent]]:
        """
        Build back-adjusted continuous series.

        Returns:
            - Adjusted bar series
            - List of roll events for audit
        """
        if not contracts:
            return [], []

        # Sort contracts by expiration
        sorted_contracts = sorted(
            contract_info.items(),
            key=lambda x: x[1].expiration
        )

        rolls: list[RollEvent] = []
        adjusted_bars: list[Bar] = []
        cumulative_adjustment = Decimal("0")

        for i, (contract_symbol, info) in enumerate(sorted_contracts):
            bars = contracts.get(contract_symbol, [])
            if not bars:
                continue

            # Determine roll date
            if i < len(sorted_contracts) - 1:
                next_contract = sorted_contracts[i + 1][0]
                roll_date = self._determine_roll_date(
                    bars,
                    contracts.get(next_contract, []),
                    info,
                )

                if roll_date:
                    # Calculate price gap at roll
                    old_price = self._get_price_on_date(bars, roll_date)
                    new_price = self._get_price_on_date(
                        contracts[next_contract], roll_date
                    )

                    if old_price and new_price:
                        gap = new_price - old_price
                        cumulative_adjustment += gap

                        rolls.append(RollEvent(
                            from_contract=contract_symbol,
                            to_contract=next_contract,
                            roll_date=roll_date,
                            price_adjustment=gap,
                        ))

            # Apply cumulative adjustment to all bars in this contract
            for bar in bars:
                adjusted_bar = Bar(
                    symbol=bar.symbol,
                    date=bar.date,
                    open=bar.open - cumulative_adjustment,
                    high=bar.high - cumulative_adjustment,
                    low=bar.low - cumulative_adjustment,
                    close=bar.close - cumulative_adjustment,
                    volume=bar.volume,
                )
                adjusted_bars.append(adjusted_bar)

        # Sort by date and remove duplicates
        adjusted_bars.sort(key=lambda b: b.date)
        return self._deduplicate_bars(adjusted_bars), rolls

    def _determine_roll_date(
        self,
        current_bars: list[Bar],
        next_bars: list[Bar],
        current_info: ContractInfo,
    ) -> Optional[date]:
        """Determine when to roll based on method"""
        if self.roll_method == "days_before_expiry":
            from datetime import timedelta
            return current_info.expiration - timedelta(days=self.days_before_expiry)

        # Volume-based roll (default)
        # Find first date where next contract volume > current
        next_volume = {b.date: b.volume for b in next_bars}
        for bar in reversed(current_bars):
            if bar.date in next_volume:
                if next_volume[bar.date] > bar.volume:
                    return bar.date

        return None

    def _get_price_on_date(
        self,
        bars: list[Bar],
        target_date: date
    ) -> Optional[Decimal]:
        """Get closing price on specific date"""
        for bar in bars:
            if bar.date == target_date:
                return bar.close
        return None

    def _deduplicate_bars(self, bars: list[Bar]) -> list[Bar]:
        """Remove duplicate dates, keeping latest"""
        seen = {}
        for bar in bars:
            seen[bar.date] = bar
        return sorted(seen.values(), key=lambda b: b.date)
```

---

## IBKR Data Feed Implementation

```python
# market_data/feeds/ibkr.py
import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional
import logging

from ib_insync import IB, Contract, BarData, util
from turtle_core.models import Bar, MarketData, MarketSpec
from turtle_core.config import IBKRConfig
from .base import DataFeed
from ..symbols.mapper import SymbolMapper

logger = logging.getLogger(__name__)


class IBKRDataFeed(DataFeed):
    """
    Interactive Brokers data feed implementation.

    Connects to TWS or IB Gateway running on local Mac Mini.
    Provides historical bars and real-time prices.
    """

    def __init__(self, config: Optional[IBKRConfig] = None):
        self.config = config or IBKRConfig()
        self.ib = IB()
        self.mapper = SymbolMapper()
        self._connected = False
        self._price_cache: dict[str, tuple[Decimal, datetime]] = {}
        self._cache_ttl = 5  # seconds

    async def connect(self) -> bool:
        """Establish connection to TWS/Gateway"""
        if self._connected:
            return True

        try:
            await asyncio.wait_for(
                self.ib.connectAsync(
                    host=self.config.host,
                    port=self.config.port,
                    clientId=self.config.client_id,
                ),
                timeout=self.config.connection_timeout,
            )
            self._connected = True
            logger.info(f"Connected to IBKR at {self.config.host}:{self.config.port}")
            return True

        except asyncio.TimeoutError:
            logger.error(f"IBKR connection timeout after {self.config.connection_timeout}s")
            return False
        except Exception as e:
            logger.error(f"IBKR connection failed: {e}")
            return False

    async def disconnect(self):
        """Close connection"""
        if self._connected:
            self.ib.disconnect()
            self._connected = False
            logger.info("Disconnected from IBKR")

    def _create_contract(self, symbol: str) -> Contract:
        """Create IB Contract object from internal symbol"""
        ib_symbol, sec_type, exchange, currency = self.mapper.to_ibkr(symbol)

        if sec_type == "FUT":
            # For futures, need to specify contract month
            contract_month = self.mapper._extract_contract_month(symbol)
            contract = Contract(
                symbol=ib_symbol,
                secType=sec_type,
                exchange=exchange,
                currency=currency,
            )
            if contract_month:
                # Convert G26 -> 202603 (March 2026)
                contract.lastTradeDateOrContractMonth = self._parse_contract_month(contract_month)
            else:
                # Use continuous contract (front month)
                contract.includeExpired = False
        else:
            contract = Contract(
                symbol=ib_symbol,
                secType=sec_type,
                exchange=exchange,
                currency=currency,
            )

        return contract

    def _parse_contract_month(self, month_code: str) -> str:
        """Convert G26 to 202603 format"""
        month_map = {
            'F': '01', 'G': '02', 'H': '03', 'J': '04',
            'K': '05', 'M': '06', 'N': '07', 'Q': '08',
            'U': '09', 'V': '10', 'X': '11', 'Z': '12',
        }
        if len(month_code) >= 2:
            month_letter = month_code[0].upper()
            year_suffix = month_code[1:]
            if month_letter in month_map:
                year = f"20{year_suffix}" if len(year_suffix) == 2 else f"202{year_suffix}"
                return f"{year}{month_map[month_letter]}"
        return month_code

    async def get_bars(self, symbol: str, days: int) -> list[Bar]:
        """
        Fetch historical OHLCV bars from IBKR.

        Args:
            symbol: Internal symbol (e.g., /MGC, /MGCG26)
            days: Number of days of history to fetch

        Returns:
            List of Bar objects, oldest first
        """
        if not await self.connect():
            raise ConnectionError("Failed to connect to IBKR")

        contract = self._create_contract(symbol)

        # Qualify the contract to get full details
        try:
            qualified = await asyncio.wait_for(
                self.ib.qualifyContractsAsync(contract),
                timeout=self.config.request_timeout,
            )
            if not qualified:
                raise ValueError(f"Could not qualify contract: {symbol}")
            contract = qualified[0]
        except asyncio.TimeoutError:
            raise TimeoutError(f"Contract qualification timeout for {symbol}")

        # Calculate duration string
        duration = f"{days} D"

        # Request historical data
        try:
            bars: list[BarData] = await asyncio.wait_for(
                self.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime='',  # Current time
                    durationStr=duration,
                    barSizeSetting='1 day',
                    whatToShow='TRADES',
                    useRTH=self.config.use_rth,
                    formatDate=1,
                ),
                timeout=self.config.request_timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Historical data timeout for {symbol}")

        # Convert to our Bar model
        result = []
        for bar in bars:
            result.append(Bar(
                symbol=symbol,
                date=bar.date.date() if isinstance(bar.date, datetime) else bar.date,
                open=Decimal(str(bar.open)),
                high=Decimal(str(bar.high)),
                low=Decimal(str(bar.low)),
                close=Decimal(str(bar.close)),
                volume=int(bar.volume),
            ))

        # Validate data quality
        self._validate_bars(result)

        return result

    async def get_current_price(self, symbol: str) -> Decimal:
        """
        Get latest price from IBKR.

        Uses market data snapshot for efficiency.
        Caches results for a few seconds to avoid rate limiting.
        """
        # Check cache first
        if symbol in self._price_cache:
            price, cached_at = self._price_cache[symbol]
            if (datetime.now() - cached_at).total_seconds() < self._cache_ttl:
                return price

        if not await self.connect():
            raise ConnectionError("Failed to connect to IBKR")

        contract = self._create_contract(symbol)

        try:
            qualified = await asyncio.wait_for(
                self.ib.qualifyContractsAsync(contract),
                timeout=self.config.request_timeout,
            )
            if not qualified:
                raise ValueError(f"Could not qualify contract: {symbol}")
            contract = qualified[0]
        except asyncio.TimeoutError:
            raise TimeoutError(f"Contract qualification timeout for {symbol}")

        # Request market data snapshot
        try:
            ticker = await asyncio.wait_for(
                self.ib.reqMktDataAsync(contract, snapshot=True),
                timeout=10,
            )

            # Wait for data to populate
            await asyncio.sleep(0.5)

            # Get last price, falling back to close
            price = ticker.last or ticker.close
            if price is None or price <= 0:
                raise ValueError(f"No valid price for {symbol}")

            price = Decimal(str(price))

            # Cache the result
            self._price_cache[symbol] = (price, datetime.now())

            return price

        except asyncio.TimeoutError:
            raise TimeoutError(f"Market data timeout for {symbol}")
        finally:
            self.ib.cancelMktData(contract)

    async def get_account_summary(self) -> dict:
        """Get account summary including equity"""
        if not await self.connect():
            raise ConnectionError("Failed to connect to IBKR")

        summary = await self.ib.accountSummaryAsync()

        result = {}
        for item in summary:
            if item.tag in ['NetLiquidation', 'TotalCashValue', 'GrossPositionValue']:
                result[item.tag] = Decimal(item.value)

        return result

    async def get_positions(self) -> list[dict]:
        """Get current positions from IBKR"""
        if not await self.connect():
            raise ConnectionError("Failed to connect to IBKR")

        positions = self.ib.positions()

        result = []
        for pos in positions:
            result.append({
                'symbol': pos.contract.symbol,
                'quantity': pos.position,
                'avg_cost': Decimal(str(pos.avgCost)),
                'market_value': Decimal(str(pos.marketValue)) if pos.marketValue else None,
            })

        return result

    def _validate_bars(self, bars: list[Bar]) -> None:
        """
        Validate bar data quality.

        Checks:
        - High >= Low
        - High >= Open and Close
        - Low <= Open and Close
        - No negative prices
        - Reasonable price ranges (no "bad ticks")
        """
        for i, bar in enumerate(bars):
            # Basic OHLC validation
            if bar.high < bar.low:
                raise ValueError(f"Invalid bar {bar.date}: high < low")
            if bar.high < bar.open or bar.high < bar.close:
                raise ValueError(f"Invalid bar {bar.date}: high not highest")
            if bar.low > bar.open or bar.low > bar.close:
                raise ValueError(f"Invalid bar {bar.date}: low not lowest")

            # Check for bad ticks (>20% daily move is suspicious)
            if i > 0:
                prev_close = bars[i-1].close
                if prev_close > 0:
                    change_pct = abs((bar.close - prev_close) / prev_close)
                    if change_pct > Decimal("0.20"):
                        logger.warning(
                            f"Large price move on {bar.date}: "
                            f"{prev_close} -> {bar.close} ({change_pct:.1%})"
                        )

    @property
    def is_connected(self) -> bool:
        return self._connected and self.ib.isConnected()
```

---

## Yahoo Finance Backup Feed

```python
# market_data/feeds/yahoo.py
import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional
import logging

import yfinance as yf
from turtle_core.models import Bar, MarketData, MarketSpec
from turtle_core.config import YahooConfig
from .base import DataFeed
from ..symbols.mapper import SymbolMapper

logger = logging.getLogger(__name__)


class YahooDataFeed(DataFeed):
    """
    Yahoo Finance data feed (backup source).

    Free, reliable for daily bars.
    Does not require connection management.
    """

    def __init__(self, config: Optional[YahooConfig] = None):
        self.config = config or YahooConfig()
        self.mapper = SymbolMapper()
        self._last_request: Optional[datetime] = None
        self._request_interval = 60 / self.config.requests_per_minute

    async def _rate_limit(self):
        """Enforce rate limiting"""
        if self._last_request:
            elapsed = (datetime.now() - self._last_request).total_seconds()
            if elapsed < self._request_interval:
                await asyncio.sleep(self._request_interval - elapsed)
        self._last_request = datetime.now()

    async def get_bars(self, symbol: str, days: int) -> list[Bar]:
        """
        Fetch historical OHLCV bars from Yahoo Finance.

        Args:
            symbol: Internal symbol (e.g., /MGC)
            days: Number of days of history to fetch

        Returns:
            List of Bar objects, oldest first
        """
        await self._rate_limit()

        yahoo_symbol = self.mapper.to_yahoo(symbol)

        # Run yfinance in executor (it's blocking)
        loop = asyncio.get_event_loop()

        def fetch():
            ticker = yf.Ticker(yahoo_symbol)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days + 10)  # Buffer for weekends

            df = ticker.history(
                start=start_date,
                end=end_date,
                interval="1d",
                auto_adjust=self.config.auto_adjust,
            )
            return df

        try:
            df = await loop.run_in_executor(None, fetch)
        except Exception as e:
            logger.error(f"Yahoo Finance error for {symbol}: {e}")
            raise

        if df.empty:
            raise ValueError(f"No data returned for {yahoo_symbol}")

        # Convert to Bar objects
        result = []
        for idx, row in df.iterrows():
            bar_date = idx.date() if hasattr(idx, 'date') else idx
            result.append(Bar(
                symbol=symbol,
                date=bar_date,
                open=Decimal(str(row['Open'])),
                high=Decimal(str(row['High'])),
                low=Decimal(str(row['Low'])),
                close=Decimal(str(row['Close'])),
                volume=int(row['Volume']),
            ))

        # Sort by date and limit to requested days
        result.sort(key=lambda b: b.date)
        return result[-days:] if len(result) > days else result

    async def get_current_price(self, symbol: str) -> Decimal:
        """
        Get latest price from Yahoo Finance.

        Uses the most recent closing price.
        """
        await self._rate_limit()

        yahoo_symbol = self.mapper.to_yahoo(symbol)

        loop = asyncio.get_event_loop()

        def fetch():
            ticker = yf.Ticker(yahoo_symbol)
            # Get last 2 days to ensure we have data
            df = ticker.history(period="2d", interval="1d")
            if df.empty:
                raise ValueError(f"No price data for {yahoo_symbol}")
            return df['Close'].iloc[-1]

        try:
            price = await loop.run_in_executor(None, fetch)
            return Decimal(str(price))
        except Exception as e:
            logger.error(f"Yahoo Finance price error for {symbol}: {e}")
            raise
```

---

## Composite Data Feed (Failover)

```python
# market_data/feeds/composite.py
from datetime import datetime
from decimal import Decimal
from typing import Optional
import logging

from turtle_core.models import Bar, MarketData, MarketSpec
from turtle_core.config import DataSourceConfig
from .base import DataFeed
from .ibkr import IBKRDataFeed
from .yahoo import YahooDataFeed

logger = logging.getLogger(__name__)


class CompositeDataFeed(DataFeed):
    """
    Composite data feed with automatic failover.

    Primary: IBKR (local TWS/Gateway on Mac Mini)
    Backup: Yahoo Finance

    Automatically falls back to Yahoo if:
    - IBKR connection fails
    - IBKR data request times out
    - Data validation fails
    """

    def __init__(self, config: Optional[DataSourceConfig] = None):
        self.config = config or DataSourceConfig()

        self.ibkr = IBKRDataFeed(self.config.ibkr)
        self.yahoo = YahooDataFeed(self.config.yahoo)

        self._last_source: str = ""
        self._failover_count: int = 0

    async def get_bars(self, symbol: str, days: int) -> list[Bar]:
        """
        Fetch bars with automatic failover.
        """
        # Try primary source (IBKR)
        if self.config.primary_source == "ibkr":
            try:
                bars = await self.ibkr.get_bars(symbol, days)
                self._last_source = "ibkr"
                logger.debug(f"Got {len(bars)} bars for {symbol} from IBKR")

                # Optionally validate against secondary
                if self.config.validate_against_secondary:
                    await self._cross_validate(symbol, bars)

                return bars

            except Exception as e:
                logger.warning(f"IBKR failed for {symbol}: {e}")
                self._failover_count += 1

                if not self.config.enable_fallback:
                    raise

        # Fallback to Yahoo Finance
        try:
            bars = await self.yahoo.get_bars(symbol, days)
            self._last_source = "yahoo"
            logger.info(f"Got {len(bars)} bars for {symbol} from Yahoo (fallback)")
            return bars

        except Exception as e:
            logger.error(f"Yahoo Finance also failed for {symbol}: {e}")
            raise

    async def get_current_price(self, symbol: str) -> Decimal:
        """
        Get current price with automatic failover.
        """
        if self.config.primary_source == "ibkr":
            try:
                price = await self.ibkr.get_current_price(symbol)
                self._last_source = "ibkr"
                return price

            except Exception as e:
                logger.warning(f"IBKR price failed for {symbol}: {e}")
                self._failover_count += 1

                if not self.config.enable_fallback:
                    raise

        # Fallback
        try:
            price = await self.yahoo.get_current_price(symbol)
            self._last_source = "yahoo"
            logger.info(f"Got price for {symbol} from Yahoo (fallback)")
            return price

        except Exception as e:
            logger.error(f"Yahoo Finance price also failed for {symbol}: {e}")
            raise

    async def _cross_validate(self, symbol: str, ibkr_bars: list[Bar]) -> None:
        """
        Cross-validate IBKR data against Yahoo Finance.

        Logs warnings if prices deviate more than threshold.
        """
        try:
            yahoo_bars = await self.yahoo.get_bars(symbol, len(ibkr_bars))

            # Compare last few bars
            for i in range(-1, -min(5, len(ibkr_bars)), -1):
                ibkr_bar = ibkr_bars[i]

                # Find matching Yahoo bar
                yahoo_bar = next(
                    (b for b in yahoo_bars if b.date == ibkr_bar.date),
                    None
                )

                if yahoo_bar:
                    deviation = abs(ibkr_bar.close - yahoo_bar.close) / yahoo_bar.close
                    if deviation > Decimal(str(self.config.max_price_deviation_pct / 100)):
                        logger.warning(
                            f"Price deviation for {symbol} on {ibkr_bar.date}: "
                            f"IBKR={ibkr_bar.close}, Yahoo={yahoo_bar.close} "
                            f"({deviation:.2%})"
                        )
        except Exception as e:
            logger.debug(f"Cross-validation skipped for {symbol}: {e}")

    @property
    def last_source(self) -> str:
        """Get the last data source used"""
        return self._last_source

    @property
    def failover_count(self) -> int:
        """Get number of failovers since startup"""
        return self._failover_count

    async def health_check(self) -> dict:
        """Check health of all data sources"""
        result = {
            "ibkr_connected": self.ibkr.is_connected,
            "ibkr_available": False,
            "yahoo_available": False,
            "failover_count": self._failover_count,
        }

        # Test IBKR
        try:
            await self.ibkr.connect()
            result["ibkr_available"] = self.ibkr.is_connected
        except Exception:
            pass

        # Test Yahoo (try a simple fetch)
        try:
            await self.yahoo.get_current_price("/MES")
            result["yahoo_available"] = True
        except Exception:
            pass

        return result
```

---

## Persisting N Values

As noted in your requirements, N values should be persisted rather than recalculated from scratch:

```python
# market_data/store/n_repository.py
from datetime import date
from decimal import Decimal
from typing import Optional
import asyncpg

from turtle_core.models import NValue


class NValueRepository:
    """
    Persist and retrieve N (ATR) values.

    Statefulness is critical:
    - Yesterday's N is needed to calculate today's N
    - Recalculating from scratch can cause drift
    - Database storage ensures consistency across restarts
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_previous_n(
        self,
        symbol: str,
        as_of_date: date,
    ) -> Optional[Decimal]:
        """
        Get the Previous Day's N (PDN) for EMA calculation.

        If no previous N exists (new market), returns None
        to trigger SMA initialization.
        """
        query = """
            SELECT n_value
            FROM calculated_indicators
            WHERE market_id = (SELECT id FROM markets WHERE symbol = $1)
            AND calc_date < $2
            ORDER BY calc_date DESC
            LIMIT 1
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, symbol, as_of_date)
            if row:
                return Decimal(str(row['n_value']))
            return None

    async def save_n(
        self,
        symbol: str,
        calc_date: date,
        n_value: Decimal,
        donchian_10_high: Decimal,
        donchian_10_low: Decimal,
        donchian_20_high: Decimal,
        donchian_20_low: Decimal,
        donchian_55_high: Decimal,
        donchian_55_low: Decimal,
    ) -> None:
        """
        Save calculated indicators for a date.

        Uses UPSERT to handle recalculations.
        """
        query = """
            INSERT INTO calculated_indicators (
                market_id, calc_date, n_value,
                donchian_10_high, donchian_10_low,
                donchian_20_high, donchian_20_low,
                donchian_55_high, donchian_55_low
            )
            SELECT
                id, $2, $3, $4, $5, $6, $7, $8, $9
            FROM markets WHERE symbol = $1
            ON CONFLICT (market_id, calc_date)
            DO UPDATE SET
                n_value = EXCLUDED.n_value,
                donchian_10_high = EXCLUDED.donchian_10_high,
                donchian_10_low = EXCLUDED.donchian_10_low,
                donchian_20_high = EXCLUDED.donchian_20_high,
                donchian_20_low = EXCLUDED.donchian_20_low,
                donchian_55_high = EXCLUDED.donchian_55_high,
                donchian_55_low = EXCLUDED.donchian_55_low
        """

        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                symbol, calc_date, n_value,
                donchian_10_high, donchian_10_low,
                donchian_20_high, donchian_20_low,
                donchian_55_high, donchian_55_low,
            )

    async def get_latest_indicators(
        self,
        symbol: str,
    ) -> Optional[dict]:
        """Get most recent calculated indicators"""
        query = """
            SELECT
                calc_date,
                n_value,
                donchian_10_high, donchian_10_low,
                donchian_20_high, donchian_20_low,
                donchian_55_high, donchian_55_low
            FROM calculated_indicators
            WHERE market_id = (SELECT id FROM markets WHERE symbol = $1)
            ORDER BY calc_date DESC
            LIMIT 1
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, symbol)
            if row:
                return dict(row)
            return None
```

---

## Daily Update Workflow

```python
# orchestrator/daily_update.py
from datetime import date, datetime
from decimal import Decimal
import logging

from market_data.feeds.composite import CompositeDataFeed
from market_data.store.n_repository import NValueRepository
from market_data.calc.volatility import calculate_true_range
from market_data.calc.channels import calculate_donchian
from turtle_core.models import Bar

logger = logging.getLogger(__name__)


class DailyUpdateService:
    """
    End-of-day update service.

    Runs after market close to:
    1. Fetch new price bar
    2. Calculate new N using previous N (EMA)
    3. Calculate Donchian channels
    4. Persist to database
    """

    def __init__(
        self,
        data_feed: CompositeDataFeed,
        n_repo: NValueRepository,
    ):
        self.data_feed = data_feed
        self.n_repo = n_repo

    async def update_market(self, symbol: str) -> dict:
        """
        Update calculations for a single market.

        Returns dict with new values for logging/audit.
        """
        today = date.today()

        # Get previous N value
        previous_n = await self.n_repo.get_previous_n(symbol, today)

        # Fetch recent bars (need at least 2 for TR calculation)
        bars = await self.data_feed.get_bars(symbol, days=70)

        if len(bars) < 2:
            raise ValueError(f"Not enough bars for {symbol}")

        # Get today's bar
        today_bar = bars[-1]
        yesterday_bar = bars[-2]

        # Calculate True Range
        current_tr = calculate_true_range(
            today_bar.high,
            today_bar.low,
            yesterday_bar.close,
        )

        # Calculate new N
        if previous_n is None:
            # Initialization: Use SMA of last 20 TRs
            logger.info(f"Initializing N for {symbol} with SMA(20)")
            trs = []
            for i in range(1, min(21, len(bars))):
                tr = calculate_true_range(
                    bars[i].high,
                    bars[i].low,
                    bars[i-1].close,
                )
                trs.append(tr)
            new_n = sum(trs) / len(trs)
        else:
            # Routine: EMA formula
            # N = ((19 * Previous_N) + Current_TR) / 20
            new_n = ((Decimal("19") * previous_n) + current_tr) / Decimal("20")

        # Calculate Donchian channels
        donchian_10 = calculate_donchian(bars, 10)
        donchian_20 = calculate_donchian(bars, 20)
        donchian_55 = calculate_donchian(bars, 55)

        # Persist to database
        await self.n_repo.save_n(
            symbol=symbol,
            calc_date=today,
            n_value=new_n,
            donchian_10_high=donchian_10.upper,
            donchian_10_low=donchian_10.lower,
            donchian_20_high=donchian_20.upper,
            donchian_20_low=donchian_20.lower,
            donchian_55_high=donchian_55.upper,
            donchian_55_low=donchian_55.lower,
        )

        result = {
            "symbol": symbol,
            "date": today,
            "previous_n": previous_n,
            "current_tr": current_tr,
            "new_n": new_n,
            "donchian_10": (donchian_10.lower, donchian_10.upper),
            "donchian_20": (donchian_20.lower, donchian_20.upper),
            "donchian_55": (donchian_55.lower, donchian_55.upper),
            "data_source": self.data_feed.last_source,
        }

        logger.info(
            f"Updated {symbol}: N={new_n:.4f} "
            f"(prev={previous_n}, TR={current_tr})"
        )

        return result

    async def update_all_markets(self, symbols: list[str]) -> list[dict]:
        """Update all markets in universe"""
        results = []

        for symbol in symbols:
            try:
                result = await self.update_market(symbol)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to update {symbol}: {e}")
                results.append({
                    "symbol": symbol,
                    "error": str(e),
                })

        return results
```

---

## TWS/Gateway Setup on Mac Mini

### Prerequisites

1. **Install TWS or IB Gateway** on your Mac Mini
2. **Enable API connections** in TWS/Gateway settings
3. **Configure socket port** (7497 for paper trading)

### TWS API Settings

In TWS, go to **Edit → Global Configuration → API → Settings**:

```
☑ Enable ActiveX and Socket Clients
☑ Read-Only API (uncheck for trading)
Socket port: 7497 (paper) or 7496 (live)
☐ Allow connections from localhost only (uncheck if bot runs elsewhere)
Master API client ID: leave empty
```

### Auto-Start Configuration

Create a launchd plist to auto-start TWS on Mac Mini boot:

```xml
<!-- ~/Library/LaunchAgents/com.ib.tws.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ib.tws</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/Trader Workstation/Trader Workstation.app/Contents/MacOS/Trader Workstation</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load with: `launchctl load ~/Library/LaunchAgents/com.ib.tws.plist`

---

## Data Validation Checklist

Per your requirements, validate all incoming data:

```python
# market_data/validation.py

def validate_bar(bar: Bar, prev_bar: Bar | None = None) -> list[str]:
    """
    Validate bar data quality.

    Returns list of validation errors (empty if valid).

    Checks per your spec:
    - High >= Low
    - High >= Open AND High >= Close
    - Low <= Open AND Low <= Close
    """
    errors = []

    # Required checks
    if bar.high < bar.low:
        errors.append(f"high ({bar.high}) < low ({bar.low})")

    if bar.high < bar.open:
        errors.append(f"high ({bar.high}) < open ({bar.open})")

    if bar.high < bar.close:
        errors.append(f"high ({bar.high}) < close ({bar.close})")

    if bar.low > bar.open:
        errors.append(f"low ({bar.low}) > open ({bar.open})")

    if bar.low > bar.close:
        errors.append(f"low ({bar.low}) > close ({bar.close})")

    # Check for zero/negative prices
    for field in ['open', 'high', 'low', 'close']:
        value = getattr(bar, field)
        if value <= 0:
            errors.append(f"{field} ({value}) must be positive")

    # Check for bad ticks (optional, if prev_bar provided)
    if prev_bar and prev_bar.close > 0:
        change = abs(bar.close - prev_bar.close) / prev_bar.close
        if change > Decimal("0.20"):  # 20% move
            errors.append(
                f"Suspicious move: {prev_bar.close} -> {bar.close} ({change:.1%})"
            )

    return errors
```
