import pandas as pd
import numpy as np

symbol = "FETUSDT"
target_day = pd.Timestamp("2025-12-01")

# Load 15m data
df_15m = pd.read_parquet(f"coin_cells/{symbol}/data/history_15m.parquet")
df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
df_15m.set_index('dt', inplace=True)

# RMA based RSI (Wilder's)
def calculate_rsi_rma(df, period=11):
    delta = df['close'].diff()
    alpha = 1 / period
    avg_gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    avg_loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

df_15m['rsi'] = calculate_rsi_rma(df_15m, 11)

# Get target day data
day_data = df_15m[df_15m.index.normalize() == target_day]

if day_data.empty:
    print("Veri bulunamadı.")
else:
    print(f"--- FET 1 Aralık RSI(11) RMA Denetimi ---")
    crosses = 0
    rsi_vals = day_data['rsi'].values
    times = day_data.index.values
    
    for i in range(1, len(rsi_vals)):
        if rsi_vals[i-1] <= 70 and rsi_vals[i] > 70:
            crosses += 1
            print(f"Kesişim! Zaman: {times[i]}, RSI: {rsi_vals[i]:.2f}")

    print(f"\nToplam Kesişim Sayısı: {crosses}")
    print("Günün Maksimum RSI Değeri:", day_data['rsi'].max())
