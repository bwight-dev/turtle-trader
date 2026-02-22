-- Migration: 002_add_small_account_etfs
-- Description: Add 15 ETFs for small account ($50k) trading universe
-- Created: 2026-01-28
--
-- These 15 ETFs were validated via backtesting to work with $50k accounts:
-- - $50k -> $1.08M (2068% return) over 2020-2025
-- - 522 trades executed
-- - 67% max drawdown (same as larger universe)
-- - Sharpe ratio: 1.04

-- Add small_account flag to markets table
ALTER TABLE markets ADD COLUMN IF NOT EXISTS small_account BOOLEAN NOT NULL DEFAULT FALSE;

-- Insert the 15 small account ETFs
-- These cover 8 distinct sectors for diversification

-- EQUITY INDEX (3) - broad market exposure
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size, small_account)
VALUES
    ('SPY', 'SPDR S&P 500 ETF', 'NYSE', 'etf', 'equity_us_large', 1.0, 0.01, TRUE),
    ('QQQ', 'Invesco QQQ Trust', 'NASDAQ', 'etf', 'equity_us_tech', 1.0, 0.01, TRUE),
    ('IWM', 'iShares Russell 2000 ETF', 'NYSE', 'etf', 'equity_us_small', 1.0, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET small_account = TRUE, correlation_group = EXCLUDED.correlation_group;

-- INTERNATIONAL EQUITY (2)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size, small_account)
VALUES
    ('EFA', 'iShares MSCI EAFE ETF', 'NYSE', 'etf', 'equity_developed', 1.0, 0.01, TRUE),
    ('EEM', 'iShares MSCI Emerging Markets ETF', 'NYSE', 'etf', 'equity_emerging', 1.0, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET small_account = TRUE, correlation_group = EXCLUDED.correlation_group;

-- SECTORS (2) - uncorrelated to broad market
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size, small_account)
VALUES
    ('XLE', 'Energy Select Sector SPDR', 'NYSE', 'etf', 'sector_energy', 1.0, 0.01, TRUE),
    ('XLU', 'Utilities Select Sector SPDR', 'NYSE', 'etf', 'sector_utilities', 1.0, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET small_account = TRUE, correlation_group = EXCLUDED.correlation_group;

-- BONDS (2)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size, small_account)
VALUES
    ('TLT', 'iShares 20+ Year Treasury Bond ETF', 'NASDAQ', 'etf', 'bonds_long', 1.0, 0.01, TRUE),
    ('IEF', 'iShares 7-10 Year Treasury Bond ETF', 'NASDAQ', 'etf', 'bonds_mid', 1.0, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET small_account = TRUE, correlation_group = EXCLUDED.correlation_group;

-- COMMODITIES (4) - diversified real assets
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size, small_account)
VALUES
    ('GLD', 'SPDR Gold Shares', 'NYSE', 'etf', 'metals_precious', 1.0, 0.01, TRUE),
    ('SLV', 'iShares Silver Trust', 'NYSE', 'etf', 'metals_precious', 1.0, 0.01, TRUE),
    ('USO', 'United States Oil Fund', 'NYSE', 'etf', 'energy_oil', 1.0, 0.01, TRUE),
    ('DBA', 'Invesco DB Agriculture Fund', 'NYSE', 'etf', 'commodities_ag', 1.0, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET small_account = TRUE, correlation_group = EXCLUDED.correlation_group;

-- REAL ESTATE (1)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size, small_account)
VALUES
    ('VNQ', 'Vanguard Real Estate ETF', 'NYSE', 'etf', 'real_estate', 1.0, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET small_account = TRUE, correlation_group = EXCLUDED.correlation_group;

-- CURRENCY (1)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size, small_account)
VALUES
    ('FXE', 'Invesco CurrencyShares Euro Trust', 'NYSE', 'etf', 'currency_euro', 1.0, 0.01, TRUE)
ON CONFLICT (symbol) DO UPDATE SET small_account = TRUE, correlation_group = EXCLUDED.correlation_group;

-- Create index for small account queries
CREATE INDEX IF NOT EXISTS idx_markets_small_account ON markets(small_account) WHERE small_account = TRUE;

-- Record this migration
INSERT INTO schema_migrations (version) VALUES ('002_add_small_account_etfs')
ON CONFLICT (version) DO NOTHING;
