import MetaTrader5 as mt5
import pandas as pd
import time

# --- CONFIGURATION ---
# If you have multiple MT5s, paste the path to your preferred 'terminal64.exe' here
# Example: r"C:\Program Files\XM Global MT5\terminal64.exe"
TERMINAL_PATH = None 

def execute_mt5_trade(strategy_name, action, symbol="EURUSD", volume=0.2, tp_pips=20, sl_pips=15):
    """
    Executes a trade on MetaTrader 5.
    volume: 0.1 = 10,000 units, 0.2 = 20,000 units
    """
    if not mt5.initialize(path=TERMINAL_PATH):
        print("MT5 initialize() failed, error code =", mt5.last_error())
        return False

    # 1. Check if we have an open position already for this symbol
    positions = mt5.positions_get(symbol=symbol)
    if positions:
        current_pos = positions[0]
        if action == 'EXIT':
            print(f"MT5: Closing position for {symbol}")
            # Logic to close...
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": current_pos.volume,
                "type": mt5.ORDER_TYPE_SELL if current_pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": current_pos.ticket,
                "price": mt5.symbol_info_tick(symbol).bid if current_pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).ask,
                "magic": 123456,
                "comment": "Close Trade",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(close_request)
            return result.retcode == mt5.TRADE_RETCODE_DONE
        else:
            print(f"MT5: Already have a position in {symbol}. Skipping.")
            return True

    if action == 'EXIT': return True

    # 2. Prepare Entry
    tick = mt5.symbol_info_tick(symbol)
    point = mt5.symbol_info(symbol).point
    
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
        "magic": 123456,
        "comment": f"{strategy_name} Trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    print(f"MT5: Sending {action} for {symbol} @ {price}")
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"MT5 ERROR: Order failed, retcode={result.retcode}")
        return False

    print(f"MT5 SUCCESS: Ticket #{result.order}")
    return True

def get_mt5_active_positions():
    if not mt5.initialize(): return []
    positions = mt5.positions_get()
    return [p.symbol for p in positions] if positions else []

if __name__ == "__main__":
    # Test
    print("MT5 Active Positions:", get_mt5_active_positions())
