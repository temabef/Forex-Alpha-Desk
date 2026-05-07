from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import (
    BacktestRunConfig,
    BacktestVenueConfig,
    BacktestDataConfig,
    BacktestEngineConfig,
)
from nautilus_trader.trading.config import ImportableStrategyConfig
import os
import sys

# Ensure the strategy module can be found in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

run_config = BacktestRunConfig(
    engine=BacktestEngineConfig(
        strategies=[
            ImportableStrategyConfig(
                strategy_path="trend_breakout_strategy:DonchianBreakoutStrategy",
                config_path="trend_breakout_strategy:DonchianBreakoutConfig",
                config={
                    "instrument_id": "EURUSD.SIM",
                    "entry_lookback": 400, # ~2.5 weeks (captures real macro trends)
                    "exit_lookback": 200,  # ~1.2 weeks trailing stop
                    "trade_size": 100000  # 1 lot
                }
            )
        ]
    ),
    venues=[
        BacktestVenueConfig(
            name="SIM",
            oms_type="NETTING",
            account_type="MARGIN",
            base_currency="USD",
            starting_balances=["1000000 USD"],
        )
    ],
    data=[
        BacktestDataConfig(
            catalog_path="./catalog",
            data_cls="nautilus_trader.model.data:Bar",
            instrument_id="EURUSD.SIM",
            bar_spec="1-HOUR-MID",
        )
    ],
    raise_exception=True,
)

if __name__ == "__main__":
    node = BacktestNode(configs=[run_config])
    results = node.run()
    print("\n--- TREND BREAKOUT BACKTEST COMPLETED ---")
