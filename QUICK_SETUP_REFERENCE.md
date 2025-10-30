# Quick Setup Reference - Turtle Trading System

## TL;DR - What You Need to Do

1. **Set your ACTUAL capital** in `config.py`:
   ```python
   INITIAL_CAPITAL = 2500.00  # NOT $13,489, NOT $500 - your REAL Turtle capital
   ```

2. **Scale max positions** to your account size:
   ```python
   MAX_POSITIONS = 3  # Use 2-3 for $2,500-5,000
   ```

3. **Choose appropriate watchlist**:
   ```python
   ALL_SYMBOLS = WATCHLIST_SMALL  # 12 symbols for $2,500-7,500
   ```

4. **Keep fractional shares OFF** for now:
   ```python
   ALLOW_FRACTIONAL_SHARES = False  # Keep simple while learning
   ```

## Your Two Critical Questions Answered

### Question 1: Account Size Conflict

**THE PROBLEM:**
- Your system thinks you have $13,489.57
- You actually only have $500 available
- System says "buy $5,470 of GOOGL"
- You can't execute = system is broken

**THE SOLUTION:**
Set `INITIAL_CAPITAL` to your ACTUAL available Turtle Trading capital.

**Options:**
- **RECOMMENDED:** Start with $2,500 ($2k upfront + $500) = Real trading from Day 1
- **NOT RECOMMENDED:** Start with $500 = Can't execute system properly for 2-3 months
- **BROKEN:** Keep $13,489.57 when you have $500 = Complete disconnect from reality

**What to do:**
```python
# In config.py, line 33:
INITIAL_CAPITAL = 2500.00  # Set to your ACTUAL Turtle capital (not $13,489!)
```

Update this value when you add $500 deposits:
```python
# Nov 1: Started with $2,500
# Nov 15: Added $500 → INITIAL_CAPITAL = 3000.00
# Dec 1: Added $500 → INITIAL_CAPITAL = 3500.00
```

### Question 2: Fractional Shares

**THE QUESTION:**
Should you use fractional shares (0.72 shares of GOOGL) to trade with small capital?

**THE ANSWER:**
Not yet. Wait 3-6 months.

**Why?**
1. **They don't solve the real problem** - $500 is too small even with fractionals
2. **Adds complexity** - Master basics with whole shares first
3. **Capital growth helps more** - Your $1k/month additions matter more than fractionals
4. **Keep it simple** - Focus on discipline, not technical optimization

**When to reconsider:**
- After 3-6 months of trading
- When you have $3,500-5,000+ capital
- If you're consistently missing good signals due to share prices
- After you've proven you can follow rules with whole shares

**For now:**
```python
# In config.py, line 54:
ALLOW_FRACTIONAL_SHARES = False  # Keep this False for first 3-6 months
```

## Minimum Capital Requirements

| Your Capital | What You Can Do | Recommended Action |
|--------------|-----------------|-------------------|
| **$500** | 0-1 micro positions, no diversification | **DON'T START YET** - Save to $2,500 first |
| **$2,500** | 1-2 positions, tight but workable | **Minimum viable** - Start here if possible |
| **$5,000** | 2-3 positions, comfortable | **Good starting point** - Recommended |
| **$10,000+** | 3-6 positions, full diversification | **Ideal** - Full system execution |

## Example: GOOGL Signal with Different Account Sizes

**Signal:** BUY GOOGL @ $287.87, ATR = $6.96

### With $500 Account:
- Risk: $10 (2%)
- Shares: 0.72 → 0 whole shares
- **Result: CANNOT TAKE POSITION**

### With $2,500 Account:
- Risk: $50 (2%)
- Shares: 3.59 → 3 whole shares
- Cost: $863.61 (34.5% of account)
- **Result: Can take position, tight capital**

### With $5,000 Account:
- Risk: $100 (2%)
- Shares: 7.18 → 7 whole shares
- Cost: $2,015 (40% of account)
- **Result: Comfortable position size**

### With $10,000 Account:
- Risk: $200 (2%)
- Shares: 14.37 → 14 whole shares
- Cost: $4,030 (40% of account)
- **Result: Ideal, can take multiple positions**

## Configuration Checklist

Open `/home/bwight/git/turtle-trader/config.py` and verify:

- [ ] Line 33: `INITIAL_CAPITAL` = your ACTUAL Turtle capital (not $13,489!)
- [ ] Line 48: `MAX_POSITIONS` = 2-3 for small accounts
- [ ] Line 54: `ALLOW_FRACTIONAL_SHARES` = False
- [ ] Line 110: `ALL_SYMBOLS = WATCHLIST_SMALL` (12 symbols)
- [ ] Watchlist excludes expensive stocks (NVDA, TSLA if under $5k)

## Your Growth Plan

**Month 1: $2,500**
- Can take: 1-2 positions
- Focus: Learning entries, exits, basic discipline
- Expect: Tight capital, limited diversification

**Month 3: $4,500**
- Can take: 2-3 positions
- Focus: Managing multiple positions, portfolio risk
- Expect: System functioning properly

**Month 6: $7,500**
- Can take: 3-4 positions
- Focus: Full system execution, consider pyramiding
- Expect: Comfortable diversification

**Month 12: $13,500**
- Can take: 4-6 positions
- Focus: Advanced techniques, full watchlist
- Expect: Professional execution

## What Changes Were Made

Two files were updated to support your configuration:

### 1. config.py
- Added detailed `INITIAL_CAPITAL` documentation
- Created three watchlist tiers (FULL=20, SMALL=12, MICRO=8)
- Added `ALLOW_FRACTIONAL_SHARES` setting
- Added capital-scaled `MAX_POSITIONS` guidance

### 2. src/position_sizing.py
- Added fractional share support (when enabled in config)
- Defaults to whole shares (current behavior)
- Backward compatible with existing code

**Both changes are optional** - system works with default settings.

## The Core Rule

**Your system configuration must match your reality EXACTLY.**

- Have $2,500? Set `INITIAL_CAPITAL = 2500.00`
- Have $500? Don't start yet (or accept severe limitations)
- Have $13,489 but only $500 available? Set to $500 (but really, wait until $2,500)

**Never pretend you have more capital than you do.**

That creates a simulation that can't be executed in reality. That's not Turtle Trading. That's fantasy.

## Next Steps

1. **Decide your starting capital**
   - Recommendation: $2,500 ($2k upfront + $500)
   - Minimum: $2,500 for viable trading
   - Not recommended: $500 (wait until you have more)

2. **Update config.py**
   - Set `INITIAL_CAPITAL` to your actual amount
   - Choose `WATCHLIST_SMALL` for $2,500-7,500
   - Set `MAX_POSITIONS = 3` for small accounts
   - Keep `ALLOW_FRACTIONAL_SHARES = False`

3. **Separate your capital**
   - Ideal: Dedicated Turtle Trading account
   - Acceptable: Strict mental accounting in one account
   - Never: Mixed capital with unclear boundaries

4. **Start trading**
   - With configuration matching reality
   - Following rules from Day 1
   - Building discipline systematically
   - Growing capital steadily with $1k/month

## Questions?

Read the full guide: `/home/bwight/git/turtle-trader/ACCOUNT_SETUP_GUIDE.md`

**Bottom line:** Start with $2,500 if possible. Configure system to match your actual capital. Keep fractional shares off. Grow steadily with $1k/month additions. You'll have $7,500+ by Month 6 and be running the system properly.
