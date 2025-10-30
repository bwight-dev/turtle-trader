#!/usr/bin/env python3
"""
Quick script to add paper trades for CAT and NVDA
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.portfolio import add_position

# CAT trade
cat_id = add_position(
    symbol='CAT',
    direction='LONG',
    entry_price=585.49,
    shares=8,
    stop_price=552.10,
    exit_level=469.79,  # 20-day low
    trade_type='PAPER',
    notes='55-day breakout @ $585.49 (above $543.43). Strong +7.7% breakout.'
)
print(f"✓ Added PAPER position #{cat_id}: CAT 8 shares @ $585.49")

# NVDA trade
nvda_id = add_position(
    symbol='NVDA',
    direction='LONG',
    entry_price=207.04,
    shares=21,
    stop_price=194.67,
    exit_level=176.76,  # 20-day low
    trade_type='PAPER',
    notes='55-day breakout @ $207.04 (above $203.15). Clean breakout signal.'
)
print(f"✓ Added PAPER position #{nvda_id}: NVDA 21 shares @ $207.04")

print()
print("Paper trades recorded! Run ./venv/bin/python3 scripts/view_portfolio.py to view.")
