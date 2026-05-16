# 🏦 Automated Dual-Account Forex Trading Desk: System Manual

This document provides a comprehensive overview of the trading system architecture, strategies, and safety configurations. Use this as a reference for any future development or maintenance tasks.

## 🏗️ System Architecture
The system is built on a **Twin Folder Architecture** to manage two separate prop firm accounts independently on the same server.

*   **5k Account**: Located at `C:\Users\globalpert62\Documents\Forex-Desk-5k`
*   **10k Account**: Located at `C:\Users\globalpert62\Documents\Forex-Desk-10k`

### Tech Stack
*   **Language**: Python 3.12+
*   **Broker Interface**: MetaTrader 5 (MT5) Python API.
*   **Data Analysis**: Pandas, NumPy, Statsmodels (OLS Regression).
*   **AI Engine**: Scikit-learn (RandomForestClassifier).
*   **Automation**: Windows Task Scheduler (Hourly execution, staggered by 5 minutes between accounts).

---

## 📈 Trading Strategies
The desk runs three distinct strategies simultaneously to diversify risk.

### 1. Pairs Trading (Mean Reversion)
*   **Logic**: Uses OLS Regression to find cointegration between `EURUSD` and `GBPUSD`.
*   **Signal**: Triggers when the Z-Score of the spread exceeds **2.0** (Sell Spread) or falls below **-2.0** (Buy Spread).
*   **Exit**: Closes when Z-Score reverts to **0.2** or hits a **40-pip TP**.
*   **Magic Number**: `222`

### 2. Donchian Breakout (Trend Following)
*   **Logic**: Monitors a 400-hour price channel.
*   **Signal**: Buys on a break above the 400-hour high; Sells on a break below the 400-hour low.
*   **Exit**: 200-hour trailing exit or a **1:2 Risk/Reward TP**.
*   **Magic Number**: `333`

### 3. Quant Predictor (AI / Machine Learning)
*   **Logic**: A Random Forest model trained on RSI, Volatility, and Momentum indicators.
*   **Signal**: Predicts the direction of the next 4-hour candle for `EURUSD` and `USDJPY`.
*   **Confidence**: Requires a **58% confidence threshold** to execute a trade.
*   **Magic Number**: `111`

---

## 🛡️ Prop Firm Safety Shields (GFT Compliance)
To protect the account from breaches and "Black Swan" events, the system includes:

1.  **High-Impact News Filter**: Skips trades 30 minutes before and after "Red Folder" news events for USD, EUR, and GBP (using MT5 Calendar API).
2.  **Daily Drawdown Kill-Switch**: Monitors equity in real-time. If the daily loss exceeds **3.5%**, it immediately closes all trades and locks the account for the remainder of the day.
3.  **Friday Safety**: (Currently **DISABLED** by user request) Previously closed all trades on Friday evening. Now allowed to run through the weekend to capture trend momentum.

---

## ⚙️ Maintenance & Logs
*   **Environment Settings**: Managed via `.env` in each folder.
*   **Signal Logs**: `logs/signal_history.txt` (Records every analysis cycle).
*   **Trade History**: Recorded in the MT5 terminal and exported periodically to Excel for analysis.

## 🚀 Future AI Instructions
When starting a new session with an AI assistant:
1.  Reference this `Forex_Trading_Desk_Manual.md` file.
2.  Ensure any changes are applied to **BOTH** the 5k and 10k directories.
3.  Check the `mt5_executor.py` for trade execution logic before modifying strategy entry rules.
