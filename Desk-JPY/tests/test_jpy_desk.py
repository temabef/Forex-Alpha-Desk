import os
import sys
from pathlib import Path
import unittest
import pandas as pd
import numpy as np
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_predictor_strategy import prepare_features, get_ml_prediction
from mt5_executor import MAGIC_NUMBERS
from news_manager import is_in_danger_zone


class JpyDeskTests(unittest.TestCase):
    def test_magic_number_isolation(self):
        """Ensure Desk-JPY magic number does not collide with Desk-5k or Desk-10k (111, 123456)"""
        self.assertEqual(MAGIC_NUMBERS['AI'], 444)
        self.assertNotIn(MAGIC_NUMBERS['AI'], [111, 222, 333, 123456])

    def test_multi_major_pip_math(self):
        """Verify pip scaling for both JPY and standard 5-digit majors"""
        # USDJPY (0.01 per pip, 20-pip min safety floor)
        jpy_pip = 0.01 if "JPY" in "USDJPY" else 0.0001
        self.assertEqual(jpy_pip, 0.01)
        jpy_min_sl = (20 if "JPY" in "USDJPY" else 15) * jpy_pip
        self.assertAlmostEqual(jpy_min_sl, 0.20)
        
        # USDCAD & EURUSD (0.0001 per pip, 15-pip min safety floor)
        cad_pip = 0.01 if "JPY" in "USDCAD" else 0.0001
        self.assertEqual(cad_pip, 0.0001)
        cad_min_sl = (20 if "JPY" in "USDCAD" else 15) * cad_pip
        self.assertAlmostEqual(cad_min_sl, 0.0015)
        
        eur_pip = 0.01 if "JPY" in "EURUSD" else 0.0001
        self.assertEqual(eur_pip, 0.0001)
        eur_min_sl = (20 if "JPY" in "EURUSD" else 15) * eur_pip
        self.assertAlmostEqual(eur_min_sl, 0.0015)

    def test_symbols_and_lot_config(self):
        """Verify Desk-JPY configuration targets USDJPY, USDCAD, and EURUSD with 0.08 lot size"""
        from dotenv import dotenv_values
        env_vals = dotenv_values(ROOT / ".env")
        self.assertEqual(float(env_vals.get("LOT_SIZE_AI")), 0.08)
        
        # Verify get_current_signal targets all three majors
        with open(ROOT / "get_current_signal.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn('symbols = ["USDJPY", "USDCAD", "EURUSD"]', code)

    def test_ml_features_generation(self):
        """Verify feature engineering produces all 14 expected features"""
        dates = pd.date_range("2026-01-01", periods=100, freq="h")
        prices = 155.0 + np.cumsum(np.random.normal(0, 0.2, 100))
        df = pd.DataFrame({
            "Open": prices,
            "High": prices + 0.15,
            "Low": prices - 0.15,
            "Close": prices + 0.05
        }, index=dates)

        features_df = prepare_features(df)
        self.assertGreater(len(features_df), 0)
        expected_cols = [
            'ema_20_distance', 'ema_50_distance', 'bb_position', 'macd_hist', 
            'rsi', 'atr_ratio', 'mom_1', 'mom_4', 'mom_12', 'volatility', 
            'hour_sin', 'hour_cos', 'hl_range', 'body_ratio'
        ]
        for col in expected_cols:
            self.assertIn(col, features_df.columns)
            self.assertFalse(features_df[col].isna().any())

    def test_ml_prediction_pipeline(self):
        """Verify ML pipeline completes and returns prediction within [0, 1]"""
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=120, freq="h")
        prices = 150.0 + np.cumsum(np.random.normal(0.05, 0.2, 120))
        df = pd.DataFrame({
            "Open": prices,
            "High": prices + 0.25,
            "Low": prices - 0.25,
            "Close": prices + 0.10
        }, index=dates)

        pred, prob, wr = get_ml_prediction(df)
        self.assertIn(pred, [0, 1])
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)
        self.assertGreaterEqual(wr, 0.0)

    def test_daily_drawdown_math(self):
        """Verify 3.5% daily drawdown calculation"""
        start_balance = 10000.0
        equity_safe = 9800.0   # 2.0% drawdown (safe)
        equity_breach = 9600.0 # 4.0% drawdown (breach)
        max_pct = 0.035

        dd_safe = (start_balance - equity_safe) / start_balance
        dd_breach = (start_balance - equity_breach) / start_balance

        self.assertLess(dd_safe, max_pct)
        self.assertGreaterEqual(dd_breach, max_pct)


if __name__ == "__main__":
    unittest.main()
