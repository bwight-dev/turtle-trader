"""
Turtle Trading System - Configuration File

This file contains all configuration settings for the Turtle Trading system.
Modify these values to customize the system to your needs.
"""

# ==================================================================
# ACCOUNT SETTINGS
# ==================================================================

# CRITICAL: Set this to your ACTUAL available Turtle Trading capital
# This is the exact amount of cash you have dedicated to this system
#
# RULES:
# 1. This must match your real trading capital EXACTLY
# 2. Update this value when you add deposits (e.g., your $500 twice monthly)
# 3. Never set this higher than your actual available cash
# 4. If using a mixed account, this is ONLY your Turtle Trading allocation
#
# MINIMUM CAPITAL GUIDELINES:
# - $500: Too small, cannot execute system properly
# - $2,500: Minimum viable, tight but workable (1-2 positions)
# - $5,000: Comfortable minimum, can diversify (2-3 positions)
# - $10,000+: Full system execution (3-6 positions)
#
# EXAMPLE TRACKING (update this when you add capital):
# Nov 1, 2025: $2,500 (initial deposit)
# Nov 15, 2025: $3,000 (added $500)
# Dec 1, 2025: $3,500 (added $500)
# Dec 15, 2025: $4,000 (added $500)
#
INITIAL_CAPITAL = 2500.00  # SET THIS TO YOUR ACTUAL STARTING CAPITAL

# Risk per trade as a percentage of account value
# 0.02 = 2% risk per trade (Turtle Trading standard)
# Do not change this - risk management is core to the system
RISK_PER_TRADE = 0.02

# Maximum number of concurrent positions
# Scale this based on your account size:
# - $2,500-3,500: Use 2-3 positions (8% total risk)
# - $5,000-7,500: Use 3-4 positions (8-10% total risk)
# - $10,000+: Use 4-6 positions (10-12% total risk)
#
# This limits total portfolio risk to MAX_POSITIONS * RISK_PER_TRADE
# Start conservative, increase as you gain experience and capital
MAX_POSITIONS = 3  # Adjust based on your capital level

# Position Sizing Configuration
# Set to True to allow fractional shares (e.g., 0.72 shares)
# Set to False to use whole shares only (rounds down)
# RECOMMENDATION: Keep False for first 3-6 months (simplicity)
ALLOW_FRACTIONAL_SHARES = False

# If using fractional shares, this sets decimal precision
# Fidelity supports up to 3 decimal places (e.g., 1.427 shares)
FRACTIONAL_PRECISION = 3


# ==================================================================
# WATCHLIST CONFIGURATION
# ==================================================================

# IMPORTANT: Scale your watchlist to your account size
# Expensive stocks ($500+/share) can consume too much capital in small accounts
#
# GUIDELINES BY ACCOUNT SIZE:
# - $2,500-3,500: Use 8-12 symbols, max ~$400/share (avoid NVDA, expensive tech)
# - $5,000-7,500: Use 12-16 symbols, max ~$600/share (can include most)
# - $10,000+: Use 16-20 symbols, no restrictions
#
# Choose ONE option below based on your capital level:

# OPTION 1: FULL WATCHLIST (20 symbols) - For $10,000+ accounts
# Includes expensive stocks like NVDA ($730), TSLA ($300+), MSFT ($430)
WATCHLIST_FULL = [
    # ETFs
    'SPY', 'QQQ', 'IWM', 'DIA', 'GLD', 'SLV', 'TLT', 'XLE', 'XLF', 'USO',
    # Stocks
    'AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN', 'META', 'GOOGL', 'JPM', 'CAT', 'BA'
]

# OPTION 2: SMALL ACCOUNT WATCHLIST (12 symbols) - For $2,500-5,000 accounts
# Excludes expensive stocks, focuses on affordable, liquid names
WATCHLIST_SMALL = [
    # ETFs (keep these - essential diversification)
    'SPY', 'QQQ', 'GLD', 'XLE',
    # Affordable stocks (<$400/share)
    'GOOGL', 'CAT', 'BA', 'AAPL', 'JPM', 'XOM', 'RTX', 'LMT'
]

# OPTION 3: MICRO ACCOUNT WATCHLIST (8 symbols) - For <$2,500 accounts (NOT RECOMMENDED)
# Bare minimum for learning, not optimal for diversification
WATCHLIST_MICRO = [
    'SPY', 'QQQ', 'GLD',  # Core ETFs
    'BA', 'JPM', 'XOM', 'CAT', 'GOOGL'  # Affordable stocks
]

# ==================================================================
# ACTIVE WATCHLIST SELECTION
# ==================================================================

# UNCOMMENT ONE LINE BELOW based on your account size:

# Use this for $10,000+ accounts:
# ALL_SYMBOLS = WATCHLIST_FULL

# Use this for $2,500-7,500 accounts (RECOMMENDED for most users):
ALL_SYMBOLS = WATCHLIST_SMALL

# Use this only if you have <$2,500 (not recommended, wait until $2,500+):
# ALL_SYMBOLS = WATCHLIST_MICRO

# Legacy separate lists (for backward compatibility)
# These are derived from your active watchlist selection above
WATCHLIST_ETFS = [s for s in ALL_SYMBOLS if s in ['SPY', 'QQQ', 'IWM', 'DIA', 'GLD', 'SLV', 'TLT', 'XLE', 'XLF', 'USO']]
WATCHLIST_STOCKS = [s for s in ALL_SYMBOLS if s not in WATCHLIST_ETFS]


# ==================================================================
# DONCHIAN CHANNEL SETTINGS
# ==================================================================

# Entry signal: Breakout of N-day high (for LONG) or N-day low (for SHORT)
# Turtle Trading uses 55-day breakout for entries
ENTRY_PERIOD = 55

# Exit signal: Breakout of N-day high/low in opposite direction
# Turtle Trading uses 20-day breakout for exits
EXIT_PERIOD = 20


# ==================================================================
# AVERAGE TRUE RANGE (ATR) SETTINGS
# ==================================================================

# Period for calculating ATR (rolling window in days)
ATR_PERIOD = 20

# Stop loss multiplier: Stop distance = ATR * ATR_MULTIPLIER
# Turtle Trading uses 2 * ATR for stop losses
# For LONG: stop = entry_price - (ATR * 2)
# For SHORT: stop = entry_price + (ATR * 2)
ATR_MULTIPLIER = 2


# ==================================================================
# DATABASE PATHS
# ==================================================================

# SQLite database for storing historical price data (OHLCV)
DB_PRICES = 'data/prices.db'

# SQLite database for storing trade history and positions
DB_TRADES = 'data/trades.db'


# ==================================================================
# ALERT / NOTIFICATION SETTINGS
# ==================================================================

# Email Notifications
# To enable: Set EMAIL_ENABLED = True and configure your email settings below
EMAIL_ENABLED = False
EMAIL_TO = 'your_email@example.com'

# For Gmail, you'll need to:
# 1. Enable 2-factor authentication
# 2. Generate an app-specific password
# 3. Set these environment variables:
#    - GMAIL_USER (your gmail address)
#    - GMAIL_APP_PASSWORD (your app password)
EMAIL_FROM = None  # Will use GMAIL_USER environment variable
EMAIL_PASSWORD = None  # Will use GMAIL_APP_PASSWORD environment variable

# Slack Notifications
# To enable: Set SLACK_ENABLED = True and add your webhook URL below
# Get webhook URL from: https://api.slack.com/messaging/webhooks
SLACK_ENABLED = False
SLACK_WEBHOOK = ''  # Example: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'


# ==================================================================
# MARKET HOURS & SCHEDULING (Eastern Time)
# ==================================================================

# US stock market close time (4:00 PM ET)
MARKET_CLOSE_HOUR = 16

# Time to run daily scan (after market close)
# 4:15 PM ET gives time for final prices to settle
SCAN_TIME = '16:15'

# Timezone for scheduling (US Eastern Time)
TIMEZONE = 'US/Eastern'


# ==================================================================
# NOTES
# ==================================================================

"""
TURTLE TRADING SYSTEM OVERVIEW:

1. Entry Signal:
   - LONG: Price breaks above 55-day high
   - SHORT: Price breaks below 55-day low

2. Exit Signal:
   - LONG: Price breaks below 20-day low
   - SHORT: Price breaks above 20-day high

3. Position Sizing:
   - Risk 2% of account value per trade
   - Position size = (Account * 0.02) / (ATR * 2)
   - Stop loss = Entry +/- (2 * ATR)

4. Portfolio Management:
   - Maximum 6 positions at once (12% total risk)
   - Scale in: Add to winning positions
   - Scale out: Exit losers quickly

5. Trading Edge:
   - Win rate typically 35-40%
   - Average win > 2x average loss
   - Edge = (Win% * Avg Win) - (Loss% * Avg Loss)

For more information, see requirements.md
"""
