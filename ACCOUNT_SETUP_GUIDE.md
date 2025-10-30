# Turtle Trading Account Setup Guide

## Critical Configuration Issues - READ THIS FIRST

This guide addresses two critical questions about running the Turtle Trading system with limited capital:

1. **Account Structure**: How to properly configure the system when you have limited capital
2. **Fractional Shares**: Whether to use fractional shares and how to implement them

---

## Problem 1: Account Size Mismatch

### The Issue

If your main account has $14,000 but most is tied up in other (non-Turtle) positions, and only $500 is available for Turtle Trading, you have a **critical configuration problem**:

- System calculates positions based on full account value ($13,489.57)
- But only $500 is actually available for trading
- Result: System says "buy 19 shares of GOOGL ($5,470)" but you only have $500
- **This makes the system unusable**

### The Solution: Match Configuration to Reality

**RULE: Your `INITIAL_CAPITAL` setting must match your ACTUAL available Turtle Trading capital.**

#### Option A: Dedicated Turtle Account (RECOMMENDED)

1. Open a second brokerage account specifically for Turtle Trading
2. Transfer your dedicated Turtle capital there (start with $2,500-3,000 if possible)
3. Add $500 twice monthly to THIS account only
4. Never mix with other positions
5. Set `INITIAL_CAPITAL` to the exact starting balance

**Benefits:**
- Perfect separation
- Clean performance tracking
- No confusion about available capital
- Psychological clarity

#### Option B: Same Account, Separate Mental Accounting

1. Designate exactly how much is "Turtle Capital" (e.g., $3,000)
2. Track it separately in a spreadsheet
3. NEVER let Turtle positions touch non-Turtle money
4. Set `INITIAL_CAPITAL` to your designated Turtle capital
5. Update it manually when you add $500 deposits

**Benefits:**
- No need for second account
- Can work with existing setup

**Drawbacks:**
- Requires strong discipline (easy to violate)
- More complex tracking

#### Option C: What You're Doing Now (BROKEN - STOP THIS)

Running a simulation with $13,489.57 while having only $500 available.

**This does NOT work. Stop immediately.**

---

## Problem 2: Minimum Viable Capital

### How Much Do You Actually Need?

**The Math:**

With **$500 capital**:
- 2% risk per trade = $10
- Example: GOOGL at $287.87, ATR $6.96
  - Stop distance: 2 × $6.96 = $13.92
  - Shares: $10 ÷ $13.92 = 0.72 shares
  - Cost: 0.72 × $287.87 = $207 (41% of capital)
- **Result: Can take 0-1 micro positions, no diversification possible**

With **$2,500 capital**:
- 2% risk per trade = $50
- Same GOOGL example:
  - Shares: $50 ÷ $13.92 = 3.59 → 3 shares
  - Cost: 3 × $287.87 = $864 (35% of capital)
- **Result: Can take 1-2 positions, tight but workable**

With **$5,000 capital**:
- 2% risk per trade = $100
- Same GOOGL example:
  - Shares: $100 ÷ $13.92 = 7.18 → 7 shares
  - Cost: 7 × $287.87 = $2,015 (40% of capital)
- **Result: Can take 2-3 positions comfortably**

With **$10,000 capital**:
- 2% risk per trade = $200
- Same GOOGL example:
  - Shares: $200 ÷ $13.92 = 14.37 → 14 shares
  - Cost: 14 × $287.87 = $4,030 (40% of capital)
- **Result: Can take 3-5 positions, proper diversification**

### Recommended Minimum Capital by Watchlist Size

| Account Size | Watchlist Size | Max Positions | Notes |
|--------------|----------------|---------------|-------|
| $500 | 8 symbols | 1 | **NOT RECOMMENDED** - Too constrained |
| $2,500 | 10-12 symbols | 2-3 | **Minimum viable** - Learning phase |
| $5,000 | 12-16 symbols | 3-4 | **Comfortable** - Good diversification |
| $10,000+ | 16-20 symbols | 4-6 | **Ideal** - Full system execution |

### Your Plan: $500 Start + $1k/Month

**If Starting with $500 (NOT RECOMMENDED):**
- Month 1: $500 → Can take 0-1 micro positions (not really trading)
- Month 2: $1,500 → Can take 1 small position (still constrained)
- Month 3: $2,500 → Starting to function properly
- **Problem: First 2-3 months are wasted learning time**

**If Starting with $2,500 (RECOMMENDED):**
- Deposit $2,000 upfront + your planned $500 = $2,500
- Month 1: $2,500 → Can take 1-2 positions (tight but real trading)
- Month 2: $3,500 → Can take 2 positions comfortably
- Month 3: $4,500 → Can take 2-3 positions
- Month 6: $7,500 → Running properly with good diversification
- **Result: Executing real Turtle Trading from Day 1**

**Recommendation: Front-load your capital to $2,500 if at all possible.**

Reasons:
1. Psychological reality - $500 feels like play money, $2,500 feels real
2. System integrity - You can execute signals properly from Day 1
3. Compound learning - You're learning the REAL system, not a toy version
4. Opportunity cost - Don't miss major trends in early months

---

## Problem 3: Fractional Shares

### Are They Compatible with Turtle Trading?

**Answer: Technically yes, philosophically questionable, practically problematic.**

**Turtle Trading Orthodoxy:**
- Original Turtles traded futures (whole contracts only)
- System designed around discrete position sizing
- Nothing explicitly forbids fractional shares
- But they weren't part of the original design

**Verdict: Not a violation of methodology, but adds complexity.**

### Would Fractional Shares Help with Small Accounts?

**Answer: Yes, marginally, but they don't solve the fundamental problem.**

**Example with $500 capital:**

**Whole Shares:**
- Risk: $10, Stop Distance: $13.92
- Shares: 0.72 → rounds to **0 shares**
- **Result: Cannot take position at all**

**Fractional Shares:**
- Risk: $10, Stop Distance: $13.92
- Shares: 0.72 shares
- Cost: $207.27 (41% of capital)
- **Result: Can take position, but 1 position eats 41% of capital**

**Fractional shares let you take positions, but you still can't diversify with $500.**

### Downsides of Fractional Shares

1. **Exit Execution**
   - Whole shares: "SELL 19 shares" (clean)
   - Fractional: "SELL 19.427 shares" (less standard)

2. **Tracking Complexity**
   - Decimal precision required (0.72 shares × $287.87 = ?)
   - Need careful accounting to avoid rounding errors

3. **Stop Loss Precision**
   - ATR stops must be calculated precisely
   - Risk of rounding errors accumulating

4. **Broker Support**
   - Not all symbols support fractional shares
   - Execution may differ (aggregated fills, etc.)

5. **Psychological Clarity**
   - "I own 19 shares" is simple
   - "I own 19.4287 shares" feels abstract

6. **System Complexity**
   - Code must handle decimals everywhere
   - More potential for bugs
   - Harder to verify calculations manually

### Recommendation: When to Use Fractional Shares

**Phase 1 (Months 1-3): DON'T USE THEM**
- Start with $2,500+ capital
- Use whole shares only
- Master basics: entries, exits, position sizing, discipline
- Accept that some signals can't be taken (too expensive)
- Focus on building rule-following habits

**Phase 2 (Months 4-6): EVALUATE**
- If consistently missing good signals due to share price
- AND you have $3,500-5,000 capital (fractionals help more here)
- AND you've proven you can follow rules with whole shares
- THEN consider implementing fractional support

**Phase 3 (Month 7+): OPTIONAL**
- By now you have $7,500+ capital
- Fractional shares matter less (you can afford most positions)
- But if implemented, they add flexibility

**Why Wait?**
1. Simplicity first - master system with clean math
2. Capital growth - your $1k/month additions reduce need for fractionals
3. Focus on discipline - fractionals are a technical detail, discipline is everything
4. Avoid premature optimization - you don't know what problems you'll face yet

---

## Configuration Steps

### Step 1: Decide Your Starting Capital

Choose ONE:

**Option A: $2,500 Start (RECOMMENDED)**
- Deposit $2,000 now + your planned $500 = $2,500
- Timeline: Functional from Month 1, comfortable by Month 4

**Option B: $5,000 Start (IDEAL)**
- Save for 5 months, start with $5,000
- Timeline: Comfortable from Day 1, but 5 months delay

**Option C: $500 Start (NOT RECOMMENDED)**
- Accept first 2-3 months are essentially paper trading
- Real trading starts Month 4+ when you have $3,500+

### Step 2: Update config.py

Open `/home/bwight/git/turtle-trader/config.py` and configure:

```python
# Set to your ACTUAL starting capital
INITIAL_CAPITAL = 2500.00  # Change this to match your reality

# Scale max positions to your capital
MAX_POSITIONS = 3  # Use 2-3 for $2,500-5,000 accounts

# Keep fractional shares off for now
ALLOW_FRACTIONAL_SHARES = False

# Choose appropriate watchlist
# For $2,500-5,000: Use WATCHLIST_SMALL (12 symbols)
ALL_SYMBOLS = WATCHLIST_SMALL
```

### Step 3: Update INITIAL_CAPITAL When Adding Deposits

**Example tracking in config.py:**
```python
# CAPITAL TRACKING (update this when you add deposits):
# Nov 1, 2025: $2,500 (initial)
# Nov 15, 2025: $3,000 (added $500)
# Dec 1, 2025: $3,500 (added $500)
# Dec 15, 2025: $4,000 (added $500)

INITIAL_CAPITAL = 4000.00  # Update this line when you add capital
```

**Important:** This is NOT "gaming" the system. The Turtles had capital additions too. The key is:
- Know your exact capital at all times
- All position sizing uses this exact number
- Update it when you add funds (real capital growth, allowed)
- Never "pretend" you have more than you do

### Step 4: Scale Your Watchlist

Your watchlist should match your account size:

**For $2,500-5,000 (WATCHLIST_SMALL):**
```python
WATCHLIST_SMALL = [
    # ETFs
    'SPY', 'QQQ', 'GLD', 'XLE',
    # Affordable stocks (<$400/share)
    'GOOGL', 'CAT', 'BA', 'AAPL', 'JPM', 'XOM', 'RTX', 'LMT'
]
```

**Why remove expensive stocks?**
- NVDA at $730: Single share = 29% of $2,500 account (violates diversification)
- TSLA at $300+: Too expensive for proper position sizing
- Focus on affordable, liquid names

**For $5,000-7,500:**
- Can use most symbols up to ~$600/share
- Add back MSFT, META, others

**For $10,000+:**
- Use full 20-symbol watchlist
- No restrictions

---

## Minimum Viable Turtle System

Given your situation, here's what will actually work:

### Starting Setup

**Capital:** $2,500 to start (not $500)

**Growth Timeline:**
- Month 1: $2,500
- Month 2: $3,500 (+$1,000)
- Month 3: $4,500 (+$1,000)
- Month 6: $7,500 (+$1,000/month)

**Configuration:**
- `INITIAL_CAPITAL`: $2,500 (update monthly with deposits)
- `RISK_PER_TRADE`: 2% ($50 per trade in Month 1)
- `MAX_POSITIONS`: 2-3 (tight but workable)
- Watchlist: 10-12 affordable symbols (<$400/share)
- Fractional shares: NO (whole shares only)

### Realistic Expectations

**Month 1-3 (Learning Phase):**
- Capital: $2,500-4,500
- Signals per month: 2-4
- Positions you can take: 1-2
- Diversification: Limited
- Focus: Building discipline, learning entries/exits

**Month 4-6 (Functional Phase):**
- Capital: $5,500-7,500
- Signals per month: 2-4
- Positions you can take: 2-3
- Diversification: Improving
- Focus: Refining execution, managing multiple positions

**Month 7-12 (Comfortable Phase):**
- Capital: $10,000+
- Signals per month: 3-6
- Positions you can take: 3-5
- Diversification: Good
- Focus: Full system execution, considering pyramiding

**This works.** It's constrained early on, but you're executing the REAL system from Day 1.

---

## What NOT to Do

❌ **Don't run system with $13,489 when you have $500**
- Creates disconnect between simulation and reality
- Can't execute the signals
- Builds false confidence

❌ **Don't try to trade 20 expensive symbols with $500**
- Mathematically impossible
- Violates diversification principles

❌ **Don't implement fractional shares until Month 4+**
- Adds complexity before mastering basics
- Capital growth will reduce need

❌ **Don't mix Turtle positions with other trading capital**
- Breaks risk management
- Impossible to track performance

❌ **Don't wait until $10k if you can start with $2,500**
- 5 months of lost learning time
- Front-loading capital accelerates learning

---

## Summary: Your Action Plan

1. **Decide starting capital** → Recommend $2,500 ($2k upfront + $500)
2. **Set `INITIAL_CAPITAL`** → Match your exact reality
3. **Choose watchlist** → Use `WATCHLIST_SMALL` for $2,500-7,500
4. **Set `MAX_POSITIONS`** → Use 2-3 for small accounts
5. **Keep fractional shares OFF** → Simplicity first
6. **Separate your capital** → Mentally or physically
7. **Start real trading** → With configuration matching reality

### The Core Principle

**Your system configuration must match your reality EXACTLY.**

If you have $2,500, set `INITIAL_CAPITAL = 2500.00`. Take the positions the system calculates for $2,500. Accept the constraints of $2,500. Grow from there.

**Never run a simulation that doesn't match your actual execution capacity.**

That's not Turtle Trading. That's fantasy. And it will teach you the wrong habits.

---

## System Changes Made

The following files have been updated to support proper account configuration:

### 1. config.py

**Changes:**
- Added detailed `INITIAL_CAPITAL` documentation with tracking template
- Added `ALLOW_FRACTIONAL_SHARES` and `FRACTIONAL_PRECISION` settings
- Created three watchlist tiers: FULL (20), SMALL (12), MICRO (8)
- Added capital-appropriate guidance for `MAX_POSITIONS`

**What to configure:**
```python
INITIAL_CAPITAL = 2500.00  # SET TO YOUR ACTUAL CAPITAL
MAX_POSITIONS = 3  # Scale to your capital level
ALLOW_FRACTIONAL_SHARES = False  # Keep off for now
ALL_SYMBOLS = WATCHLIST_SMALL  # Choose appropriate watchlist
```

### 2. src/position_sizing.py

**Changes:**
- Imported `ALLOW_FRACTIONAL_SHARES` and `FRACTIONAL_PRECISION` from config
- Modified share rounding logic:
  - If `ALLOW_FRACTIONAL_SHARES = True`: Rounds to 3 decimals (e.g., 1.427 shares)
  - If `ALLOW_FRACTIONAL_SHARES = False`: Rounds down to whole shares (default)
- Updated validation to handle fractional share minimums

**How it works:**
```python
# With ALLOW_FRACTIONAL_SHARES = False (default)
shares_raw = 19.427
shares = int(np.floor(shares_raw))  # Result: 19 shares

# With ALLOW_FRACTIONAL_SHARES = True
shares_raw = 19.427
shares = round(shares_raw, 3)  # Result: 19.427 shares
```

Both changes are **backward compatible** - existing code continues to work with default settings.

---

## File Locations

- **Configuration:** `/home/bwight/git/turtle-trader/config.py`
- **Position Sizing:** `/home/bwight/git/turtle-trader/src/position_sizing.py`
- **This Guide:** `/home/bwight/git/turtle-trader/ACCOUNT_SETUP_GUIDE.md`

---

## Questions?

This guide addresses the most critical setup issues. If you have questions:

1. Re-read the relevant section carefully
2. Check your `config.py` settings match your reality
3. Verify `INITIAL_CAPITAL` equals your actual available Turtle Trading cash
4. Start with $2,500+ if at all possible
5. Keep fractional shares OFF for first 3-6 months

**The system works. But only if configured correctly.**
