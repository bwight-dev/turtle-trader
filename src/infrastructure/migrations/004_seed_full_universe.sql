-- Migration: 004_seed_full_universe
-- Description: Seed full 228-market Turtle Trading universe (Jerry Parker approach)
-- Created: 2026-01-27

-- Clear existing and insert full universe
TRUNCATE TABLE markets RESTART IDENTITY;

-- ============================================================================
-- FULL SIZE FUTURES (58)
-- ============================================================================

-- Interest Rates (6)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/ZB', '30-Year Treasury Bond', 'CBOT', 'futures', 'rates_long', 1000.0, 0.03125),
('/UB', 'Ultra Treasury Bond', 'CBOT', 'futures', 'rates_long', 1000.0, 0.03125),
('/ZN', '10-Year Treasury Note', 'CBOT', 'futures', 'rates_mid', 1000.0, 0.015625),
('/ZF', '5-Year Treasury Note', 'CBOT', 'futures', 'rates_short', 1000.0, 0.0078125),
('/ZT', '2-Year Treasury Note', 'CBOT', 'futures', 'rates_short', 2000.0, 0.0078125),
('/SR3', '3-Month SOFR', 'CME', 'futures', 'rates_short', 2500.0, 0.0025);

-- Currencies (9)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/6E', 'Euro FX', 'CME', 'futures', 'currency_eur', 125000.0, 0.00005),
('/6B', 'British Pound', 'CME', 'futures', 'currency_gbp', 62500.0, 0.0001),
('/6J', 'Japanese Yen', 'CME', 'futures', 'currency_jpy', 12500000.0, 0.0000005),
('/6S', 'Swiss Franc', 'CME', 'futures', 'currency_chf', 125000.0, 0.0001),
('/6C', 'Canadian Dollar', 'CME', 'futures', 'currency_cad', 100000.0, 0.00005),
('/6A', 'Australian Dollar', 'CME', 'futures', 'currency_aud', 100000.0, 0.0001),
('/6N', 'New Zealand Dollar', 'CME', 'futures', 'currency_nzd', 100000.0, 0.0001),
('/6M', 'Mexican Peso', 'CME', 'futures', 'currency_mxn', 500000.0, 0.000025),
('/DX', 'US Dollar Index', 'ICE', 'futures', 'currency_usd', 1000.0, 0.005);

-- Metals (5)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/GC', 'Gold', 'COMEX', 'futures', 'metals_precious', 100.0, 0.10),
('/SI', 'Silver', 'COMEX', 'futures', 'metals_precious', 5000.0, 0.005),
('/HG', 'Copper', 'COMEX', 'futures', 'metals_industrial', 25000.0, 0.0005),
('/PL', 'Platinum', 'NYMEX', 'futures', 'metals_precious', 50.0, 0.10),
('/PA', 'Palladium', 'NYMEX', 'futures', 'metals_precious', 100.0, 0.50);

-- Energy (7)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/CL', 'Crude Oil WTI', 'NYMEX', 'futures', 'energy_oil', 1000.0, 0.01),
('/BZ', 'Brent Crude', 'NYMEX', 'futures', 'energy_oil', 1000.0, 0.01),
('/HO', 'Heating Oil', 'NYMEX', 'futures', 'energy_refined', 42000.0, 0.0001),
('/RB', 'RBOB Gasoline', 'NYMEX', 'futures', 'energy_refined', 42000.0, 0.0001),
('/NG', 'Natural Gas', 'NYMEX', 'futures', 'energy_gas', 10000.0, 0.001),
('/QG', 'E-mini Natural Gas', 'NYMEX', 'futures', 'energy_gas', 2500.0, 0.005),
('/QM', 'E-mini Crude Oil', 'NYMEX', 'futures', 'energy_oil', 500.0, 0.025);

-- Stock Indices (8)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/ES', 'E-mini S&P 500', 'CME', 'futures', 'equity_us', 50.0, 0.25),
('/NQ', 'E-mini NASDAQ 100', 'CME', 'futures', 'equity_us_tech', 20.0, 0.25),
('/RTY', 'E-mini Russell 2000', 'CME', 'futures', 'equity_us_small', 50.0, 0.10),
('/YM', 'E-mini Dow', 'CBOT', 'futures', 'equity_us', 5.0, 1.0),
('/EMD', 'E-mini S&P Midcap', 'CME', 'futures', 'equity_us', 100.0, 0.10),
('/NKD', 'Nikkei 225', 'CME', 'futures', 'equity_japan', 5.0, 5.0),
('/FFI', 'FTSE 100', 'ICE', 'futures', 'equity_uk', 10.0, 0.5),
('/FDAX', 'DAX', 'EUREX', 'futures', 'equity_europe', 25.0, 0.5);

-- Grains (10)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/ZC', 'Corn', 'CBOT', 'futures', 'grains_feed', 50.0, 0.25),
('/ZS', 'Soybeans', 'CBOT', 'futures', 'grains_oilseed', 50.0, 0.25),
('/ZW', 'Wheat', 'CBOT', 'futures', 'grains_wheat', 50.0, 0.25),
('/KE', 'KC Wheat', 'CBOT', 'futures', 'grains_wheat', 50.0, 0.25),
('/MWE', 'Minneapolis Wheat', 'MGEX', 'futures', 'grains_wheat', 50.0, 0.25),
('/ZL', 'Soybean Oil', 'CBOT', 'futures', 'grains_oilseed', 600.0, 0.01),
('/ZM', 'Soybean Meal', 'CBOT', 'futures', 'grains_oilseed', 100.0, 0.10),
('/ZO', 'Oats', 'CBOT', 'futures', 'grains_feed', 50.0, 0.25),
('/ZR', 'Rough Rice', 'CBOT', 'futures', 'grains_feed', 2000.0, 0.005),
('/RS', 'Canola', 'ICE', 'futures', 'grains_oilseed', 20.0, 0.10);

-- Softs (6)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/CT', 'Cotton', 'ICE', 'futures', 'softs', 500.0, 0.01),
('/SB', 'Sugar #11', 'ICE', 'futures', 'softs', 1120.0, 0.01),
('/KC', 'Coffee', 'ICE', 'futures', 'softs', 375.0, 0.05),
('/CC', 'Cocoa', 'ICE', 'futures', 'softs', 10.0, 1.0),
('/OJ', 'Orange Juice', 'ICE', 'futures', 'softs', 150.0, 0.05),
('/LBS', 'Lumber', 'CME', 'futures', 'softs', 110.0, 0.10);

-- Livestock (3)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/LE', 'Live Cattle', 'CME', 'futures', 'livestock', 400.0, 0.025),
('/GF', 'Feeder Cattle', 'CME', 'futures', 'livestock', 500.0, 0.025),
('/HE', 'Lean Hogs', 'CME', 'futures', 'livestock', 400.0, 0.025);

-- Dairy (2)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/DC', 'Class III Milk', 'CME', 'futures', 'dairy', 2000.0, 0.01),
('/CSC', 'Cheese', 'CME', 'futures', 'dairy', 200.0, 0.001);

-- Crypto (2)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/BTC', 'Bitcoin', 'CME', 'futures', 'crypto', 5.0, 5.0),
('/ETH', 'Ether', 'CME', 'futures', 'crypto', 50.0, 0.25);


-- ============================================================================
-- MICRO FUTURES (24)
-- ============================================================================

-- Interest Rates (2)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/MTN', 'Micro 10-Year Yield', 'CBOT', 'futures', 'rates_mid', 100.0, 0.001),
('/MWN', 'Micro 30-Year Yield', 'CBOT', 'futures', 'rates_long', 100.0, 0.001);

-- Currencies (6)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/M6E', 'Micro Euro FX', 'CME', 'futures', 'currency_eur', 12500.0, 0.0001),
('/M6B', 'Micro British Pound', 'CME', 'futures', 'currency_gbp', 6250.0, 0.0001),
('/M6J', 'Micro Japanese Yen', 'CME', 'futures', 'currency_jpy', 1250000.0, 0.000001),
('/M6S', 'Micro Swiss Franc', 'CME', 'futures', 'currency_chf', 12500.0, 0.0001),
('/M6C', 'Micro Canadian Dollar', 'CME', 'futures', 'currency_cad', 10000.0, 0.0001),
('/M6A', 'Micro Australian Dollar', 'CME', 'futures', 'currency_aud', 10000.0, 0.0001);

-- Metals (3)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/MGC', 'Micro Gold', 'COMEX', 'futures', 'metals_precious', 10.0, 0.10),
('/SIL', 'Micro Silver', 'COMEX', 'futures', 'metals_precious', 1000.0, 0.005),
('/MHG', 'Micro Copper', 'COMEX', 'futures', 'metals_industrial', 2500.0, 0.001);

-- Energy (1)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/MCL', 'Micro Crude Oil', 'NYMEX', 'futures', 'energy_oil', 100.0, 0.01);

-- Stock Indices (5)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/MES', 'Micro E-mini S&P 500', 'CME', 'futures', 'equity_us', 5.0, 0.25),
('/MNQ', 'Micro E-mini NASDAQ', 'CME', 'futures', 'equity_us_tech', 2.0, 0.25),
('/M2K', 'Micro E-mini Russell 2000', 'CME', 'futures', 'equity_us_small', 5.0, 0.10),
('/MYM', 'Micro E-mini Dow', 'CBOT', 'futures', 'equity_us', 0.5, 1.0),
('/MNK', 'Micro Nikkei', 'CME', 'futures', 'equity_japan', 0.5, 5.0);

-- Grains (5)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/MZC', 'Micro Corn', 'CBOT', 'futures', 'grains_feed', 5.0, 0.125),
('/MZS', 'Micro Soybeans', 'CBOT', 'futures', 'grains_oilseed', 5.0, 0.125),
('/MZW', 'Micro Wheat', 'CBOT', 'futures', 'grains_wheat', 5.0, 0.125),
('/MZL', 'Micro Soybean Oil', 'CBOT', 'futures', 'grains_oilseed', 60.0, 0.01),
('/MZM', 'Micro Soybean Meal', 'CBOT', 'futures', 'grains_oilseed', 10.0, 0.10);

-- Crypto (2)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('/MBT', 'Micro Bitcoin', 'CME', 'futures', 'crypto', 0.1, 5.0),
('/MET', 'Micro Ether', 'CME', 'futures', 'crypto', 0.1, 0.25);


-- ============================================================================
-- ETFs (41)
-- ============================================================================

-- US Broad Market (6)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('SPY', 'SPDR S&P 500 ETF', 'ARCA', 'etf', 'equity_us', 1.0, 0.01),
('QQQ', 'Invesco QQQ Trust', 'NASDAQ', 'etf', 'equity_us_tech', 1.0, 0.01),
('IWM', 'iShares Russell 2000', 'ARCA', 'etf', 'equity_us_small', 1.0, 0.01),
('DIA', 'SPDR Dow Jones', 'ARCA', 'etf', 'equity_us', 1.0, 0.01),
('VTI', 'Vanguard Total Stock', 'ARCA', 'etf', 'equity_us', 1.0, 0.01),
('IJH', 'iShares S&P MidCap', 'ARCA', 'etf', 'equity_us', 1.0, 0.01);

-- Sectors (11)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('XLK', 'Technology Select', 'ARCA', 'etf', 'equity_us_tech', 1.0, 0.01),
('XLF', 'Financial Select', 'ARCA', 'etf', 'equity_us_financials', 1.0, 0.01),
('XLE', 'Energy Select', 'ARCA', 'etf', 'energy_oil', 1.0, 0.01),
('XLV', 'Health Care Select', 'ARCA', 'etf', 'equity_us_healthcare', 1.0, 0.01),
('XLY', 'Consumer Discretionary', 'ARCA', 'etf', 'equity_us_consumer', 1.0, 0.01),
('XLP', 'Consumer Staples', 'ARCA', 'etf', 'equity_us_staples', 1.0, 0.01),
('XLI', 'Industrial Select', 'ARCA', 'etf', 'equity_us_industrial', 1.0, 0.01),
('XLB', 'Materials Select', 'ARCA', 'etf', 'metals_industrial', 1.0, 0.01),
('XLU', 'Utilities Select', 'ARCA', 'etf', 'equity_us_utilities', 1.0, 0.01),
('XLRE', 'Real Estate Select', 'ARCA', 'etf', 'equity_us_reits', 1.0, 0.01),
('XLC', 'Communication Services', 'ARCA', 'etf', 'equity_us_tech', 1.0, 0.01);

-- International (8)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('EFA', 'iShares MSCI EAFE', 'ARCA', 'etf', 'equity_intl', 1.0, 0.01),
('EEM', 'iShares MSCI Emerging', 'ARCA', 'etf', 'equity_em', 1.0, 0.01),
('FXI', 'iShares China Large-Cap', 'ARCA', 'etf', 'equity_china', 1.0, 0.01),
('EWJ', 'iShares MSCI Japan', 'ARCA', 'etf', 'equity_japan', 1.0, 0.01),
('EWG', 'iShares MSCI Germany', 'ARCA', 'etf', 'equity_europe', 1.0, 0.01),
('EWU', 'iShares MSCI UK', 'ARCA', 'etf', 'equity_uk', 1.0, 0.01),
('EWZ', 'iShares MSCI Brazil', 'ARCA', 'etf', 'equity_em', 1.0, 0.01),
('EWW', 'iShares MSCI Mexico', 'ARCA', 'etf', 'equity_em', 1.0, 0.01);

-- Commodities (7)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('GLD', 'SPDR Gold Trust', 'ARCA', 'etf', 'metals_precious', 1.0, 0.01),
('SLV', 'iShares Silver Trust', 'ARCA', 'etf', 'metals_precious', 1.0, 0.01),
('USO', 'United States Oil Fund', 'ARCA', 'etf', 'energy_oil', 1.0, 0.01),
('UNG', 'United States Natural Gas', 'ARCA', 'etf', 'energy_gas', 1.0, 0.01),
('DBA', 'Invesco DB Agriculture', 'ARCA', 'etf', 'grains_feed', 1.0, 0.01),
('DBC', 'Invesco DB Commodity', 'ARCA', 'etf', 'commodities', 1.0, 0.01),
('DJP', 'iPath Bloomberg Commodity', 'ARCA', 'etf', 'commodities', 1.0, 0.01);

-- Bonds (6)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('TLT', 'iShares 20+ Year Treasury', 'NASDAQ', 'etf', 'rates_long', 1.0, 0.01),
('IEF', 'iShares 7-10 Year Treasury', 'NASDAQ', 'etf', 'rates_mid', 1.0, 0.01),
('SHY', 'iShares 1-3 Year Treasury', 'NASDAQ', 'etf', 'rates_short', 1.0, 0.01),
('TIP', 'iShares TIPS Bond', 'ARCA', 'etf', 'rates_inflation', 1.0, 0.01),
('LQD', 'iShares Investment Grade', 'ARCA', 'etf', 'bonds_corporate', 1.0, 0.01),
('HYG', 'iShares High Yield', 'ARCA', 'etf', 'bonds_high_yield', 1.0, 0.01);

-- Volatility/Crypto (3)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('VXX', 'iPath VIX Short-Term', 'CBOE', 'etf', 'volatility', 1.0, 0.01),
('IBIT', 'iShares Bitcoin Trust', 'NASDAQ', 'etf', 'crypto', 1.0, 0.01),
('ETHA', 'iShares Ethereum Trust', 'NASDAQ', 'etf', 'crypto', 1.0, 0.01);


-- ============================================================================
-- SINGLE STOCKS (105)
-- ============================================================================

-- Technology (23)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('AAPL', 'Apple Inc', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('MSFT', 'Microsoft Corp', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('NVDA', 'NVIDIA Corp', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('GOOGL', 'Alphabet Inc', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('AMZN', 'Amazon.com Inc', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('META', 'Meta Platforms', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('TSLA', 'Tesla Inc', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('AVGO', 'Broadcom Inc', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('ADBE', 'Adobe Inc', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('CRM', 'Salesforce Inc', 'NYSE', 'stock', 'equity_us_tech', 1.0, 0.01),
('ORCL', 'Oracle Corp', 'NYSE', 'stock', 'equity_us_tech', 1.0, 0.01),
('CSCO', 'Cisco Systems', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('INTC', 'Intel Corp', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('AMD', 'Advanced Micro Devices', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('QCOM', 'Qualcomm Inc', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('TXN', 'Texas Instruments', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('MU', 'Micron Technology', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('NOW', 'ServiceNow Inc', 'NYSE', 'stock', 'equity_us_tech', 1.0, 0.01),
('INTU', 'Intuit Inc', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('PANW', 'Palo Alto Networks', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('CRWD', 'CrowdStrike Holdings', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('SNOW', 'Snowflake Inc', 'NYSE', 'stock', 'equity_us_tech', 1.0, 0.01),
('PLTR', 'Palantir Technologies', 'NYSE', 'stock', 'equity_us_tech', 1.0, 0.01);

-- Financials (13)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('JPM', 'JPMorgan Chase', 'NYSE', 'stock', 'equity_us_financials', 1.0, 0.01),
('BAC', 'Bank of America', 'NYSE', 'stock', 'equity_us_financials', 1.0, 0.01),
('WFC', 'Wells Fargo', 'NYSE', 'stock', 'equity_us_financials', 1.0, 0.01),
('GS', 'Goldman Sachs', 'NYSE', 'stock', 'equity_us_financials', 1.0, 0.01),
('MS', 'Morgan Stanley', 'NYSE', 'stock', 'equity_us_financials', 1.0, 0.01),
('C', 'Citigroup Inc', 'NYSE', 'stock', 'equity_us_financials', 1.0, 0.01),
('SCHW', 'Charles Schwab', 'NYSE', 'stock', 'equity_us_financials', 1.0, 0.01),
('BLK', 'BlackRock Inc', 'NYSE', 'stock', 'equity_us_financials', 1.0, 0.01),
('AXP', 'American Express', 'NYSE', 'stock', 'equity_us_financials', 1.0, 0.01),
('V', 'Visa Inc', 'NYSE', 'stock', 'equity_us_financials', 1.0, 0.01),
('MA', 'Mastercard Inc', 'NYSE', 'stock', 'equity_us_financials', 1.0, 0.01),
('PYPL', 'PayPal Holdings', 'NASDAQ', 'stock', 'equity_us_financials', 1.0, 0.01),
('BRK.B', 'Berkshire Hathaway B', 'NYSE', 'stock', 'equity_us_financials', 1.0, 0.01);

-- Healthcare (12)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('UNH', 'UnitedHealth Group', 'NYSE', 'stock', 'equity_us_healthcare', 1.0, 0.01),
('JNJ', 'Johnson & Johnson', 'NYSE', 'stock', 'equity_us_healthcare', 1.0, 0.01),
('LLY', 'Eli Lilly', 'NYSE', 'stock', 'equity_us_healthcare', 1.0, 0.01),
('PFE', 'Pfizer Inc', 'NYSE', 'stock', 'equity_us_healthcare', 1.0, 0.01),
('MRK', 'Merck & Co', 'NYSE', 'stock', 'equity_us_healthcare', 1.0, 0.01),
('ABBV', 'AbbVie Inc', 'NYSE', 'stock', 'equity_us_healthcare', 1.0, 0.01),
('AMGN', 'Amgen Inc', 'NASDAQ', 'stock', 'equity_us_healthcare', 1.0, 0.01),
('GILD', 'Gilead Sciences', 'NASDAQ', 'stock', 'equity_us_healthcare', 1.0, 0.01),
('MRNA', 'Moderna Inc', 'NASDAQ', 'stock', 'equity_us_healthcare', 1.0, 0.01),
('TMO', 'Thermo Fisher', 'NYSE', 'stock', 'equity_us_healthcare', 1.0, 0.01),
('ABT', 'Abbott Laboratories', 'NYSE', 'stock', 'equity_us_healthcare', 1.0, 0.01),
('CVS', 'CVS Health', 'NYSE', 'stock', 'equity_us_healthcare', 1.0, 0.01);

-- Consumer Discretionary (11)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('HD', 'Home Depot', 'NYSE', 'stock', 'equity_us_consumer', 1.0, 0.01),
('MCD', 'McDonalds Corp', 'NYSE', 'stock', 'equity_us_consumer', 1.0, 0.01),
('NKE', 'Nike Inc', 'NYSE', 'stock', 'equity_us_consumer', 1.0, 0.01),
('SBUX', 'Starbucks Corp', 'NASDAQ', 'stock', 'equity_us_consumer', 1.0, 0.01),
('LOW', 'Lowes Companies', 'NYSE', 'stock', 'equity_us_consumer', 1.0, 0.01),
('TGT', 'Target Corp', 'NYSE', 'stock', 'equity_us_consumer', 1.0, 0.01),
('COST', 'Costco Wholesale', 'NASDAQ', 'stock', 'equity_us_staples', 1.0, 0.01),
('BKNG', 'Booking Holdings', 'NASDAQ', 'stock', 'equity_us_consumer', 1.0, 0.01),
('ABNB', 'Airbnb Inc', 'NASDAQ', 'stock', 'equity_us_consumer', 1.0, 0.01),
('GM', 'General Motors', 'NYSE', 'stock', 'equity_us_consumer', 1.0, 0.01),
('F', 'Ford Motor', 'NYSE', 'stock', 'equity_us_consumer', 1.0, 0.01);

-- Consumer Staples (8)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('WMT', 'Walmart Inc', 'NYSE', 'stock', 'equity_us_staples', 1.0, 0.01),
('PG', 'Procter & Gamble', 'NYSE', 'stock', 'equity_us_staples', 1.0, 0.01),
('KO', 'Coca-Cola Co', 'NYSE', 'stock', 'equity_us_staples', 1.0, 0.01),
('PEP', 'PepsiCo Inc', 'NASDAQ', 'stock', 'equity_us_staples', 1.0, 0.01),
('PM', 'Philip Morris', 'NYSE', 'stock', 'equity_us_staples', 1.0, 0.01),
('MO', 'Altria Group', 'NYSE', 'stock', 'equity_us_staples', 1.0, 0.01),
('CL', 'Colgate-Palmolive', 'NYSE', 'stock', 'equity_us_staples', 1.0, 0.01),
('MDLZ', 'Mondelez International', 'NASDAQ', 'stock', 'equity_us_staples', 1.0, 0.01);

-- Energy (8)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('XOM', 'Exxon Mobil', 'NYSE', 'stock', 'energy_oil', 1.0, 0.01),
('CVX', 'Chevron Corp', 'NYSE', 'stock', 'energy_oil', 1.0, 0.01),
('COP', 'ConocoPhillips', 'NYSE', 'stock', 'energy_oil', 1.0, 0.01),
('SLB', 'Schlumberger Ltd', 'NYSE', 'stock', 'energy_oil', 1.0, 0.01),
('EOG', 'EOG Resources', 'NYSE', 'stock', 'energy_oil', 1.0, 0.01),
('PXD', 'Pioneer Natural Resources', 'NYSE', 'stock', 'energy_oil', 1.0, 0.01),
('OXY', 'Occidental Petroleum', 'NYSE', 'stock', 'energy_oil', 1.0, 0.01),
('DVN', 'Devon Energy', 'NYSE', 'stock', 'energy_oil', 1.0, 0.01);

-- Industrials (11)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('CAT', 'Caterpillar Inc', 'NYSE', 'stock', 'equity_us_industrial', 1.0, 0.01),
('BA', 'Boeing Co', 'NYSE', 'stock', 'equity_us_industrial', 1.0, 0.01),
('HON', 'Honeywell International', 'NASDAQ', 'stock', 'equity_us_industrial', 1.0, 0.01),
('UNP', 'Union Pacific', 'NYSE', 'stock', 'equity_us_industrial', 1.0, 0.01),
('UPS', 'United Parcel Service', 'NYSE', 'stock', 'equity_us_industrial', 1.0, 0.01),
('FDX', 'FedEx Corp', 'NYSE', 'stock', 'equity_us_industrial', 1.0, 0.01),
('DE', 'Deere & Co', 'NYSE', 'stock', 'equity_us_industrial', 1.0, 0.01),
('MMM', '3M Company', 'NYSE', 'stock', 'equity_us_industrial', 1.0, 0.01),
('GE', 'General Electric', 'NYSE', 'stock', 'equity_us_industrial', 1.0, 0.01),
('LMT', 'Lockheed Martin', 'NYSE', 'stock', 'equity_us_industrial', 1.0, 0.01),
('RTX', 'RTX Corporation', 'NYSE', 'stock', 'equity_us_industrial', 1.0, 0.01);

-- Materials (5)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('LIN', 'Linde PLC', 'NYSE', 'stock', 'metals_industrial', 1.0, 0.01),
('FCX', 'Freeport-McMoRan', 'NYSE', 'stock', 'metals_industrial', 1.0, 0.01),
('NEM', 'Newmont Corp', 'NYSE', 'stock', 'metals_precious', 1.0, 0.01),
('NUE', 'Nucor Corp', 'NYSE', 'stock', 'metals_industrial', 1.0, 0.01),
('SHW', 'Sherwin-Williams', 'NYSE', 'stock', 'equity_us_industrial', 1.0, 0.01);

-- Communication (6)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('NFLX', 'Netflix Inc', 'NASDAQ', 'stock', 'equity_us_tech', 1.0, 0.01),
('DIS', 'Walt Disney', 'NYSE', 'stock', 'equity_us_consumer', 1.0, 0.01),
('CMCSA', 'Comcast Corp', 'NASDAQ', 'stock', 'equity_us_telecom', 1.0, 0.01),
('T', 'AT&T Inc', 'NYSE', 'stock', 'equity_us_telecom', 1.0, 0.01),
('VZ', 'Verizon Communications', 'NYSE', 'stock', 'equity_us_telecom', 1.0, 0.01),
('TMUS', 'T-Mobile US', 'NASDAQ', 'stock', 'equity_us_telecom', 1.0, 0.01);

-- Utilities (3)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('NEE', 'NextEra Energy', 'NYSE', 'stock', 'equity_us_utilities', 1.0, 0.01),
('DUK', 'Duke Energy', 'NYSE', 'stock', 'equity_us_utilities', 1.0, 0.01),
('SO', 'Southern Company', 'NYSE', 'stock', 'equity_us_utilities', 1.0, 0.01);

-- Real Estate (5)
INSERT INTO markets (symbol, name, exchange, asset_class, correlation_group, point_value, tick_size) VALUES
('AMT', 'American Tower', 'NYSE', 'stock', 'equity_us_reits', 1.0, 0.01),
('PLD', 'Prologis Inc', 'NYSE', 'stock', 'equity_us_reits', 1.0, 0.01),
('CCI', 'Crown Castle', 'NYSE', 'stock', 'equity_us_reits', 1.0, 0.01),
('EQIX', 'Equinix Inc', 'NASDAQ', 'stock', 'equity_us_reits', 1.0, 0.01),
('O', 'Realty Income', 'NYSE', 'stock', 'equity_us_reits', 1.0, 0.01);


-- Record this migration
INSERT INTO schema_migrations (version) VALUES ('004_seed_full_universe')
ON CONFLICT (version) DO NOTHING;
