import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime

def prepare_features(df):
    """
    Feature Engineering for the Quant Predictor.
    Creates indicators like RSI, Volatility, and Momentum.
    """
    df = df.copy()
    
    # 1. Returns (Momentum)
    df['returns'] = df['Close'].pct_change()
    df['mom_5'] = df['Close'].pct_change(5)
    
    # 2. Volatility (24h Standard Deviation)
    df['volatility'] = df['returns'].rolling(window=24).std()
    
    # 3. Simple RSI (Relative Strength Index)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 4. Target: Did the price go UP in 4 hours?
    # We shift -4 to look at the "future" during training
    df['target'] = (df['Close'].shift(-4) > df['Close']).astype(int)
    
    return df.dropna()

def get_ml_prediction(df):
    """
    Trains a Random Forest model on recent data and predicts current direction.
    """
    # 1. Prepare features
    data = prepare_features(df)
    
    if len(data) < 100:
        return None, 0.0

    # 2. Split features (X) and target (y)
    # We exclude the last 4 rows because we don't know their future target yet
    features = ['returns', 'mom_5', 'volatility', 'rsi']
    X = data[features].iloc[:-4] 
    y = data['target'].iloc[:-4]
    
    # 3. Train the Model (Random Forest)
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X, y)
    
    # 4. Predict for the VERY LATEST data point
    latest_x = data[features].tail(1)
    prediction = model.predict(latest_x)[0]
    probability = model.predict_proba(latest_x)[0][prediction]
    
    return prediction, probability
