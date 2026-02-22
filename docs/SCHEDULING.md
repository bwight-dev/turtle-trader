# Turtle Trading Bot - Scheduled Tasks

## Overview

The turtle trading system runs two scheduled tasks on macOS using launchd:

1. **Daily Scanner** - Runs once at market open to find new entry signals
2. **Position Monitor** - Runs continuously, checking positions every 60 seconds

## Task Configuration

### Daily Scanner (`com.turtle.daily`)

| Setting | Value |
|---------|-------|
| Schedule | 6:30 AM Mon-Fri (Pacific) |
| Script | `scripts/daily_run.py` |
| Log | `logs/daily.log` |
| Error Log | `logs/daily.error.log` |
| Plist | `~/Library/LaunchAgents/com.turtle.daily.plist` |

**What it does:**
- Scans all 15 ETFs for breakout signals
- Checks 20-day (S1) and 55-day (S2) Donchian channels
- Applies S1 filter (skip if last S1 was winner)
- Reports any entry signals found

### Position Monitor (`com.turtle.monitor`)

| Setting | Value |
|---------|-------|
| Schedule | Continuous (every 60 seconds) |
| Script | `scripts/monitor_positions.py` |
| Log | `logs/monitor.log` |
| Error Log | `logs/monitor.error.log` |
| Plist | `~/Library/LaunchAgents/com.turtle.monitor.plist` |

**What it does:**
- Connects to IBKR TWS
- Fetches all open positions
- For each position, checks:
  - Stop hit (2N hard stop) → EXIT_STOP
  - Breakout exit (10/20-day low) → EXIT_BREAKOUT
  - Pyramid trigger (+½N from last entry) → PYRAMID
- Logs status and any actions needed

## Monitoring Commands

### Check job status
```bash
launchctl list | grep turtle
```

Output shows PID (or `-` if not running) and exit status:
```
34316   0   com.turtle.monitor    # Running with PID 34316
-       0   com.turtle.daily      # Loaded but not running (scheduled)
```

### Watch logs in real-time
```bash
# Position monitor (most useful)
tail -f logs/monitor.error.log

# Daily scanner
tail -f logs/daily.error.log
```

### Run status dashboard
```bash
python scripts/status.py
```

Shows:
- Current IBKR positions
- launchd job status
- Recent log entries
- Quick command reference

## Control Commands

### Position Monitor

```bash
# Stop the monitor
launchctl unload ~/Library/LaunchAgents/com.turtle.monitor.plist

# Start the monitor
launchctl load ~/Library/LaunchAgents/com.turtle.monitor.plist

# Restart (stop + start)
launchctl unload ~/Library/LaunchAgents/com.turtle.monitor.plist && \
launchctl load ~/Library/LaunchAgents/com.turtle.monitor.plist

# Run single check manually
python scripts/monitor_positions.py --once

# Run continuous manually (foreground)
python scripts/monitor_positions.py --interval 60
```

### Daily Scanner

```bash
# Disable daily runs
launchctl unload ~/Library/LaunchAgents/com.turtle.daily.plist

# Enable daily runs
launchctl load ~/Library/LaunchAgents/com.turtle.daily.plist

# Run manually
python scripts/daily_run.py
```

## Log Locations

All logs are in the `logs/` directory:

| File | Contents |
|------|----------|
| `monitor.error.log` | Position monitor output (main log) |
| `monitor.log` | Position monitor stdout (usually empty) |
| `daily.error.log` | Daily scanner output |
| `daily.log` | Daily scanner stdout |

**Note:** Python logging goes to stderr by default, so `.error.log` files contain the main output.

## Troubleshooting

### Monitor not running
```bash
# Check if loaded
launchctl list | grep turtle

# Check for errors
cat logs/monitor.error.log | tail -50

# Common issues:
# - TWS not running (start TWS first)
# - Client ID conflict (another connection using same ID)
# - Network issues with IBKR
```

### TWS connection issues
```bash
# Make sure TWS is running with API enabled:
# - TWS > Edit > Global Configuration > API > Settings
# - Enable "Enable ActiveX and Socket Clients"
# - Port: 7497 (paper) or 7496 (live)
# - Allow connections from localhost
```

### Reload after editing plist
```bash
launchctl unload ~/Library/LaunchAgents/com.turtle.monitor.plist
launchctl load ~/Library/LaunchAgents/com.turtle.monitor.plist
```

## File Locations Summary

```
~/Library/LaunchAgents/
├── com.turtle.daily.plist      # Daily scanner schedule
└── com.turtle.monitor.plist    # Position monitor schedule

turtle-trading-bot/
├── scripts/
│   ├── daily_run.py            # Daily signal scanner
│   ├── monitor_positions.py    # Position monitor
│   └── status.py               # Status dashboard
└── logs/
    ├── monitor.error.log       # Monitor output
    ├── monitor.log
    ├── daily.error.log         # Daily scanner output
    └── daily.log
```
