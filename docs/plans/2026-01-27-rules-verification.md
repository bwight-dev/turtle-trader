# Rules Verification: Implementation Plan vs. Verified Business Logic

**Date:** 2026-01-27
**Purpose:** Cross-reference implementation plan against docs/RULES.md

---

## Verification Summary

| Rule | Description | Milestone | Status | Notes |
|------|-------------|-----------|--------|-------|
| 1 | Price Only Input | M2, M7 | ✅ COVERED | DataFeed only returns OHLCV |
| 2 | 300 Market Universe | M11 | ⚠️ PARTIAL | Config exists but needs universe file |
| 3 | Calculate N (TR + EMA) | M4 | ✅ COVERED | TOS validation included |
| 4 | Unit Size Calculation | M14 | ✅ FIXED | Now uses 0.5% (Parker rule) |
| 5 | Drawdown Reduction | M14 | ✅ FIXED | Added DrawdownTracker |
| 6 | System 1 Entry | M9 | ✅ COVERED | 20-day breakout detection |
| 7 | System 1 Filter | M10 | ✅ COVERED | Winner skip logic |
| 8 | System 2 Entry | M9 | ✅ COVERED | 55-day breakout detection |
| 9 | Failsafe Entry | M9, M10 | ⚠️ IMPLICIT | Need explicit test |
| 10 | 2N Hard Stop | M14, M16 | ✅ COVERED | Stop calculator + monitor |
| 11 | Pyramiding (½N) | M13, M17 | ✅ FIXED | Corrected to ½N interval |
| 12 | Aggressive Stop Adjustment | M17, M20 | ✅ COVERED | All stops move on pyramid |
| 13 | System 1 Exit (10-day) | M17 | ✅ COVERED | Donchian 10 exit |
| 14 | System 2 Exit (20-day) | M17 | ✅ COVERED | Donchian 20 exit |
| 15 | Rollover Logic | M7.5 | ✅ FIXED | Added new milestone |
| 16 | Fast Market Logic | M19 | ⚠️ IMPLICIT | Gap handling in IBKR broker |
| 17 | Portfolio Heat Cap | M15 | ✅ CONFIRMED | Using unit limits (original rules)

---

## Detailed Analysis

### ✅ Fully Covered Rules

#### Rule 1: Price Only Input
- **Milestone:** M2 (IBKR), M7 (Composite Feed)
- **Implementation:** DataFeed ABC only returns Bar (OHLCV)
- **Verification:** `test_bar_validation()` in M3

#### Rule 3: Calculate N
- **Milestone:** M4
- **Implementation:** `calculate_true_range()`, `calculate_n()` with Wilders smoothing
- **Verification:** `test_n_matches_tos()` validates within 0.5% of TOS

#### Rule 6: System 1 Entry (20-day)
- **Milestone:** M9
- **Implementation:** SignalDetector checks price > donchian_20_upper
- **Verification:** `test_s1_long_breakout()`

#### Rule 7: System 1 Filter
- **Milestone:** M10
- **Implementation:** S1Filter checks last S1 trade outcome
- **Verification:** `test_skip_after_winner()`, `test_take_after_loser()`

#### Rule 8: System 2 Entry (55-day)
- **Milestone:** M9
- **Implementation:** SignalDetector checks price > donchian_55_upper
- **Verification:** `test_s2_never_filtered()` confirms always taken

#### Rule 10: 2N Hard Stop
- **Milestone:** M14, M16
- **Implementation:** `calculate_stop()` returns Entry - 2N
- **Verification:** `test_stop_calculation_long()` expects 2800 - 40 = 2760

#### Rule 12: Aggressive Stop Adjustment
- **Milestone:** M17, M20
- **Implementation:** PyramidHandler moves ALL stops to new entry - 2N
- **Verification:** Position Monitor architecture note specifies this

#### Rule 13 & 14: System Exits
- **Milestone:** M17
- **Implementation:** PositionMonitor checks donchian_10 (S1) or donchian_20 (S2)
- **Verification:** `test_s1_long_exit_on_10day_low()`

---

### ❌ Missing or Wrong Rules

#### Rule 5: Drawdown Reduction - MISSING
**Problem:** No milestone addresses the 10% drawdown → 20% equity reduction rule.

**Required Addition:**
- Add to M14 (Unit Size Calculator) or create new milestone
- Need `DrawdownTracker` service
- Need `notional_equity` vs `actual_equity` distinction

**Suggested Test:**
```python
def test_drawdown_reduces_notional_equity():
    tracker = DrawdownTracker(peak_equity=Decimal("100000"))
    tracker.update_equity(Decimal("89000"))  # 11% drawdown

    # Notional should be reduced by 20%
    assert tracker.notional_equity == Decimal("80000")  # 100k * 0.8

def test_drawdown_recovery():
    tracker = DrawdownTracker(peak_equity=Decimal("100000"))
    tracker.update_equity(Decimal("89000"))  # Draw down
    tracker.update_equity(Decimal("100000"))  # Recover

    # Notional should return to actual
    assert tracker.notional_equity == Decimal("100000")
```

---

#### Rule 11: Pyramiding Interval - WRONG
**Problem:** Plan says pyramid at +1N, but verified rules say ½N.

**Current (WRONG):**
```python
def test_next_pyramid_trigger_long():
    pos = make_position(
        latest_entry_price=Decimal("2800"),
        latest_n_at_entry=Decimal("20"),
    )
    assert pos.next_pyramid_trigger == Decimal("2820")  # +1N WRONG!
```

**Correct (from RULES.md):**
```python
def test_next_pyramid_trigger_long():
    pos = make_position(
        latest_entry_price=Decimal("2800"),
        latest_n_at_entry=Decimal("20"),
    )
    # ½N = 10, so trigger at 2810
    assert pos.next_pyramid_trigger == Decimal("2810")  # +½N CORRECT
```

**Note:** The original Turtle rules used ½N intervals. Some modern adaptations use 1N. Verify which you want to use.

---

#### Rule 15: Rollover Logic - MISSING
**Problem:** No milestone handles futures contract rollover.

**Required Addition:**
- Add to Market Data phase (new M5.5 or extend M7)
- Need continuous contract builder
- Need rollover detection (volume shift or days before expiry)

**Suggested Deliverables:**
- `src/adapters/data_feeds/continuous_contract.py` - ContinuousContractBuilder
- Rollover detection logic
- Back-adjustment for historical data

**Note:** The original spec doc 06-data-sources.md HAS this code but it's not in a milestone!

---

### ⚠️ Partially Covered Rules

#### Rule 2: 300 Market Universe
**Current:** M11 has "universe configuration" but no details.

**Needed:**
- Define universe file format (JSON/YAML)
- Include correlation groups for each market
- Sample universe with 20+ micro futures to start

---

#### Rule 4: Unit Size - Risk Factor Config
**Current:** M14 test uses `risk_pct=Decimal("0.02")` (2%)

**Problem:** This doesn't match original (1%) or modern (0.5%) rules.

**Fix:** Make risk factor configurable in TurtleRules:
```python
class TurtleRules(BaseModel):
    risk_factor: Decimal = Field(default=Decimal("0.01"))  # Original: 1%
    # risk_factor: Decimal = Field(default=Decimal("0.005"))  # Parker: 0.5%
```

---

#### Rule 9: Failsafe Entry
**Current:** Implicitly covered by S2 always being taken.

**Needed:** Explicit test case:
```python
def test_failsafe_catches_filtered_s1():
    """If S1 was skipped due to filter, S2 MUST be taken"""
    # Setup: Last S1 was winner (so new S1 would be skipped)
    # Signal: Price now breaks 55-day (S2)
    # Assert: Signal taken even though we have no position
```

---

#### Rule 16: Fast Market Logic
**Current:** IBKR broker will execute at market price on gaps.

**Needed:** Explicit handling:
```python
def test_gap_execution():
    """Execute even if price gaps past stop"""
    # Stop was at 2760
    # Market gaps to 2740
    # Should still exit at market (2740), not wait for 2760
```

---

#### Rule 17: Portfolio Heat Cap
**Current:** M15 uses fixed unit limits (4/6/12).

**Original Rules:** Fixed unit limits are correct.
**Modern Parker:** Volatility-based heat cap.

**Decision Needed:** Which approach do you want?
- If original: Current plan is fine
- If modern: Need `PortfolioHeatCalculator` that sums (N × contracts × point_value) across all positions

---

## Required Plan Updates

### Critical Fixes

1. **Add Rule 5 (Drawdown)** - New milestone or extend M14
2. **Fix Rule 11 (Pyramid ½N vs 1N)** - Clarify which interval to use, update tests

### Recommended Additions

3. **Add Rule 15 (Rollover)** - New milestone M5.5 or extend M7
4. **Enhance Rule 2 (Universe)** - Add universe file to M11

### Minor Clarifications

5. **Rule 4 (Risk Factor)** - Make configurable, add to TurtleRules
6. **Rule 9 (Failsafe)** - Add explicit test
7. **Rule 16 (Fast Market)** - Add gap handling test
8. **Rule 17 (Heat Cap)** - Document decision: unit limits vs volatility cap

---

## Decision Required

Before updating the plan, please confirm:

1. **Pyramid Interval:** Use ½N (original) or 1N (some modern adaptations)?
2. **Risk Factor:** Use 1% (original), 0.5% (Parker), or 2% (your current spec)?
3. **Portfolio Limits:** Use unit counts (original) or volatility heat cap (modern)?
