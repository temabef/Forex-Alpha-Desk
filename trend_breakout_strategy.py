from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType, BarSpecification
from nautilus_trader.model.enums import BarAggregation, PriceType, OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
import numpy as np

class DonchianBreakoutConfig(StrategyConfig):
    instrument_id: str
    entry_lookback: int = 48  # 48 hours (2 days) to define the channel
    exit_lookback: int = 24   # 24 hours (1 day) for the trailing exit
    trade_size: int = 100000  # 1 standard lot

class DonchianBreakoutStrategy(Strategy):
    def __init__(self, config: DonchianBreakoutConfig):
        super().__init__(config)
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.entry_lookback = config.entry_lookback
        self.exit_lookback = config.exit_lookback
        self.trade_size = Quantity.from_int(config.trade_size)
        
        self.highs = []
        self.lows = []
        self.closes = []

    def on_start(self):
        # We must precisely match the BarType in the catalog
        bar_spec = BarSpecification(1, BarAggregation.HOUR, PriceType.MID)
        self.subscribe_bars(BarType(self.instrument_id, bar_spec))
        self.log.info(f"Trend Breakout Strategy started for {self.instrument_id}")

    def on_bar(self, bar: Bar):
        self.highs.append(float(bar.high))
        self.lows.append(float(bar.low))
        self.closes.append(float(bar.close))
        
        # We need at least enough history to calculate the channel
        if len(self.highs) < self.entry_lookback + 1:
            return
            
        # Keep arrays manageable to prevent memory bloat
        max_lookback = max(self.entry_lookback, self.exit_lookback)
        self.highs = self.highs[-(max_lookback + 5):]
        self.lows = self.lows[-(max_lookback + 5):]
        self.closes = self.closes[-(max_lookback + 5):]

        # Calculate Donchian Channels (excluding the current bar to prevent lookahead)
        recent_highs = self.highs[-self.entry_lookback - 1 : -1]
        recent_lows = self.lows[-self.entry_lookback - 1 : -1]
        
        upper_channel = max(recent_highs)
        lower_channel = min(recent_lows)
        
        # Calculate Exit Channels (often shorter than entry to lock in profits)
        exit_recent_highs = self.highs[-self.exit_lookback - 1 : -1]
        exit_recent_lows = self.lows[-self.exit_lookback - 1 : -1]
        
        exit_upper = max(exit_recent_highs)
        exit_lower = min(exit_recent_lows)

        current_close = self.closes[-1]
        
        is_flat = self.portfolio.is_flat(self.instrument_id)
        is_long = self.portfolio.is_net_long(self.instrument_id)
        is_short = self.portfolio.is_net_short(self.instrument_id)

        if is_flat:
            # Entry Logic: Breakout of the highest high or lowest low
            if current_close > upper_channel:
                self.log.info(f"SIGNAL: BREAKOUT LONG (Close {current_close:.5f} > {self.entry_lookback}h High {upper_channel:.5f})")
                self.submit_order(self.order_factory.market(self.instrument_id, OrderSide.BUY, self.trade_size))
            elif current_close < lower_channel:
                self.log.info(f"SIGNAL: BREAKOUT SHORT (Close {current_close:.5f} < {self.entry_lookback}h Low {lower_channel:.5f})")
                self.submit_order(self.order_factory.market(self.instrument_id, OrderSide.SELL, self.trade_size))
        else:
            # Exit Logic: Trailing stop based on a shorter channel
            if is_long and current_close < exit_lower:
                self.log.info(f"SIGNAL: EXIT LONG (Close {current_close:.5f} < {self.exit_lookback}h Low {exit_lower:.5f})")
                self.close_all_positions(self.instrument_id)
            elif is_short and current_close > exit_upper:
                self.log.info(f"SIGNAL: EXIT SHORT (Close {current_close:.5f} > {self.exit_lookback}h High {exit_upper:.5f})")
                self.close_all_positions(self.instrument_id)
