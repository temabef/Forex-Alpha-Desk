import pandas as pd
import yfinance as yf
import numpy as np
import statsmodels.api as sm
import asyncio
from telegram import Bot
from datetime import datetime
from ml_predictor_strategy import get_ml_prediction
from mt5_executor import execute_mt5_trade, get_mt5_active_positions
import os
from dotenv import load_dotenv

# Load secrets from .env file
load_dotenv()

# --- PATH FIX FOR BACKGROUND TASKS ---
# This ensures the script always runs in its own folder
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ENTRY_THRESHOLD = 2.0
EXIT_THRESHOLD = 0.2
ML_CONFIDENCE_THRESHOLD = 0.58 
LOT_SIZE = 20000 # 0.20 Lots (Adjust based on account size)

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

async def get_signal():
    print(f"--- Multi-Strategy Live Signal Report ---")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    log_to_file("--- Multi-Strategy Live Signal Report ---")
    log_to_file(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # --- SYMBOL CONFIG ---
    # Added USDJPY for the AI Strategy
    symbols = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X"}
    raw_data = {}
    raw_data = {}

    # Fetch recent data (60 days for ML training)
    for name, ticker in symbols.items():
        print(f"Fetching latest data for {name}...")
        df = yf.download(ticker, period="60d", interval="1h", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
        raw_data[name] = df

    print("\n" + "="*40)
    print("STRATEGY 1: PAIRS TRADING (Mean Reversion)")
    print("="*40)
    
    # --- CHECK ACTIVE POSITIONS FOR PAIRS ---
    active_positions = get_mt5_active_positions(strategy_name='Pairs')
    print(f"INFO: MT5 Active positions for Pairs: {active_positions}")
    
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
                execute_mt5_trade('Pairs', 'SELL', symbol='EURUSD', volume=0.2)
                execute_mt5_trade('Pairs', 'BUY', symbol='GBPUSD', volume=0.2)
            else:
                log_to_file(f"Pairs: Z-Score={z_score:.2f} (Already in trade - suppressing alert)")
                print("Pairs: Already in trade, suppressing duplicate SELL alert.")
        elif z_score < -ENTRY_THRESHOLD:
            # Only send BUY signal if we DON'T have a position
            if not any(pos.upper() == "EURUSD" for pos in active_positions):
                msg = f"🚀 *SIGNAL: BUY SPREAD*\n⚖️ Pairs Trading (Mean Reversion)\nZ-Score: `{z_score:.2f}`\nEURUSD: `{eur_price:.5f}`\nGBPUSD: `{gbp_price:.5f}`\nAction: BUY EURUSD, SELL GBPUSD"
                log_to_file(f"Pairs: BUY SPREAD Signal Sent (Z-Score: {z_score:.2f})")
                await send_telegram_msg(msg)
                execute_mt5_trade('Pairs', 'BUY', symbol='EURUSD', volume=0.2)
                execute_mt5_trade('Pairs', 'SELL', symbol='GBPUSD', volume=0.2)
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
                tp_price = current_close + ((current_close - sl_price) * 2.0)
                trend_report = f"📈 *SIGNAL: BREAKOUT LONG*\nEntry: `{current_close:.5f}`\nSL: `{sl_price:.5f}`\nTP: `{tp_price:.5f}`"
                log_to_file(f"Trend: BREAKOUT LONG Signal Sent (Price: {current_close:.5f})")
                await send_telegram_msg(trend_report)
                execute_mt5_trade('Trend', 'BUY', symbol='EURUSD', volume=0.2)
            else:
                print("Trend: Breakout detected but Trend position already open. Skipping.")
        elif current_close < lower_channel:
            # Case-Insensitive check
            if not any(pos.upper() == "EURUSD" for pos in active_positions):
                sl_price = upper_channel
                tp_price = current_close - ((sl_price - current_close) * 2.0)
                trend_report = f"🔴 *SIGNAL: BREAKOUT SHORT*\nEntry: `{current_close:.5f}`\nSL: `{sl_price:.5f}`\nTP: `{tp_price:.5f}`"
                log_to_file(f"Trend: BREAKOUT SHORT Signal Sent (Price: {current_close:.5f})")
                await send_telegram_msg(trend_report)
                execute_mt5_trade('Trend', 'SELL', symbol='EURUSD', volume=0.2)
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
    print("STRATEGY 3: QUANT PREDICTOR (USDJPY AI)")
    print("="*40)
    
    usdjpy_df = raw_data["USDJPY"].dropna()
    prediction, probability = get_ml_prediction(usdjpy_df)
    
    if prediction is not None:
        print(f"AI Prediction: {'UP' if prediction == 1 else 'DOWN'}")
        print(f"Confidence: {probability*100:.1f}%")
        
        # Calculate Dynamic TP/SL based on 24h Volatility (ATR)
        # Using a simple high-low range for the last 24 bars
        recent_24 = eurusd_df.tail(24)
        atr = (recent_24['High'] - recent_24['Low']).mean()
        dynamic_sl = atr * 1.2
        dynamic_tp = dynamic_sl * 1.5
        
        current_price = eurusd_df['Close'].iloc[-1]
        
        if probability >= ML_CONFIDENCE_THRESHOLD:
            direction = "BULLISH (UP)" if prediction == 1 else "BEARISH (DOWN)"
            icon = "🧠"
            
            # Calculate actual price levels
            if prediction == 1: # UP
                tp_level = current_price + dynamic_tp
                sl_level = current_price - dynamic_sl
            # --- PIP CALCULATION (JPY vs Normal) ---
            # For JPY pairs, 1 pip is 0.01. For others, 1 pip is 0.0001
            pip_multiplier = 100 if "JPY" in "USDJPY" else 10000
            tp_pips = int(dynamic_tp * pip_multiplier)
            sl_pips = int(dynamic_sl * pip_multiplier)

            # --- CHECK ACTIVE POSITIONS FOR THIS STRATEGY ---
            active_positions = get_mt5_active_positions(strategy_name='AI')
            
            # Case-Insensitive check to see if we already have a USDJPY trade
            if not any(pos.upper() == "USDJPY" for pos in active_positions):
                ml_report = (
                    f"{icon} *Quant Predictor (Adaptive AI)*\n"
                    f"Asset: `USDJPY`\n"
                    f"Prediction: `{direction}`\n"
                    f"Confidence: `{probability*100:.1f}%`\n"
                    f"Price: `{current_price:.2f}`\n\n"
                    f"🎯 *Adaptive Targets:* \n"
                    f"TP: `{tp_level:.2f}` (~{tp_pips} pips)\n"
                    f"SL: `{sl_level:.2f}` (~{sl_pips} pips)\n\n"
                    f"Action: Consider entering {'Long' if prediction == 1 else 'Short'}"
                )
                log_to_file(f"AI: Signal Sent (USDJPY {direction}, Confidence: {probability*100:.1f}%)")
                await send_telegram_msg(ml_report)
                # Volume 0.2 for USDJPY
                execute_mt5_trade('AI', 'BUY' if prediction == 1 else 'SELL', symbol='USDJPY', volume=0.2)
            else:
                log_to_file(f"AI: Confidence high ({probability*100:.1f}%) but USDJPY position already open. Skipping.")
                print("AI: Signal detected but USDJPY position already open. Skipping.")
        else:
            log_to_file(f"AI: Confidence low ({probability*100:.1f}%)")
            print("RECOMMENDATION: WAIT (Low confidence)")
    else:
        log_to_file("AI: Not enough data")
        print("Not enough data for ML Predictor.")
        
    print("\n========================================")

if __name__ == "__main__":
    asyncio.run(get_signal())
