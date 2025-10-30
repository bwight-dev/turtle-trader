# Turtle Trading System - Build Requirements

## Overview
Build a Python-based Turtle Trading system that:
- Tracks 20 symbols (10 ETFs + 10 stocks)
- Calculates Donchian Channel breakouts (55-day entry, 20-day exit)
- Manages position sizing using ATR and 2% risk rule
- Tracks portfolio and calculates trading edge
- Sends daily alerts for entry/exit signals
- Provides web dashboard for monitoring

## User Context
- Account size: $13,489.57 (starting)
- Risk per trade: 2% of capital
- Adding $500 twice monthly
- Python experience: Advanced
- Trading experience: Learning Turtle Trading system
- Time available: Midday check-in + evening execution (4:30-5:30 PM ET)

---

## PIECE 1: Configuration & Setup

### File: `config.py`

**Purpose:** Central configuration for all settings

**Requirements:**

```python
# Account settings
INITIAL_CAPITAL = 13489.57
RISK_PER_TRADE = 0.02  # 2% risk per trade
MAX_POSITIONS = 6  # Maximum concurrent positions

# Watchlist - 20 symbols
WATCHLIST_ETFS = [
    'SPY',   # S&P 500
    'QQQ',   # Nasdaq
    'IWM',   # Russell 2000
    'DIA',   # Dow Jones
    'GLD',   # Gold
    'SLV',   # Silver
    'TLT',   # 20+ Year Treasury
    'XLE',   # Energy
    'XLF',   # Financials
    'USO'    # Oil
]

WATCHLIST_STOCKS = [
    'AAPL',  # Apple
    'MSFT',  # Microsoft
    'NVDA',  # Nvidia
    'TSLA',  # Tesla
    'AMZN',  # Amazon
    'META',  # Meta
    'GOOGL', # Google
    'JPM',   # JP Morgan
    'CAT',   # Caterpillar
    'BA'     # Boeing
]

ALL_SYMBOLS = WATCHLIST_ETFS + WATCHLIST_STOCKS

# Donchian Channel periods
ENTRY_PERIOD = 55  # 55-day breakout for entry
EXIT_PERIOD = 20   # 20-day breakout for exit

# ATR settings
ATR_PERIOD = 20    # Period for ATR calculation
ATR_MULTIPLIER = 2 # Stop loss = 2 × ATR

# Database paths
DB_PRICES = 'data/prices.db'
DB_TRADES = 'data/trades.db'

# Alert settings (to be configured by user)
EMAIL_ENABLED = False
EMAIL_TO = 'your_email@example.com'
SLACK_ENABLED = False
SLACK_WEBHOOK = ''

# Market hours (Eastern Time)
MARKET_CLOSE_HOUR = 16  # 4 PM ET
SCAN_TIME = '16:15'     # Run scan at 4:15 PM ET
```

**Deliverable:**
- Create `config.py` with all constants above
- Add comments explaining each setting
- Make it easy for user to modify settings

---

## PIECE 2: Data Fetcher

### File: `src/data_fetcher.py`

**Purpose:** Download historical price data from Yahoo Finance and store in SQLite database

**Requirements:**

1. **Function: `fetch_historical_data(symbol, period='6mo')`**
   - Input: Stock/ETF symbol (string), period (default '6mo' for 6 months)
   - Downloads OHLCV data using yfinance
   - Returns: pandas DataFrame with columns ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
   - Handle errors gracefully (symbol not found, network issues)

2. **Function: `save_to_database(symbol, dataframe, db_path)`**
   - Input: Symbol, DataFrame, database path
   - Creates/updates SQLite table for the symbol
   - Table schema:
     ```sql
     CREATE TABLE IF NOT EXISTS {symbol} (
         date TEXT PRIMARY KEY,
         open REAL,
         high REAL,
         low REAL,
         close REAL,
         volume INTEGER
     )
     ```
   - Uses REPLACE INTO for upserts (update existing, insert new)

3. **Function: `get_latest_prices(symbols_list, db_path)`**
   - Input: List of symbols, database path
   - Fetches most recent date's data for all symbols
   - Returns: Dictionary `{symbol: {'close': price, 'date': date}}`

4. **Function: `update_all_symbols()`**
   - Loops through config.ALL_SYMBOLS
   - Fetches latest data for each
   - Saves to database
   - Prints progress: "Updated SPY: $685.88 (2025-10-28)"
   - Returns summary dict with update status

**Error Handling:**
- Retry failed downloads (3 attempts)
- Log errors to console
- Continue with other symbols if one fails
- Return list of failed symbols

**Dependencies:**
```python
import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime
from config import ALL_SYMBOLS, DB_PRICES
```

**Testing Requirements:**
- Test with valid symbol (SPY)
- Test with invalid symbol (XXXXXX)
- Test database creation and updates
- Verify data integrity (no null dates)

---

## PIECE 3: Signal Calculator

### File: `src/signals.py`

**Purpose:** Calculate Donchian Channel breakouts and generate trading signals

**Requirements:**

1. **Function: `calculate_donchian(dataframe, period)`**
   - Input: DataFrame with OHLC data, period (55 or 20)
   - Calculates rolling high and low over period
   - Returns: DataFrame with added columns:
     - `donchian_high_{period}`: Highest high over period
     - `donchian_low_{period}`: Lowest low over period
   - Uses pandas rolling window: `df['High'].rolling(window=period).max()`

2. **Function: `get_current_levels(symbol, db_path)`**
   - Input: Symbol, database path
   - Reads last 60 days of data from database
   - Calculates both 55-day and 20-day Donchian channels
   - Returns dictionary:
     ```python
     {
         'symbol': 'SPY',
         'current_price': 685.88,
         'date': '2025-10-28',
         'entry_high': 685.54,  # 55-day high
         'entry_low': 652.45,   # 55-day low
         'exit_high': 685.54,   # 20-day high
         'exit_low': 652.84,    # 20-day low
     }
     ```

3. **Function: `check_breakout(symbol, db_path)`**
   - Gets current levels
   - Determines if there's a breakout signal
   - Returns:
     ```python
     {
         'symbol': 'SPY',
         'signal': 'BUY',  # or 'SELL', 'EXIT_LONG', 'EXIT_SHORT', 'NONE'
         'current_price': 685.88,
         'entry_level': 685.54,
         'exit_level': 652.84,
         'reason': 'Price broke above 55-day high'
     }
     ```
   - **Signal Logic:**
     - `BUY`: current_price > entry_high
     - `SELL`: current_price < entry_low (short signal)
     - `EXIT_LONG`: current_price < exit_low (exit long position)
     - `EXIT_SHORT`: current_price > exit_high (exit short position)
     - `NONE`: No signal

4. **Function: `scan_all_symbols(open_positions=[])`**
   - Input: List of currently open position symbols
   - Checks all symbols in config.ALL_SYMBOLS
   - For new positions: look for entry signals
   - For open positions: look for exit signals
   - Returns list of signal dictionaries

**Dependencies:**
```python
import pandas as pd
import sqlite3
from config import ALL_SYMBOLS, DB_PRICES, ENTRY_PERIOD, EXIT_PERIOD
from src.data_fetcher import get_latest_prices
```

**Testing Requirements:**
- Test with known breakout (price > 55-day high)
- Test with no signal (price in middle of range)
- Test exit signal detection
- Verify calculations match manual calculation

---

## PIECE 4: Position Sizing

### File: `src/position_sizing.py`

**Purpose:** Calculate proper position sizes based on ATR and 2% risk rule

**Requirements:**

1. **Function: `calculate_atr(dataframe, period=20)`**
   - Input: DataFrame with OHLC data, ATR period
   - Calculates Average True Range using:
     ```
     TR = max(High - Low, abs(High - Close_prev), abs(Low - Close_prev))
     ATR = rolling average of TR over period
     ```
   - Returns: Float (most recent ATR value)

2. **Function: `get_position_size(symbol, entry_price, account_value, risk_percent=0.02)`**
   - Input: Symbol, entry price, account value, risk percent
   - Gets ATR for the symbol
   - Calculates position size using:
     ```
     risk_amount = account_value × risk_percent
     stop_distance = ATR × ATR_MULTIPLIER (from config)
     shares = risk_amount / stop_distance
     position_value = shares × entry_price
     ```
   - Returns dictionary:
     ```python
     {
         'symbol': 'SPY',
         'entry_price': 685.88,
         'atr': 8.50,
         'stop_distance': 17.00,  # 2 × ATR
         'stop_price': 668.88,    # entry - stop_distance
         'risk_amount': 269.79,   # 2% of account
         'shares': 15,            # Rounded down
         'position_value': 10288.20,
         'actual_risk': 255.00,   # shares × stop_distance
         'risk_percent': 0.0189   # actual risk / account value
     }
     ```
   - Round shares DOWN to whole numbers
   - Ensure actual risk ≤ risk_amount

3. **Function: `calculate_stop_loss(symbol, entry_price, direction='LONG')`**
   - Input: Symbol, entry price, direction
   - Calculates stop based on ATR
   - For LONG: stop = entry - (ATR × multiplier)
   - For SHORT: stop = entry + (ATR × multiplier)
   - Returns: Float (stop price)

4. **Function: `validate_position_size(position_dict, account_value, open_positions)`**
   - Checks if position would exceed portfolio limits
   - Ensures total portfolio risk < 12% (6 positions × 2% each)
   - Ensures enough capital available
   - Returns: (bool, reason) - (True, "Valid") or (False, "Insufficient capital")

**Dependencies:**
```python
import pandas as pd
import numpy as np
from config import ATR_PERIOD, ATR_MULTIPLIER, RISK_PER_TRADE, MAX_POSITIONS
from src.data_fetcher import fetch_historical_data
```

**Testing Requirements:**
- Test ATR calculation against known values
- Test position sizing with $10,000 account
- Verify risk never exceeds 2%
- Test with high volatility (large ATR) and low volatility symbols

---

## PIECE 5: Portfolio Tracker

### File: `src/portfolio.py`

**Purpose:** Track open positions, calculate P&L, and maintain trade history

**Requirements:**

1. **Initialize Database: `init_portfolio_db()`**
   - Creates trades.db with two tables:
   
   ```sql
   CREATE TABLE IF NOT EXISTS positions (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       symbol TEXT NOT NULL,
       direction TEXT NOT NULL,  -- 'LONG' or 'SHORT'
       entry_date TEXT NOT NULL,
       entry_price REAL NOT NULL,
       shares INTEGER NOT NULL,
       stop_price REAL,
       exit_level REAL,          -- 20-day low for LONG, 20-day high for SHORT
       status TEXT DEFAULT 'OPEN', -- 'OPEN' or 'CLOSED'
       exit_date TEXT,
       exit_price REAL,
       pnl REAL,
       notes TEXT
   )
   
   CREATE TABLE IF NOT EXISTS account_history (
       date TEXT PRIMARY KEY,
       account_value REAL,
       num_positions INTEGER,
       daily_pnl REAL
   )
   ```

2. **Function: `add_position(symbol, direction, entry_price, shares, stop_price, exit_level)`**
   - Adds new position to positions table
   - Status = 'OPEN'
   - Entry_date = today
   - Returns: position ID

3. **Function: `get_open_positions()`**
   - Queries all positions where status='OPEN'
   - Returns: List of dictionaries with position details

4. **Function: `update_position_exit_level(position_id, new_exit_level)`**
   - Updates the exit level (20-day low/high) as it changes daily
   - Used to track trailing stop movement

5. **Function: `close_position(position_id, exit_price, exit_date)`**
   - Updates position status to 'CLOSED'
   - Calculates P&L:
     - For LONG: (exit_price - entry_price) × shares
     - For SHORT: (entry_price - exit_price) × shares
   - Updates exit_date, exit_price, pnl fields
   - Returns: P&L amount

6. **Function: `get_portfolio_summary(current_prices=None)`**
   - Gets all open positions
   - If current_prices provided, calculates unrealized P&L
   - Returns:
     ```python
     {
         'num_positions': 3,
         'total_invested': 15000.00,
         'unrealized_pnl': 450.50,
         'positions': [
             {
                 'symbol': 'SPY',
                 'shares': 10,
                 'entry_price': 685.00,
                 'current_price': 690.00,
                 'unrealized_pnl': 50.00,
                 'days_held': 5
             }
         ]
     }
     ```

7. **Function: `calculate_trading_edge()`**
   - Queries all CLOSED positions
   - Calculates:
     ```python
     {
         'total_trades': 50,
         'winning_trades': 18,
         'losing_trades': 32,
         'win_percent': 0.36,
         'avg_win': 850.00,
         'avg_loss': 270.00,
         'edge': 142.40,  # (0.36 × 850) - (0.64 × 270)
         'total_pnl': 7120.00,
         'largest_win': 2500.00,
         'largest_loss': 450.00
     }
     ```

**Dependencies:**
```python
import sqlite3
from datetime import datetime
from config import DB_TRADES
```

**Testing Requirements:**
- Test position creation and retrieval
- Test P&L calculation for long and short
- Test edge calculation with known trades
- Verify database persistence

---

## PIECE 6: Alert System

### File: `src/alerts.py`

**Purpose:** Send notifications via email or Slack when signals occur

**Requirements:**

1. **Function: `format_signal_message(signal_dict)`**
   - Input: Signal dictionary from signals.py
   - Formats into readable message:
     ```
     🚨 BUY SIGNAL: SPY
     Current Price: $685.88
     Breakout Level: $685.54
     Exit Level: $652.84
     Risk: $33.04 per share
     
     Recommended Position: 8 shares ($5,487)
     Stop Loss: $668.88 (2 × ATR)
     ```
   - Returns: Formatted string

2. **Function: `send_email(subject, body, to_email)`**
   - Uses smtplib to send email
   - Configuration from config.py
   - Handle errors gracefully
   - Returns: (bool, message)

3. **Function: `send_slack(message, webhook_url)`**
   - Posts message to Slack via webhook
   - Uses requests library
   - Returns: (bool, message)

4. **Function: `send_daily_summary(signals, portfolio_summary)`**
   - Creates daily summary message:
     ```
     📊 Daily Trading Summary - Oct 28, 2025
     
     🎯 New Signals: 2
     - BUY SPY @ $685.88
     - EXIT IWM @ $248.50
     
     💼 Portfolio Status:
     - Open Positions: 3
     - Unrealized P&L: +$450.50 (+3.3%)
     
     📈 Trading Edge: $142.40 per trade
     Win Rate: 36% (18/50 trades)
     ```
   - Sends via configured method (email/Slack)

5. **Function: `notify_all(signals_list, portfolio_summary)`**
   - Main function called by main.py
   - Checks if notifications enabled in config
   - Sends individual signal alerts (if any)
   - Sends daily summary
   - Logs all notifications

**Dependencies:**
```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from config import EMAIL_ENABLED, EMAIL_TO, SLACK_ENABLED, SLACK_WEBHOOK
```

**Configuration Note:**
User will need to set up:
- Gmail app password (if using email)
- Slack webhook URL (if using Slack)

**Testing Requirements:**
- Test message formatting
- Test email sending (with user's credentials)
- Test Slack posting (with webhook)
- Test with notifications disabled

---

## PIECE 7: Main Daily Runner

### File: `main.py`

**Purpose:** Orchestrate daily scan and alert workflow

**Requirements:**

1. **Function: `run_daily_scan()`**
   - Main workflow:
     ```
     1. Update all price data
     2. Get open positions from portfolio
     3. Scan for entry signals (new positions)
     4. Scan for exit signals (open positions)
     5. Calculate position sizes for entry signals
     6. Get portfolio summary
     7. Send alerts
     8. Print summary to terminal
     ```
   
2. **Terminal Output:**
   ```
   ═══════════════════════════════════════════
   TURTLE TRADING SYSTEM - Daily Scan
   Date: 2025-10-28 16:15:00 ET
   ═══════════════════════════════════════════
   
   📊 Price Data Update:
   ✓ Updated 20/20 symbols
   
   🎯 Entry Signals Found: 2
   
   1. BUY SPY @ $685.88
      Entry Level: $685.54 (55-day high)
      Exit Level: $652.84 (20-day low)
      Position Size: 8 shares ($5,487)
      Stop Loss: $668.88
      Risk: $264.00 (1.96%)
   
   2. BUY IWM @ $253.15
      Entry Level: $252.77 (55-day high)
      Exit Level: $237.56 (20-day low)
      Position Size: 17 shares ($4,303)
      Stop Loss: $237.96
      Risk: $269.23 (1.99%)
   
   ⚠️  Exit Signals Found: 0
   
   💼 Portfolio Status:
   Open Positions: 1
   - SPY: 10 shares @ $685.00
     Current: $688.50 | Unrealized: +$35.00
     Exit if below: $652.84
   
   📈 Performance:
   Total Trades: 12
   Win Rate: 33% (4/12)
   Average Win: $780.00
   Average Loss: $245.00
   Edge: $98.40 per trade
   Total P&L: +$1,180.80
   
   ═══════════════════════════════════════════
   ✅ Scan complete. Alerts sent.
   ═══════════════════════════════════════════
   ```

3. **Function: `schedule_daily_run()`**
   - Uses schedule library
   - Runs at 4:15 PM ET daily
   - Keeps running in background
   
4. **Main execution:**
   ```python
   if __name__ == "__main__":
       import argparse
       parser = argparse.ArgumentParser()
       parser.add_argument('--now', action='store_true', 
                          help='Run scan immediately')
       parser.add_argument('--schedule', action='store_true',
                          help='Run on schedule (4:15 PM daily)')
       args = parser.parse_args()
       
       if args.now:
           run_daily_scan()
       elif args.schedule:
           schedule_daily_run()
       else:
           print("Use --now or --schedule")
   ```

**Dependencies:**
```python
import schedule
import time
from datetime import datetime
import argparse
from src.data_fetcher import update_all_symbols
from src.signals import scan_all_symbols
from src.position_sizing import get_position_size
from src.portfolio import get_open_positions, get_portfolio_summary, calculate_trading_edge
from src.alerts import notify_all
from config import INITIAL_CAPITAL
```

**Testing Requirements:**
- Test immediate run (--now)
- Test scheduled run (--schedule)
- Verify all components integrate correctly
- Test with no signals
- Test with multiple signals

---

## PIECE 8: Streamlit Dashboard (Optional - Build Last)

### File: `dashboard.py`

**Purpose:** Web-based dashboard for monitoring system

**Requirements:**

1. **Page Layout:**
   - Sidebar: Watchlist with current prices
   - Main area: Multiple tabs
     - Tab 1: Current Signals
     - Tab 2: Open Positions
     - Tab 3: Performance Metrics
     - Tab 4: Trade History
     - Tab 5: Charts

2. **Current Signals Tab:**
   - Display table of all signals
   - Color-coded: Green (BUY), Red (SELL), Orange (EXIT)
   - Show position sizing recommendations
   - Refresh button

3. **Open Positions Tab:**
   - Table of open positions
   - Columns: Symbol, Entry Date, Entry Price, Shares, Current Price, Unrealized P&L, Days Held, Exit Level
   - Calculate current account value

4. **Performance Metrics Tab:**
   - Display trading edge calculation
   - Win rate chart (pie chart)
   - P&L by month (bar chart)
   - Equity curve (line chart)

5. **Trade History Tab:**
   - Filterable table of closed trades
   - Sort by date, P&L, symbol
   - Export to CSV button

6. **Charts Tab:**
   - Dropdown to select symbol
   - Candlestick chart with Donchian Channels overlaid
   - Mark entry/exit points for that symbol
   - Volume subplot

**Dependencies:**
```python
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from src.portfolio import get_open_positions, get_portfolio_summary, calculate_trading_edge
from src.signals import scan_all_symbols
from src.data_fetcher import get_latest_prices
```

**Run command:**
```bash
streamlit run dashboard.py
```

**Testing Requirements:**
- Test with sample data
- Verify charts render correctly
- Test interactivity (filters, dropdowns)
- Check mobile responsiveness

---

## PIECE 9: Backtesting Module

### File: `src/backtest.py`

**Purpose:** Test the system on historical data

**Requirements:**

1. **Function: `backtest_strategy(symbols, start_date, end_date, initial_capital)`**
   - Simulates trading the Turtle system
   - For each day:
     - Calculate Donchian levels
     - Check for signals
     - Execute trades (paper)
     - Track P&L
   - Returns:
     ```python
     {
         'trades': [...],  # List of all trades
         'equity_curve': pd.DataFrame,  # Daily account values
         'metrics': {
             'total_return': 0.45,  # 45%
             'sharpe_ratio': 1.8,
             'max_drawdown': -0.15,  # -15%
             'win_rate': 0.38,
             'avg_win': 850.00,
             'avg_loss': 280.00,
             'edge': 135.50
         }
     }
     ```

2. **Function: `plot_backtest_results(backtest_dict)`**
   - Creates visualizations using plotly
   - Equity curve
   - Drawdown chart
   - Trade distribution histogram

3. **Function: `compare_to_buy_and_hold(backtest_dict, benchmark='SPY')`**
   - Downloads benchmark data for same period
   - Calculates buy-and-hold return
   - Compares to Turtle strategy
   - Returns comparison metrics

**This module helps validate the system works before risking real money.**

**Dependencies:**
```python
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from src.data_fetcher import fetch_historical_data
from src.signals import calculate_donchian, check_breakout
from src.position_sizing import get_position_size, calculate_atr
```

---

## Build Order & Testing Strategy

### Phase 1: Core Infrastructure
1. ✅ Create directory structure (DONE)
2. Build config.py (PIECE 1)
3. Build data_fetcher.py (PIECE 2)
4. Build signals.py (PIECE 3)
5. **Test:** Run `python -c "from src import signals; print(signals.check_breakout('SPY', 'data/prices.db'))"`

### Phase 2: Trading Logic
6. Build position_sizing.py (PIECE 4)
7. Build portfolio.py (PIECE 5)
8. **Test:** Manually create a position, retrieve it, close it, calculate edge

### Phase 3: Integration
9. Build alerts.py (PIECE 6)
10. Build main.py (PIECE 7)
11. **Test:** Run full scan: `python main.py --now`

### Phase 4: Enhancement
12. Build dashboard.py (PIECE 8)
13. Build backtest.py (PIECE 9)
14. **Test:** Run backtest on 6 months of data

### Phase 5: Refinement
15. Add error handling
16. Add logging
17. Optimize performance
18. User documentation

---

## Testing Checklist

After each piece, verify:
- [ ] No syntax errors
- [ ] All functions have docstrings
- [ ] Type hints on function parameters
- [ ] Error handling for edge cases
- [ ] Manual test with known data
- [ ] Print statements for debugging

---

## Final Deliverables

When complete, the system should:
1. ✅ Download and store price data for 20 symbols
2. ✅ Calculate Donchian breakouts (55/20 periods)
3. ✅ Generate BUY/SELL/EXIT signals
4. ✅ Calculate position sizes with 2% risk
5. ✅ Track open positions and P&L
6. ✅ Calculate trading edge over time
7. ✅ Send alerts via email or Slack
8. ✅ Run automatically at 4:15 PM daily
9. ✅ Provide web dashboard for monitoring
10. ✅ Backtest on historical data

**User should be able to:**
- Run `python main.py --now` to get signals immediately
- Run `python main.py --schedule` to auto-run daily
- Run `streamlit run dashboard.py` to view portfolio
- Manually add/close positions through portfolio functions
- Review performance metrics anytime

---

## Notes for AI Assistant Building This

- **Use type hints:** `def function(param: str) -> dict:`
- **Add docstrings:** Every function needs clear documentation
- **Error handling:** Wrap external calls (yfinance, database) in try/except
- **Logging:** Use print statements for user feedback during development, migrate to logging later
- **Testing:** After each piece, provide a test command the user can run
- **Incremental:** Each piece should be runnable and testable independently
- **Comments:** Explain complex logic (ATR calculation, position sizing math)

**Build one piece at a time. Test before moving to next piece.**

**User will provide feedback after each piece. Iterate until working, then move forward.**