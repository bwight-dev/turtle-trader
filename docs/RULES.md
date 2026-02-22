# Turtle Trading Rules - Verified Business Logic

**Sources:** The Original Turtle Trading Rules (Faith), The Complete TurtleTrader (Covel), Way of the Turtle (Faith), Jerry Parker/RCM interview transcripts

**Status:** Verified - No hallucinated rules (no profit targets, no moving average crossovers)

---

## Part 1: Market Universe & Data Initialization

### Rule 1: The "Reality" Input (Price Only)

- **GIVEN** the agent is ingesting data
- **WHEN** receiving market information
- **THEN** accept only Price (Open, High, Low, Close) and Volume
- **AND** ignore all fundamental news, earnings, crop reports, or TV commentary
- **DOCTRINE:** "Price is Reality"

### Rule 2: The "300 Market" Universe (Modern Adaptation)

- **GIVEN** the goal is to capture "outlier" trends
- **WHEN** selecting the portfolio
- **THEN** include a massive, diversified list of 300+ markets (Stocks, Currencies, Energies, Metals, Interest Rates, Grains, Meats)
- **REASON:** Trends are rare. Trading a small basket increases the probability of a "lost decade" where you miss the few winning trades that pay for all the losses

---

## Part 2: Volatility & Position Sizing

### Rule 3: Calculate N (The Volatility Measure)

- **GIVEN** the daily price history
- **WHEN** the market closes
- **THEN** calculate the True Range (TR):
  ```
  TR = Max(H - L, |H - PDC|, |PDC - L|)
  ```
  Where PDC = Previous Day's Close
- **AND** calculate N (20-day EMA of TR):
  ```
  N = ((19 × Previous_N) + Current_TR) / 20
  ```

### Rule 4: Unit Size Calculation

- **GIVEN** the current Account Equity and current N
- **WHEN** determining trade size
- **THEN** calculate:
  ```
  Dollar_Volatility = N × Dollars_Per_Point
  Unit_Size = (Risk_Factor × Account_Equity) / Dollar_Volatility
  ```
- **CRITICAL DISTINCTION:**
  - **Original 1983 Rule:** Risk Factor = 1% (0.01)
  - **Modern Parker Rule:** Risk Factor = 0.5% or lower (to accommodate 300+ markets)

### Rule 5: The Drawdown Reduction (The "Risk of Ruin" Rule)

- **GIVEN** the account is in a drawdown
- **WHEN** the account equity drops by 10% from the starting level (or annual high)
- **THEN** reduce the "Notional Account Equity" used in Rule 4 by 20% for all future trades until equity recovers
- **REASON:** To prevent digging a hole so deep you cannot recover

---

## Part 3: Entry Logic

### Rule 6: System 1 Entry (Short-Term)

- **GIVEN** the current price
- **WHEN** Price > 20-Day High (Buy) **OR** Price < 20-Day Low (Short)
- **AND** the previous System 1 breakout signal was a Loss (price moved 2N against before profitable exit)
- **THEN** enter 1 Unit

### Rule 7: System 1 Filter

- **GIVEN** a System 1 breakout signal
- **WHEN** the previous System 1 breakout was a Winner
- **THEN** IGNORE the signal (do not trade)
- **REASON:** To avoid "whipsaws" in choppy markets

### Rule 8: System 2 Entry (Long-Term)

- **GIVEN** the current price
- **WHEN** Price > 55-Day High (Buy) **OR** Price < 55-Day Low (Short)
- **THEN** enter 1 Unit immediately
- **CONSTRAINT:** Ignore the "Filter" rule. Always take System 2 signals

### Rule 9: The "Failsafe" Entry

- **GIVEN** you are not in a position because you skipped a System 1 entry due to the Filter (Rule 7)
- **WHEN** the market continues to trend and hits the 55-Day Breakout (System 2)
- **THEN** you MUST enter at the System 2 point
- **REASON:** To ensure you never miss a major trend just because you filtered out the early entry

---

## Part 4: Trade Management (Stops & Pyramids)

### Rule 10: The 2N Hard Stop

- **GIVEN** a filled order
- **WHEN** placing the safety net
- **THEN** place a stop-loss order at 2N from the entry price
- **FORMULA:**
  - Longs: `Stop = Entry_Price - (2 × N)`
  - Shorts: `Stop = Entry_Price + (2 × N)`

### Rule 11: Pyramiding (Adding On)

- **GIVEN** an open position
- **WHEN** the price moves ½N in your favor (from the last fill price)
- **THEN** add 1 additional Unit
- **CONSTRAINT:** Repeat until reaching the specific market max (originally 4 Units, modern often 2 Units for single stocks)

### Rule 12: Aggressive Stop Adjustment

- **GIVEN** a new Unit has been added (Rule 11)
- **WHEN** updating risk
- **THEN** raise the stops for ALL existing units to `Newest_Entry_Price - 2N`
- **REASON:** To lock in profit on earlier units and keep total trade risk minimized

---

## Part 5: Exits (Taking Profits)

### Rule 13: System 1 Exit

- **GIVEN** a long (or short) position based on System 1
- **WHEN** Price touches the 10-Day Low (for Longs) or 10-Day High (for Shorts)
- **THEN** exit the position immediately
- **CRITICAL:** Do not wait for the close. Exit intraday

### Rule 14: System 2 Exit

- **GIVEN** a long (or short) position based on System 2
- **WHEN** Price touches the 20-Day Low (for Longs) or 20-Day High (for Shorts)
- **THEN** exit the position immediately

---

## Part 6: Execution & Tactics

### Rule 15: Rollover Logic (Futures Only)

- **GIVEN** an expiring futures contract
- **WHEN** the contract is "a few weeks" from expiration **OR** volume shifts to the new month
- **AND** the new contract's price would have resulted in an existing position (i.e., price > breakout level for longs, price < breakout level for shorts)
- **THEN** roll the position: Exit the old contract and enter the new contract simultaneously
- **CONSTRAINT:** Do NOT roll if the new contract hasn't hit the breakout point - near month may trend on immediate supply/demand while distant months do not
- **REASON:** Do not exit a trend just because a contract expires, but also don't enter a contract that doesn't confirm the trend

### Rule 16a: Opening Gap Logic

- **GIVEN** a market gaps open through your breakout price or stop price overnight
- **WHEN** the market opens
- **THEN** execute the order at market price immediately on the open
- **REASON:** "If you don't bet, you can't win." You must take the entry/exit even if the price is worse than your target

### Rule 16b: Intraday Fast Market Logic

- **GIVEN** the market enters a "fast market" condition intraday (liquidity dries up, bid/ask spreads widen dramatically)
- **WHEN** price moves rapidly past your entry or stop level
- **THEN** do NOT place a market order into the panic
- **AND** WAIT for the market to trade and stabilize (look for at least a temporary price reversal)
- **THEN** execute your order after stability returns
- **REASON:** Market orders in a fast market guarantee the worst possible fill. Sellers vanish and you buy at the high of the panic. Patience preserves capital

### Rule 17: Portfolio Heat Cap (Modern Rule)

- **GIVEN** the agent is trading 300+ markets
- **WHEN** the total correlations or total risk exposure gets too high
- **THEN** stop adding new positions if total daily volatility risk exceeds a fixed cap (e.g., 20% of equity)
- **NOTE:** The original rules used fixed unit limits (12 units total). Modern trend followers like Parker suggest managing total portfolio "heat" rather than strict unit counts, provided individual positions are small

---

## Quick Reference Table

| Rule | Description | Breakout Period | Exit Period | Stop |
|------|-------------|-----------------|-------------|------|
| S1 Entry | Short-term | 20-day | - | 2N |
| S1 Exit | - | - | 10-day | - |
| S2 Entry | Long-term (failsafe) | 55-day | - | 2N |
| S2 Exit | - | - | 20-day | - |

| Parameter | Original (1983) | Modern (Parker) | **Our Config** |
|-----------|-----------------|-----------------|----------------|
| Risk per trade | 1% | 0.5% | **0.5%** |
| Markets | ~20 | 300+ | **228** |
| Max units/market | 4 | 2-4 | **4** |
| Max correlated | 6 | varies | **6** |
| Max total | 12 units | 20% risk cap | **20% risk cap** (configurable) |
| Pyramid interval | ½N | ½N | **½N** |
| Drawdown trigger | 10% | 10% | **10%** |
| Equity reduction | 20% | 20% | **20%** |

---

## Implementation Decisions

Based on 2026-01-27 and 2026-01-28 planning sessions:

1. **Risk Factor:** 0.5% (Parker modern) - accommodates large universe
2. **Pyramid Interval:** ½N (original) - more aggressive pyramiding
3. **Portfolio Limits:** **CONFIGURABLE** - supports both modes:
   - **Modern Mode (default):** 20% total risk cap (Rule 17 - Portfolio Heat Cap)
     - With 0.5% risk per unit, allows ~40 positions
     - Per Jerry Parker: Each position must be "inconsequential"
   - **Original Mode:** 4/6/12 unit count limits
     - For historical validation with ~20 markets
4. **Position Sizing:** Always truncate to 0 if calculated size < 1 contract
   - Per Curtis Faith: Never round up, as this violates risk rules
   - Small accounts ($10K) will be unable to trade some markets - intentional
