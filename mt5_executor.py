import MetaTrader5 as mt5
import pandas as pd
import time

# --- CONFIGURATION ---
TERMINAL_PATH = None 

# Strategy Magic Numbers
MAGIC_NUMBERS = {
    'Pairs': 222,
    'AI': 111,
    'Trend': 333
}

def execute_mt5_trade(strategy_name, action, symbol="EURUSD", volume=0.2, tp_pips=20, sl_pips=15):
    """
    Executes a trade on MetaTrader 5.
    """
    magic = MAGIC_NUMBERS.get(strategy_name, 123456)
    
    if TERMINAL_PATH:
        init_ok = mt5.initialize(path=TERMINAL_PATH)
    else:
        init_ok = mt5.initialize()

    if not init_ok:
        print("MT5 initialize() failed, error code =", mt5.last_error())
        return False

    # 1. Check if we have an open position for THIS strategy (by magic number)
    positions = mt5.positions_get(symbol=symbol)
    strategy_pos = None
    if positions:
        for p in positions:
            if p.magic == magic:
                strategy_pos = p
                break

    if strategy_pos:
        if action == 'EXIT':
            print(f"MT5: Closing {strategy_name} position for {symbol}")
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": strategy_pos.volume,
                "type": mt5.ORDER_TYPE_SELL if strategy_pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": strategy_pos.ticket,
                "price": mt5.symbol_info_tick(symbol).bid if strategy_pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).ask,
                "magic": magic,
                "comment": f"Close {strategy_name}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK, # Default close
            }
            # Auto-detect filling for close too
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info.filling_mode & 1: close_request["type_filling"] = mt5.ORDER_FILLING_FOK
            elif symbol_info.filling_mode & 2: close_request["type_filling"] = mt5.ORDER_FILLING_IOC
            
            result = mt5.order_send(close_request)
            return result.retcode == mt5.TRADE_RETCODE_DONE
        else:
            print(f"MT5: Already have a {strategy_name} position in {symbol}. Skipping.")
            return True

    if action == 'EXIT': return True

    # 2. Prepare Entry
    tick = mt5.symbol_info_tick(symbol)
    point = mt5.symbol_info(symbol).point
    
    # Auto-detect filling mode (using raw numbers since library constants vary)
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info.filling_mode & 1: # FOK
        filling_type = mt5.ORDER_FILLING_FOK
    elif symbol_info.filling_mode & 2: # IOC
        filling_type = mt5.ORDER_FILLING_IOC
    else:
        filling_type = mt5.ORDER_FILLING_RETURN

    order_type = mt5.ORDER_TYPE_BUY if action == 'BUY' or action == 'BUY_SPREAD' else mt5.ORDER_TYPE_SELL
    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
    
    sl = price - (sl_pips * 10 * point) if order_type == mt5.ORDER_TYPE_BUY else price + (sl_pips * 10 * point)
    tp = price + (tp_pips * 10 * point) if order_type == mt5.ORDER_TYPE_BUY else price - (tp_pips * 10 * point)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "magic": magic,
        "comment": f"{strategy_name} Trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_type,
    }

    print(f"MT5: Sending {action} for {symbol} @ {price}")
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"MT5 ERROR: Order failed, retcode={result.retcode}")
        return False

    print(f"MT5 SUCCESS: Ticket #{result.order}")
    return True

def get_mt5_active_positions(strategy_name=None):
    if TERMINAL_PATH:
        init_ok = mt5.initialize(path=TERMINAL_PATH)
    else:
        init_ok = mt5.initialize()
    
    if not init_ok: return []
    positions = mt5.positions_get()
    
    if not positions: return []
    
    if strategy_name:
        magic = MAGIC_NUMBERS.get(strategy_name)
        return [p.symbol for p in positions if p.magic == magic]
    
    return [p.symbol for p in positions]

if __name__ == "__main__":
    # Test
    print("MT5 Active Positions:", get_mt5_active_positions())
