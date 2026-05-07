import pandas as pd
import matplotlib.pyplot as plt
import re
import numpy as np
from datetime import datetime

def analyze_log(log_path):
    data = []
    signals = []
    print(f"Analyzing log: {log_path}")
    
    # Regex for DATA
    data_pattern = re.compile(r"DATA: (\d+), ([\d\.]+), ([\d\.]+), ([\-?\d\.]+), ([\-?\d\.]+), ([\-?\d\.]+)")
    # Regex for SIGNAL
    signal_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}).*SIGNAL: (.*)")

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            d_match = data_pattern.search(line)
            if d_match:
                ts = int(d_match.group(1))
                data.append({
                    "timestamp": pd.to_datetime(ts, unit="ns"),
                    "price_a": float(d_match.group(2)),
                    "price_b": float(d_match.group(3)),
                    "spread": float(d_match.group(4)),
                    "z_score": float(d_match.group(5)),
                    "gamma": float(d_match.group(6))
                })
            
            s_match = signal_pattern.search(line)
            if s_match:
                signals.append({
                    "time": s_match.group(1),
                    "msg": s_match.group(2)
                })

    if not data:
        print("No telemetry data found in log!")
        return

    df = pd.DataFrame(data)
    df = df.set_index("timestamp")
    print(f"Extracted {len(df)} data points and {len(signals)} signals.")

    # Create plots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

    # Plot 1: Prices
    ax1.plot(df.index, df["price_a"], label="EURUSD", alpha=0.6, color="tab:blue")
    ax1.plot(df.index, df["price_b"], label="GBPUSD", alpha=0.6, color="tab:orange")
    ax1.set_title("Historical Prices", fontsize=14)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: Z-Score with Signal Markers
    ax2.plot(df.index, df["z_score"], color="purple", label="Z-Score", linewidth=0.8)
    ax2.axhline(1.5, color="red", linestyle="--", alpha=0.5, label="Entry Threshold")
    ax2.axhline(-1.5, color="red", linestyle="--", alpha=0.5)
    ax2.axhline(0.5, color="green", linestyle="--", alpha=0.5, label="Exit Threshold")
    ax2.axhline(-0.5, color="green", linestyle="--", alpha=0.5)
    ax2.set_title("Z-Score & Mean Reversion Levels", fontsize=14)
    ax2.set_ylabel("Standard Deviations")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Plot 3: Gamma
    ax3.plot(df.index, df["gamma"], color="brown", label="Hedge Ratio (Gamma)", alpha=0.8)
    ax3.set_title("Rolling Hedge Ratio (OLS)", fontsize=14)
    ax3.set_ylabel("Multiplier")
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("backtest_v7_analysis.png")
    print("Analysis plot saved as 'backtest_v7_analysis.png'")
    
    # Print a small summary of signals
    print("\n--- Recent Signals ---")
    for s in signals[-10:]:
        print(f"{s['time']}: {s['msg']}")

if __name__ == "__main__":
    analyze_log("backtest_real_log_v7.txt")
