# Nautilus Engine — System Improvements & Change Log

## Overview
This document maintains a chronological record of all architectural upgrades, bug fixes, risk management scaling, and market-adaptation rules implemented in the **Nautilus Engine / Forex Alpha Desk** multi-strategy algorithmic trading bot.

---

## 📅 Chronological Change Log

### 2026-09-30: 80% Breakeven Lock Threshold & ADX Trend Gate on GBPJPY

1. **Refined Breakeven Lock from 70% to 80% (`apply_ai_breakeven_stops`)**:
   - **Reason**: Live trade audit of September 23–26 revealed that setting the threshold to 70% was prematurely truncating winning trades during mid-expansion pullbacks (e.g. EURUSD on 5K was stopped out at +1.2 pips for +$0.59, missing a +35 pip drop to full TP that 10K captured for +$52.56).
   - **Fix**: Adjusted the trigger threshold across all three desks (`Desk-5k`, `Desk-10k`, and `Desk-JPY`) from `0.70` to `0.80`. Trades now have wider breathing room through standard 10–15 pip retests and only lock to Breakeven (+1 pip) during late-stage moves toward TP.

2. **Added 14-Period ADX Momentum Filter to Strategy 2 (GBPJPY Breakout)**:
   - **Reason**: Performance analysis showed GBPJPY suffered consecutive stop-outs (-$89.90 on 10K) when taking breakouts during low-volatility consolidation ranges where 24-hour channel extremes were poked by minor wicks.
   - **Fix**: Implemented Welles Wilder's `calculate_adx(gbpjpy_df, period=14)` in `get_current_signal.py`. Gated both BUY and SELL breakout executions with `adx_val >= 25.0`. When `ADX < 25`, breakout signals are safely filtered out, preventing chop and false-break losses while preserving execution during true trending expansions.

---

### 2026-09-15: AI Quant Strategy Risk Re-alignment

1. **Widened AI Quant Stop Loss (1.2x ATR ➔ 2.5x ATR)**:
   - **Reason**: Following the September 14th removal of the 4-hour time stop, holding trades open indefinitely with a tight 1.2x ATR Stop Loss resulted in premature stop-outs from normal intraday market noise. To allow trades to develop naturally toward their 1:1.5 R:R targets without time constraints, they require standard "breathing room".
   - **Fix**: Updated `dynamic_sl` multiplier in `get_current_signal.py` from `1.2` to `2.5`. This protects trades against structural reversals while providing enough leeway to survive standard intraday pullbacks.

---

### 2026-09-14: Deployment of Approach 2 (Pure SL/TP, 70% Breakeven Lock & Early Reversal Exit)

1. **Retirement of Naive 4-Hour Time-Based Cutoff & 1-Hour Cooldown**:
   - **Problem**: Analysis of live execution revealed that the fixed 4-hour age cutoff (`close_expired_ai_positions`) prematurely truncated winning trades (e.g., closing USDJPY at +27 pips when only 20 pips away from the 47-pip TP target). The subsequent 1-hour cooldown locked the desk out, after which the model re-entered the exact same trend at a worse price, incurring double spread and execution commission fees.
   - **Fix**: Retired the arbitrary 4-hour time stop in `mt5_executor.py` and `get_current_signal.py`. Deactivated the 1-hour post-expiration re-entry cooldown. Trades now develop naturally towards their calculated 1:1.5 Risk-to-Reward targets.

2. **Automated 70% Progress Breakeven Stop-Loss Lock (`apply_ai_breakeven_stops`)**:
   - **Mechanism**: Every hourly cycle, the engine inspects all active AI positions (`magic=111`). When a position achieves **>= 70% progress towards its Take Profit** (`(price - entry) / (tp - entry) >= 0.70`), the engine automatically modifies the Stop Loss in MT5 to `Entry Price ± 1 pip`.
   - **Advantage Over Tight Breakeven**: Setting the threshold to 70% rather than 30-50% protects winning trades from premature stop-outs during standard 10-15 pip market retests/pullbacks, while guaranteeing that any trade reaching the late expansion phase becomes 100% risk-free.

3. **High-Confidence Early Reversal Exit**:
   - **Mechanism**: If an AI position is already open and a new hourly cycle generates a high-confidence signal in the **OPPOSITE direction** (`probability >= ML_CONFIDENCE_THRESHOLD`) confirmed by the 20 EMA trend filter, the engine executes an immediate market exit (`execute_mt5_trade('AI', 'EXIT', symbol=asset)`), dispatches a Telegram alert, and opens the new reversed position.
   - **Impact**: Provides an intelligent, signal-driven exit without holding positions against confirmed macro reversals.

4. **Synchronized Multi-Desk Deployment**:
   - Applied and verified across both `Desk-5k` and `Desk-10k` with full MT5 IPC isolation.

---

### 2026-09-10: Strategic Transition to Multi-Pair AI Desk (Path 2) & Z-Score Retirement

1. **Retirement of Strategy 1 (Z-Score Pairs Arbitrage)**:
   - **Reason**: Quantitative analysis of 260+ closed trades (May–September 2026) revealed that Strategy 1 was unprofitable (Profit Factor 0.70 – 0.81) and caused a cumulative loss drag of **-$423.64** across both accounts due to double-spread friction, swap fees, and macroeconomic non-cointegration between EUR and GBP.
   - **Action**: Completely deactivated Z-Score paired entry execution in `get_current_signal.py`. Added auto-exit fail-safe for any lingering legacy pairs positions.

2. **Expansion of Strategy 3 (AI Quant Predictor) to Multi-Pair Desk (`USDJPY`, `EURUSD`, `GBPUSD`)**:
   - **Walk-Forward Validation**: 1,500-bar out-of-sample backtest demonstrated consistent predictive accuracy across majors: **EURUSD (54.9%)**, **GBPUSD (53.7%)**, and **USDJPY (53.1%)**.
   - **Execution Model**: All 3 pairs now trade independently with single-direction execution, dynamic ATR targets (1.2x ATR Stop Loss, 1.8x ATR Take Profit = 1:1.5 R:R), 4-hour time-stop expiration, and 1-hour post-expiration cooldown. Minimum safety Stop Loss is set to 20 pips for JPY pairs and 15 pips for EURUSD/GBPUSD.

3. **Risk Budget Reallocation & Lot Size Tuning**:
   - **10k Account**: `LOT_SIZE_AI = 0.15` (spread across USDJPY, EURUSD, GBPUSD), `LOT_SIZE_TREND = 0.14` (GBPJPY Swing). Max risk per trade ~0.35% - 0.45%.
   - **5k Account**: `LOT_SIZE_AI = 0.08`, `LOT_SIZE_TREND = 0.08`. Max risk per trade ~0.35% - 0.45%.
   - Total portfolio risk is calibrated for institutional FTMO $100k requirements, keeping daily drawdown far below the 4-5% threshold.

4. **Dynamic Fill-Price Anchoring for AI Quant Trades**:
   - **Problem**: Previously, AI Stop Loss and Take Profit levels were calculated relative to the past H1 candle close (`asset_df['Close'].iloc[-1]`). Because the Task Scheduler executes at XX:21 (21 minutes past the hour), price movement during those 21 minutes distorted the fill-relative distances (e.g. producing 19-pip TP and 62-pip SL on USDJPY).
   - **Fix**: Updated `get_current_signal.py` to calculate dynamic target distances (`dynamic_sl`, `dynamic_tp = dynamic_sl * 1.5`) and pass `sl_dist` and `tp_dist` directly to `mt5_executor.py`. `execute_mt5_trade()` now anchors SL and TP directly to the **live execution fill price (`price`)** at the exact millisecond the order fills.
   - **Impact**: Guarantees an exact, uncompromised **1 : 1.5 Risk-to-Reward ratio** for every AI trade relative to the actual fill price.

---

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

### 2026-09-21: Bar 1 (Closed Candle) Evaluation & Schedule Alignment

1. **Closed Candle Ingestion (`start_pos = 1`)**:
   - **Problem**: Previously, `fetch_mt5_data()` fetched candles starting from `start_pos = 0` (the currently forming, unclosed H1 candle). Because Desk-5k ran at `:20` and Desk-10k ran at `:22`, the two desks evaluated different intra-candle ticks. Single-tick price shifts caused non-linear probability jumps in `GradientBoostingClassifier` (e.g. USDJPY confidence leaping from 56.4% to 70.0% in 2 minutes), causing one account to trade while the other sat out.
   - **Fix**: Updated `copy_rates_from_pos` to `start_pos = 1` across all data fetches, ensuring the engine exclusively evaluates confirmed, fully closed H1 bars. In the tick resampling fallback, dropped the current forming candle (`df.iloc[:-1]`).
   - **Impact**: Guarantees 100% data parity and deterministic signals across all desks, eliminates covariate shift (model was trained on closed bars), and prevents false breakout wicks in Strategy 4.

2. **Automation Timing Alignment (`XX:01` & `XX:02`)**:
   - **Fix**: Updated `setup_automation.bat` and active Windows Task Scheduler entries:
     - `Forex-Bot-5k`: Runs hourly at `XX:01` (1 minute after candle close).
     - `Forex-Bot-10k`: Runs hourly at `XX:02` (2 minutes after candle close).
   - **Impact**: Evaluates the newly closed candle immediately upon hour completion and enters trades at the open of the new bar with zero lag.

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
