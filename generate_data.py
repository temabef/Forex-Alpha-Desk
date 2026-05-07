import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_csv(symbol, base_price, num_bars=10000):
    rows = []
    start_time = datetime(2025, 1, 1, 9, 0)
    
    # Generate hourly bars
    np.random.seed(42 if symbol == "EURUSD" else 43)
    
    current_price = base_price
    for i in range(num_bars):
        # Add some random walk logic
        move = np.random.normal(0, 0.001)
        # Add a shared trend component (correlation)
        shared_move = np.sin(i / 10.0) * 0.002 
        
        open_p = current_price
        close_p = open_p + move + shared_move
        
        high_p = max(open_p, close_p) + abs(np.random.normal(0, 0.0005))
        low_p = min(open_p, close_p) - abs(np.random.normal(0, 0.0005))
        
        rows.append({
            "timestamp": (start_time + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
            "open": round(open_p, 5),
            "high": round(high_p, 5),
            "low": round(low_p, 5),
            "close": round(close_p, 5),
            "volume": np.random.randint(100, 1000)
        })
        current_price = close_p
        
    df = pd.DataFrame(rows)
    df.to_csv(f"data/{symbol}.csv", index=False)
    print(f"Created data/{symbol}.csv with {num_bars} bars")

generate_csv("EURUSD", 1.0850, 10000)
generate_csv("GBPUSD", 1.2650, 10000)
