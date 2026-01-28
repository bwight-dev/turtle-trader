# Turtle Trading Bot System Specification v2

## Part 1: Overview and Domain Model

---

## 1. System Overview

### 1.1 Vision

Build a fully mechanical trading system that:
- Executes Turtle Trading rules without discretionary intervention
- Scales from paper trading → live micro futures → managed accounts
- Provides AI assistance for rule clarification and decision validation
- Maintains auditable trade records for future CTA registration

### 1.2 Core Principles

| Principle | Implementation |
|-----------|---------------|
| **Price Only** | No fundamental data, news, or external signals |
| **Mechanical Execution** | Zero discretion once rules are defined |
| **Volatility-Based Sizing** | N (ATR) drives all position calculations |
| **Let Winners Run** | No profit targets; exit only on opposite breakout (S1=10-day, S2=20-day) or hard stop |
| **Cut Losses** | Hard 2N stops, no exceptions |

### 1.3 Modern Adaptations (Parker Rules)

| Original 1983 | Modern 2025 | Rationale |
|---------------|-------------|-----------|
| ~20 commodities | 300+ markets | Capture rare outliers |
| 20/55-day breakouts | 55-200 day emphasis | Reduce whipsaws |
| 1-2% risk/trade | 0.25-0.5% risk/trade | Support larger universe |
| 12 unit limit | Portfolio heat cap | Dynamic risk management |

---

## 2. Domain Model

### 2.1 Ubiquitous Language

```
Market          := Tradeable instrument (futures, ETF, stock)
N (Volatility)  := 20-day ATR (Wilders smoothing)
Unit            := Position sized to risk X% of equity at 2N stop
Signal          := Breakout event (S1=20-day, S2=55-day)
Filter          := S1 skip rule (last S1 was winner)
Pyramid         := Adding units at +1N intervals
Stop            := Hard exit at 2N from entry (moves only on pyramid)
Breakout Exit   := Exit on opposite N-day breakout (S1=10-day, S2=20-day)
Correlation     := Market grouping for unit limits
Heat            := Total portfolio risk exposure
```

### 2.2 Core Aggregates

```
┌─────────────────────────────────────────────────────────────┐
│                        AGGREGATES                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  Portfolio  │    │   Market    │    │    Trade    │     │
│  │  (Root)     │    │  (Root)     │    │   (Root)    │     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘     │
│         │                  │                  │             │
│    ┌────┴────┐        ┌────┴────┐        ┌────┴────┐       │
│    │Position │        │  OHLCV  │        │  Entry  │       │
│    │Pyramid  │        │   Bar   │        │  Exit   │       │
│    │  Level  │        │    N    │        │ Pyramid │       │
│    │  Stop   │        │ Signal  │        │  Level  │       │
│    └─────────┘        │Donchian │        └─────────┘       │
│                       └─────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Bounded Contexts

```
┌──────────────────────────────────────────────────────────────────────┐
│                          TURTLE TRADING SYSTEM                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                │
│  │   MARKET    │   │  STRATEGY   │   │  PORTFOLIO  │                │
│  │   DATA      │──▶│   ENGINE    │──▶│  MANAGER    │                │
│  │             │   │             │   │             │                │
│  └─────────────┘   └─────────────┘   └──────┬──────┘                │
│        │                 │                  │                        │
│        │                 │           ┌──────┴──────┐                 │
│        │                 │           │  POSITION   │                 │
│        │                 │           │  MONITOR    │ ◀── KEY MODULE │
│        │                 │           └──────┬──────┘                 │
│        ▼                 ▼                  ▼                        │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                │
│  │   AI        │   │  EXECUTION  │   │   AUDIT     │                │
│  │  ADVISOR    │◀─▶│   GATEWAY   │──▶│   LOG       │                │
│  │             │   │             │   │             │                │
│  └─────────────┘   └─────────────┘   └─────────────┘                │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

#### Context Responsibilities

| Context | Responsibility |
|---------|---------------|
| **Market Data** | Ingest from IBKR (primary) or Yahoo (backup), normalize, serve price data; calculate and persist N and Donchian |
| **Strategy Engine** | Generate entry signals, apply S1 filter |
| **Portfolio Manager** | Track positions, units, enforce limits |
| **Position Monitor** | **Monitor open positions for pyramids, exits, stops** |
| **Execution Gateway** | Interface with IBKR API for order execution |
| **AI Advisor** | Rule clarification, decision validation |
| **Audit Log** | Immutable trade history for compliance |

#### Data Source Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA SOURCE PRIORITY                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐                                               │
│  │  PRIMARY: IBKR   │ ◀── TWS/Gateway on Mac Mini (local)          │
│  │  Port 7497       │     Paper: DUP318628                          │
│  └────────┬─────────┘                                               │
│           │                                                          │
│           │ Failover on: connection error, timeout, validation fail │
│           ▼                                                          │
│  ┌──────────────────┐                                               │
│  │  BACKUP: Yahoo   │ ◀── yfinance library                          │
│  │  Finance         │     Free, reliable for daily bars             │
│  └──────────────────┘                                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

See `06-data-sources.md` for complete IBKR integration details.
