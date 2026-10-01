import os
import sys

# Set UTF-8 encoding for Windows console print output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# --- PATH FIX FOR BACKGROUND TASKS ---
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
os.chdir(script_dir)

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import pandas as pd
import numpy as np
import asyncio
from telegram import Bot
from datetime import datetime, timedelta, timezone
import json
from dotenv import load_dotenv
import MetaTrader5 as mt5

from mt5_executor import execute_mt5_trade, get_mt5_active_positions, close_all_active_positions, apply_ai_breakeven_stops, get_ai_position_info
from news_manager import is_in_danger_zone

# Load secrets from .env file
load_dotenv()

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ML_CONFIDENCE_THRESHOLD = float(os.getenv("ML_CONFIDENCE_THRESHOLD", 0.60))
LOT_SIZE_AI = float(os.getenv("LOT_SIZE_AI", 0.06))
os.makedirs("logs", exist_ok=True)

DRY_RUN = "--dry-run" in sys.argv

def log_to_file(message):
    os.makedirs("logs", exist_ok=True)
    with open("logs/signal_history.txt", "a", encoding="utf-8") as f:
        f.write(message + "\n")

async def send_telegram_msg(message):
    if DRY_RUN:
        print(f"[DRY RUN TELEGRAM]\n{message}\n")
        return
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "PASTE_YOUR_CHAT_ID_HERE":
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
        
    suffix = os.getenv("SYMBOL_SUFFIX", "")
    broker_symbol = f"{symbol}{suffix}"
    
    mt5.symbol_select(broker_symbol, True)
    rates = mt5.copy_rates_from_pos(broker_symbol, mt5.TIMEFRAME_H1, 1, num_bars)
    if rates is not None and len(rates) > 0:
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        latest_bar_time = df['time'].iloc[-1]
        now_time = datetime.now(timezone.utc)
        if (now_time - latest_bar_time.tz_localize(timezone.utc) if latest_bar_time.tzinfo is None else (now_time - latest_bar_time)).total_seconds() < 9000:
            df.set_index('time', inplace=True)
            df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)
            return df
        else:
            print(f"MT5 rates for {broker_symbol} are STALE (last bar: {latest_bar_time}). Falling back to tick resampling...")

    # Fallback tick resampling
    try:
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=5)
        ticks = mt5.copy_ticks_range(broker_symbol, past, now, mt5.COPY_TICKS_ALL)
        if ticks is not None and len(ticks) > 0:
            df_ticks = pd.DataFrame(ticks)
            df_ticks['time'] = pd.to_datetime(df_ticks['time'], unit='s')
            df_ticks.set_index('time', inplace=True)
            df = df_ticks['bid'].resample('1h').ohlc().dropna()
            df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)
            if len(df) > 1:
                df = df.iloc[:-1]
                return df
    except Exception as e:
        print(f"Tick fallback error for {broker_symbol}: {e}")

    print(f"Failed to fetch data for {broker_symbol}")
    return None

def check_daily_drawdown():
    """
    Checks if the account has hit the daily drawdown limit.
    """
    max_drawdown_pct = float(os.getenv("MAX_DAILY_DRAWDOWN_PCT", 0.035))
    lock_file = "logs/daily_lock.txt"
    balance_file = "logs/daily_start_balance.json"
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(lock_file):
        with open(lock_file, "r") as f:
            lock_date = f.read().strip()
            if lock_date == today_str:
                return True, "Account is locked due to daily drawdown breach."

    terminal_path = os.getenv("MT5_TERMINAL_PATH")
    if not mt5.initialize(path=terminal_path):
        return False, "MT5 Init Failed"

    account_info = mt5.account_info()
    if not account_info:
        return False, "Could not fetch account info"

    # 3. Manage Daily Starting Balance (Account-Aware)
    current_account = account_info.login
    start_balance = account_info.balance
    if os.path.exists(balance_file):
        try:
            with open(balance_file, "r") as f:
                data = json.load(f)
                if data.get("date") == today_str and data.get("account") == current_account:
                    start_balance = data.get("balance")
                else:
                    # New Day or Account Switch - Update balance
                    with open(balance_file, "w") as fw:
                        json.dump({"date": today_str, "account": current_account, "balance": account_info.balance}, fw)
        except:
            with open(balance_file, "w") as fw:
                json.dump({"date": today_str, "account": current_account, "balance": account_info.balance}, fw)
    else:
        with open(balance_file, "w") as fw:
            json.dump({"date": today_str, "account": current_account, "balance": account_info.balance}, fw)

    current_equity = account_info.equity
    drawdown_pct = (start_balance - current_equity) / start_balance
    
    if drawdown_pct >= max_drawdown_pct:
        with open(lock_file, "w") as f:
            f.write(today_str)
        return True, f"DAILY DRAWDOWN BREACH: {drawdown_pct*100:.2f}% (Limit: {max_drawdown_pct*100:.2f}%). Closing all trades."

    return False, ""

def is_friday_night():
    """
    Checks if it's Friday after 20:00 GMT.
    """
    if os.getenv("ENABLE_FRIDAY_EXIT", "False") != "True":
        return False
        
    now_utc = datetime.now(timezone.utc)
    if now_utc.weekday() == 4 and now_utc.hour >= 20:
        return True
    return False

async def get_signal():
    try:
        from ml_predictor_strategy import get_ml_prediction
    except Exception as e:
        log_to_file(f"FATAL: Could not import ml_predictor_strategy: {e}")
        print(f"FATAL: Could not import ml_predictor_strategy: {e}")
        return

    print("=" * 60)
    print("      NAUTILUS DESK-JPY (YEN ALPHA QUANT DESK)")
    print(f"      Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Dry-Run: {DRY_RUN}")
    print("=" * 60)

    log_to_file("--- Desk-JPY Live Signal Report ---")
    log_to_file(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # --- SHIELD 1: DAILY DRAWDOWN KILL-SWITCH ---
    is_breached, breach_msg = check_daily_drawdown()
    if is_breached:
        print(f"🛑 {breach_msg}")
        log_to_file(f"KILL-SWITCH: {breach_msg}")
        await send_telegram_msg(f"🛑 *DESK-JPY EMERGENCY KILL-SWITCH*\n{breach_msg}")
        if not DRY_RUN:
            close_all_active_positions()
        return

    # --- SHIELD 2: FRIDAY MARKET CLOSE ---
    if is_friday_night():
        print("📅 Friday 20:00 GMT Reached. Closing all positions for the weekend.")
        log_to_file("FRIDAY EXIT: Closing all positions.")
        await send_telegram_msg("📅 *DESK-JPY FRIDAY EXIT*\nClosing all positions for the weekend.")
        if not DRY_RUN:
            close_all_active_positions()
        return

    # --- SHIELD 3: HIGH-IMPACT NEWS FILTER ---
    in_danger, news_msg = is_in_danger_zone()
    if in_danger:
        print(f"⚠️ {news_msg}")
        log_to_file(f"NEWS FILTER: {news_msg}")
        await send_telegram_msg(f"⚠️ *DESK-JPY NEWS DANGER ZONE*\n{news_msg}\n\nExecution skipped for this hour.")
        return

    # --- SHIELD 4: AI 80% BREAKEVEN LOCK ---
    try:
        if not DRY_RUN:
            be_updates = apply_ai_breakeven_stops(progress_threshold=0.80)
            for be in be_updates:
                msg = (
                    f"🛡️ *Desk-JPY AI Breakeven Lock Activated*\n"
                    f"Asset: `{be['symbol']}` ({be['type']})\n"
                    f"Ticket: `{be['ticket']}`\n"
                    f"Progress: `{be['progress_pct']:.1f}%` of TP target\n"
                    f"New SL: `{be['new_sl']}` (Entry: `{be['entry']}`)\n"
                    f"*Trade is now 100% Risk-Free!*"
                )
                print(f"🛡️ Breakeven activated for {be['symbol']} (Ticket {be['ticket']})")
                log_to_file(f"BREAKEVEN: {be['symbol']} {be['type']} moved SL to {be['new_sl']} (Risk-Free)")
                await send_telegram_msg(msg)
    except Exception as e:
        print(f"⚠️ Error checking AI breakeven stops: {e}")

    # --- YEN ASSETS CONFIG (USDJPY EXCLUSIVE) ---
    symbols = ["USDJPY"]
    raw_data = {}

    for symbol in symbols:
        print(f"Fetching latest data for {symbol} from MT5...")
        df = fetch_mt5_data(symbol, num_bars=1500)
        if df is None or df.empty or len(df) < 60:
            print(f"⚠️ WARNING: Not enough data for {symbol} in MT5. Skipping strategy logic.")
            continue
        raw_data[symbol] = df

    print("\n" + "="*50)
    print("STRATEGY 1: YEN QUANT PREDICTOR (Adaptive AI)")
    print("="*50)
    
    current_utc_hour = datetime.now(timezone.utc).hour
    # Active London & NY expansion hours: 06:00 to 18:00 UTC
    if not (6 <= current_utc_hour <= 18):
        print(f"ℹ️ AI Strategy inactive outside active session (Current UTC hour: {current_utc_hour}).")
        log_to_file(f"AI: Skipping execution, outside active session (hour {current_utc_hour})")
    else:
        for asset in symbols:
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
                
                # Dynamic SL = 2.5x ATR
                dynamic_sl = atr * 2.5
                
                # All pairs are JPY: 1 pip = 0.01. Minimum safety floor = 20 pips (0.20 JPY)
                pip_size = 0.01
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
                    
                    # EMA-20 Trend Gate Confirmation
                    ema_20 = asset_df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                    if prediction == 1 and current_price < ema_20:
                        log_to_file(f"AI ({asset}): Signal UP rejected: Price ({current_price:.2f}) < EMA-20 ({ema_20:.2f}).")
                        print(f"AI ({asset}): Signal UP rejected (Price < EMA-20).")
                        continue
                    elif prediction == 0 and current_price > ema_20:
                        log_to_file(f"AI ({asset}): Signal DOWN rejected: Price ({current_price:.2f}) > EMA-20 ({ema_20:.2f}).")
                        print(f"AI ({asset}): Signal DOWN rejected (Price > EMA-20).")
                        continue
                        
                    icon = "🚀" if prediction == 1 else "📉"
                    
                    # Fetch live tick price for exact fill-anchoring
                    suffix = os.getenv("SYMBOL_SUFFIX", "")
                    broker_asset = f"{asset}{suffix}"
                    live_tick = mt5.symbol_info_tick(broker_asset)
                    execution_price = (live_tick.ask if prediction == 1 else live_tick.bid) if live_tick else current_price
                    
                    if prediction == 1: # UP
                        tp_level = execution_price + dynamic_tp
                        sl_level = execution_price - dynamic_sl
                    else: # DOWN
                        tp_level = execution_price - dynamic_tp
                        sl_level = execution_price + dynamic_sl
                    
                    tp_pips = int(dynamic_tp * 100)
                    sl_pips = int(dynamic_sl * 100)

                    # --- CHECK ACTIVE AI POSITIONS & REVERSAL LOGIC ---
                    ai_pos_info = get_ai_position_info(symbol=asset)
                    signal_pos_type = 'BUY' if prediction == 1 else 'SELL'
                    
                    if asset.upper() in ai_pos_info:
                        existing_pos = ai_pos_info[asset.upper()]
                        current_pos_type = existing_pos['type']
                        
                        if current_pos_type == signal_pos_type:
                            log_to_file(f"AI ({asset}): Holding existing {current_pos_type} position (Confidence: {probability*100:.1f}%).")
                            print(f"AI ({asset}): Holding existing {current_pos_type} position (Confidence: {probability*100:.1f}%).")
                        else:
                            # Confirmed Early Reversal Exit!
                            log_to_file(f"AI REVERSAL: Confirmed reversal for {asset} ({current_pos_type} -> {signal_pos_type}, Conf: {probability*100:.1f}%).")
                            print(f"🔄 AI REVERSAL: Exiting {current_pos_type} on {asset} and reversing to {signal_pos_type}!")
                            reversal_msg = (
                                f"🔄 *Desk-JPY Early Reversal Triggered*\n"
                                f"Asset: `{asset}`\n"
                                f"Closed: `{current_pos_type}` (Ticket: `{existing_pos['ticket']}`)\n"
                                f"New Signal: `{direction}` ({probability*100:.1f}% confidence)\n"
                                f"Target TP: `{tp_level:.2f}` (~{tp_pips} pips)\n"
                                f"Action: Reversing to `{signal_pos_type}`"
                            )
                            await send_telegram_msg(reversal_msg)
                            if not DRY_RUN:
                                execute_mt5_trade('AI', 'EXIT', symbol=asset)
                                execute_mt5_trade('AI', signal_pos_type, symbol=asset, volume=LOT_SIZE_AI, sl=sl_level, tp=tp_level, sl_dist=dynamic_sl, tp_dist=dynamic_tp)
                    else:
                        ml_report = (
                            f"{icon} *Desk-JPY Quant Predictor (Adaptive AI)*\n"
                            f"Asset: `{asset}`\n"
                            f"Prediction: `{direction}`\n"
                            f"Confidence: `{probability*100:.1f}%` (WF WR: `{est_win_rate*100:.1f}%`)\n"
                            f"Price: `{execution_price:.2f}`\n\n"
                            f"🎯 *Adaptive JPY Targets:* \n"
                            f"TP: `{tp_level:.2f}` (~{tp_pips} pips)\n"
                            f"SL: `{sl_level:.2f}` (~{sl_pips} pips)\n\n"
                            f"Action: Entering {'Long' if prediction == 1 else 'Short'} ({LOT_SIZE_AI} lot)"
                        )
                        log_to_file(f"AI: Signal Sent ({asset} {direction}, Confidence: {probability*100:.1f}%)")
                        await send_telegram_msg(ml_report)
                        if not DRY_RUN:
                            execute_mt5_trade('AI', signal_pos_type, symbol=asset, volume=LOT_SIZE_AI, sl=sl_level, tp=tp_level, sl_dist=dynamic_sl, tp_dist=dynamic_tp)
                else:
                    log_to_file(f"AI ({asset}): Confidence low ({probability*100:.1f}%). Threshold: {ML_CONFIDENCE_THRESHOLD*100}%. Waiting.")
                    print(f"AI ({asset}): Low confidence ({probability*100:.1f}%). Waiting.")
            else:
                print(f"AI ({asset}): Not enough data or prediction failed.")

    print("\n" + "="*60)
    print("Desk-JPY Scan Complete.")
    print("="*60)
    mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(get_signal())
