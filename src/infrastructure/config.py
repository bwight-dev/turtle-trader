"""Environment configuration using pydantic-settings."""

from decimal import Decimal
from functools import lru_cache

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: PostgresDsn = Field(
        ...,
        alias="DATABASE_URL",
        description="Neon PostgreSQL connection string",
    )
    database_pool_size: int = Field(default=5, alias="DATABASE_POOL_SIZE")

    # IBKR
    ibkr_host: str = Field(default="127.0.0.1", alias="IBKR_HOST")
    ibkr_port: int = Field(default=7497, alias="IBKR_PORT")
    ibkr_client_id: int = Field(default=1, alias="IBKR_CLIENT_ID")
    ibkr_account_id: str = Field(default="", alias="IBKR_ACCOUNT_ID")
    ibkr_connection_timeout: int = Field(default=30, alias="IBKR_CONNECTION_TIMEOUT")
    ibkr_request_timeout: int = Field(default=60, alias="IBKR_REQUEST_TIMEOUT")
    ibkr_use_rth: bool = Field(default=True, alias="IBKR_USE_RTH")
    ibkr_max_retries: int = Field(default=3, alias="IBKR_MAX_RETRIES")
    ibkr_retry_delay: float = Field(default=2.0, alias="IBKR_RETRY_DELAY")

    # Yahoo Finance
    yahoo_requests_per_minute: int = Field(default=60, alias="YAHOO_REQUESTS_PER_MINUTE")
    yahoo_auto_adjust: bool = Field(default=True, alias="YAHOO_AUTO_ADJUST")

    # Data source
    data_primary_source: str = Field(default="ibkr", alias="DATA_PRIMARY_SOURCE")
    data_enable_fallback: bool = Field(default=True, alias="DATA_ENABLE_FALLBACK")
    data_validate_against_secondary: bool = Field(
        default=False, alias="DATA_VALIDATE_AGAINST_SECONDARY"
    )
    data_max_price_deviation_pct: Decimal = Field(
        default=Decimal("2.0"), alias="DATA_MAX_PRICE_DEVIATION_PCT"
    )

    # Trading - Risk
    risk_per_trade: Decimal = Field(
        default=Decimal("0.005"),
        alias="RISK_PER_TRADE",
        description="Risk per trade as decimal (0.005 = 0.5%)",
    )

    # Trading - Position limits
    max_units_per_market: int = Field(default=4, alias="MAX_UNITS_PER_MARKET")
    max_units_correlated: int = Field(default=6, alias="MAX_UNITS_CORRELATED")
    max_units_total: int = Field(default=12, alias="MAX_UNITS_TOTAL")

    # Trading - Drawdown
    drawdown_reduction_threshold: Decimal = Field(
        default=Decimal("0.10"), alias="DRAWDOWN_REDUCTION_THRESHOLD"
    )
    drawdown_equity_reduction: Decimal = Field(
        default=Decimal("0.20"), alias="DRAWDOWN_EQUITY_REDUCTION"
    )

    # Cache
    cache_ttl_seconds: int = Field(default=5, alias="CACHE_TTL_SECONDS")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
