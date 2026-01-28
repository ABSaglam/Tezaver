import pandas as pd
import numpy as np

symbol = "FETUSDT"
target_day = pd.Timestamp("2025-12-01")

# Load 15m data
df_15m = pd.read_parquet(f"coin_cells/{symbol}/data/history_15m.parquet")
df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
df_15m.set_index('dt', inplace=True)

# RSI(11) Calculation
def calculate_rsi_manual(df, period=11):
    delta = df['close'].diff()
    # SMA based gain/loss (as per the code I used)
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean().replace(0, 0.001)
    rs = gain / loss
    return 100 - (100 / (1 + rs))

df_15m['rsi'] = calculate_rsi_manual(df_15m, 11)

# Get target day data
day_data = df_15m[df_15m.index.normalize() == target_day].copy()

if day_data.empty:
    print("Veri bulunamadı.")
else:
    print(f"--- FET 1 Aralık RSI(11) Denetimi ---")
    crosses = []
    rsi_vals = day_data['rsi'].values
    times = day_data.index.values
    
    # Previous bar from the day before might be needed for the first cross
    prev_rsi = df_15m[df_15m.index < day_data.index[0]].iloc[-1]['rsi'] if not df_15m[df_15m.index < day_data.index[0]].empty else 50
    
    # Check first bar
    if prev_rsi <= 70 and rsi_vals[0] > 70:
        crosses.append(times[0])
    
    for i in range(1, len(rsi_vals)):
        # print(f"Time: {times[i]}, RSI: {rsi_vals[i]:.2f}")
        if rsi_vals[i-1] <= 70 and rsi_vals[i] > 70:
            crosses.append(times[i])
            print(f"Kesişim Yakalandı! Zaman: {times[i]}, RSI: {rsi_vals[i]:.2f}, Önceki RSI: {rsi_vals[i-1]:.2f}")

    print(f"\nToplam Kesişim Sayısı: {len(crosses)}")
    if len(crosses) == 0:
        print("Maksimum RSI:", day_data['rsi'].max())
