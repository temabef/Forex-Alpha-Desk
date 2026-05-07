import numpy as np
import statsmodels.api as sm
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType, BarSpecification
from nautilus_trader.model.enums import BarAggregation, PriceType, OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity

class PairsTradingConfig(StrategyConfig):
    instrument_id_a: str
    instrument_id_b: str
    lookback_period: int = 60
    entry_threshold: float = 2.0
    exit_threshold: float = 0.0
    stop_loss_usd: float = 1000.0
    take_profit_usd: float = 2500.0

class CointegratedPairsStrategy(Strategy):
    def __init__(self, config: PairsTradingConfig):
        super().__init__(config)
        self.lookback = config.lookback_period
        self.entry_threshold = config.entry_threshold
        self.exit_threshold = config.exit_threshold
        self.id_a = InstrumentId.from_str(config.instrument_id_a)
        self.id_b = InstrumentId.from_str(config.instrument_id_b)
        
        # Buffer to synchronize bars (more lenient)
        self.last_price_a = None
        self.last_price_b = None
        
        # Price history
        self.prices_a = []
        self.prices_b = []
        self.gamma = 1.0

    def on_start(self):
        # We must precisely match the BarType in the catalog: 1-HOUR-MID-EXTERNAL
        from nautilus_trader.model.data import BarType, BarSpecification
        from nautilus_trader.model.enums import BarAggregation, PriceType
        
        # This matches the 'MID' price type we ingested in ingest_data.py
        bar_spec = BarSpecification(1, BarAggregation.HOUR, PriceType.MID)
        
        # Subscribe explicitly using the Instrument IDs
        self.subscribe_bars(BarType(self.id_a, bar_spec))
        self.subscribe_bars(BarType(self.id_b, bar_spec))
        
        self.log.info(f"Strategy started for {self.id_a} and {self.id_b}")

    def on_bar(self, bar: Bar):
        # 1. Store latest price for each
        if bar.bar_type.instrument_id == self.id_a:
            self.last_price_a = float(bar.close)
        elif bar.bar_type.instrument_id == self.id_b:
            self.last_price_b = float(bar.close)
        
        # 2. Only proceed when we have a new "Pair"
        if self.last_price_a is None or self.last_price_b is None:
            return
            
        # Add to history and reset "last" to wait for next hour
        self.prices_a.append(self.last_price_a)
        self.prices_b.append(self.last_price_b)
        self.last_price_a = None
        self.last_price_b = None
        
        if len(self.prices_a) < self.lookback:
            return

        # Keep history at lookback size
        hist_a = self.prices_a[-self.lookback:]
        hist_b = self.prices_b[-self.lookback:]
        
        # 3. Calculate Cointegration (OLS)
        y = np.array(hist_a)
        x = sm.add_constant(np.array(hist_b))
        model = sm.OLS(y, x).fit()
        
        intercept = model.params[0]
        self.gamma = model.params[1]
        
        # 4. Calculate Z-Score
        spreads = y - (self.gamma * np.array(hist_b) + intercept)
        current_spread = spreads[-1]
        z_score = (current_spread - np.mean(spreads)) / np.std(spreads)

        # Telemetry
        self.log.info(f"DATA: {bar.ts_event}, {hist_a[-1]:.5f}, {hist_b[-1]:.5f}, {current_spread:.6f}, {z_score:.2f}, {self.gamma:.4f}")

        # --- TRADING LOGIC ---
        is_flat_a = self.portfolio.is_flat(self.id_a)
        is_flat_b = self.portfolio.is_flat(self.id_b)
        
        if is_flat_a and is_flat_b:
            if z_score > self.entry_threshold:
                self.log.info(f"SIGNAL: SELL SPREAD (Z={z_score:.2f})")
                qty_a = 10000
                qty_b = int(10000 * self.gamma)
                self.submit_order(self.order_factory.market(self.id_a, OrderSide.SELL, Quantity.from_int(qty_a)))
                self.submit_order(self.order_factory.market(self.id_b, OrderSide.BUY, Quantity.from_int(qty_b)))
            
            elif z_score < -self.entry_threshold:
                self.log.info(f"SIGNAL: BUY SPREAD (Z={z_score:.2f})")
                qty_a = 10000
                qty_b = int(10000 * self.gamma)
                self.submit_order(self.order_factory.market(self.id_a, OrderSide.BUY, Quantity.from_int(qty_a)))
                self.submit_order(self.order_factory.market(self.id_b, OrderSide.SELL, Quantity.from_int(qty_b)))

        else:
            if abs(z_score) < self.exit_threshold:
                self.log.info(f"SIGNAL: REVERTED (Z={z_score:.2f}). CLOSING.")
                self.close_all_positions(self.id_a)
                self.close_all_positions(self.id_b)
            
            # SL/TP
            pnl = float(self.portfolio.unrealized_pnl(self.id_a)) + float(self.portfolio.unrealized_pnl(self.id_b))
            if pnl < -1000 or pnl > 2500:
                self.log.info(f"RISK EXIT (PnL={pnl:.2f})")
                self.close_all_positions(self.id_a)
                self.close_all_positions(self.id_b)
