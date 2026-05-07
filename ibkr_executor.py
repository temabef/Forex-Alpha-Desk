import asyncio
import nest_asyncio
import os
from dotenv import load_dotenv
from ib_insync import IB, Forex, MarketOrder, LimitOrder, StopOrder, BracketOrder
import logging

# Load secrets
load_dotenv()

# Required for ib_insync in async environments like Jupyter or some event loops
nest_asyncio.apply()

# --- CONFIGURATION ---
IB_HOST = '127.0.0.1'
IB_PORT = 4002  
IB_CLIENT_ID = 1  
ACCOUNT_ID = os.getenv('IBKR_ACCOUNT_ID')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger('IBKR_Executor')

async def execute_ibkr_trade(strategy_name, action, symbol="EURUSD", quantity=20000, tp=None, sl=None):
    """
    Executes a trade on IBKR Gateway.
    strategy_name: 'Pairs', 'Trend', or 'AI'
    action: 'BUY', 'SELL', or 'EXIT'
    """
    if action == 'PING': return True
    
    ib = IB()
    
    # Error Listener to catch "No Permissions" or "Margin" errors
    def onError(reqId, errorCode, errorString, contract):
        print(f"IBKR MESSAGE [{errorCode}]: {errorString}")

    ib.errorEvent += onError

    try:
        print(f"--- [IBKR] Connecting to {IB_HOST}:{IB_PORT} ---")
        await ib.connectAsync(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
        
        if not ib.isConnected():
            print("ERROR: [IBKR] Failed to connect to Gateway!")
            return False

        print(f"INFO: [IBKR] Connected! Checking positions for {symbol}...")
        
        # Check current positions to avoid duplicates
        positions = ib.positions()
        current_pos = 0
        for p in positions:
            if p.contract.symbol == symbol.replace('USD', ''):
                current_pos = p.position
                break

        # 1. Handle EXIT signals
        if action == 'EXIT':
            if current_pos == 0:
                print(f"INFO: [IBKR] No position found for {symbol}. Skipping EXIT.")
                return True
            side = 'SELL' if current_pos > 0 else 'BUY'
            order = MarketOrder(side, abs(current_pos))
            trade = ib.placeOrder(p.contract, order)
            print(f"EXEC: [IBKR] EXIT: Closing {abs(current_pos)} units of {symbol}")
            return True

        # 2. Check if we are already in a trade (to avoid stacking)
        if current_pos != 0:
            print(f"WAIT: [IBKR] DUPLICATE PREVENTED: Already have {current_pos} units of {symbol}. Skipping {action}.")
            return True

        # 3. Setup Contract
        base_curr = symbol[:3]
        quote_curr = symbol[3:]
        contract = Forex(pair=f"{base_curr}{quote_curr}")
        await ib.qualifyContractsAsync(contract)

        # 4. Handle PAIRS Trading
        if strategy_name == 'Pairs':
            if "_" in symbol:
                s1, s2 = symbol.split("_")
                if action == 'BUY_SPREAD':
                    print("EXEC: [IBKR] Executing BUY SPREAD (Buy EUR, Sell GBP)")
                    await execute_ibkr_trade('Pairs_Sub', 'BUY', symbol=s1, quantity=quantity)
                    await execute_ibkr_trade('Pairs_Sub', 'SELL', symbol=s2, quantity=quantity)
                elif action == 'SELL_SPREAD':
                    print("EXEC: [IBKR] Executing SELL SPREAD (Sell EUR, Buy GBP)")
                    await execute_ibkr_trade('Pairs_Sub', 'SELL', symbol=s1, quantity=quantity)
                    await execute_ibkr_trade('Pairs_Sub', 'BUY', symbol=s2, quantity=quantity)
                return True

        # 5. Place the Entry order and wait for SUBMITTED (not just ApiPending)
        print(f"EXEC: [IBKR] Placing {action} Market Order: {quantity} {symbol}")
        entry_order = MarketOrder(action, quantity)
        entry_order.account = ACCOUNT_ID
        entry_order.transmit = True 
        entry_trade = ib.placeOrder(contract, entry_order)

        # Wait for entry to be accepted by the exchange
        print("INFO: [IBKR] Waiting for exchange confirmation...")
        for _ in range(30): # Wait up to 30 seconds
            await asyncio.sleep(1)
            status = entry_trade.orderStatus.status
            if status in ('PreSubmitted', 'Submitted', 'Filled'):
                break
            if status == 'Cancelled':
                break
            if _ % 5 == 0:
                print(f"INFO: [IBKR] Entry Status: {status}...")

        if entry_trade.orderStatus.status not in ('PreSubmitted', 'Submitted', 'Filled'):
            print(f"WARNING: [IBKR] Entry order status is {entry_trade.orderStatus.status}. It might be rejected or queued.")
            return False

        print(f"SUCCESS: [IBKR] Entry order LIVE! Status={entry_trade.orderStatus.status}")

        # Now attach TP and SL if provided
        if tp and sl:
            parent_id = entry_trade.order.orderId
            close_action = 'BUY' if action == 'SELL' else 'SELL'

            # Take Profit (Limit Order)
            tp_order = LimitOrder(close_action, quantity, tp)
            tp_order.account = ACCOUNT_ID
            tp_order.parentId = parent_id
            tp_order.transmit = False
            ib.placeOrder(contract, tp_order)

            # Stop Loss (Stop Order)
            sl_order = StopOrder(close_action, quantity, sl)
            sl_order.account = ACCOUNT_ID
            sl_order.parentId = parent_id
            sl_order.transmit = True  # Transmit sends all 3 at once
            ib.placeOrder(contract, sl_order)

            print(f"EXEC: [IBKR] TP set at {tp:.5f}, SL set at {sl:.5f}")
            await asyncio.sleep(2)

        return True

    except Exception as e:
        print(f"ERROR: [IBKR] Execution Error: {e}")
        return False
    finally:
        print("--- [IBKR] Disconnecting ---")
        ib.disconnect()

async def get_active_positions():
    """
    Returns a list of symbols that currently have open positions.
    """
    ib = IB()
    try:
        await ib.connectAsync(IB_HOST, IB_PORT, clientId=99) # Use a separate ID for checking
        positions = ib.positions()
        active_symbols = []
        for p in positions:
            if p.position != 0:
                # Convert 'EUR' to 'EURUSD' for consistency
                symbol = p.contract.symbol + "USD"
                active_symbols.append(symbol)
        return active_symbols
    except:
        return []
    finally:
        ib.disconnect()


if __name__ == "__main__":
    # Test connection
    asyncio.run(execute_ibkr_trade('Test', 'PING'))
