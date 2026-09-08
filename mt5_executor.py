import MetaTrader5 as mt5
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Path to your MT5 terminal (Dynamic via .env for multi-account setup)
TERMINAL_PATH = os.getenv("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")

# Magic Numbers for Strategy Isolation
MAGIC_NUMBERS = {
    'AI': 111,
    'Pairs': 222,
    'Trend': 333
}

def execute_mt5_trade(strategy_name, action, symbol="EURUSD", volume=0.2, sl=None, tp=None):
    """
    Professional Trade Executor. 
    Handles price rounding, filling modes, and strategy-specific SL/TP.
    """
    magic = MAGIC_NUMBERS.get(strategy_name, 123456)
    
    if not mt5.initialize(path=TERMINAL_PATH):
        print("MT5 initialize() failed")
        return False

    # Append broker suffix
    suffix = os.getenv("SYMBOL_SUFFIX", "")
    broker_symbol = f"{symbol}{suffix}"

    # Get symbol properties
    symbol_info = mt5.symbol_info(broker_symbol)
    if symbol_info is None:
        print(f"Symbol {broker_symbol} not found")
        return False

    # Ensure symbol is visible
    if not symbol_info.visible:
        mt5.symbol_select(broker_symbol, True)

    # 1. Rounding Price Logic
    tick = mt5.symbol_info_tick(broker_symbol)
    if tick is None:
        return False
        
    price = tick.bid if action == 'SELL' or action == 'EXIT' else tick.ask
    price = round(price, symbol_info.digits) 

    # 2. Filling Mode Logic
    filling_type = mt5.ORDER_FILLING_FOK
    if symbol_info.filling_mode & 1: filling_type = mt5.ORDER_FILLING_FOK
    elif symbol_info.filling_mode & 2: filling_type = mt5.ORDER_FILLING_IOC
    else: filling_type = mt5.ORDER_FILLING_RETURN

    # 3. Position Check (Strategy Isolation)
    positions = mt5.positions_get(symbol=broker_symbol)
    strategy_pos = None
    if positions:
        for p in positions:
            if p.magic == magic:
                strategy_pos = p
                break

    if strategy_pos and action != 'EXIT':
        print(f"MT5: Already have a {strategy_name} position in {symbol}. Skipping.")
        return True

    if action == 'EXIT' and not strategy_pos:
        return True

    # 4. Prepare Order Type
    if action == 'EXIT':
        order_type = mt5.ORDER_TYPE_SELL if strategy_pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    else:
        order_type = mt5.ORDER_TYPE_BUY if action == 'BUY' else mt5.ORDER_TYPE_SELL
    
    # 5. Handle SL/TP (Smart vs Emergency Backup)
    if action != 'EXIT':
        pip_size = 0.01 if "JPY" in symbol else 0.0001
        if strategy_name == 'Swing':
            # Always anchor GBPJPY Swing SL/TP to live fill price: 50 pips SL, 100 pips TP
            sl_dist = 50 * pip_size
            tp_dist = 100 * pip_size
            sl = price - sl_dist if order_type == mt5.ORDER_TYPE_BUY else price + sl_dist
            tp = price + tp_dist if order_type == mt5.ORDER_TYPE_BUY else price - tp_dist
        elif sl is None or tp is None:
            # Safety targets
            sl_dist = 150 * pip_size
            # For Pairs trading, do NOT set tight single-leg TP that breaks the hedge!
            # Use broad 150 pip safety TP so Z-Score exit manages the pair exit.
            tp_dist = 150 * pip_size if strategy_name == 'Pairs' else 40 * pip_size
            sl = price - sl_dist if order_type == mt5.ORDER_TYPE_BUY else price + sl_dist
            tp = price + tp_dist if order_type == mt5.ORDER_TYPE_BUY else price - tp_dist
    else:
        sl = 0.0
        tp = 0.0

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": broker_symbol,
        "volume": float(volume) if action != 'EXIT' else float(strategy_pos.volume),
        "type": int(order_type),
        "price": float(price),
        "sl": round(float(sl), symbol_info.digits) if sl else 0.0,
        "tp": round(float(tp), symbol_info.digits) if tp else 0.0,
        "magic": int(magic),
        "comment": f"{strategy_name} Trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": int(filling_type),
    }

    if action == 'EXIT' and strategy_pos:
        request["position"] = strategy_pos.ticket

    print(f"MT5: Sending {action} for {symbol} (SL: {sl}, TP: {tp})")
    result = mt5.order_send(request)
    
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"MT5 Order Failed: {result.comment if result else 'Unknown'}")
        return False

    # --- CRITICAL FIX: ENSURE SL/TP ARE APPLIED (Two-Step for Prop Brokers) ---
    if action != 'EXIT' and (sl or tp):
        # We wait a split second for the position to be recognized
        import time
        time.sleep(0.1)
        
        # Get the ticket of the position we just opened
        # We search by magic number to find the exact trade
        positions = mt5.positions_get(symbol=broker_symbol)
        new_pos = None
        if positions:
            for p in positions:
                if p.magic == magic:
                    new_pos = p
                    break
        
        if new_pos:
            modify_request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": broker_symbol,
                "position": new_pos.ticket,
                "sl": round(float(sl), symbol_info.digits) if sl else 0.0,
                "tp": round(float(tp), symbol_info.digits) if tp else 0.0,
            }
            modify_result = mt5.order_send(modify_request)
            if modify_result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"⚠️ MT5: Failed to modify SL/TP safety net: {modify_result.comment}")
            else:
                print(f"✅ MT5: SL/TP Safety Net applied successfully to ticket {new_pos.ticket}")

    return True

def get_mt5_active_positions(strategy_name=None):
    """
    Returns a list of symbols that have active positions for a specific strategy.
    """
    if not mt5.initialize(path=TERMINAL_PATH):
        return []
        
    positions = mt5.positions_get()
    if positions is None:
        return []
    
    magic = MAGIC_NUMBERS.get(strategy_name)
    suffix = os.getenv("SYMBOL_SUFFIX", "")
    
    active_symbols = []
    for p in positions:
        if magic is None or p.magic == magic:
            # Strip the suffix before returning to the main logic
            clean_symbol = p.symbol.replace(suffix, "") if suffix else p.symbol
            active_symbols.append(clean_symbol)
            
    return active_symbols

def close_all_active_positions():
    """
    Emergency/Global exit function. Closes every single open position 
    on the account regardless of strategy.
    """
    if not mt5.initialize(path=TERMINAL_PATH):
        print("MT5: Failed to initialize for global exit")
        return False
        
    positions = mt5.positions_get()
    if not positions:
        print("MT5: No active positions found for global exit.")
        return True
        
    print(f"MT5: Attempting to close {len(positions)} positions...")
    success = True
    for p in positions:
        # Determine order type to close
        order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(p.symbol)
        if not tick:
            continue
        price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
        
        # Get symbol properties for digits and filling mode
        symbol_info = mt5.symbol_info(p.symbol)
        if symbol_info is None:
            continue
            
        filling_type = mt5.ORDER_FILLING_FOK
        if symbol_info.filling_mode & 1: filling_type = mt5.ORDER_FILLING_FOK
        elif symbol_info.filling_mode & 2: filling_type = mt5.ORDER_FILLING_IOC
        else: filling_type = mt5.ORDER_FILLING_RETURN

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": p.symbol,
            "volume": float(p.volume),
            "type": int(order_type),
            "position": p.ticket,
            "price": float(price),
            "magic": int(p.magic),
            "comment": "Global Exit",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": int(filling_type),
        }
        
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Failed to close position {p.ticket}: {result.comment if result else 'Unknown'}")
            success = False
        else:
            print(f"Successfully closed position {p.ticket} ({p.symbol})")
            
    return success

def close_expired_ai_positions(max_age_seconds=14300):
    """
    Closes any AI position (magic number 111) that has been open for >= max_age_seconds (approx 4 hours).
    Uses the broker server time to compute exact position duration.
    """
    magic = MAGIC_NUMBERS.get('AI', 111)
    
    if not mt5.initialize(path=TERMINAL_PATH):
        print("MT5: Failed to initialize for checking expired positions.")
        return False
        
    positions = mt5.positions_get()
    if not positions:
        return True
        
    suffix = os.getenv("SYMBOL_SUFFIX", "")
    
    # Fetch broker current time from ticks of EURUSD to avoid local time/server time mismatch
    eurusd_broker_symbol = f"EURUSD{suffix}"
    tick = mt5.symbol_info_tick(eurusd_broker_symbol)
    if tick is None:
        print("MT5: Failed to fetch symbol tick for time comparison. Skipping age check.")
        return False
        
    current_time = tick.time
    
    for p in positions:
        if p.magic == magic:
            age = current_time - p.time
            clean_symbol = p.symbol.replace(suffix, "") if suffix else p.symbol
            print(f"AI Position check - Ticket {p.ticket} ({clean_symbol}): Age is {age}s (Threshold: {max_age_seconds}s)")
            if age >= max_age_seconds:
                print(f"AI Position {p.ticket} ({clean_symbol}) has expired (age: {age}s >= {max_age_seconds}s). Closing.")
                
                # Close the position using market order
                order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                
                # Get close tick
                close_tick = mt5.symbol_info_tick(p.symbol)
                if not close_tick:
                    print(f"Failed to get price tick to close {p.symbol}")
                    continue
                    
                price = close_tick.bid if order_type == mt5.ORDER_TYPE_SELL else close_tick.ask
                symbol_info = mt5.symbol_info(p.symbol)
                if symbol_info is None:
                    continue
                
                price = round(price, symbol_info.digits)
                
                filling_type = mt5.ORDER_FILLING_FOK
                if symbol_info.filling_mode & 1: filling_type = mt5.ORDER_FILLING_FOK
                elif symbol_info.filling_mode & 2: filling_type = mt5.ORDER_FILLING_IOC
                else: filling_type = mt5.ORDER_FILLING_RETURN
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": p.symbol,
                    "volume": float(p.volume),
                    "type": int(order_type),
                    "position": p.ticket,
                    "price": float(price),
                    "magic": int(p.magic),
                    "comment": "AI Age Exit",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": int(filling_type),
                }
                
                result = mt5.order_send(request)
                if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(f"MT5 Order Failed on age exit: {result.comment if result else 'Unknown'}")
                else:
                    print(f"Successfully closed expired AI position {p.ticket} ({p.symbol})")
                    # Record 1-hour cooldown timestamp to prevent immediate re-entry loop
                    try:
                        import json
                        import time
                        cooldown_file = f"logs/ai_cooldown_{clean_symbol.upper()}.json"
                        with open(cooldown_file, "w") as cf:
                            json.dump({"timestamp": time.time(), "symbol": clean_symbol}, cf)
                        print(f"Recorded post-expiration 1-hour cooldown for {clean_symbol}")
                    except Exception as ce:
                        print(f"Error saving cooldown file: {ce}")
                    
    return True

