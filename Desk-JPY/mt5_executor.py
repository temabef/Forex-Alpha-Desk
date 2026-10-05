import MetaTrader5 as mt5
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Path to your MT5 terminal (Dynamic via .env for multi-account setup)
TERMINAL_PATH = os.getenv("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")

# Magic Numbers for Desk-JPY Strategy Isolation (444 for AI)
MAGIC_NUMBERS = {
    'AI': 444,
}

def execute_mt5_trade(strategy_name, action, symbol="USDJPY", volume=0.08, sl=None, tp=None, sl_dist=None, tp_dist=None):
    """
    Professional Trade Executor for Desk-JPY. 
    Handles price rounding, filling modes, and strategy-specific SL/TP.
    """
    magic = MAGIC_NUMBERS.get(strategy_name, 444)
    
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
        if strategy_name == 'AI' and sl_dist is not None and tp_dist is not None:
            sl = price - sl_dist if order_type == mt5.ORDER_TYPE_BUY else price + sl_dist
            tp = price + tp_dist if order_type == mt5.ORDER_TYPE_BUY else price - tp_dist
        elif sl is None or tp is None:
            sl_dist = 40 * pip_size
            tp_dist = 60 * pip_size
            sl = price - sl_dist if order_type == mt5.ORDER_TYPE_BUY else price + sl_dist
            tp = price + tp_dist if order_type == mt5.ORDER_TYPE_BUY else price - tp_dist

    # 6. Build Request
    if action == 'EXIT':
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": broker_symbol,
            "volume": float(strategy_pos.volume),
            "type": order_type,
            "position": int(strategy_pos.ticket),
            "price": float(price),
            "deviation": 20,
            "magic": magic,
            "comment": f"Desk-JPY Close {strategy_name}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }
    else:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": broker_symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(round(sl, symbol_info.digits)) if sl else 0.0,
            "tp": float(round(tp, symbol_info.digits)) if tp else 0.0,
            "deviation": 20,
            "magic": magic,
            "comment": f"Desk-JPY {strategy_name}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }

    # 7. Send Order
    result = mt5.order_send(request)
    if result is None:
        print(f"MT5: order_send returned None for {strategy_name} {action}")
        return False
        
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"MT5: Order Failed! Retcode: {result.retcode}, Comment: {result.comment}")
        return False

    print(f"MT5: Trade SUCCESS! {action} {volume} {broker_symbol} @ {price}")
    return True

def get_mt5_active_positions(strategy_name='AI'):
    """
    Returns a list of symbols for which the specified strategy has an active position.
    """
    magic = MAGIC_NUMBERS.get(strategy_name, 444)
    if not mt5.initialize(path=TERMINAL_PATH):
        return []
        
    positions = mt5.positions_get()
    if not positions:
        return []
        
    suffix = os.getenv("SYMBOL_SUFFIX", "")
    active_symbols = []
    for p in positions:
        if p.magic == magic:
            clean_symbol = p.symbol.replace(suffix, "") if suffix else p.symbol
            active_symbols.append(clean_symbol)
            
    return active_symbols

def get_ai_position_info(symbol=None):
    """
    Returns detailed dictionary of active AI positions.
    """
    magic = MAGIC_NUMBERS.get('AI', 444)
    if not mt5.initialize(path=TERMINAL_PATH):
        return {}
        
    positions = mt5.positions_get()
    if not positions:
        return {}
        
    suffix = os.getenv("SYMBOL_SUFFIX", "")
    ai_positions = {}
    for p in positions:
        if p.magic == magic:
            clean_sym = p.symbol.replace(suffix, "") if suffix else p.symbol
            if symbol and clean_sym.upper() != symbol.upper():
                continue
            pos_type = 'BUY' if p.type == mt5.ORDER_TYPE_BUY else 'SELL'
            ai_positions[clean_sym.upper()] = {
                'ticket': p.ticket,
                'symbol': p.symbol,
                'clean_symbol': clean_sym,
                'type': pos_type,
                'volume': p.volume,
                'price_open': p.price_open,
                'sl': p.sl,
                'tp': p.tp,
                'time': p.time
            }
    return ai_positions

def apply_ai_breakeven_stops(progress_threshold=0.80):
    """
    Audits active AI positions (magic 444).
    If a trade has progressed >= progress_threshold (default 70%) towards its TP target,
    moves the Stop Loss to Breakeven (entry price ± 1 pip) to make it 100% risk-free.
    """
    magic = MAGIC_NUMBERS.get('AI', 444)
    if not mt5.initialize(path=TERMINAL_PATH):
        print("MT5: Failed to initialize for breakeven check.")
        return []
        
    positions = mt5.positions_get()
    if not positions:
        return []
        
    suffix = os.getenv("SYMBOL_SUFFIX", "")
    modified_positions = []
    
    for p in positions:
        if p.magic != magic:
            continue
            
        clean_symbol = p.symbol.replace(suffix, "") if suffix else p.symbol
        symbol_info = mt5.symbol_info(p.symbol)
        tick = mt5.symbol_info_tick(p.symbol)
        if not symbol_info or not tick:
            continue
            
        pip_size = 0.01 if "JPY" in clean_symbol.upper() else 0.0001
        is_buy = (p.type == mt5.ORDER_TYPE_BUY)
        current_price = tick.bid if is_buy else tick.ask
        
        if p.tp == 0.0:
            continue
            
        total_target_dist = abs(p.tp - p.price_open)
        if total_target_dist <= 0:
            continue
            
        if is_buy:
            profit_dist = current_price - p.price_open
            progress = profit_dist / total_target_dist
            target_be_sl = round(p.price_open + (1.0 * pip_size), symbol_info.digits)
            
            if progress >= progress_threshold and p.sl < target_be_sl:
                print(f"Breakeven trigger for {clean_symbol} BUY (Ticket {p.ticket}): Progress {progress*100:.1f}% >= {progress_threshold*100:.0f}%.")
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": int(p.ticket),
                    "symbol": p.symbol,
                    "sl": float(target_be_sl),
                    "tp": float(p.tp)
                }
                result = mt5.order_send(request)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"SUCCESS: Moved SL to Breakeven (+1 pip) for {clean_symbol} BUY: {target_be_sl}")
                    modified_positions.append({
                        'symbol': clean_symbol,
                        'ticket': p.ticket,
                        'type': 'BUY',
                        'progress_pct': progress * 100,
                        'entry': p.price_open,
                        'new_sl': target_be_sl,
                        'tp': p.tp
                    })
        else: # SELL
            profit_dist = p.price_open - current_price
            progress = profit_dist / total_target_dist
            target_be_sl = round(p.price_open - (1.0 * pip_size), symbol_info.digits)
            
            if progress >= progress_threshold and (p.sl > target_be_sl or p.sl == 0.0):
                print(f"Breakeven trigger for {clean_symbol} SELL (Ticket {p.ticket}): Progress {progress*100:.1f}% >= {progress_threshold*100:.0f}%.")
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": int(p.ticket),
                    "symbol": p.symbol,
                    "sl": float(target_be_sl),
                    "tp": float(p.tp)
                }
                result = mt5.order_send(request)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"SUCCESS: Moved SL to Breakeven (+1 pip) for {clean_symbol} SELL: {target_be_sl}")
                    modified_positions.append({
                        'symbol': clean_symbol,
                        'ticket': p.ticket,
                        'type': 'SELL',
                        'progress_pct': progress * 100,
                        'entry': p.price_open,
                        'new_sl': target_be_sl,
                        'tp': p.tp
                    })
                    
    return modified_positions

def close_all_active_positions():
    """
    Emergency procedure: Closes ALL open positions managed by Desk-JPY.
    """
    if not mt5.initialize(path=TERMINAL_PATH):
        print("MT5: Failed to initialize for close_all.")
        return False
        
    positions = mt5.positions_get()
    if not positions:
        return True
        
    jpy_magics = [MAGIC_NUMBERS['AI']]
    for p in positions:
        if p.magic in jpy_magics:
            symbol_info = mt5.symbol_info(p.symbol)
            if not symbol_info:
                continue
            filling_type = mt5.ORDER_FILLING_FOK
            if symbol_info.filling_mode & 1: filling_type = mt5.ORDER_FILLING_FOK
            elif symbol_info.filling_mode & 2: filling_type = mt5.ORDER_FILLING_IOC
            else: filling_type = mt5.ORDER_FILLING_RETURN

            tick = mt5.symbol_info_tick(p.symbol)
            if not tick:
                continue
            price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask
            order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": p.symbol,
                "volume": float(p.volume),
                "type": order_type,
                "position": int(p.ticket),
                "price": float(price),
                "deviation": 20,
                "magic": int(p.magic),
                "comment": "Desk-JPY Emergency Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_type,
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"Closed Desk-JPY position {p.ticket} for {p.symbol}")
            else:
                print(f"Failed to close position {p.ticket}: {res.comment if res else 'Unknown'}")
                
    return True
