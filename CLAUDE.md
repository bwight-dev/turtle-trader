# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Turtle Trading System** implementation in Python - an automated trend-following trading strategy based on the legendary Turtle Trading methodology. The system tracks 20 symbols (10 ETFs + 10 stocks), generates BUY/SELL signals based on Donchian Channel breakouts (55-day entry, 20-day exit), manages position sizing using ATR and 2% risk rule, and tracks portfolio performance.

**Key Trading Rules:**
- **Entry Signal:** LONG when price breaks above 55-day high, SHORT when price breaks below 55-day low
- **Exit Signal:** Exit LONG when price breaks below 20-day low, exit SHORT when price breaks above 20-day high
- **Position Sizing:** Risk 2% of account value per trade, calculated as: shares = (account × 0.02) / (ATR × 2)
- **Stop Loss:** Entry price ± (2 × ATR)
- **Maximum Positions:** 6 concurrent positions (12% total portfolio risk)

## Architecture

### Core Trading Loop
The system follows a daily workflow orchestrated by `main.py`:
1. **Data Update** (`src/data_fetcher.py`) - Fetch latest OHLCV data from Yahoo Finance
2. **Signal Calculation** (`src/signals.py`) - Calculate Donchian Channels and detect breakouts
3. **Position Sizing** (`src/position_sizing.py`) - Calculate ATR and determine proper share quantities
4. **Portfolio Management** (`src/portfolio.py`) - Track open positions, calculate P&L, maintain trade history
5. **Alerts** (`src/alerts.py`) - Send notifications via email or Slack (optional)

### Dual Trading Modes
The system supports both **PAPER** (practice) and **REAL** trading modes, tracked separately in the database:
- All functions accept `trade_type` parameter ('PAPER' or 'REAL')
- Default mode is PAPER for safety
- Account balances, positions, and trade history are isolated per mode
- Use `--real` flag with main.py to operate in REAL mode

### Database Architecture
Two SQLite databases store system data:

**`data/prices.db`** - Historical price data
- One table per symbol (e.g., `SPY`, `AAPL`)
- Schema: date (PRIMARY KEY), open, high, low, close, volume
- Updated daily via `src/data_fetcher.py`

**`data/trades.db`** - Portfolio and trade tracking
- `positions` table: All trades (open/closed) with trade_type, symbol, direction, entry/exit prices, P&L
- `accounts` table: Current account balances for PAPER and REAL modes
- `account_history` table: Historical account values for equity curve

### Signal Detection Flow
Signals are calculated in `src/signals.py`:
1. `get_current_levels(symbol)` - Fetches last 60 days of price data, calculates both 55-day and 20-day Donchian Channels
2. `check_breakout(symbol)` - Compares current price to channels, returns signal type (BUY/SELL/EXIT_LONG/EXIT_SHORT/NONE)
3. `scan_all_symbols(open_positions)` - Scans all watchlist symbols, prioritizes exit signals for open positions

**Critical:** The system tracks entry signals (55-day breakout) separately from exit signals (20-day breakout). Exit signals only trigger for currently held positions.

### Position Sizing Logic
Implemented in `src/position_sizing.py`:
1. `calculate_atr(dataframe, period=20)` - Calculates Average True Range using max(High-Low, abs(High-Close_prev), abs(Low-Close_prev))
2. `get_position_size(symbol, entry_price, account_value)` - Returns position details including:
   - Stop distance = ATR × 2
   - Risk amount = account_value × 2%
   - Shares = risk_amount / stop_distance (rounded down)
3. `validate_position_size(position, account_value, open_positions)` - Ensures sufficient capital and doesn't exceed max positions

## Common Commands

### Running the Trading System
```bash
# Run daily scan immediately (paper trading)
python main.py --now

# Run daily scan immediately (real trading)
python main.py --now --real

# Schedule daily scans at 4:15 PM ET (paper trading)
python main.py --schedule

# Schedule daily scans at 4:15 PM ET (real trading)
python main.py --schedule --real
```

### Running the Dashboard
```bash
# Launch web dashboard (opens at http://localhost:8501)
streamlit run dashboard.py

# The dashboard provides:
# - Current signals with position sizing recommendations
# - Open positions with unrealized P&L
# - Performance metrics and trading statistics
# - Trade history with filters
# - Interactive price charts with Donchian Channels
```

### Helper Scripts (in `scripts/` directory)
```bash
# Update price data for all symbols
python scripts/update_data.py

# Check current signals
python scripts/check_signals.py

# View portfolio status
python scripts/view_portfolio.py

# View trade history
python scripts/view_history.py

# View price data for a symbol
python scripts/view_prices.py SPY

# Calculate position size for a potential trade
python scripts/calculate_position.py SPY 685.00

# Add sample paper trades for testing
python scripts/add_paper_trades.py
```

### Testing and Development
```bash
# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install yfinance pandas numpy pandas-ta schedule streamlit plotly

# Run backtest (when implemented)
python src/backtest.py --start 2024-01-01 --end 2024-12-31

# Initialize database tables
python -c "from src.portfolio import init_portfolio_db; init_portfolio_db()"
```

## Important Configuration

All configuration is centralized in `config.py`:
- `INITIAL_CAPITAL` - Starting account balance
- `RISK_PER_TRADE` - Risk percentage (default 0.02 = 2%)
- `MAX_POSITIONS` - Maximum concurrent positions (default 6)
- `ALL_SYMBOLS` - List of 20 tracked symbols (10 ETFs + 10 stocks)
- `ENTRY_PERIOD` - Donchian breakout period for entries (default 55)
- `EXIT_PERIOD` - Donchian breakout period for exits (default 20)
- `ATR_PERIOD` - ATR calculation period (default 20)
- `ATR_MULTIPLIER` - Stop loss distance multiplier (default 2)
- `SCAN_TIME` - Daily scan time in ET (default '16:15')

## Key Design Patterns

### Error Handling
- All data fetching functions retry failed downloads (3 attempts)
- Database operations use try/except with graceful degradation
- Failed symbol updates don't halt the entire scan
- All functions return success/failure indicators with reasons

### Data Caching
- Dashboard uses `@st.cache_data` with TTL to avoid redundant database queries
- Price data cached for 60 seconds
- Portfolio data cached for 5 seconds (faster refresh)
- Historical data cached for 5 minutes

### Type Safety
- Functions use type hints: `def function(param: str) -> dict:`
- Return types are documented in docstrings
- Optional types used for nullable returns: `Optional[Dict]`

## Development Notes

### When Adding New Symbols
1. Add symbol to `WATCHLIST_ETFS` or `WATCHLIST_STOCKS` in `config.py`
2. Run `python scripts/update_data.py` to fetch historical data
3. The symbol will automatically be included in scans

### When Modifying Trading Logic
- **Signal calculation:** Edit `src/signals.py`
- **Position sizing:** Edit `src/position_sizing.py`
- **Stop loss rules:** Edit ATR calculation or multiplier in `config.py`
- **Entry/exit periods:** Change `ENTRY_PERIOD` and `EXIT_PERIOD` in `config.py`

### When Working with the Database
- Use context managers for connections: `with sqlite3.connect(DB_PATH) as conn:`
- Always close connections after queries
- Use parameterized queries to prevent SQL injection: `cursor.execute(query, params=(value,))`
- Tables are created automatically via `init_portfolio_db()`

### Testing the System
- Start with paper trading mode (default)
- Use `scripts/add_paper_trades.py` to create sample trades for dashboard testing
- Run `python main.py --now` after market close (4:00 PM ET) for real signals
- Verify position sizing calculations with `scripts/calculate_position.py`

## File Organization

```
turtle-trader/
├── config.py              # Central configuration
├── main.py                # Main trading system orchestrator
├── dashboard.py           # Streamlit web dashboard
├── requirements.md        # Detailed build requirements
├── src/
│   ├── data_fetcher.py    # Yahoo Finance data downloader
│   ├── signals.py         # Donchian Channel and signal detection
│   ├── position_sizing.py # ATR calculation and position sizing
│   ├── portfolio.py       # Position tracking and P&L calculation
│   ├── alerts.py          # Email/Slack notifications
│   └── backtest.py        # Backtesting module (optional)
├── scripts/               # Utility scripts for common tasks
├── data/                  # SQLite databases (created automatically)
│   ├── prices.db          # Historical price data
│   └── trades.db          # Portfolio and trade history
└── venv/                  # Python virtual environment
```

## Common Issues and Solutions

**Issue:** `yfinance` fails to download data for a symbol
- **Solution:** Check if symbol is valid, verify internet connection, retry with `scripts/update_data.py`

**Issue:** Dashboard shows "No price data available"
- **Solution:** Run `python scripts/update_data.py` first to populate prices.db

**Issue:** Position size validation fails with "Insufficient capital"
- **Solution:** Check `get_account_balance(trade_type)` - may need to close positions or add capital

**Issue:** Signals detected but marked as invalid
- **Solution:** Check `validate_position_size()` - likely insufficient capital or max positions reached

**Issue:** ATR calculation returns None
- **Solution:** Ensure at least 20 days of price history exists in database

## Trading System Expectations

The Turtle Trading system is designed for long-term trend following with these characteristics:
- **Win Rate:** Typically 35-40% (most trades are small losses)
- **Win/Loss Ratio:** Average win should be 2-3x average loss
- **Trading Edge:** Calculated as (Win% × Avg Win) - (Loss% × Avg Loss)
- **Expectancy:** System is profitable when edge is positive despite low win rate
- **Drawdowns:** Expect 15-25% drawdowns during choppy markets
- **Best Performance:** Strong trending markets (bull or bear runs)

The system's profitability comes from letting winners run (captured by 20-day exit) while cutting losers quickly (2×ATR stop loss).
