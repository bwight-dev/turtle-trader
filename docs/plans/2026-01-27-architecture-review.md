# Architecture Review: Turtle Trading Bot DDD Design

**Date:** 2026-01-27
**Based on:** architecture-patterns skill analysis
**Status:** Applied to implementation plan

---

## Executive Summary

The current spec uses a **pragmatic DDD approach** which is appropriate for this project. However, I've identified several areas where the design could be improved for testability and maintainability.

**Overall Assessment:** Good design with minor adjustments needed.

---

## Current Architecture Analysis

### Bounded Contexts (from spec)

```
MARKET DATA ──► STRATEGY ENGINE ──► PORTFOLIO MANAGER
                                           │
                                    POSITION MONITOR
                                           │
                                           ▼
AI ADVISOR ◄──► EXECUTION GATEWAY ──► AUDIT LOG
```

### Strengths

1. **Clear Aggregate Roots**
   - Portfolio, Market, Trade are well-defined aggregates
   - Position contains PyramidLevel as nested entity (correct)

2. **Value Objects**
   - NValue, DonchianChannel, StopLevel are immutable (frozen=True)
   - Money calculations handled correctly via Decimal

3. **Ubiquitous Language**
   - Domain terms (N, Unit, Pyramid, Signal, S1/S2) are well-defined
   - Consistent across all spec documents

4. **Repository Pattern**
   - NValueRepository, TradeRepository properly abstract persistence
   - Async interface for database operations

### Issues Identified

#### Issue 1: Position Monitor Coupling (Medium Priority)

**Problem:** The Position Monitor in the spec directly calls:
- Market Data (for prices)
- Limit Checker (for validation)
- Stop Calculator (for new stops)
- Sizing Calculator (for new units)

This creates a "god object" that knows too much.

**Recommendation:** Use Domain Events pattern:

```python
# Instead of:
class PositionMonitor:
    def check_position(self, position, market):
        if self._is_pyramid_triggered(position, market):
            # Directly calculate new unit, stop, etc.
            size = calculate_unit_size(...)
            stop = calculate_stop(...)

# Use:
class PositionMonitor:
    def check_position(self, position, market) -> PositionCheck:
        # Only detect and return action needed
        if self._is_pyramid_triggered(position, market):
            return PositionCheck(
                action=PositionAction.PYRAMID,
                # Don't calculate new values here
            )

class PyramidHandler:
    # Separate handler for pyramid execution
    def handle(self, check: PositionCheck, portfolio, market):
        size = self.sizing.calculate(...)
        stop = self.stop_calc.calculate(...)
        return PyramidOpportunity(...)
```

**Impact:** Minor refactor. Current design works, but this improves testability.

---

#### Issue 2: Portfolio Mutation (Low Priority)

**Problem:** Portfolio model has mutable `positions` dict:

```python
class Portfolio(BaseModel):
    positions: dict[str, Position] = Field(default_factory=dict)
```

Positions are added/removed directly:
```python
del portfolio.positions[exit_signal.symbol]
```

**Recommendation:** Use aggregate methods:

```python
class Portfolio(BaseModel):
    _positions: dict[str, Position] = Field(default_factory=dict, alias="positions")

    def add_position(self, position: Position) -> None:
        if self._check_limits(position):
            self._positions[position.symbol] = position
        else:
            raise PortfolioLimitExceeded(...)

    def close_position(self, symbol: str) -> Position:
        if symbol not in self._positions:
            raise PositionNotFound(symbol)
        return self._positions.pop(symbol)
```

**Impact:** Minor. Current approach works but doesn't enforce invariants.

---

#### Issue 3: Broker Interface Location (Low Priority)

**Problem:** `Broker` interface is in `execution/brokers/base.py`. This creates a dependency from domain toward infrastructure.

**Recommendation:** Move interface to domain layer:

```
# Current
execution/
├── brokers/
│   ├── base.py       # Broker ABC here
│   ├── paper.py
│   └── ibkr.py

# Better (Clean Architecture)
turtle_core/
├── interfaces/
│   ├── broker.py     # Broker ABC here (domain knows this)
│   └── data_feed.py  # DataFeed ABC here

execution/
├── adapters/
│   ├── paper_broker.py    # Implements turtle_core.interfaces.Broker
│   └── ibkr_broker.py
```

**Impact:** Directory restructure. Not critical for functionality.

---

#### Issue 4: Missing Anti-Corruption Layer (Low Priority)

**Problem:** IBKR data feed directly converts to domain models:

```python
# In ibkr.py
return Bar(
    symbol=symbol,
    date=bar.date.date(),
    open=Decimal(str(bar.open)),
    ...
)
```

This tightly couples the domain to IBKR's data format.

**Recommendation:** Add explicit mapping layer:

```python
class IBKRBarMapper:
    def to_domain(self, ibkr_bar: ib_insync.BarData, symbol: str) -> Bar:
        return Bar(
            symbol=symbol,
            date=self._parse_date(ibkr_bar.date),
            open=self._to_decimal(ibkr_bar.open),
            ...
        )
```

**Impact:** Minor. Adds explicit boundaries but current approach is pragmatic.

---

## Recommended Directory Structure

Applying Clean Architecture principles to the current spec:

```
src/
├── domain/                    # Core domain (innermost layer)
│   ├── models/               # Entities and Value Objects
│   │   ├── market.py         # NValue, DonchianChannel, Bar, MarketSpec
│   │   ├── position.py       # Position, PyramidLevel
│   │   ├── portfolio.py      # Portfolio aggregate
│   │   ├── signal.py         # Signal, FilterResult
│   │   └── trade.py          # Trade (audit record)
│   ├── interfaces/           # Ports (abstract interfaces)
│   │   ├── data_feed.py      # DataFeed ABC
│   │   ├── broker.py         # Broker ABC
│   │   └── repository.py     # Repository ABCs
│   ├── services/             # Domain services
│   │   ├── signal_detector.py
│   │   ├── position_monitor.py
│   │   └── limit_checker.py
│   └── rules.py              # TurtleRules configuration
│
├── application/              # Use cases (application layer)
│   ├── commands/
│   │   ├── place_entry.py
│   │   ├── execute_pyramid.py
│   │   └── close_position.py
│   ├── queries/
│   │   ├── scan_markets.py
│   │   └── get_portfolio.py
│   └── workflows/
│       ├── daily_workflow.py
│       └── monitoring_loop.py
│
├── adapters/                 # Interface adapters (infrastructure)
│   ├── data_feeds/
│   │   ├── ibkr_feed.py
│   │   ├── yahoo_feed.py
│   │   └── composite_feed.py
│   ├── brokers/
│   │   ├── paper_broker.py
│   │   └── ibkr_broker.py
│   ├── repositories/
│   │   ├── postgres_trade_repo.py
│   │   └── postgres_n_repo.py
│   └── mappers/
│       ├── ibkr_mapper.py
│       └── yahoo_mapper.py
│
└── infrastructure/           # Frameworks & drivers (outermost)
    ├── database.py           # Neon connection pool
    ├── config.py             # Environment configuration
    └── logging.py
```

**Note:** This is the "ideal" structure. The current spec structure is simpler and acceptable for pragmatic DDD. Only refactor if complexity grows.

---

## Verdict: Current Spec is Acceptable

The current spec's directory structure:

```
src/
├── turtle_core/       # Models + Rules (domain)
├── market_data/       # Data feeds + calculations
├── strategy/          # Signal detection + filters
├── portfolio/         # Position tracking + monitor
├── execution/         # Broker implementations
├── ai_advisor/        # Gemini integration
├── audit/             # Trade logging
└── orchestrator/      # Workflows
```

**This is fine because:**

1. **turtle_core** acts as the domain layer - models are shared
2. Dependencies generally flow correctly (market_data → strategy → portfolio → execution)
3. The system is not complex enough to warrant full Clean Architecture separation
4. Testability is maintained via interfaces (DataFeed ABC, Broker ABC)

---

## Recommendations Summary

| Issue | Priority | Action |
|-------|----------|--------|
| Position Monitor coupling | Medium | Consider domain events pattern in M17 |
| Portfolio mutation | Low | Add aggregate methods in M13 |
| Broker interface location | Low | Keep as-is for simplicity |
| Anti-corruption layer | Low | Keep as-is, pragmatic approach |

---

## Testing Strategy Validation

The milestone approach properly tests each layer:

1. **Domain tests** (M3, M13, M14, M15): Pure unit tests, no mocks needed
2. **Service tests** (M9, M10, M16, M17): Mock repositories/feeds
3. **Integration tests** (M2, M7, M19, M20): Real IBKR connection
4. **End-to-end tests** (M23, M24): Full workflow validation

This layered testing approach aligns with Clean Architecture principles.

---

## Conclusion

The current spec design is **pragmatically sound** for a system of this complexity. The DDD tactical patterns (Entities, Value Objects, Aggregates, Repositories) are applied correctly.

**Recommendation:** Proceed with implementation as planned. Consider the Position Monitor refactor (Issue 1) during M17 if testing becomes difficult.
