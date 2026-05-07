import pandas as pd
import yfinance as yf
from nautilus_trader.model.data import Bar, BarType, BarSpecification
from nautilus_trader.model.enums import BarAggregation, PriceType
from nautilus_trader.model.identifiers import InstrumentId, Symbol
from nautilus_trader.model.objects import Quantity, Price, Currency
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.model.instruments.currency_pair import CurrencyPair

def download_and_ingest(symbol, yf_ticker, catalog):
    print(f"Downloading real data for {symbol} ({yf_ticker})...")
    
    df = yf.download(yf_ticker, period="730d", interval="1h")
    
    if df.empty:
        print(f"Error: No data found for {yf_ticker}")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df = df.reset_index()
    df = df.rename(columns={
        "Datetime": "timestamp", 
        "Open": "open", 
        "High": "high", 
        "Low": "low", 
        "Close": "close", 
        "Volume": "volume"
    })

    instrument_id = InstrumentId.from_str(f"{symbol}.SIM")
    
    # Correct positional arguments for CurrencyPair v1.226.0
    instrument = CurrencyPair(
        instrument_id,
        Symbol(symbol),
        Currency.from_str(symbol[:3]),
        Currency.from_str(symbol[3:]),
        5, # price_precision
        0, # size_precision
        Price.from_str("0.00001"), # price_increment
        Quantity.from_int(1), # size_increment
        Quantity.from_int(1), # lot_size
        Price.from_str("1.0"), # multiplier
    )
    
    # In this version, use write_data for instruments too
    catalog.write_data([instrument])
    print(f"Instrument {instrument_id} written to catalog.")

    bar_spec = BarSpecification(1, BarAggregation.HOUR, PriceType.MID)
    bar_type = BarType(instrument_id, bar_spec)
    
    bars = []
    for _, row in df.iterrows():
        ts_nanos = int(row['timestamp'].timestamp() * 1e9)
        if pd.isna(row['close']) or row['close'] <= 0:
            continue

        bars.append(
            Bar(
                bar_type=bar_type,
                open=Price.from_str(f"{row['open']:.5f}"),
                high=Price.from_str(f"{row['high']:.5f}"),
                low=Price.from_str(f"{row['low']:.5f}"),
                close=Price.from_str(f"{row['close']:.5f}"),
                volume=Quantity.from_int(int(row['volume'] or 0)),
                ts_event=ts_nanos,
                ts_init=ts_nanos,
            )
        )

    print(f"Writing {len(bars)} bars for {symbol} to catalog...")
    catalog.write_data(bars)
    print(f"Successfully ingested {len(bars)} bars for {symbol}.")

if __name__ == "__main__":
    catalog = ParquetDataCatalog("catalog")
    download_and_ingest("EURUSD", "EURUSD=X", catalog)
    download_and_ingest("GBPUSD", "GBPUSD=X", catalog)
    print("Real Data Ingestion Successful!")
