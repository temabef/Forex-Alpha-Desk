import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import pandas as pd
import numpy as np
import asyncio
from telegram import Bot
from datetime import datetime, timezone
from mt5_executor import execute_mt5_trade, get_mt5_active_positions, close_all_active_positions
import os
import json
from dotenv import load_dotenv
import MetaTrader5 as mt5
from news_manager import is_in_danger_zone

# Load secrets from .env file
load_dotenv()

# --- PATH FIX FOR BACKGROUND TASKS ---
# This ensures the script always runs in its own folder
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# --- RISK CONFIGURATION (For $10k Prop Account) ---
ENTRY_THRESHOLD = 2.0
EXIT_THRESHOLD = 0.2
ML_CONFIDENCE_THRESHOLD = 0.62 
LOT_SIZE_AI = float(os.getenv("LOT_SIZE_AI", 0.05))
LOT_SIZE_PAIRS = float(os.getenv("LOT_SIZE_PAIRS", 0.02))
LOT_SIZE_TREND = float(os.getenv("LOT_SIZE_TREND", 0.05))

def log_to_file(message):
    with open("logs/signal_history.txt", "a", encoding="utf-8") as f:
        f.write(message + "\n")

async def send_telegram_msg(message):
    if TELEGRAM_CHAT_ID == "PASTE_YOUR_CHAT_ID_HERE":
        print("⚠️ Telegram Chat ID not set. Skipping notification.")
        return
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")
        print("Telegram notification sent!")
    except Exception as e:
        print(f"FAILED to send Telegram: {e}")

def fetch_mt5_data(symbol, num_bars=1500):
    """
    Fetches the latest H1 (Hourly) candle data directly from MT5.
    """
    terminal_path = os.getenv("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
    if not mt5.initialize(path=terminal_path):
        print(f"MT5 initialize() failed for data fetch")
        return None
        
    # Append broker suffix if necessary (e.g. .x)
    suffix = os.getenv("SYMBOL_SUFFIX", "")
    broker_symbol = f"{symbol}{suffix}"
        
    rates = mt5.copy_rates_from_pos(broker_symbol, mt5.TIMEFRAME_H1, 0, num_bars)
    if rates is None or len(rates) == 0:
        print(f"Failed to fetch data for {broker_symbol}")
        return None
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)
    return df

def check_daily_drawdown():
    """
    Checks if the account has hit the daily drawdown limit.
    """
    max_drawdown_pct = float(os.getenv("MAX_DAILY_DRAWDOWN_PCT", 0.035))
    lock_file = "logs/daily_lock.txt"
    balance_file = "logs/daily_start_balance.json"
    
    # 1. Check if we are already locked out for today
    today_str = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(lock_file):
        with open(lock_file, "r") as f:
            lock_date = f.read().strip()
            if lock_date == today_str:
                return True, "Account is locked due to daily drawdown breach."

    # 2. Initialize MT5
    terminal_path = os.getenv("MT5_TERMINAL_PATH")
    if not mt5.initialize(path=terminal_path):
        return False, "MT5 Init Failed"

    account_info = mt5.account_info()
    if not account_info:
        return False, "Could not fetch account info"

    # 3. Manage Daily Starting Balance
    start_balance = account_info.balance
    if os.path.exists(balance_file):
        try:
            with open(balance_file, "r") as f:
                data = json.load(f)
                if data.get("date") == today_str:
                    start_balance = data.get("balance")
                else:
                    # New Day - Update balance
                    with open(balance_file, "w") as fw:
                        json.dump({"date": today_str, "balance": account_info.balance}, fw)
        except:
            # Fallback if file is corrupted
            with open(balance_file, "w") as fw:
                json.dump({"date": today_str, "balance": account_info.balance}, fw)
    else:
        # First Run ever
        with open(balance_file, "w") as fw:
            json.dump({"date": today_str, "balance": account_info.balance}, fw)

    # 4. Calculate Drawdown
    current_equity = account_info.equity
    drawdown_pct = (start_balance - current_equity) / start_balance
    
    if drawdown_pct >= max_drawdown_pct:
        # BREACH DETECTED
        with open(lock_file, "w") as f:
            f.write(today_str)
        return True, f"DAILY DRAWDOWN BREACH: {drawdown_pct*100:.2f}% (Limit: {max_drawdown_pct*100:.2f}%). Closing all trades."

    return False, ""

def is_friday_night():
    """
    Checks if it's Friday after 20:00 GMT.
    """
    if os.getenv("ENABLE_FRIDAY_EXIT", "True") != "True":
        return False
        
    now_utc = datetime.now(timezone.utc)
    # Friday = 4
    if now_utc.weekday() == 4 and now_utc.hour >= 20:
        return True
    return False

async def get_signal():
    # Defer heavy imports to save RAM on startup
    import statsmodels.api as sm
    from ml_predictor_strategy import get_ml_prediction
    
    print(f"--- Multi-Strategy Live Signal Report ---")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    log_to_file("--- Multi-Strategy Live Signal Report ---")
    log_to_file(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # --- SHIELD 1: DAILY DRAWDOWN KILL-SWITCH ---
    is_breached, breach_msg = check_daily_drawdown()
    if is_breached:
        print(f"🛑 {breach_msg}")
        log_to_file(f"KILL-SWITCH: {breach_msg}")
        await send_telegram_msg(f"🛑 *EMERGENCY KILL-SWITCH*\n{breach_msg}")
        close_all_active_positions()
        return

    # --- SHIELD 2: FRIDAY MARKET CLOSE ---
    if is_friday_night():
        print("📅 Friday 20:00 GMT Reached. Closing all positions for the weekend.")
        log_to_file("FRIDAY EXIT: Closing all positions.")
        await send_telegram_msg("📅 *FRIDAY EXIT*\nClosing all positions for the weekend. See you Sunday night!")
        close_all_active_positions()
        return

    # --- SHIELD 3: HIGH-IMPACT NEWS FILTER ---
    in_danger, news_msg = is_in_danger_zone()
    if in_danger:
        print(f"⚠️ {news_msg}")
        log_to_file(f"NEWS FILTER: {news_msg}")
        # We don't exit the script, but we will pass a flag to strategies to skip ENTRIES
        # Actually, for prop firm safety, let's just skip the entire execution this hour
        await send_telegram_msg(f"⚠️ *NEWS DANGER ZONE*\n{news_msg}\n\nExecution skipped for this hour.")
        return

    # --- SHIELD 4: AI TRADE EXPIRATION CLOSE (4-HOUR MAX HOLD) ---
    try:
        from mt5_executor import close_expired_ai_positions
        close_expired_ai_positions()
    except Exception as e:
        print(f"⚠️ Error running expired AI close: {e}")

    # --- SYMBOL CONFIG ---
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "GBPJPY"]
    raw_data = {}

    # Fetch recent data directly from MT5 (1500 bars ~ 60 trading days of H1)
    for symbol in symbols:
        print(f"Fetching latest data for {symbol} from MT5...")
        df = fetch_mt5_data(symbol, num_bars=1500)
        if df is None or df.empty or len(df) < 60:
            print(f"⚠️ WARNING: Not enough data for {symbol} in MT5. Skipping strategy logic.")
            continue
        raw_data[symbol] = df

    print("\n" + "="*40)
    print("STRATEGY 1: PAIRS TRADING (Mean Reversion)")
    print("="*40)
    
    # --- CHECK ACTIVE POSITIONS FOR PAIRS ---
    active_positions = get_mt5_active_positions(strategy_name='Pairs')
    print(f"INFO: MT5 Active positions for Pairs: {active_positions}")
    
    # --- SAFETY CHECK: Ensure both symbols exist in raw_data ---
    if "EURUSD" not in raw_data or "GBPUSD" not in raw_data:
        print("⚠️ SKIPPING Strategy 1 (Pairs): Missing data for EURUSD or GBPUSD.")
    else:
        df_combined = pd.concat([raw_data["EURUSD"]["Close"], raw_data["GBPUSD"]["Close"]], axis=1).dropna()
        df_combined.columns = ["EURUSD", "GBPUSD"]
        
        lookback_pairs = 60 
        if len(df_combined) >= lookback_pairs:
            recent = df_combined.tail(lookback_pairs)
            y = recent["EURUSD"].values
            x = sm.add_constant(recent["GBPUSD"].values)
            model = sm.OLS(y, x).fit()
            
            intercept = model.params[0]
            gamma = model.params[1]
            
            spreads = y - (gamma * recent["GBPUSD"].values + intercept)
            current_spread = spreads[-1]
            mean_spread = np.mean(spreads)
            std_spread = np.std(spreads)
            z_score = (current_spread - mean_spread) / std_spread
            eur_price = recent['EURUSD'].iloc[-1]
            gbp_price = recent['GBPUSD'].iloc[-1]

            print(f"Current Z-Score: {z_score:.2f}")
            
            if z_score > ENTRY_THRESHOLD:
                # Only send SELL signal if we DON'T have a position (Case-Insensitive check)
                if not any(pos.upper() == "EURUSD" for pos in active_positions):
                    msg = f"🚨 *SIGNAL: SELL SPREAD*\n⚖️ Pairs Trading (Mean Reversion)\nZ-Score: `{z_score:.2f}`\nEURUSD: `{eur_price:.5f}`\nGBPUSD: `{gbp_price:.5f}`\nAction: SELL EURUSD, BUY GBPUSD"
                    log_to_file(f"Pairs: SELL SPREAD Signal Sent (Z-Score: {z_score:.2f})")
                    await send_telegram_msg(msg)
                    execute_mt5_trade('Pairs', 'SELL', symbol='EURUSD', volume=LOT_SIZE_PAIRS)
                    execute_mt5_trade('Pairs', 'BUY', symbol='GBPUSD', volume=LOT_SIZE_PAIRS)
                else:
                    log_to_file(f"Pairs: Z-Score={z_score:.2f} (Already in trade - suppressing alert)")
                    print("Pairs: Already in trade, suppressing duplicate SELL alert.")
            elif z_score < -ENTRY_THRESHOLD:
                # Only send BUY signal if we DON'T have a position
                if not any(pos.upper() == "EURUSD" for pos in active_positions):
                    msg = f"🚀 *SIGNAL: BUY SPREAD*\n⚖️ Pairs Trading (Mean Reversion)\nZ-Score: `{z_score:.2f}`\nEURUSD: `{eur_price:.5f}`\nGBPUSD: `{gbp_price:.5f}`\nAction: BUY EURUSD, SELL GBPUSD"
                    log_to_file(f"Pairs: BUY SPREAD Signal Sent (Z-Score: {z_score:.2f})")
                    await send_telegram_msg(msg)
                    execute_mt5_trade('Pairs', 'BUY', symbol='EURUSD', volume=LOT_SIZE_PAIRS)
                    execute_mt5_trade('Pairs', 'SELL', symbol='GBPUSD', volume=LOT_SIZE_PAIRS)
                else:
                    log_to_file(f"Pairs: Z-Score={z_score:.2f} (Already in trade - suppressing alert)")
                    print("Pairs: Already in trade, suppressing duplicate BUY alert.")
            elif abs(z_score) < EXIT_THRESHOLD:
                # Only send EXIT signal if we actually have a position! (Case-Insensitive)
                if any(pos.upper() in ["EURUSD", "GBPUSD"] for pos in active_positions):
                    msg = f"✅ *TARGET REACHED / EXIT*\n⚖️ Pairs Trading (Mean Reversion)\nZ-Score: `{z_score:.2f}`\nEURUSD: `{eur_price:.5f}`\nGBPUSD: `{gbp_price:.5f}`\n\nAction: CLOSE both Pair positions."
                    print("RECOMMENDATION: EXIT (Target Reached)")
                    log_to_file(f"Pairs: TARGET REACHED / EXIT Signal Sent (Z-Score: {z_score:.2f})")
                    await send_telegram_msg(msg)
                    execute_mt5_trade('Pairs', 'EXIT', symbol='EURUSD')
                    execute_mt5_trade('Pairs', 'EXIT', symbol='GBPUSD')
                else:
                    log_to_file(f"Pairs: Z-Score={z_score:.2f} (Target reached but no active position)")
                    print("Pairs: Target reached but no active position found. Skipping alert.")
            else:
                log_to_file(f"Pairs: Z-Score={z_score:.2f} (WAIT)")
                print("RECOMMENDATION: WAIT (No signal)")

    print("\n" + "="*40)
    print("STRATEGY 2: DONCHIAN BREAKOUT (Trend)")
    print("="*40)
    
    eurusd_df = raw_data["EURUSD"].dropna()
    
    # --- CHECK ACTIVE POSITIONS FOR TREND ---
    active_positions = get_mt5_active_positions(strategy_name='Trend')
    print(f"INFO: MT5 Active positions for Trend: {active_positions}")
    entry_lookback = 400
    exit_lookback = 200 
    
    if len(eurusd_df) >= entry_lookback + 1:
        highs = eurusd_df['High'].values
        lows = eurusd_df['Low'].values
        closes = eurusd_df['Close'].values
        
        recent_highs = highs[-entry_lookback - 1 : -1]
        recent_lows = lows[-entry_lookback - 1 : -1]
        upper_channel = np.max(recent_highs)
        lower_channel = np.min(recent_lows)
        
        exit_recent_highs = highs[-exit_lookback - 1 : -1]
        exit_recent_lows = lows[-exit_lookback - 1 : -1]
        exit_upper = np.max(exit_recent_highs)
        exit_lower = np.min(exit_recent_lows)
        
        current_close = closes[-1]
        
        print(f"Close: {current_close:.5f} | Upper: {upper_channel:.5f} | Lower: {lower_channel:.5f}")
        
        if current_close > upper_channel:
            # Case-Insensitive check
            if not any(pos.upper() == "EURUSD" for pos in active_positions):
                sl_price = lower_channel
                max_sl_dist = 50 * 0.0001
                if current_close - sl_price > max_sl_dist:
                    sl_price = current_close - max_sl_dist
                
                tp_dist = 70 * 0.0001
                tp_price = current_close + tp_dist
                trend_report = f"📈 *SIGNAL: BREAKOUT LONG*\nEntry: `{current_close:.5f}`\nSL: `{sl_price:.5f}`\nTP: `{tp_price:.5f}`"
                log_to_file(f"Trend: BREAKOUT LONG Signal Sent (Price: {current_close:.5f})")
                await send_telegram_msg(trend_report)
                execute_mt5_trade('Trend', 'BUY', symbol='EURUSD', volume=LOT_SIZE_TREND, sl=sl_price, tp=tp_price)
            else:
                print("Trend: Breakout detected but Trend position already open. Skipping.")
        elif current_close < lower_channel:
            # Case-Insensitive check
            if not any(pos.upper() == "EURUSD" for pos in active_positions):
                sl_price = upper_channel
                max_sl_dist = 50 * 0.0001
                if sl_price - current_close > max_sl_dist:
                    sl_price = current_close + max_sl_dist
                
                tp_dist = 70 * 0.0001
                tp_price = current_close - tp_dist
                trend_report = f"🔴 *SIGNAL: BREAKOUT SHORT*\nEntry: `{current_close:.5f}`\nSL: `{sl_price:.5f}`\nTP: `{tp_price:.5f}`"
                log_to_file(f"Trend: BREAKOUT SHORT Signal Sent (Price: {current_close:.5f})")
                await send_telegram_msg(trend_report)
                execute_mt5_trade('Trend', 'SELL', symbol='EURUSD', volume=LOT_SIZE_TREND, sl=sl_price, tp=tp_price)
            else:
                print("Trend: Breakout detected but Trend position already open. Skipping.")
        elif current_close < exit_lower or current_close > exit_upper:
            trend_report = f"🛑 *TREND EXIT ALERT*\nClose: `{current_close:.5f}`\nAction: Consider CLOSING Trend trades."
            log_to_file("Trend: EXIT ALERT Sent")
            await send_telegram_msg(trend_report)
            execute_mt5_trade('Trend', 'EXIT', symbol='EURUSD')
        else:
            log_to_file(f"Trend: Inside Channel (High: {upper_channel:.5f}, Low: {lower_channel:.5f})")
            print("RECOMMENDATION: WAIT (Inside channel)")

    print("\n" + "="*40)
    print("STRATEGY 3: QUANT PREDICTOR (Multi-Pair AI)")
    print("="*40)
    
    current_utc_hour = datetime.utcnow().hour
    if not (7 <= current_utc_hour <= 17):
        print(f"⚠️ AI Strategy inactive outside London/NY hours (Current UTC hour: {current_utc_hour}).")
        log_to_file(f"AI: Skipping execution, outside active session (hour {current_utc_hour})")
    else:
        for asset in ["USDJPY"]:
            if asset not in raw_data:
                print(f"⚠️ SKIPPING AI analysis for {asset}: Missing data.")
                continue
                
            print(f"\nAnalyzing {asset}...")
            asset_df = raw_data[asset].dropna()
            prediction, probability, est_win_rate = get_ml_prediction(asset_df)
            
            if prediction is not None:
                print(f"AI Prediction for {asset}: {'UP' if prediction == 1 else 'DOWN'}")
                print(f"Confidence: {probability*100:.1f}%")
                print(f"Estimated Walk-Forward Win Rate: {est_win_rate*100:.1f}%")
                
                # Calculate Dynamic TP/SL based on Asset Volatility (ATR)
                recent_24 = asset_df.tail(24)
                atr = (recent_24['High'] - recent_24['Low']).mean()
                
                # Increase ATR multiplier to give trades breathing room (3.5x ATR instead of 1.2x)
                dynamic_sl = atr * 3.5
                
                # Enforce a minimum safety SL of 20 pips to avoid instant stop-outs during low-volatility hours
                pip_size = 0.01 if "JPY" in asset else 0.0001
                min_sl_dist = 20 * pip_size
                if dynamic_sl < min_sl_dist:
                    dynamic_sl = min_sl_dist
                    
                dynamic_tp = dynamic_sl * 1.5
                current_price = asset_df['Close'].iloc[-1]
                
                if probability >= ML_CONFIDENCE_THRESHOLD:
                    if est_win_rate < 0.42:
                        log_to_file(f"AI ({asset}): Estimated win rate too low ({est_win_rate*100:.1f}%). Threshold: 42%. Skipping.")
                        print(f"AI ({asset}): Estimated win rate too low ({est_win_rate*100:.1f}%). Skipping.")
                        continue
                    
                    direction = "BULLISH (UP)" if prediction == 1 else "BEARISH (DOWN)"
                    
                    # EMA-20 Confirmation
                    ema_20 = asset_df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                    if prediction == 1 and current_price < ema_20:
                        log_to_file(f"AI ({asset}): Signal UP rejected: Price ({current_price:.5f}) < EMA-20 ({ema_20:.5f}).")
                        print(f"AI ({asset}): Signal UP rejected (Price < EMA-20).")
                        continue
                    elif prediction == 0 and current_price > ema_20:
                        log_to_file(f"AI ({asset}): Signal DOWN rejected: Price ({current_price:.5f}) > EMA-20 ({ema_20:.5f}).")
                        print(f"AI ({asset}): Signal DOWN rejected (Price > EMA-20).")
                        continue
                        
                    icon = "🚀" if prediction == 1 else "📉"
                    
                    if prediction == 1: # UP
                        tp_level = current_price + dynamic_tp
                        sl_level = current_price - dynamic_sl
                    else: # DOWN
                        tp_level = current_price - dynamic_tp
                        sl_level = current_price + dynamic_sl
                    
                    # --- PIP CALCULATION (JPY vs Normal) ---
                    pip_multiplier = 100 if "JPY" in asset else 10000
                    tp_pips = int(dynamic_tp * pip_multiplier)
                    sl_pips = int(dynamic_sl * pip_multiplier)

                    # --- CHECK ACTIVE POSITIONS FOR THIS STRATEGY ---
                    active_positions = get_mt5_active_positions(strategy_name='AI')
                    
                    if not any(pos.upper() == asset.upper() for pos in active_positions):
                        # Format based on JPY
                        p_fmt = ".2f" if "JPY" in asset else ".5f"
                        ml_report = (
                            f"{icon} *Quant Predictor (Adaptive AI)*\n"
                            f"Asset: `{asset}`\n"
                            f"Prediction: `{direction}`\n"
                            f"Confidence: `{probability*100:.1f}%`\n"
                            f"Price: `{current_price:{p_fmt}}`\n\n"
                            f"🎯 *Adaptive Targets:* \n"
                            f"TP: `{tp_level:{p_fmt}}` (~{tp_pips} pips)\n"
                            f"SL: `{sl_level:{p_fmt}}` (~{sl_pips} pips)\n\n"
                            f"Action: Entering {'Long' if prediction == 1 else 'Short'}"
                        )
                        log_to_file(f"AI: Signal Sent ({asset} {direction}, Confidence: {probability*100:.1f}%)")
                        await send_telegram_msg(ml_report)
                        # Safe volume for $10k Prop Account
                        execute_mt5_trade('AI', 'BUY' if prediction == 1 else 'SELL', symbol=asset, volume=LOT_SIZE_AI, sl=sl_level, tp=tp_level)
                    else:
                        print(f"AI: {asset} position already open. Skipping.")
                else:
                    log_to_file(f"AI ({asset}): Confidence low ({probability*100:.1f}%). Threshold: {ML_CONFIDENCE_THRESHOLD*100}%. Waiting.")
                    print(f"AI ({asset}): Low confidence ({probability*100:.1f}%). Waiting.")
        else:
            print(f"AI ({asset}): Not enough data or prediction failed.")

    print("\n" + "="*40)
    print("STRATEGY 4: GBPJPY SWING BREAKOUT")
    print("="*40)
    
    asset = "GBPJPY"
    if asset in raw_data:
        gbpjpy_df = raw_data[asset].dropna()
        active_positions = get_mt5_active_positions(strategy_name='Swing')
        
        if len(gbpjpy_df) >= 200:
            closes = gbpjpy_df['Close'].values
            highs = gbpjpy_df['High'].values
            lows = gbpjpy_df['Low'].values
            
            ema_50 = gbpjpy_df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
            ema_200 = gbpjpy_df['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
            
            # 24-hour breakout
            lookback = 24
            recent_highs = highs[-lookback - 1 : -1]
            recent_lows = lows[-lookback - 1 : -1]
            
            upper_channel = np.max(recent_highs)
            lower_channel = np.min(recent_lows)
            
            current_close = closes[-1]
            
            print(f"Close: {current_close:.3f} | Upper 24h: {upper_channel:.3f} | Lower 24h: {lower_channel:.3f}")
            print(f"EMA-50: {ema_50:.3f} | EMA-200: {ema_200:.3f}")
            
            if current_close > upper_channel and ema_50 > ema_200:
                if not any(pos.upper() == asset for pos in active_positions):
                    sl_price = current_close - (50 * 0.01)
                    tp_price = current_close + (100 * 0.01)
                    report = f"📈 *SIGNAL: THE BEAST (LONG)*\nAsset: `{asset}`\nEntry: `{current_close:.3f}`\nSL: `{sl_price:.3f}` (50 pips)\nTP: `{tp_price:.3f}` (100 pips)"
                    log_to_file(f"Swing: {asset} LONG Signal Sent")
                    await send_telegram_msg(report)
                    execute_mt5_trade('Swing', 'BUY', symbol=asset, volume=LOT_SIZE_TREND, sl=sl_price, tp=tp_price)
                else:
                    print(f"Swing: {asset} position already open.")
            elif current_close < lower_channel and ema_50 < ema_200:
                if not any(pos.upper() == asset for pos in active_positions):
                    sl_price = current_close + (50 * 0.01)
                    tp_price = current_close - (100 * 0.01)
                    report = f"🔴 *SIGNAL: THE BEAST (SHORT)*\nAsset: `{asset}`\nEntry: `{current_close:.3f}`\nSL: `{sl_price:.3f}` (50 pips)\nTP: `{tp_price:.3f}` (100 pips)"
                    log_to_file(f"Swing: {asset} SHORT Signal Sent")
                    await send_telegram_msg(report)
                    execute_mt5_trade('Swing', 'SELL', symbol=asset, volume=LOT_SIZE_TREND, sl=sl_price, tp=tp_price)
                else:
                    print(f"Swing: {asset} position already open.")
            else:
                print(f"RECOMMENDATION: WAIT (No breakout or against macro trend)")
        else:
            print(f"⚠️ SKIPPING Strategy 4: Not enough data for {asset}.")
    else:
        print(f"⚠️ SKIPPING Strategy 4: Missing data for {asset}.")

    
    # --- SESSION CLEANUP ---
    mt5.shutdown()
    print("\n" + "="*40)
    print("SESSION COMPLETE - Connection Closed")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(get_signal())
