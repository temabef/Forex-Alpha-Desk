# 📊 Forex Multi-Strategy Trading Desk: Owner's Manual

This document summarizes the professional trading system built on **May 3rd, 2026**.

## 1. System Overview
We have built a 3-pillar automated analysis system using the **Nautilus Trader** engine and **Python Machine Learning**.

### The 3 Pillars (Strategies)
1.  **Mean Reversion (Pairs Arbitrage):** Bets that EURUSD and GBPUSD will always return to their historical relationship.
2.  **Trend Follower (Donchian Breakout):** Identifies and rides massive price "rocket ships" using a 400-hour lookback.
3.  **Quant Predictor (Machine Learning):** Uses a Random Forest AI to predict the next 4 hours of market movement.

---

## 2. Daily Routine & Manual Checks
Your system is **100% Automated** via the Windows Task Scheduler. It runs quietly every hour. However, if you want to check things manually, here are your "Command Center" lines:

### A. How to check for LIVE Signals (All 3 Strategies)
Run this command anytime to see the current market pulse and send a fresh Telegram alert:
```powershell
.\venv\Scripts\python.exe get_current_signal.py
```

### B. How to run a Backtest (History Simulation)
If you want to see how a strategy performed over the last 3 years:
*   **For Pairs Trading:** `.\venv\Scripts\python.exe run_backtest.py`
*   **For Trend Following:** `.\venv\Scripts\python.exe run_trend_backtest.py`

### C. How to see the Visual Charts
After running a backtest, generate the 3-panel performance chart:
```powershell
.\venv\Scripts\python.exe analyze_results.py
```

---

## 3. Maintenance & "Always-On" Logic

### Does the AI need to "Keep Learning"?
**No manual action needed.** 
Every time the `get_current_signal.py` script runs (manually or automatically), it fetches the last **60 days** of data and re-trains the model from scratch. This ensures the AI is always aware of the most recent market "mood."

### What happens when I close my computer?
*   **Computer Closed/Off:** The bot pauses. It cannot check the market or send signals if it has no power or Wi-Fi.
*   **Restarting the Computer:** As soon as you log back into Windows, the **Task Scheduler** will automatically resume the hourly checks. 
*   **Checking the Schedule:** Click the Start menu and type **Task Scheduler**. Find `ForexPairsSignal` in the Library.

---

## 4. Key Files in your Folder

| File | Purpose |
| :--- | :--- |
| `get_current_signal.py` | **The Main Bot.** Fetches data, runs all 3 strategies, and pings Telegram. |
| `logs/signal_history.txt` | **The Black Box.** A permanent history of every hourly analysis. |
| `ml_predictor_strategy.py` | The "Brain" of the AI strategy. |
| `trend_breakout_strategy.py` | The logic for the Donchian Trend strategy. |
| `pairs_trading_strategy.py` | The logic for the Mathematical Arbitrage strategy. |
| `setup_automation.bat` | The installer that schedules the bot in Windows. |

---

## 5. Professional Safety Specs
*   **Pairs SL/TP:** $1,000 Loss / $2,500 Profit.
*   **Trend RR:** 1:2.0 Reward-to-Risk ratio.
*   **AI Confidence:** 58% minimum threshold to send a signal.

---

## 6. Glossary: What is a "Spread" Trade?
In Strategy 1, you aren't just betting on one price. You are trading the **gap** between EURUSD and GBPUSD.
*   **"SELL SPREAD":** Means EURUSD is too high relative to GBPUSD. You **Sell EURUSD** and **Buy GBPUSD**.
*   **"BUY SPREAD":** Means EURUSD is too low relative to GBPUSD. You **Buy EURUSD** and **Sell GBPUSD**.
*   **Goal:** You profit when the two currencies move back to their "Normal" relationship, regardless of whether the whole market goes up or down.

## 7. Strategic Timing: When to be "Online"
You do **not** need to leave your computer on 24/7. 

*   **The Power Hours (Best Signals):** Most signals will trigger during the **London Open** (8 AM GMT) and **New York Open** (1 PM GMT). 
*   **The Quiet Time (Safe to Sleep):** The **Asian Session** (11 PM to 7 AM GMT) is usually very slow for EUR and GBP. It is perfectly safe to turn off your computer and rest during this time.
*   **Why 1-Hour Polling?** These pairs move slower than Gold. An hourly check-in is the industry standard for catching high-quality moves while ignoring 5-minute "noise."

**Your desk is ready. Let the signals work for you!**
