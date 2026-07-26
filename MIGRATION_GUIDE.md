# Nautilus Engine - VPS Migration Guide

This document outlines the exact steps required to set up the Nautilus Engine on a brand new Virtual Private Server (VPS / RDP).

## 1. Initial Software Setup
1. **Download and Install MetaTrader 5 (MT5):** 
   - Install the terminal provided by your Prop Firm.
   - Log into your trading account.
   - Go to `Tools > Options > Expert Advisors` and check **"Allow algorithmic trading"**.
2. **Download and Install Python:**
   - Download Python (3.9 or higher) for Windows.
   - **CRITICAL:** During the installation screen, you MUST check the box at the bottom that says **"Add Python to PATH"** before clicking Install.

## 2. Clone the Repository
1. Open Command Prompt (`cmd`) or PowerShell.
2. Navigate to your Documents folder: `cd Documents`
3. Clone your private repository: 
   `git clone https://github.com/temabef/Forex-Alpha-Desk.git`
4. Enter the folder: `cd Forex-Alpha-Desk`

## 3. Install Dependencies
1. While inside the `Forex-Alpha-Desk` folder in the terminal, create a virtual environment (optional but recommended):
   `python -m venv venv`
2. Activate the virtual environment:
   `venv\Scripts\activate`
3. Install the required packages:
   `pip install -r requirements.txt`

## 4. Environment Variables (.env)
Because `.env` files contain sensitive API keys and secrets, they are intentionally ignored by Git and will not exist when you clone the repo.
1. Create a new file named `.env` in the root folder of your project.
2. Paste your configuration into it. Example format:
   ```text
   TELEGRAM_TOKEN=your_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   MT5_TERMINAL_PATH=C:\Program Files\Your MT5 Terminal\terminal64.exe
   LOT_SIZE_AI=0.05
   LOT_SIZE_PAIRS=0.02
   LOT_SIZE_TREND=0.04
   SYMBOL_SUFFIX=.x
   ENABLE_NEWS_FILTER=True
   ENABLE_FRIDAY_EXIT=False
   MAX_DAILY_DRAWDOWN_PCT=0.035
   NEWS_BUFFER_MINUTES=30
   ```
3. Make absolutely sure the `MT5_TERMINAL_PATH` exactly matches the installation path on your new PC.

## 5. Automation Setup (Task Scheduler)
1. Open the Windows **Task Scheduler**.
2. Click **Create Task...** on the right side.
3. **General Tab:** Name it `Nautilus Bot`. Check "Run whether user is logged on or not".
4. **Triggers Tab:** Click New. Set it to Daily, repeat task every 1 hour, indefinitely.
5. **Actions Tab:** Click New. 
   - Action: Start a program.
   - Program/script: Browse to your Python executable (e.g., `C:\Users\Administrator\Documents\Forex-Alpha-Desk\venv\Scripts\python.exe`).
   - Add arguments: `get_current_signal.py`
   - Start in: The full path to your folder (e.g., `C:\Users\Administrator\Documents\Forex-Alpha-Desk`).
6. Save the task and enter your Windows administrator password.

---

## 📜 Historical Strategy Evolution (For Future Engineers)

If you are reading this codebase in the future, it is important to understand the evolutionary history of the Nautilus Engine and why certain strategies exist (or were removed). Over several months of live-market prop firm testing, the portfolio underwent significant tuning.

### Phase 1: The Kitchen Sink Approach
Initially, the bot ran multiple strategies simultaneously:
1. **Pairs Trading (EURUSD / GBPUSD):** A statistical arbitrage mean-reversion hedge.
2. **Donchian Breakout (Trend):** A breakout momentum strategy targeting EURUSD.
3. **Quant Predictor (AI):** A machine-learning adaptive model predicting short-term direction.

**The Problem:** The portfolio stagnated around break-even. While the AI strategy was consistently generating profits, the Breakout and Pairs strategies were extremely vulnerable to summer market chop and fundamental divergence. 
- *Pairs Breakdown:* During major central bank announcements, the EUR/GBP correlation broke down, causing the mean-reversion logic to fail and hit deep drawdowns.
- *Breakout Fakeouts:* The EURUSD Donchian Breakout strategy repeatedly bought the absolute top and sold the absolute bottom of ranges right before violent reversals, immediately hitting the 50-pip stop loss.

### Phase 2: Adding "The Beast" (GBPJPY)
To capture massive volatility, we implemented a specialized breakout strategy just for GBPJPY ("The Beast"). 
- **Specs:** 100-pip Take Profit, 50-pip Stop Loss.
- **Filter:** We added a strict H1 50/200 EMA trend filter to prevent it from firing during sideways chop. 
- **Result:** The EMA filter worked beautifully to keep the bot out of bad trades, but whenever it did fire, GBPJPY's erratic fakeouts still caused unnecessary losses.

### Phase 3: Risk Mitigation & Order 66
Realizing that the Breakout strategies were dragging down the highly accurate AI strategy, we took the following steps:
1. **Halved Lot Sizes:** We manually cut the `LOT_SIZE_TREND` in the `.env` files by 50% to stop the bleeding while we observed the Breakouts for one final week.
2. **The Final Cut (July 2026):** After one final week where the AI generated massive profits (+$25/trade) and the EURUSD Breakout lost money again (-$20/trade), we officially executed "Order 66". 
3. **Code Purge:** The `STRATEGY 2: DONCHIAN BREAKOUT (Trend)` block was completely deleted from `get_current_signal.py`.

### The Current State (The Lean MVP)
The Nautilus Engine now operates as a lean, highly targeted machine:
- **The MVP:** The Quant Predictor AI handles the heavy lifting, currently fine-tuned to extract consistent profits from USDJPY using dynamic targets.
- **The Hedge:** The Pairs strategy runs quietly in the background for low-risk, steady grinding when correlations align.
- **The Standby:** The GBPJPY Beast remains in the code but is heavily filtered, waiting silently for a true macro trend breakout.

*Future Note: If you wish to scale the bot's profitability, DO NOT reintroduce simple breakouts. Instead, expand the Quant Predictor AI to cover more assets (EURUSD, GBPUSD) or increase `LOT_SIZE_AI`.*
