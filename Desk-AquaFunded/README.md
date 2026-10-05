# Nautilus Desk-AquaFunded — Multi-Asset AI Quant Desk

Dedicated algorithmic trading desk deploying the proven **AI Quant Predictor Engine** across:
- **`USDJPY`**: Macro trend runner driven by US-Japan interest rate divergence and carry trade flows (0.08 lot size).
- **`USDCAD`**: North American commodity & monetary policy divergence pair (0.08 lot size).
- **`EURUSD`**: High-liquidity premier major with consistent walk-forward predictive edge (0.08 lot size).

---

## Strategy: Multi-Asset Quant Predictor (Adaptive AI)

Every asset is evaluated hourly using the identical machine learning quantitative engine:
- **Timeframe**: Hourly (H1) candles with real-time MT5 tick fill price anchoring.
- **Machine Learning**: Walk-forward validated Gradient Boosting Classifier with 14 cyclical, volatility, and momentum features.
- **Gating Filters**:
  - Minimum Confidence: $\ge 60\%$.
  - Walk-Forward Historical Win Rate: $\ge 42\%$.
  - Trend Confirmation: Alignment with 20-period EMA.
- **Adaptive Targets**:
  - Stop Loss: `2.5x ATR` (minimum 20 pips for JPY pairs / 15 pips for 5-digit majors safety floor).
  - Take Profit: `1.5x` Risk-to-Reward ratio (`3.75x ATR`).
- **Active Trade Management**:
  - **80% Breakeven Lock**: Moves SL to entry + 1 pip once 80% of TP distance is achieved.
  - **Early Reversal Exit**: Exits opposite positions immediately when an opposing high-conviction signal is confirmed.

---

## Prop Firm Shield Suite

1. **Daily Drawdown Kill-Switch**: Hard-coded 3.5% equity drawdown lock. If breached, all open trades are closed instantly and execution is locked until the next calendar day.
2. **High-Impact News Filter**: Real-time HTTP feed checking red-folder news for **USD, JPY, EUR, and CAD**. Suspends entries 30 minutes before and after events.
3. **Friday Weekend Exit**: Optional 20:00 GMT Friday closure to eliminate weekend gap risk.
4. **Isolated Magic Number**: `444` (AI) ensures zero interference with other trading desks (`Desk-5k`, `Desk-10k`).

---

## Commands

Run manual scan:
```powershell
python get_current_signal.py
```

Run dry-run scan (safe mode, no live orders placed):
```powershell
python get_current_signal.py --dry-run
```

Run test suite:
```powershell
python -m unittest discover -s tests -v
```
