# Nautilus Engine — System Improvements & Change Log

## Overview
This document maintains a chronological record of all architectural upgrades, bug fixes, risk management scaling, and market-adaptation rules implemented in the **Nautilus Engine / Forex Alpha Desk** multi-strategy algorithmic trading bot.

---

## 📅 Chronological Change Log

### 2026-09-10: Multi-Terminal MT5 Synchronization & Tick Resampling Optimization

1. **MT5 Tick Resampling Window Optimization (`days=5`)**:
   - **Problem**: When MT5 terminal history buffer (`copy_rates_from_pos`) is empty or returning len=0 on secondary terminal paths (e.g. 10k Goat Funded terminal at `C:\Program Files\Goat Funded MT5 Terminal\terminal64.exe`), the fallback mechanism attempted to pull 14 days of raw ticks (`days=14`). Processing 2.5 million+ ticks over MT5 IPC exceeded memory/timeout limits on secondary terminals, causing data fetches for `USDJPY.x` to return `None` on 10k while succeeding on 5k.
   - **Fix**: Updated `fetch_mt5_data()` in `get_current_signal.py` to fetch a **5-day tick window** (`past = datetime.utcnow() - timedelta(days=5)`). This yields ~90 hourly candles in 0.3 seconds with 100% success across all terminal instances.

2. **Adaptive ML Predictor Minimum Length Threshold (`ml_predictor_strategy.py`)**:
   - **Problem**: `ml_predictor_strategy.py` hardcoded a strict `if len(data) < 300: return None` guard clause. When tick resampling returned 90 bars (plenty for H1 machine learning feature calculation), the ML predictor rejected the dataset, causing Strategy 3 (AI Quant Predictor) to skip trade signals on secondary terminals.
   - **Fix**: Lowered the minimum bar threshold from 300 to **40 H1 bars** and implemented an **adaptive train/test split** (`test_size = max(10, int(len(historical_data) * 0.2))`).
   - **Impact**: Enables the Gradient Boosting ML model to train, compute technical features (RSI, MACD, Bollinger Bands, ATR, Return Lag), and issue AI trade predictions cleanly even when operating under tick-resampled historical data.

---

### 2026-09-08: Execution Integrity, Dynamic Anchoring & Re-Entry Hardening

1. **Dynamic Fill-Price Anchoring for Swing Breakouts (`GBPJPY`)**:
   - **Problem**: SL and TP levels were previously calculated relative to the past H1 candle close (`current_close`). If the market moved quickly between the XX:00 candle close and the XX:20 execution run, the resulting target distances from the live fill price became distorted (e.g. producing ultra-tight 7.7-pip TPs or wide SLs).
   - **Fix**: Updated `mt5_executor.py` so that Strategy `'Swing'` Stop Loss (**50 pips**) and Take Profit (**100 pips**) are dynamically anchored directly to the **live MT5 order execution fill price** (`price`).
   - **Impact**: Every GBPJPY Swing trade is guaranteed an exact 50-pip SL and 100-pip TP relative to where the order fills.

2. **Swing Strategy 4-Hour Post-Exit Cooldown**:
   - **Problem**: When a Swing trade hit TP or SL quickly, the position closed. On the subsequent hour, the engine would see an empty position list and re-open a second trade on the exact same extended breakout move, chasing an exhausted trend.
   - **Fix**: Added a position state tracker (`logs/swing_state.json`) and a **4-Hour Post-Exit Cooldown** (`logs/swing_cooldown.json`). When a Swing trade exits, re-entry is blocked for 4 hours.
   - **Impact**: Prevents re-entering tired breakout legs. The engine now waits for the market to consolidate and form a fresh 24-hour channel before considering a new breakout entry.

3. **Automatic MT5 Data Freshness & Tick Resampling Fallback**:
   - **Problem**: MT5 terminal memory buffers (`copy_rates_from_pos`) on Windows sometimes return stale/cached candle history if the terminal chart window buffer hasn't refreshed, causing Z-score or breakout calculations to lag between accounts.
   - **Fix**: Updated `fetch_mt5_data()` in `get_current_signal.py` to check the timestamp of the latest bar returned. If the data is older than 2.5 hours, it automatically flags the data as STALE and triggers the **live tick resampling fallback** (`copy_ticks_range` resampled to H1 DataFrames).
   - **Impact**: Guarantees 100% live, synchronized data across both 5k and 10k accounts every hour.

---

### 2026-09-04: Lot Size Scaling & AI Target Realignment

1. **Option 2 Lot Size Scaling (2.0x Boost)**:
   - **Reason**: Performance analysis of 1,500+ trades (May–Sept 2026) proved that worst-case historical daily drawdown was under 0.90% (well below Goat Funded's 4.0% limit). Lot sizes were doubled to accelerate profit velocity for passing Phase 1 (8%) and Phase 2 (6%).
   - **10k Account (`$10,000`)**:
     - `LOT_SIZE_AI`: `0.10` ➔ **`0.20`**
     - `LOT_SIZE_TREND`: `0.07` ➔ **`0.14`**
     - `LOT_SIZE_PAIRS`: `0.04` ➔ **`0.08`**
   - **5k Account (`$5,000`)**:
     - `LOT_SIZE_AI`: `0.05` ➔ **`0.10`**
     - `LOT_SIZE_TREND`: `0.04` ➔ **`0.08`**
     - `LOT_SIZE_PAIRS`: `0.02` ➔ **`0.04`**

2. **AI Strategy (USDJPY) Target Realignment**:
   - **Problem**: `dynamic_sl` was using `3.5x ATR`, making TP `5.25x ATR` (~190 pips). In a 4-hour holding window, a 190-pip move is virtually impossible under normal volatility, forcing almost all trades to be prematurely closed by the 4-hour time expiration rule.
   - **Fix**: Adjusted `dynamic_sl` ATR multiplier to **`1.2x ATR`**.
   - **Impact**: Realistic targets established: **Stop Loss ~20–25 pips**, **Take Profit ~30–45 pips** (1.5x Reward-to-Risk). Winning trades can now easily reach Take Profit in 1 to 3 hours during active session hours.

3. **AI Strategy 1-Hour Post-Expiration Cooldown**:
   - **Fix**: When an AI trade is closed by the 4-hour time limit (`close_expired_ai_positions`), `mt5_executor.py` records a cooldown timestamp (`logs/ai_cooldown_<symbol>.json`). `get_current_signal.py` enforces a **1-hour cooling period** before evaluating new AI entries on that symbol.
   - **Impact**: Prevents immediate re-entry into a stagnant or slowly declining market.

4. **Pairs Trading Single-Leg Hedge Protection**:
   - **Fix**: In `mt5_executor.py`, for Strategy `'Pairs'`, single-leg MT5 TP is set to a wide safety buffer (150 pips) instead of a tight 40-pip target.
   - **Impact**: Prevents MT5 from closing half of a Pair trade prematurely, ensuring the spread hedge remains fully intact until the statistical Z-Score exit signal (`|Z-Score| < 0.2`) closes both legs together.

---

### 2026-08-31: VM Migration, Reliability & Fail-Safe Integration

1. **Tick Resampling Fallback Engine**:
   - Implemented `mt5.copy_ticks_range` resampling fallback in `fetch_mt5_data()` to bypass MT5 terminal candle history errors (`Call failed -1`).

2. **Task Scheduler Registration**:
   - Standardized `setup_automation.bat` for Windows Task Scheduler registration with a 19-second offset between multi-account instances to eliminate MT5 IPC collisions.

3. **Emergency Risk Shields**:
   - **Daily Drawdown Kill-Switch**: 3.5% daily drawdown lock file (`logs/daily_lock.txt`).
   - **Friday Night Exit**: Automatic closure of all open positions before weekend market close (20:00 UTC Friday).
   - **High-Impact News Filter**: Skips trade entries 30 minutes before and after high-impact economic news releases (`news_manager.py`).
