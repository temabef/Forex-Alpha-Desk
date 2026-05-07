import nautilus_trader
from nautilus_trader.core.datetime import Clock

print(f"✅ Nautilus Trader v{nautilus_trader.__version__} installed successfully!")
clock = Clock()
print(f"🕒 Engine clock initialized at: {clock.utc_now()}")
