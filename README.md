# Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

# Install packages
```bash
pip install yfinance pandas numpy pandas-ta schedule streamlit plotly
```



QUICK REFERENCE
When Brad says:

"I have signals" → Analyze, prioritize, size positions
"Check my positions" → Review status, update exits, assess risk
"Exit signal triggered" → Confirm and provide execution plan
"Should I...?" → Usually answer: "What do the rules say?"
"The market is..." → Redirect: "We don't predict. We follow price."

Your default response to rule questions:
"The Turtle rule is [X]. Execute [Y] action. Here's why this rule exists: [Z]."
Never say:

"I think the market will..."
"Maybe wait and see..."
"You could try..."
"It depends on how you feel..."

Always say:

"The rule is..."
"Execute this action..."
"Here's the calculation..."
"This is within/outside the rules..."


Command Line Interface:

  # Run immediately (paper trading - default)
  python main.py --now

  # Run immediately (real trading)
  python main.py --now --real

  # Schedule daily scan (paper trading)
  python main.py --schedule

  # Schedule daily scan (real trading)
  python main.py --schedule --real

  Live Test Results! 🎉

  Just ran a live scan and found 5 BUY SIGNALS:

  1. SPY @ $687.05 - Broke above $685.54
    - 17 shares ($11,679.85)
    - Stop: $671.85
    - Risk: $258.35 (1.92%)
  2. QQQ @ $632.92 - Broke above $628.55
    - 14 shares ($8,860.88)
    - Stop: $614.78
    - Risk: $253.93 (1.88%)
  3. DIA @ $477.16 - Broke above $475.62
    - 25 shares ($11,929.00)
    - Stop: $466.70
    - Risk: $261.58 (1.94%)
  4. MSFT @ $542.07 - Broke above $534.58
    - 15 shares ($8,131.05)
    - Stop: $524.76
    - Risk: $259.69 (1.93%)
  5. NVDA @ $201.03 - Broke above $195.62
    - 23 shares ($4,623.69)
    - Stop: $189.35
    - Risk: $268.64 (1.99%)