"""
Portfolio Tracker Module - Turtle Trading System

This module tracks open positions, calculates P&L, maintains trade history,
and supports both PAPER (practice) and REAL trading modes.

Key Features:
- Separate tracking for paper and real trades
- Position management (open, update, close)
- P&L calculation and tracking
- Trading edge statistics (win rate, avg win/loss)
- Account balance management

Functions:
    - init_portfolio_db: Initialize database tables
    - add_position: Open a new position
    - get_open_positions: Get all open positions
    - close_position: Close a position and calculate P&L
    - get_portfolio_summary: Current portfolio state
    - calculate_trading_edge: Performance statistics
    - get_account_balance: Current account value
    - update_account_balance: Update account value
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from config import DB_TRADES, INITIAL_CAPITAL


# ==================================================================
# FUNCTION: init_portfolio_db
# ==================================================================

def init_portfolio_db(db_path: str = DB_TRADES) -> None:
    """
    Initialize the portfolio database with required tables.

    Creates three tables:
    1. positions - Track all trades (open and closed)
    2. accounts - Track account balances for PAPER and REAL
    3. account_history - Historical account values

    Args:
        db_path: Path to database file (default from config)

    Example:
        >>> init_portfolio_db()
    """

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Table 1: positions - Track all trades
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_type TEXT NOT NULL,       -- 'PAPER' or 'REAL'
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,        -- 'LONG' or 'SHORT'
        entry_date TEXT NOT NULL,
        entry_price REAL NOT NULL,
        shares INTEGER NOT NULL,
        stop_price REAL,
        exit_level REAL,                -- 20-day low for LONG, 20-day high for SHORT
        status TEXT DEFAULT 'OPEN',     -- 'OPEN' or 'CLOSED'
        exit_date TEXT,
        exit_price REAL,
        pnl REAL,
        notes TEXT
    )
    """)

    # Table 2: accounts - Current account balances
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        trade_type TEXT PRIMARY KEY,    -- 'PAPER' or 'REAL'
        current_balance REAL NOT NULL,
        initial_balance REAL NOT NULL,
        last_updated TEXT NOT NULL
    )
    """)

    # Table 3: account_history - Historical account values
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS account_history (
        date TEXT NOT NULL,
        trade_type TEXT NOT NULL,       -- 'PAPER' or 'REAL'
        account_value REAL NOT NULL,
        num_positions INTEGER,
        daily_pnl REAL,
        PRIMARY KEY (date, trade_type)
    )
    """)

    # Initialize account balances if they don't exist
    cursor.execute("SELECT trade_type FROM accounts WHERE trade_type = 'PAPER'")
    if cursor.fetchone() is None:
        cursor.execute("""
        INSERT INTO accounts (trade_type, current_balance, initial_balance, last_updated)
        VALUES ('PAPER', ?, ?, ?)
        """, (INITIAL_CAPITAL, INITIAL_CAPITAL, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    cursor.execute("SELECT trade_type FROM accounts WHERE trade_type = 'REAL'")
    if cursor.fetchone() is None:
        cursor.execute("""
        INSERT INTO accounts (trade_type, current_balance, initial_balance, last_updated)
        VALUES ('REAL', ?, ?, ?)
        """, (INITIAL_CAPITAL, INITIAL_CAPITAL, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    conn.commit()
    conn.close()

    print(f"Portfolio database initialized: {db_path}")


# ==================================================================
# FUNCTION: get_account_balance
# ==================================================================

def get_account_balance(trade_type: str = 'PAPER', db_path: str = DB_TRADES) -> float:
    """
    Get current account balance for PAPER or REAL trading.

    Args:
        trade_type: 'PAPER' or 'REAL' (default 'PAPER' for safety)
        db_path: Path to database file

    Returns:
        Float: Current account balance

    Example:
        >>> balance = get_account_balance('PAPER')
        >>> print(f"Paper account: ${balance:,.2f}")
    """

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT current_balance FROM accounts WHERE trade_type = ?
    """, (trade_type,))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        # Initialize if doesn't exist
        init_portfolio_db(db_path)
        return INITIAL_CAPITAL

    return float(row[0])


# ==================================================================
# FUNCTION: update_account_balance
# ==================================================================

def update_account_balance(trade_type: str, new_balance: float, db_path: str = DB_TRADES) -> None:
    """
    Update account balance.

    Args:
        trade_type: 'PAPER' or 'REAL'
        new_balance: New account balance
        db_path: Path to database file

    Example:
        >>> update_account_balance('PAPER', 14000.00)
    """

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE accounts
    SET current_balance = ?, last_updated = ?
    WHERE trade_type = ?
    """, (new_balance, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), trade_type))

    conn.commit()
    conn.close()


# ==================================================================
# FUNCTION: add_position
# ==================================================================

def add_position(symbol: str, direction: str, entry_price: float, shares: int,
                stop_price: float, exit_level: float,
                trade_type: str = 'PAPER', notes: str = '',
                db_path: str = DB_TRADES) -> int:
    """
    Add a new position to the portfolio.

    Args:
        symbol: Stock/ETF ticker
        direction: 'LONG' or 'SHORT'
        entry_price: Entry price per share
        shares: Number of shares
        stop_price: Stop loss price
        exit_level: Exit signal level (20-day Donchian)
        trade_type: 'PAPER' or 'REAL' (default 'PAPER' for safety)
        notes: Optional notes about the trade
        db_path: Path to database file

    Returns:
        Integer: Position ID

    Example:
        >>> position_id = add_position('SPY', 'LONG', 687.60, 17, 672.52, 652.84)
        >>> print(f"Added position #{position_id}")
    """

    entry_date = datetime.now().strftime('%Y-%m-%d')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO positions (
        trade_type, symbol, direction, entry_date, entry_price,
        shares, stop_price, exit_level, status, notes
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
    """, (trade_type, symbol, direction, entry_date, entry_price,
          shares, stop_price, exit_level, notes))

    position_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return position_id


# ==================================================================
# FUNCTION: get_open_positions
# ==================================================================

def get_open_positions(trade_type: str = 'PAPER', db_path: str = DB_TRADES) -> List[Dict]:
    """
    Get all open positions for a given trade type.

    Args:
        trade_type: 'PAPER' or 'REAL' (default 'PAPER')
        db_path: Path to database file

    Returns:
        List of dictionaries with position details

    Example:
        >>> positions = get_open_positions('PAPER')
        >>> for pos in positions:
        ...     print(f"{pos['symbol']}: {pos['shares']} shares")
    """

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, symbol, direction, entry_date, entry_price, shares,
           stop_price, exit_level, notes
    FROM positions
    WHERE status = 'OPEN' AND trade_type = ?
    ORDER BY entry_date DESC
    """, (trade_type,))

    rows = cursor.fetchall()
    conn.close()

    positions = []
    for row in rows:
        positions.append({
            'id': row[0],
            'symbol': row[1],
            'direction': row[2],
            'entry_date': row[3],
            'entry_price': row[4],
            'shares': row[5],
            'stop_price': row[6],
            'exit_level': row[7],
            'notes': row[8]
        })

    return positions


# ==================================================================
# FUNCTION: update_position_exit_level
# ==================================================================

def update_position_exit_level(position_id: int, new_exit_level: float,
                               db_path: str = DB_TRADES) -> None:
    """
    Update the exit level for a position (as 20-day Donchian changes).

    Args:
        position_id: Position ID
        new_exit_level: New exit level
        db_path: Path to database file

    Example:
        >>> update_position_exit_level(1, 655.00)
    """

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE positions
    SET exit_level = ?
    WHERE id = ?
    """, (new_exit_level, position_id))

    conn.commit()
    conn.close()


# ==================================================================
# FUNCTION: close_position
# ==================================================================

def close_position(position_id: int, exit_price: float, exit_date: Optional[str] = None,
                  db_path: str = DB_TRADES) -> float:
    """
    Close a position and calculate P&L.

    Args:
        position_id: Position ID to close
        exit_price: Exit price per share
        exit_date: Exit date (default today)
        db_path: Path to database file

    Returns:
        Float: P&L amount

    Example:
        >>> pnl = close_position(1, 695.00)
        >>> print(f"P&L: ${pnl:.2f}")
    """

    if exit_date is None:
        exit_date = datetime.now().strftime('%Y-%m-%d')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get position details
    cursor.execute("""
    SELECT direction, entry_price, shares
    FROM positions
    WHERE id = ?
    """, (position_id,))

    row = cursor.fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"Position {position_id} not found")

    direction, entry_price, shares = row

    # Calculate P&L
    if direction == 'LONG':
        pnl = (exit_price - entry_price) * shares
    elif direction == 'SHORT':
        pnl = (entry_price - exit_price) * shares
    else:
        conn.close()
        raise ValueError(f"Invalid direction: {direction}")

    # Update position
    cursor.execute("""
    UPDATE positions
    SET status = 'CLOSED', exit_date = ?, exit_price = ?, pnl = ?
    WHERE id = ?
    """, (exit_date, exit_price, pnl, position_id))

    conn.commit()
    conn.close()

    return pnl


# ==================================================================
# FUNCTION: get_portfolio_summary
# ==================================================================

def get_portfolio_summary(trade_type: str = 'PAPER', current_prices: Optional[Dict] = None,
                         db_path: str = DB_TRADES) -> Dict:
    """
    Get portfolio summary with unrealized P&L.

    Args:
        trade_type: 'PAPER' or 'REAL'
        current_prices: Dict of {symbol: price} for calculating unrealized P&L
        db_path: Path to database file

    Returns:
        Dictionary with portfolio summary

    Example:
        >>> summary = get_portfolio_summary('PAPER', {'SPY': 690.00})
        >>> print(f"Open positions: {summary['num_positions']}")
    """

    positions = get_open_positions(trade_type, db_path)

    total_invested = 0
    unrealized_pnl = 0
    position_details = []

    for pos in positions:
        entry_value = pos['entry_price'] * pos['shares']
        total_invested += entry_value

        # Calculate days held
        entry_date = datetime.strptime(pos['entry_date'], '%Y-%m-%d')
        days_held = (datetime.now() - entry_date).days

        position_detail = {
            'id': pos['id'],
            'symbol': pos['symbol'],
            'direction': pos['direction'],
            'shares': pos['shares'],
            'entry_price': pos['entry_price'],
            'entry_value': entry_value,
            'stop_price': pos['stop_price'],
            'exit_level': pos['exit_level'],
            'days_held': days_held,
            'current_price': None,
            'current_value': None,
            'unrealized_pnl': None
        }

        # Calculate unrealized P&L if current prices provided
        if current_prices and pos['symbol'] in current_prices:
            current_price = current_prices[pos['symbol']]['close']
            current_value = current_price * pos['shares']

            if pos['direction'] == 'LONG':
                pnl = (current_price - pos['entry_price']) * pos['shares']
            else:  # SHORT
                pnl = (pos['entry_price'] - current_price) * pos['shares']

            position_detail['current_price'] = current_price
            position_detail['current_value'] = current_value
            position_detail['unrealized_pnl'] = pnl
            unrealized_pnl += pnl

        position_details.append(position_detail)

    # Get account balance
    account_balance = get_account_balance(trade_type, db_path)

    return {
        'trade_type': trade_type,
        'account_balance': account_balance,
        'num_positions': len(positions),
        'total_invested': total_invested,
        'unrealized_pnl': unrealized_pnl,
        'positions': position_details
    }


# ==================================================================
# FUNCTION: calculate_trading_edge
# ==================================================================

def calculate_trading_edge(trade_type: str = 'PAPER', db_path: str = DB_TRADES) -> Dict:
    """
    Calculate trading statistics and edge.

    Trading Edge = (Win% * Avg Win) - (Loss% * Avg Loss)

    Args:
        trade_type: 'PAPER' or 'REAL'
        db_path: Path to database file

    Returns:
        Dictionary with trading statistics

    Example:
        >>> stats = calculate_trading_edge('PAPER')
        >>> print(f"Win rate: {stats['win_percent']:.1%}")
        >>> print(f"Edge: ${stats['edge']:.2f}")
    """

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all closed positions
    cursor.execute("""
    SELECT pnl, entry_price, shares
    FROM positions
    WHERE status = 'CLOSED' AND trade_type = ?
    """, (trade_type,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_percent': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'edge': 0.0,
            'total_pnl': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0
        }

    # Analyze trades
    total_trades = len(rows)
    wins = [row[0] for row in rows if row[0] > 0]
    losses = [row[0] for row in rows if row[0] < 0]

    winning_trades = len(wins)
    losing_trades = len(losses)

    win_percent = winning_trades / total_trades if total_trades > 0 else 0
    loss_percent = losing_trades / total_trades if total_trades > 0 else 0

    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0

    # Calculate edge
    edge = (win_percent * avg_win) - (loss_percent * avg_loss)

    total_pnl = sum(row[0] for row in rows)
    largest_win = max(wins) if wins else 0
    largest_loss = min(losses) if losses else 0

    return {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_percent': win_percent,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'edge': edge,
        'total_pnl': total_pnl,
        'largest_win': largest_win,
        'largest_loss': largest_loss
    }


# ==================================================================
# MAIN - For testing this module directly
# ==================================================================

if __name__ == "__main__":
    """
    Test the portfolio tracker by running:
        python src/portfolio.py
    """

    print("Running portfolio tracker in test mode...\n")

    # Initialize database
    print("Step 1: Initialize database")
    init_portfolio_db()
    print()

    # Check account balances
    print("Step 2: Check account balances")
    paper_balance = get_account_balance('PAPER')
    real_balance = get_account_balance('REAL')
    print(f"  Paper account: ${paper_balance:,.2f}")
    print(f"  Real account:  ${real_balance:,.2f}")
    print()

    # Add a test position
    print("Step 3: Add test position (PAPER)")
    pos_id = add_position('SPY', 'LONG', 687.60, 17, 672.52, 652.84, 'PAPER', 'Test trade')
    print(f"  Added position #{pos_id}")
    print()

    # Get open positions
    print("Step 4: Get open positions (PAPER)")
    positions = get_open_positions('PAPER')
    print(f"  Open positions: {len(positions)}")
    for pos in positions:
        print(f"    {pos['symbol']}: {pos['shares']} shares @ ${pos['entry_price']:.2f}")
    print()

    # Get portfolio summary
    print("Step 5: Portfolio summary")
    summary = get_portfolio_summary('PAPER', {'SPY': 690.00})
    print(f"  Positions: {summary['num_positions']}")
    print(f"  Invested: ${summary['total_invested']:,.2f}")
    print(f"  Unrealized P&L: ${summary['unrealized_pnl']:,.2f}")
    print()

    print("Test complete!")
