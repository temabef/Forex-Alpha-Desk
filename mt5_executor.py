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

    # Get symbol properties
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol {symbol} not found")
        return False

    # Ensure symbol is visible
    if not symbol_info.visible:
        mt5.symbol_select(symbol, True)

    # 1. Rounding Price Logic
    tick = mt5.symbol_info_tick(symbol)
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
    positions = mt5.positions_get(symbol=symbol)
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
        if sl is None or tp is None:
            # Universal 50-pip safety net if no target is provided
            pip_size = 0.01 if "JPY" in symbol else 0.0001
            sl_dist = 50 * pip_size
            tp_dist = 50 * pip_size
            sl = price - sl_dist if order_type == mt5.ORDER_TYPE_BUY else price + sl_dist
            tp = price + tp_dist if order_type == mt5.ORDER_TYPE_BUY else price - tp_dist
    else:
        sl = 0.0
        tp = 0.0

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
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
    active_symbols = []
    for p in positions:
        if magic is None or p.magic == magic:
            active_symbols.append(p.symbol)
            
    return active_symbols
