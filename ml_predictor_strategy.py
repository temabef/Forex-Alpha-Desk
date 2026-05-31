import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score
from datetime import datetime

def prepare_features(df):
    """
    Feature Engineering for the Quant Predictor.
    Creates 14 rich features for the Gradient Boosting model.
    """
    df = df.copy()
    
    # EMAs
    ema_20 = df['Close'].ewm(span=20, adjust=False).mean()
    ema_50 = df['Close'].ewm(span=50, adjust=False).mean()
    df['ema_20_distance'] = (df['Close'] - ema_20) / ema_20
    df['ema_50_distance'] = (df['Close'] - ema_50) / ema_50
    
    # Bollinger Bands (20-period, 2 std)
    roll_mean = df['Close'].rolling(window=20).mean()
    roll_std = df['Close'].rolling(window=20).std()
    upper_bb = roll_mean + (roll_std * 2)
    lower_bb = roll_mean - (roll_std * 2)
    df['bb_position'] = (df['Close'] - lower_bb) / (upper_bb - lower_bb + 1e-8)
    
    # MACD (12, 26, 9)
    ema_12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    df['macd_hist'] = macd - macd_signal
    
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ATR Ratio (ATR14 / ATR50)
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - df['Close'].shift(1)).abs()
    tr3 = (df['Low'] - df['Close'].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_14 = tr.rolling(window=14).mean()
    atr_50 = tr.rolling(window=50).mean()
    df['atr_ratio'] = atr_14 / (atr_50 + 1e-8)
    
    # Momentum
    df['mom_1'] = df['Close'].pct_change(1)
    df['mom_4'] = df['Close'].pct_change(4)
    df['mom_12'] = df['Close'].pct_change(12)
    
    # Volatility
    df['volatility'] = df['mom_1'].rolling(window=24).std()
    
    # Hour of day cyclical encoding
    hours = df.index.hour if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df['time']).dt.hour
    df['hour_sin'] = np.sin(2 * np.pi * hours / 24)
    df['hour_cos'] = np.cos(2 * np.pi * hours / 24)
    
    # Candle Structure
    df['hl_range'] = (df['High'] - df['Low']) / df['Close']
    df['body_ratio'] = (df['Close'] - df['Open']) / (df['High'] - df['Low'] + 1e-8)
    
    # Target: Did the price go UP in 4 hours?
    df['target'] = (df['Close'].shift(-4) > df['Close']).astype(int)
    
    return df.dropna()

def get_ml_prediction(df):
    """
    Trains a Gradient Boosting model on recent data, 
    estimates walk-forward accuracy, and predicts current direction.
    Returns: prediction, probability, estimated_win_rate
    """
    # 1. Prepare features
    data = prepare_features(df)
    
    if len(data) < 300: # Need more data for proper training & validation
        return None, 0.0, 0.0

    features = [
        'ema_20_distance', 'ema_50_distance', 'bb_position', 'macd_hist', 
        'rsi', 'atr_ratio', 'mom_1', 'mom_4', 'mom_12', 'volatility', 
        'hour_sin', 'hour_cos', 'hl_range', 'body_ratio'
    ]
    
    # 2. Walk-Forward Validation (Test on last 100 historical bars)
    # We exclude the very last 4 rows from ANY training/testing as targets are unknown
    historical_data = data.iloc[:-4]
    
    train_wf = historical_data.iloc[:-100]
    test_wf = historical_data.iloc[-100:]
    
    model_wf = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=42)
    model_wf.fit(train_wf[features], train_wf['target'])
    preds_wf = model_wf.predict(test_wf[features])
    estimated_win_rate = accuracy_score(test_wf['target'], preds_wf)
    
    # 3. Train final model on ALL historical data
    X = historical_data[features]
    y = historical_data['target']
    
    final_model = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=42)
    final_model.fit(X, y)
    
    # 4. Predict for the VERY LATEST data point
    latest_x = data[features].tail(1)
    prediction = final_model.predict(latest_x)[0]
    probability = final_model.predict_proba(latest_x)[0][prediction]
    
    return prediction, probability, estimated_win_rate
