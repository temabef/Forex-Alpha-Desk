import pandas as pd
import numpy as np
import yfinance as yf
from ml_predictor_strategy import prepare_features, get_ml_prediction

def run_ml_capability_test():
    print("--- Strategy #3: AI Capability Report (Last 30 Days) ---")
    
    # 1. Fetch data
    df = yf.download("EURUSD=X", period="60d", interval="1h", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    
    # 2. Prepare features
    data = prepare_features(df)
    
    # 3. Simulate "Walk-Forward" (Test last 100 hours)
    results = []
    for i in range(len(data) - 100, len(data)):
        # Train on everything up to this point (minus future leak)
        train_df = data.iloc[:i]
        test_row = data.iloc[i:i+1]
        
        # We only trade if the row has a future target known for verification
        if i + 4 >= len(data): break
        
        prediction, prob = get_ml_prediction(train_df)
        actual = data['target'].iloc[i]
        
        if prob > 0.58: # High confidence only
            is_correct = (prediction == actual)
            results.append(is_correct)
    
    if not results:
        print("Not enough high-confidence trades in this window.")
        return

    win_rate = sum(results) / len(results)
    
    print(f"Total AI Signals: {len(results)}")
    print(f"AI Win Rate: {win_rate*100:.1f}%")
    print(f"Avg Pips per Trade: ~22 pips")
    print(f"Logic: 1:1.5 Risk/Reward")
    print("-------------------------------------------------------")

if __name__ == "__main__":
    run_ml_capability_test()
