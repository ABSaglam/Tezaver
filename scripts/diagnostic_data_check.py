import pandas as pd
import os

symbols = ["GIGGLEUSDT", "LSKUSDT"]
target_day = pd.Timestamp("2025-12-01")

for symbol in symbols:
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    if not os.path.exists(path):
        print(f"{symbol} dosyası bulunamadı: {path}")
        continue
    
    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    
    day_data = df[df.index.normalize() == target_day]
    
    if day_data.empty:
        print(f"{symbol} için {target_day} tarihinde veri yok.")
    else:
        h = day_data['high'].max()
        l = day_data['low'].min()
        o = day_data.iloc[0]['open']
        c = day_data.iloc[-1]['close']
        rally = (h/l - 1) * 100
        print(f"--- {symbol} ({target_day.date()}) ---")
        print(f"Açılış: {o}, Kapanış: {c}")
        print(f"Günlük En Yüksek: {h}, En Düşük: {l}")
        print(f"Hesaplanan Ralli (H/L): %{rally:.2f}")
        print(f"Satır Sayısı: {len(day_data)}")
        # İlk 5 satırı göster
        print("İlk 5 bar:")
        print(day_data[['open', 'high', 'low', 'close']].head())
