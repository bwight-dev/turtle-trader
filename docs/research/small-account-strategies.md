# Small Account Trading Strategies Research

## Goal
Build a systematic trading approach that:
- **Starting capital:** $10,000
- **Objective:** Beat the market (S&P 500 ~10% annually)
- **End goal:** Scale to income replacement

---

## The Math: What Does Income Replacement Require?

### Target Income: $60,000/year (example)

| Account Size | Required Annual Return | Realistic? |
|--------------|----------------------|------------|
| $10,000 | 600% | ❌ No |
| $50,000 | 120% | ❌ No |
| $100,000 | 60% | ⚠️ Exceptional years only |
| $200,000 | 30% | ⚠️ Very good years |
| $500,000 | 12% | ✅ Achievable |
| $1,000,000 | 6% | ✅ Conservative |

### The Path: Compound First, Withdraw Later

**Phase 1: Growth (Years 1-5)**
- Don't withdraw anything
- Target 20-30% annual returns
- Reinvest all profits
- $10k → $25k → $60k → $150k (at 25%/year for 5 years = ~$30k)
- More realistically with compounding: $10k × 1.25^5 = $30.5k

**Phase 2: Acceleration (Years 5-10)**
- Account large enough for better strategies
- Add income/savings to account
- Target: $100k-$250k account

**Phase 3: Income (Year 10+)**
- Account at $500k+
- Withdraw 10-12% annually ($50-60k)
- System generates enough to cover withdrawals + growth

**Reality Check:** Income replacement from a $10k start takes 7-10 years of disciplined compounding, OR you need to add significant outside capital.

---

## Strategy Candidates for $10k Accounts

### 1. RSI(2) Mean Reversion on SPY/QQQ

**Concept:** Buy extreme oversold, sell extreme overbought

**Rules (Basic Version):**
- Universe: SPY or QQQ only
- Buy: RSI(2) < 10
- Sell: RSI(2) > 70 OR after 5 days
- Position size: 100% (single position)

**Historical Performance (SPY, 2000-2020):**
- Win rate: ~65-70%
- Avg winner: 1.5-2%
- Avg loser: 2-3%
- CAGR: ~15-20% (varies by period)
- Max drawdown: 20-30%

**Pros:**
- Simple to execute
- High win rate (psychologically easier)
- Works in most market conditions
- Only need to check once per day

**Cons:**
- Can have long periods with no signals
- Big drawdowns during crashes (no short side)
- Single instrument = concentrated risk

**Research Questions:**
- [ ] Add short side when RSI(2) > 95?
- [ ] Use leveraged ETFs (TQQQ/SQQQ) for more juice?
- [ ] Filter by trend (only buy when above 200 SMA)?
- [ ] Test on sector ETFs for more signals

---

### 2. Sector Momentum Rotation

**Concept:** Ride the hot sectors, avoid the cold ones

**Rules (Basic Version):**
- Universe: 11 sector ETFs (XLK, XLF, XLE, XLV, etc.) + TLT (bonds)
- Rank by 3-month momentum
- Hold top 3 sectors
- Rebalance monthly
- If S&P below 200 SMA, go 100% TLT (bonds)

**Historical Performance:**
- CAGR: 12-18%
- Max drawdown: 15-25% (with trend filter)
- Sharpe: 0.8-1.2

**Pros:**
- Very low time commitment (1 hour/month)
- Diversified across sectors
- Trend filter reduces crash damage
- Easy to automate

**Cons:**
- Monthly rebalancing = slower response
- Sector correlations can spike in crashes
- Returns are "good" not "great"

**Research Questions:**
- [ ] Weekly rebalancing vs monthly?
- [ ] Top 2 vs top 3 vs top 4 sectors?
- [ ] Add international ETFs for more diversification?
- [ ] Dual momentum (absolute + relative)?

---

### 3. The Wheel Strategy (Options)

**Concept:** Systematically sell options premium

**Rules:**
1. Sell cash-secured puts on stocks you want to own
2. If assigned, sell covered calls
3. If called away, start over with puts
4. Collect premium throughout

**Requirements:**
- Need $2,500+ per position (100 shares × $25 stock)
- $10k = 2-4 positions max
- Best on high-IV stocks with good fundamentals

**Expected Returns:**
- Target: 1-2% per month (12-24% annually)
- Win rate: 70-80% (options expire worthless)
- Risk: Stock drops significantly while you hold

**Good Wheel Candidates ($25-50 range for $10k account):**
- AMD, PLTR, SOFI, NIO, F, BAC
- High IV = more premium
- Stocks you'd actually want to own

**Pros:**
- High probability trades
- Income every month
- Defined risk on each trade
- Time decay works for you

**Cons:**
- Capital intensive (need 100 shares)
- Can get stuck holding losers
- Capped upside (miss big rallies)
- Requires options approval

**Research Questions:**
- [ ] Which stocks have best risk/reward for wheel?
- [ ] Optimal delta for puts (0.30? 0.20?)
- [ ] Roll vs take assignment analysis
- [ ] Combine with earnings plays?

---

### 4. Trend + Mean Reversion Hybrid

**Concept:** Use trend for direction, mean reversion for entry

**Rules:**
- **Trend filter:** Only trade direction of 50-day SMA
- **Entry:** RSI(2) pullback in trend direction
- **Exit:** First profitable close OR 5-day timeout

**Example Long Setup:**
1. SPY above 50 SMA (uptrend confirmed)
2. RSI(2) drops below 20 (pullback)
3. Buy next day
4. Sell on first up close or after 5 days

**Example Short Setup:**
1. SPY below 50 SMA (downtrend confirmed)
2. RSI(2) rises above 80 (bounce)
3. Short next day (or buy SH/inverse ETF)
4. Cover on first down close or after 5 days

**Expected Performance:**
- Fewer signals than pure mean reversion
- Higher quality signals (with trend)
- Works in both directions
- Estimated CAGR: 15-25%

**Pros:**
- Best of both worlds
- Avoids fighting the trend
- Can profit in bear markets (short side)
- Clear, mechanical rules

**Cons:**
- More complex than single strategy
- Choppy sideways markets = whipsaws
- Need to be comfortable shorting

**Research Questions:**
- [ ] Best trend filter (20 SMA? 50? 200?)
- [ ] Optimal RSI threshold for entries
- [ ] Leverage on high-conviction setups?
- [ ] Apply to multiple ETFs for more signals?

---

### 5. Pairs Trading / Market Neutral

**Concept:** Long one asset, short another correlated one

**Rules:**
- Find highly correlated pairs (XLF/JPM, GLD/GDX, SPY/QQQ)
- Calculate spread (ratio or difference)
- When spread deviates 2+ standard deviations, bet on mean reversion
- Long the underperformer, short the outperformer

**Expected Performance:**
- Market neutral (works in any direction)
- Win rate: 60-70%
- Annual returns: 10-20%
- Very low correlation to S&P

**Pros:**
- Works in any market environment
- Low drawdowns (hedged)
- Statistical edge is measurable
- Can scale with more pairs

**Cons:**
- Requires shorting (margin account)
- More complex to manage
- Pairs can "break" (correlation fails)
- Lower returns than directional

**Research Questions:**
- [ ] Best pairs for small accounts?
- [ ] Cointegration vs correlation testing
- [ ] Optimal lookback for spread calculation
- [ ] How many pairs to diversify?

---

## Priority Ranking for $10k Account

Based on simplicity, capital efficiency, and realistic returns:

| Rank | Strategy | Why |
|------|----------|-----|
| 1 | RSI(2) Mean Reversion | Simplest, high win rate, proven |
| 2 | Trend + MR Hybrid | Adds short side, better risk-adjusted |
| 3 | Sector Rotation | Low maintenance, good diversification |
| 4 | Wheel Strategy | Good but capital intensive at $10k |
| 5 | Pairs Trading | Most complex, better at $50k+ |

---

## Next Steps

### Immediate (This Week)
- [ ] Backtest RSI(2) on SPY 2010-2024
- [ ] Backtest RSI(2) with trend filter
- [ ] Compare to buy-and-hold S&P 500

### Short Term (This Month)
- [ ] Build simple backtester for mean reversion strategies
- [ ] Test sector rotation with different parameters
- [ ] Research best Wheel candidates

### Medium Term (Next Quarter)
- [ ] Paper trade top 2 strategies
- [ ] Build alerting system for signals
- [ ] Develop position sizing rules for compounding

---

## Performance Tracking Template

Once we start testing:

| Strategy | Period | CAGR | Max DD | Sharpe | Win Rate | Notes |
|----------|--------|------|--------|--------|----------|-------|
| RSI(2) SPY | 2010-2024 | TBD | TBD | TBD | TBD | |
| Sector Rotation | 2010-2024 | TBD | TBD | TBD | TBD | |

---

## Resources & References

- **Mean Reversion:** Larry Connors "Short Term Trading Strategies That Work"
- **Sector Rotation:** Meb Faber "Global Tactical Asset Allocation"
- **Options/Wheel:** Tastytrade research, r/thetagang
- **Pairs Trading:** Ernie Chan "Algorithmic Trading"

---

*Document started: January 2026*
*Last updated: January 2026*
