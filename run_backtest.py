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
                strategy_path="pairs_trading_strategy:CointegratedPairsStrategy",
                config_path="pairs_trading_strategy:PairsTradingConfig",
                config={
                    "instrument_id_a": "EURUSD.SIM",
                    "instrument_id_b": "GBPUSD.SIM",
                    "lookback_period": 120,
                    "entry_threshold": 2.0,
                    "exit_threshold": 0.0,
                    "stop_loss_usd": 1000.0,  # $1,000 stop
                    "take_profit_usd": 2500.0 # $2,500 target
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
        ),
        BacktestDataConfig(
            catalog_path="./catalog",
            data_cls="nautilus_trader.model.data:Bar",
            instrument_id="GBPUSD.SIM",
            bar_spec="1-HOUR-MID",
        ),
    ],
    raise_exception=True,
)

if __name__ == "__main__":
    print("Starting Backtest using BacktestNode...")
    node = BacktestNode(configs=[run_config])
    results = node.run()

    print(f"\n--- BACKTEST RESULTS ({len(results)} total) ---")
    for i, res in enumerate(results):
        print(f"\nResult {i+1}:")
        print(f"  Run ID: {res.run_id}")
        stats_dict = res.stats_pnls
        if stats_dict:
            for currency, stats in stats_dict.items():
                print(f"  PnL Stats ({currency}):")
                if 'PnL (total)' in stats:
                    print(f"    Total PnL: {stats['PnL (total)']}")
                if 'PnL% (total)' in stats:
                    print(f"    Total Return: {stats['PnL% (total)']:.2f}%")
        
        # In v1.226.0 Node results, raw counts might be inside engine stats
        # but the log summary confirms 2 orders and 2 positions were created.
        print(f"  Total Events Processed: {res.total_events}")
        
    if not results:
        print("No results returned.")
