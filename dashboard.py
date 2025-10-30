"""
Streamlit Dashboard - Turtle Trading System

A comprehensive web-based dashboard for monitoring the Turtle Trading system.
Provides real-time insights into signals, positions, performance, and charts.

Usage:
    streamlit run dashboard.py

Features:
- Current Signals (Entry/Exit)
- Open Positions with P&L
- Performance Metrics & Charts
- Trade History
- Interactive Price Charts with Donchian Channels
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Import modules from the trading system
from src.data_fetcher import get_latest_prices
from src.signals import scan_all_symbols, check_breakout, get_current_levels
from src.position_sizing import get_position_size, get_atr_for_symbol
from src.portfolio import (
    get_open_positions,
    get_portfolio_summary,
    calculate_trading_edge,
    get_account_balance,
    init_portfolio_db
)
from config import ALL_SYMBOLS, WATCHLIST_ETFS, WATCHLIST_STOCKS, DB_PRICES, DB_TRADES


# ==================================================================
# PAGE CONFIGURATION
# ==================================================================

st.set_page_config(
    page_title="Turtle Trading Dashboard",
    page_icon="🐢",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==================================================================
# CUSTOM CSS STYLING
# ==================================================================

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
    .signal-exit {
        background-color: #fff3cd;
    }
</style>
""", unsafe_allow_html=True)


# ==================================================================
# HELPER FUNCTIONS
# ==================================================================

def format_currency(value: float) -> str:
    """Format number as currency."""
    return f"${value:,.2f}"


def format_percent(value: float) -> str:
    """Format number as percentage."""
    return f"{value:.2%}"


def color_pnl(value: float) -> str:
    """Return color based on P&L value."""
    if value > 0:
        return "=�"
    elif value < 0:
        return "=4"
    else:
        return "�"


# ==================================================================
# CACHED DATA LOADING FUNCTIONS
# ==================================================================

@st.cache_data(ttl=60)  # Cache for 60 seconds
def load_current_prices() -> Dict:
    """Load latest prices for all symbols."""
    return get_latest_prices(ALL_SYMBOLS)


@st.cache_data(ttl=60)
def load_signals(trade_type: str) -> List[Dict]:
    """Scan all symbols for trading signals."""
    # Get open positions to prioritize exit signals
    open_positions = get_open_positions(trade_type)
    open_symbols = [pos['symbol'] for pos in open_positions]

    # Scan for signals
    signals = scan_all_symbols(open_positions=open_symbols)
    return signals


@st.cache_data(ttl=5)  # Cache for 5 seconds (fast refresh)
def load_portfolio(trade_type: str) -> Dict:
    """Load portfolio summary with current prices."""
    current_prices = load_current_prices()
    return get_portfolio_summary(trade_type, current_prices)


@st.cache_data(ttl=60)
def load_trading_stats(trade_type: str) -> Dict:
    """Load trading statistics and edge."""
    return calculate_trading_edge(trade_type)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_price_history(symbol: str, days: int = 180) -> pd.DataFrame:
    """Load price history for a symbol."""
    try:
        conn = sqlite3.connect(DB_PRICES)
        query = f"""
        SELECT date, open, high, low, close, volume
        FROM {symbol}
        ORDER BY date DESC
        LIMIT {days}
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        # Sort by date ascending for charts
        df = df.sort_values('date').reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Error loading price history for {symbol}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def load_closed_trades(trade_type: str) -> pd.DataFrame:
    """Load all closed trades."""
    try:
        conn = sqlite3.connect(DB_TRADES)
        query = """
        SELECT id, symbol, direction, entry_date, exit_date,
               entry_price, exit_price, shares, pnl, notes
        FROM positions
        WHERE status = 'CLOSED' AND trade_type = ?
        ORDER BY exit_date DESC
        """
        df = pd.read_sql_query(query, conn, params=(trade_type,))
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error loading trade history: {e}")
        return pd.DataFrame()


# ==================================================================
# CHARTING FUNCTIONS
# ==================================================================

def create_candlestick_chart(symbol: str, df: pd.DataFrame) -> go.Figure:
    """Create interactive candlestick chart with Donchian Channels."""

    # Calculate Donchian Channels
    df['donchian_high_55'] = df['high'].rolling(window=55).max()
    df['donchian_low_55'] = df['low'].rolling(window=55).min()
    df['donchian_high_20'] = df['high'].rolling(window=20).max()
    df['donchian_low_20'] = df['low'].rolling(window=20).min()

    # Create figure with subplots
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.7, 0.3],
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=(f'{symbol} Price Chart', 'Volume')
    )

    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df['date'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Price'
        ),
        row=1, col=1
    )

    # 55-day Donchian Channel (blue)
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['donchian_high_55'],
            name='55-day High',
            line=dict(color='blue', width=1, dash='dash')
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['donchian_low_55'],
            name='55-day Low',
            line=dict(color='blue', width=1, dash='dash')
        ),
        row=1, col=1
    )

    # 20-day Donchian Channel (orange)
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['donchian_high_20'],
            name='20-day High',
            line=dict(color='orange', width=1, dash='dot')
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['donchian_low_20'],
            name='20-day Low',
            line=dict(color='orange', width=1, dash='dot')
        ),
        row=1, col=1
    )

    # Volume bars
    colors = ['green' if df['close'].iloc[i] >= df['open'].iloc[i] else 'red'
              for i in range(len(df))]
    fig.add_trace(
        go.Bar(
            x=df['date'],
            y=df['volume'],
            name='Volume',
            marker_color=colors
        ),
        row=2, col=1
    )

    # Update layout
    fig.update_layout(
        height=600,
        showlegend=True,
        xaxis_rangeslider_visible=False
    )

    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig


def create_equity_curve(trade_type: str) -> go.Figure:
    """Create equity curve chart."""
    try:
        conn = sqlite3.connect(DB_TRADES)
        query = """
        SELECT date, account_value
        FROM account_history
        WHERE trade_type = ?
        ORDER BY date ASC
        """
        df = pd.read_sql_query(query, conn, params=(trade_type,))
        conn.close()

        if df.empty:
            return None

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['account_value'],
                mode='lines',
                name='Account Value',
                line=dict(color='blue', width=2)
            )
        )

        fig.update_layout(
            title="Equity Curve",
            xaxis_title="Date",
            yaxis_title="Account Value ($)",
            height=400
        )

        return fig
    except Exception as e:
        st.warning(f"Could not load equity curve: {e}")
        return None


# ==================================================================
# MAIN DASHBOARD
# ==================================================================

def main():
    """Main dashboard function."""

    # Initialize portfolio database
    init_portfolio_db()

    # ==================================================================
    # SIDEBAR
    # ==================================================================

    with st.sidebar:
        st.title("🐢 TURTLE TRADING")
        st.markdown("---")

        # Trade Type Selector
        st.subheader("⚙️ Settings")
        trade_type = st.radio(
            "Trade Type",
            options=['PAPER', 'REAL'],
            index=0,  # Default to PAPER
            help="Switch between paper trading (practice) and real trading"
        )

        # Account Balance
        st.markdown("---")
        st.subheader("💰 Account")
        account_balance = get_account_balance(trade_type)
        st.metric("Balance", format_currency(account_balance))

        # Watchlist
        st.markdown("---")
        st.subheader("📈 Watchlist")

        current_prices = load_current_prices()

        if current_prices:
            st.write("**ETFs**")
            for symbol in WATCHLIST_ETFS:
                if symbol in current_prices:
                    price = current_prices[symbol]['close']
                    st.text(f"{symbol:6} ${price:8.2f}")

            st.write("**Stocks**")
            for symbol in WATCHLIST_STOCKS:
                if symbol in current_prices:
                    price = current_prices[symbol]['close']
                    st.text(f"{symbol:6} ${price:8.2f}")
        else:
            st.warning("Price data not available")

        # Last Updated
        st.markdown("---")
        st.caption(f"🔄 Last updated: {datetime.now().strftime('%H:%M:%S')}")

        # Refresh Button
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ==================================================================
    # MAIN AREA - TABS
    # ==================================================================

    st.title(f"Turtle Trading Dashboard - {trade_type} Mode")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎯 Current Signals",
        "💼 Open Positions",
        "📈 Performance",
        "📊 Trade History",
        "📉 Price Charts"
    ])

    # ==================================================================
    # TAB 1: CURRENT SIGNALS
    # ==================================================================

    with tab1:
        st.header("Current Signals")

        # Load signals
        signals = load_signals(trade_type)

        # Separate entry and exit signals
        entry_signals = [s for s in signals if s['signal'] in ['BUY', 'SELL']]
        exit_signals = [s for s in signals if s['signal'] in ['EXIT_LONG', 'EXIT_SHORT']]

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Entry Signals", len(entry_signals))
        with col2:
            st.metric("Exit Signals", len(exit_signals))
        with col3:
            st.metric("Last Scan", datetime.now().strftime('%H:%M:%S'))

        st.markdown("---")

        # Entry Signals Table
        st.subheader(f"Entry Signals ({len(entry_signals)})")

        if entry_signals:
            # Calculate position sizing for each signal
            entry_data = []
            for sig in entry_signals:
                try:
                    # Get position size
                    position = get_position_size(
                        sig['symbol'],
                        sig['current_price'],
                        account_balance
                    )

                    entry_data.append({
                        'Signal': '=� BUY' if sig['signal'] == 'BUY' else '=4 SELL',
                        'Symbol': sig['symbol'],
                        'Price': format_currency(sig['current_price']),
                        'Breakout At': format_currency(sig['entry_high'] if sig['signal'] == 'BUY' else sig['entry_low']),
                        'Shares': position['shares'],
                        'Cost': format_currency(position['position_value']),
                        'Stop Loss': format_currency(position['stop_price']),
                        'Risk': format_currency(position['actual_risk']),
                        'Risk %': format_percent(position['risk_percent'])
                    })
                except Exception as e:
                    st.warning(f"Could not calculate position size for {sig['symbol']}: {e}")

            if entry_data:
                df_entry = pd.DataFrame(entry_data)
                st.dataframe(df_entry, use_container_width=True, hide_index=True)
        else:
            st.info("No entry signals detected")

        st.markdown("---")

        # Exit Signals Table
        st.subheader(f"Exit Signals ({len(exit_signals)})")

        if exit_signals:
            exit_data = []
            for sig in exit_signals:
                exit_data.append({
                    'Signal': '=� ' + sig['signal'],
                    'Symbol': sig['symbol'],
                    'Price': format_currency(sig['current_price']),
                    'Exit Level': format_currency(sig['exit_low'] if sig['signal'] == 'EXIT_LONG' else sig['exit_high']),
                    'Reason': sig['reason']
                })

            df_exit = pd.DataFrame(exit_data)
            st.dataframe(df_exit, use_container_width=True, hide_index=True)
        else:
            st.info("No exit signals detected")

    # ==================================================================
    # TAB 2: OPEN POSITIONS
    # ==================================================================

    with tab2:
        st.header("Open Positions")

        # Load portfolio
        portfolio = load_portfolio(trade_type)

        # Portfolio Summary Cards
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Positions", portfolio['num_positions'])

        with col2:
            st.metric("Total Invested", format_currency(portfolio['total_invested']))

        with col3:
            unrealized_pnl = portfolio['unrealized_pnl']
            delta_color = "normal" if unrealized_pnl >= 0 else "inverse"
            st.metric(
                "Unrealized P&L",
                format_currency(unrealized_pnl),
                delta=format_currency(unrealized_pnl)
            )

        with col4:
            available_cash = portfolio['account_balance'] - portfolio['total_invested']
            st.metric("Available Cash", format_currency(available_cash))

        st.markdown("---")

        # Positions Table
        if portfolio['positions']:
            positions_data = []
            for pos in portfolio['positions']:
                # Calculate P&L percentage
                if pos['current_price'] and pos['entry_price']:
                    if pos['direction'] == 'LONG':
                        pnl_pct = (pos['current_price'] - pos['entry_price']) / pos['entry_price']
                    else:
                        pnl_pct = (pos['entry_price'] - pos['current_price']) / pos['entry_price']
                else:
                    pnl_pct = 0

                positions_data.append({
                    'ID': pos['id'],
                    'Symbol': pos['symbol'],
                    'Direction': pos['direction'],
                    'Days': pos['days_held'],
                    'Shares': pos['shares'],
                    'Entry': format_currency(pos['entry_price']),
                    'Current': format_currency(pos['current_price']) if pos['current_price'] else 'N/A',
                    'Value': format_currency(pos['current_value']) if pos['current_value'] else 'N/A',
                    'P&L': f"{color_pnl(pos['unrealized_pnl'] or 0)} {format_currency(pos['unrealized_pnl'])}" if pos['unrealized_pnl'] is not None else 'N/A',
                    'P&L %': format_percent(pnl_pct),
                    'Stop': format_currency(pos['stop_price']),
                    'Exit Level': format_currency(pos['exit_level'])
                })

            df_positions = pd.DataFrame(positions_data)
            st.dataframe(df_positions, use_container_width=True, hide_index=True)
        else:
            st.info("No open positions")

    # ==================================================================
    # TAB 3: PERFORMANCE METRICS
    # ==================================================================

    with tab3:
        st.header("Performance Metrics")

        # Load trading stats
        stats = load_trading_stats(trade_type)

        # Key Metrics Cards
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Trades", stats['total_trades'])

        with col2:
            st.metric("Win Rate", format_percent(stats['win_percent']))

        with col3:
            st.metric("Trading Edge", format_currency(stats['edge']))

        with col4:
            pnl_color = "normal" if stats['total_pnl'] >= 0 else "inverse"
            st.metric("Total P&L", format_currency(stats['total_pnl']))

        st.markdown("---")

        if stats['total_trades'] > 0:
            # Charts row
            col1, col2 = st.columns(2)

            with col1:
                # Win/Loss Pie Chart
                fig_pie = go.Figure(data=[go.Pie(
                    labels=['Wins', 'Losses'],
                    values=[stats['winning_trades'], stats['losing_trades']],
                    marker_colors=['green', 'red']
                )])
                fig_pie.update_layout(title="Win/Loss Distribution", height=400)
                st.plotly_chart(fig_pie, use_container_width=True)

            with col2:
                # Statistics Table
                st.subheader("Statistics")
                stats_data = {
                    'Metric': [
                        'Winning Trades',
                        'Losing Trades',
                        'Average Win',
                        'Average Loss',
                        'Largest Win',
                        'Largest Loss',
                        'Win/Loss Ratio'
                    ],
                    'Value': [
                        stats['winning_trades'],
                        stats['losing_trades'],
                        format_currency(stats['avg_win']),
                        format_currency(stats['avg_loss']),
                        format_currency(stats['largest_win']),
                        format_currency(stats['largest_loss']),
                        f"{stats['avg_win'] / stats['avg_loss']:.2f}" if stats['avg_loss'] > 0 else 'N/A'
                    ]
                }
                st.dataframe(pd.DataFrame(stats_data), hide_index=True)

            # Equity Curve
            st.markdown("---")
            equity_fig = create_equity_curve(trade_type)
            if equity_fig:
                st.plotly_chart(equity_fig, use_container_width=True)
        else:
            st.info("No closed trades yet. Performance metrics will appear after your first trade.")

    # ==================================================================
    # TAB 4: TRADE HISTORY
    # ==================================================================

    with tab4:
        st.header("Trade History")

        # Load closed trades
        trades_df = load_closed_trades(trade_type)

        if not trades_df.empty:
            # Filters
            col1, col2, col3 = st.columns(3)

            with col1:
                symbol_filter = st.selectbox(
                    "Symbol",
                    options=['All'] + sorted(trades_df['symbol'].unique().tolist())
                )

            with col2:
                direction_filter = st.selectbox(
                    "Direction",
                    options=['All', 'LONG', 'SHORT']
                )

            with col3:
                pnl_filter = st.selectbox(
                    "Result",
                    options=['All', 'Wins', 'Losses']
                )

            # Apply filters
            filtered_df = trades_df.copy()

            if symbol_filter != 'All':
                filtered_df = filtered_df[filtered_df['symbol'] == symbol_filter]

            if direction_filter != 'All':
                filtered_df = filtered_df[filtered_df['direction'] == direction_filter]

            if pnl_filter == 'Wins':
                filtered_df = filtered_df[filtered_df['pnl'] > 0]
            elif pnl_filter == 'Losses':
                filtered_df = filtered_df[filtered_df['pnl'] < 0]

            st.markdown("---")

            # Calculate summary stats for filtered data
            if not filtered_df.empty:
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Trades Shown", len(filtered_df))

                with col2:
                    wins = len(filtered_df[filtered_df['pnl'] > 0])
                    win_rate = wins / len(filtered_df) if len(filtered_df) > 0 else 0
                    st.metric("Win Rate", format_percent(win_rate))

                with col3:
                    total_pnl = filtered_df['pnl'].sum()
                    st.metric("Total P&L", format_currency(total_pnl))

                st.markdown("---")

                # Format the dataframe for display
                display_df = filtered_df.copy()
                display_df['entry_date'] = pd.to_datetime(display_df['entry_date']).dt.strftime('%Y-%m-%d')
                display_df['exit_date'] = pd.to_datetime(display_df['exit_date']).dt.strftime('%Y-%m-%d')

                # Calculate days held
                display_df['days_held'] = (
                    pd.to_datetime(filtered_df['exit_date']) -
                    pd.to_datetime(filtered_df['entry_date'])
                ).dt.days

                # Calculate P&L %
                display_df['pnl_pct'] = display_df.apply(
                    lambda row: (row['exit_price'] - row['entry_price']) / row['entry_price']
                    if row['direction'] == 'LONG'
                    else (row['entry_price'] - row['exit_price']) / row['entry_price'],
                    axis=1
                )

                # Format columns
                display_df['P&L'] = display_df['pnl'].apply(lambda x: f"{color_pnl(x)} {format_currency(x)}")
                display_df['P&L %'] = display_df['pnl_pct'].apply(format_percent)
                display_df['Entry Price'] = display_df['entry_price'].apply(format_currency)
                display_df['Exit Price'] = display_df['exit_price'].apply(format_currency)

                # Select columns to display
                display_cols = [
                    'id', 'symbol', 'direction', 'entry_date', 'exit_date',
                    'days_held', 'shares', 'Entry Price', 'Exit Price',
                    'P&L', 'P&L %'
                ]

                st.dataframe(
                    display_df[display_cols].rename(columns={
                        'id': 'ID',
                        'symbol': 'Symbol',
                        'direction': 'Direction',
                        'entry_date': 'Entry Date',
                        'exit_date': 'Exit Date',
                        'days_held': 'Days',
                        'shares': 'Shares'
                    }),
                    use_container_width=True,
                    hide_index=True
                )

                # Export button
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"trade_history_{trade_type}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No trades match the selected filters")
        else:
            st.info("No closed trades yet")

    # ==================================================================
    # TAB 5: PRICE CHARTS
    # ==================================================================

    with tab5:
        st.header("Price Charts")

        # Symbol selector
        current_prices = load_current_prices()

        if current_prices:
            # Create symbol options with current price
            symbol_options = []
            for symbol in ALL_SYMBOLS:
                if symbol in current_prices:
                    price = current_prices[symbol]['close']
                    symbol_options.append(f"{symbol} (${price:.2f})")
                else:
                    symbol_options.append(symbol)

            selected_symbol_display = st.selectbox(
                "Select Symbol",
                options=symbol_options,
                index=0
            )

            # Extract symbol from display string
            selected_symbol = selected_symbol_display.split(' ')[0]

            # Time range selector
            time_range = st.select_slider(
                "Time Range",
                options=['1M', '3M', '6M', '1Y', 'ALL'],
                value='6M'
            )

            # Map time range to days
            days_map = {'1M': 30, '3M': 90, '6M': 180, '1Y': 365, 'ALL': 1000}
            days = days_map[time_range]

            # Load and display chart
            df = load_price_history(selected_symbol, days)

            if not df.empty:
                fig = create_candlestick_chart(selected_symbol, df)
                st.plotly_chart(fig, use_container_width=True)

                # Current levels
                st.markdown("---")
                st.subheader("Current Levels")

                levels = get_current_levels(selected_symbol)
                if levels:
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Current Price", format_currency(levels['current_price']))

                    with col2:
                        st.metric("55-Day High", format_currency(levels['entry_high']))

                    with col3:
                        st.metric("20-Day Low", format_currency(levels['exit_low']))

                    with col4:
                        atr = get_atr_for_symbol(selected_symbol)
                        if atr:
                            st.metric("ATR (20-day)", format_currency(atr))
            else:
                st.error(f"No price data available for {selected_symbol}")
        else:
            st.error("No price data available. Please run the data fetcher first.")


# ==================================================================
# RUN THE DASHBOARD
# ==================================================================

if __name__ == "__main__":
    main()
