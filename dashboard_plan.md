# PIECE 8: Streamlit Dashboard - Implementation Plan

## Overview

Create a web-based dashboard using Streamlit for visual monitoring of the Turtle Trading system. The dashboard provides real-time insights into signals, positions, performance, and historical data.

---

## Installation

```bash
pip install streamlit plotly
```

---

## Running the Dashboard

```bash
streamlit run dashboard.py
```

The dashboard will open automatically in your default browser at `http://localhost:8501`

---

## Dashboard Structure

### Sidebar

**Purpose:** Navigation and quick reference information

**Components:**
- **Trade Type Selector:** Radio buttons for PAPER/REAL
- **Account Balance:** Display current account value
- **Watchlist:** Scrollable list of all 20 symbols with current prices
- **Last Updated:** Timestamp of most recent data refresh
- **Refresh Button:** Manual refresh trigger
- **Auto-refresh Toggle:** Enable/disable 60-second auto-refresh

**Example Layout:**
```
📊 TURTLE TRADING DASHBOARD
━━━━━━━━━━━━━━━━━━━━━━━━━━

⚙️ Settings
◉ Paper Trading
○ Real Trading

💰 Account: $13,489.57

📈 Watchlist
━━━━━━━━━━━━━━━━━━━━━━━━━━
SPY     $687.05  ▲
QQQ     $632.92  ▲
IWM     $248.93  ▼
...

🔄 Last Updated: 4:15 PM
[Refresh Now]
```

---

## Main Area: 5 Tabs

### Tab 1: Current Signals 🎯

**Purpose:** Show all trading signals detected today

**Components:**

1. **Summary Metrics** (at top)
   - Total entry signals
   - Total exit signals
   - Last scan time

2. **Entry Signals Table**
   - Columns:
     - Signal Type (🟢 BUY / 🔴 SELL badge)
     - Symbol
     - Current Price
     - Breakout Level
     - Position Size (shares)
     - Total Cost
     - Stop Loss
     - Risk Amount
     - Risk %
     - Valid? (✓/✗)
   - Color coding:
     - Green row background for BUY
     - Red row background for SELL
     - Gray background if invalid position
   - Sortable by any column

3. **Exit Signals Table**
   - Columns:
     - Signal Type (🟠 EXIT_LONG / EXIT_SHORT badge)
     - Symbol
     - Current Price
     - Exit Level
     - Position ID
     - Reason
   - Orange row background

4. **Refresh Button**
   - Re-scans for signals
   - Shows loading spinner during scan

**Example:**
```
Entry Signals (5)
┌──────────┬────────┬────────────┬──────────────┬────────┬───────────┬──────────┬─────────┬────────┬───────┐
│ Signal   │ Symbol │ Price      │ Breakout At  │ Shares │ Cost      │ Stop     │ Risk    │ Risk % │ Valid │
├──────────┼────────┼────────────┼──────────────┼────────┼───────────┼──────────┼─────────┼────────┼───────┤
│ 🟢 BUY   │ SPY    │ $687.05    │ $685.54      │ 17     │ $11,679   │ $671.85  │ $258.35 │ 1.92%  │ ✓     │
│ 🟢 BUY   │ QQQ    │ $632.92    │ $628.55      │ 14     │ $8,860    │ $614.78  │ $253.93 │ 1.88%  │ ✓     │
└──────────┴────────┴────────────┴──────────────┴────────┴───────────┴──────────┴─────────┴────────┴───────┘
```

---

### Tab 2: Open Positions 💼

**Purpose:** Monitor currently held positions

**Components:**

1. **Portfolio Summary Cards** (at top)
   - Total Positions
   - Total Invested
   - Unrealized P&L
   - Unrealized P&L %
   - Available Capital

2. **Positions Table**
   - Columns:
     - Position ID
     - Symbol
     - Direction (LONG/SHORT)
     - Entry Date
     - Days Held
     - Shares
     - Entry Price
     - Current Price
     - Entry Value
     - Current Value
     - Unrealized P&L
     - P&L %
     - Stop Loss
     - Exit Level
   - Color coding:
     - Green text for positive P&L
     - Red text for negative P&L
   - Click row to see details
   - Sortable by any column

3. **Position Details** (expandable)
   - Mini chart showing price movement since entry
   - Entry reason
   - Notes
   - Risk metrics

**Example:**
```
Portfolio Summary
┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐
│ Total Positions │ Total Invested  │ Unrealized P&L  │ Available Cash  │
├─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│       3         │   $35,450       │   +$1,250       │   $8,039        │
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘

Open Positions
┌────┬────────┬──────────┬────────────┬──────┬────────┬────────────┬──────────────┬────────────┬─────────┐
│ ID │ Symbol │ Entry    │ Days Held  │ Shrs │ Entry  │ Current    │ Current Val  │ P&L        │ P&L %   │
├────┼────────┼──────────┼────────────┼──────┼────────┼────────────┼──────────────┼────────────┼─────────┤
│ 15 │ SPY    │ 10/20/25 │    8       │ 17   │ $685.00│ $687.05    │ $11,679.85   │ +$34.85    │ +0.51%  │
└────┴────────┴──────────┴────────────┴──────┴────────┴────────────┴──────────────┴────────────┴─────────┘
```

---

### Tab 3: Performance Metrics 📈

**Purpose:** Analyze trading performance and statistics

**Components:**

1. **Key Metrics Cards** (top row, 4 columns)
   - Total Trades
   - Win Rate
   - Trading Edge
   - Total P&L

2. **Win/Loss Distribution** (Pie Chart)
   - Winning trades (green)
   - Losing trades (red)
   - Breakeven trades (gray)
   - Shows percentages

3. **Monthly P&L** (Bar Chart)
   - X-axis: Months
   - Y-axis: P&L ($)
   - Green bars for positive months
   - Red bars for negative months
   - Hoverable for exact values

4. **Equity Curve** (Line Chart)
   - X-axis: Date
   - Y-axis: Account Value ($)
   - Shows account growth over time
   - Drawdown shading (optional)

5. **Statistics Table**
   - Average Win
   - Average Loss
   - Largest Win
   - Largest Loss
   - Win/Loss Ratio
   - Expectancy

**Example:**
```
Key Metrics
┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐
│ Total Trades    │ Win Rate        │ Trading Edge    │ Total P&L       │
├─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│      12         │   33.3%         │   $98.40        │  +$1,180.80     │
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘

[Pie Chart: 4 Wins, 8 Losses]

[Bar Chart: Monthly P&L showing trend]

[Line Chart: Equity curve from $13,489 to $14,670]
```

---

### Tab 4: Trade History 📊

**Purpose:** Review all closed trades

**Components:**

1. **Filters** (top)
   - Symbol dropdown (All, or specific symbol)
   - Date range picker
   - Win/Loss toggle (All, Wins, Losses)
   - Direction filter (All, LONG, SHORT)

2. **Trade History Table**
   - Columns:
     - Trade ID
     - Symbol
     - Direction
     - Entry Date
     - Exit Date
     - Days Held
     - Shares
     - Entry Price
     - Exit Price
     - P&L
     - P&L %
     - Reason for Exit
   - Color-coded P&L
   - Pagination (show 20 trades per page)
   - Sortable

3. **Export Button**
   - Download as CSV
   - Includes all filtered trades

4. **Summary Statistics** (below table)
   - Filtered results summary
   - Total P&L
   - Win rate for filtered trades

**Example:**
```
Filters: [All Symbols ▼] [Last 30 Days] [All Trades] [All Directions]

Trade History
┌────┬────────┬──────────┬────────────┬────────────┬──────┬────────┬────────────┬──────────────┬─────────┐
│ ID │ Symbol │ Dir      │ Entry      │ Exit       │ Days │ Entry  │ Exit       │ P&L         │ P&L %   │
├────┼────────┼──────────┼────────────┼────────────┼──────┼────────┼────────────┼──────────────┼─────────┤
│ 12 │ SPY    │ LONG     │ 10/15/25   │ 10/22/25   │  7   │ $685.00│ $695.00    │ +$170.00    │ +1.46%  │
│ 11 │ QQQ    │ LONG     │ 10/10/25   │ 10/18/25   │  8   │ $630.00│ $625.00    │ -$70.00     │ -0.79%  │
└────┴────────┴──────────┴────────────┴────────────┴──────┴────────┴────────────┴──────────────┴─────────┘

[Download CSV]

Summary: 2 trades shown | Win rate: 50% | Total P&L: +$100.00
```

---

### Tab 5: Price Charts 📉

**Purpose:** Visualize price action with Donchian Channels

**Components:**

1. **Symbol Selector**
   - Dropdown with all 20 symbols
   - Shows current price next to symbol

2. **Main Candlestick Chart**
   - Plotly interactive candlestick chart
   - X-axis: Date
   - Y-axis: Price
   - Overlays:
     - 55-day Donchian Channel (wider, blue lines)
     - 20-day Donchian Channel (narrower, orange lines)
     - Entry points (green triangles up)
     - Exit points (red triangles down)
   - Features:
     - Zoom in/out
     - Pan left/right
     - Reset view
     - Hover for OHLC data

3. **Volume Subplot** (below main chart)
   - Bar chart of volume
   - Color-coded (green for up days, red for down days)

4. **Chart Controls**
   - Time range selector (1M, 3M, 6M, 1Y, ALL)
   - Toggle Donchian channels on/off
   - Toggle entry/exit markers on/off

**Example:**
```
Select Symbol: [SPY ▼] Current: $687.05

[Interactive Candlestick Chart with Donchian Channels]
  - Blue bands: 55-day channel
  - Orange bands: 20-day channel
  - Green ▲: Entry points
  - Red ▼: Exit points

[Volume bars below]

Time Range: [1M] [3M] [6M] [1Y] [ALL]
```

---

## Technical Implementation Details

### File Structure

```python
dashboard.py
├── Import statements
├── Page configuration
├── Helper functions
│   ├── load_data()
│   ├── format_currency()
│   ├── format_percent()
│   └── create_candlestick_chart()
├── Sidebar
│   ├── Trade type selector
│   ├── Account display
│   └── Watchlist
├── Main tabs
│   ├── Tab 1: Current Signals
│   ├── Tab 2: Open Positions
│   ├── Tab 3: Performance Metrics
│   ├── Tab 4: Trade History
│   └── Tab 5: Price Charts
└── Main execution
```

### Key Streamlit Features Used

1. **Layout:**
   - `st.sidebar` - Sidebar
   - `st.tabs()` - Tab navigation
   - `st.columns()` - Multi-column layouts
   - `st.expander()` - Collapsible sections

2. **Widgets:**
   - `st.selectbox()` - Dropdowns
   - `st.radio()` - Radio buttons
   - `st.button()` - Buttons
   - `st.date_input()` - Date pickers
   - `st.checkbox()` - Checkboxes

3. **Display:**
   - `st.dataframe()` - Interactive tables
   - `st.metric()` - Metric cards
   - `st.plotly_chart()` - Plotly charts
   - `st.markdown()` - Formatted text

4. **Performance:**
   - `@st.cache_data` - Cache data fetching
   - `st.session_state` - Persist state
   - `st.rerun()` - Trigger refresh

### Data Flow

```
Dashboard Load
    ↓
Load Trade Type from Session State (default: PAPER)
    ↓
Fetch Data (cached for 60 seconds):
    - Current prices
    - Open positions
    - Closed trades
    - Signals
    ↓
Render Sidebar
    ↓
Render Selected Tab
    ↓
Auto-refresh every 60 seconds (if enabled)
```

### Caching Strategy

```python
@st.cache_data(ttl=60)  # Cache for 60 seconds
def load_current_prices():
    return get_latest_prices(ALL_SYMBOLS)

@st.cache_data(ttl=60)
def load_signals(trade_type):
    return scan_all_symbols()

@st.cache_data(ttl=5)  # Cache for 5 seconds (fast refresh)
def load_portfolio(trade_type):
    return get_portfolio_summary(trade_type, load_current_prices())
```

---

## Dependencies

```python
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta

from src.data_fetcher import get_latest_prices
from src.signals import scan_all_symbols, check_breakout
from src.position_sizing import get_position_size
from src.portfolio import (
    get_open_positions,
    get_portfolio_summary,
    calculate_trading_edge,
    get_account_balance
)
from config import ALL_SYMBOLS, WATCHLIST_ETFS, WATCHLIST_STOCKS
```

---

## Styling and Theming

### Custom CSS

```python
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .positive {
        color: green;
    }
    .negative {
        color: red;
    }
    .signal-buy {
        background-color: #d4edda;
    }
    .signal-sell {
        background-color: #f8d7da;
    }
</style>
""", unsafe_allow_html=True)
```

### Color Scheme

- **Buy Signals:** Green (#28a745)
- **Sell Signals:** Red (#dc3545)
- **Exit Signals:** Orange (#fd7e14)
- **Positive P&L:** Green
- **Negative P&L:** Red
- **Neutral:** Gray

---

## Testing Checklist

- [ ] Dashboard loads without errors
- [ ] Can switch between PAPER and REAL modes
- [ ] Watchlist displays current prices
- [ ] Signals tab shows active signals with correct colors
- [ ] Positions tab shows open positions with P&L
- [ ] Performance metrics display correctly
- [ ] Charts are interactive and responsive
- [ ] Trade history filters work
- [ ] CSV export works
- [ ] Auto-refresh works
- [ ] Mobile view is usable

---

## Deployment Options

### Local Development
```bash
streamlit run dashboard.py
```

### Streamlit Cloud (Free)
1. Push code to GitHub
2. Sign up at https://streamlit.io/cloud
3. Connect repository
4. Deploy!

### Self-Hosted
```bash
# Install on server
pip install streamlit

# Run with custom port
streamlit run dashboard.py --server.port 8080
```

---

## Future Enhancements

1. **Real-time Updates:** WebSocket connection for live price updates
2. **Alerts:** Browser notifications for new signals
3. **Trade Execution:** Integration with broker API (optional)
4. **Multi-user Support:** Authentication and user management
5. **Advanced Charts:** Technical indicators (RSI, MACD, etc.)
6. **Mobile App:** Progressive Web App (PWA) support
7. **Email Reports:** Scheduled daily email with summary

---

## Advantages of This Approach

1. **Fast Development:** Pure Python, no frontend experience needed
2. **Interactive:** Built-in interactivity without JavaScript
3. **Professional:** Clean, modern UI out of the box
4. **Flexible:** Easy to add new features and charts
5. **Free Hosting:** Streamlit Cloud offers free hosting
6. **Mobile-Friendly:** Responsive by default
7. **Easy Sharing:** Anyone can access via URL

---

## Example Screenshots (Mockup)

### Signals Tab
```
🎯 Current Signals

Entry Signals (5)
┌─────────┬────────┬──────────┬──────────┬──────────┬─────────┐
│ Signal  │ Symbol │ Price    │ Shares   │ Cost     │ Risk    │
├─────────┼────────┼──────────┼──────────┼──────────┼─────────┤
│ 🟢 BUY  │ SPY    │ $687.05  │ 17       │ $11,679  │ 1.92%   │
│ 🟢 BUY  │ QQQ    │ $632.92  │ 14       │ $8,860   │ 1.88%   │
└─────────┴────────┴──────────┴──────────┴──────────┴─────────┘
```

### Performance Tab
```
📈 Performance Metrics

┌─────────────┬──────────┬──────────────┬─────────────┐
│ Total       │ Win      │ Trading      │ Total       │
│ Trades      │ Rate     │ Edge         │ P&L         │
├─────────────┼──────────┼──────────────┼─────────────┤
│ 12          │ 33.3%    │ $98.40       │ +$1,180.80  │
└─────────────┴──────────┴──────────────┴─────────────┘

[Pie Chart]    [Bar Chart]    [Line Chart]
Win/Loss       Monthly P&L    Equity Curve
```

---

## Conclusion

This dashboard provides a comprehensive, professional interface for monitoring your Turtle Trading system. It's built with Streamlit for rapid development while maintaining a polished appearance. The modular design makes it easy to add new features or customize existing ones.

**Estimated Development Time:** 4-6 hours

**Skills Required:** Python (no frontend experience needed)

**Result:** A fully functional, interactive web dashboard for your trading system!
