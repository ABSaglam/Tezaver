import os
import json
import pandas as pd

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = pd.Timestamp("2025-10-16")
END_DATE = pd.Timestamp("2026-01-24")

symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
print(f"Toplam Sembol Sayısı: {len(symbols)}")

for symbol in symbols[:5]:
    print(f"\n--- {symbol} Denetleniyor ---")
    key_path = f"/Users/alisaglam/TezaverMac/data/golden_keys/{symbol}_key.json"
    if not os.path.exists(key_path):
        print(f"HATA: Key dosyası bulunamadı: {key_path}")
        continue
    
    with open(key_path, "r") as f:
        data = json.load(f)
        golden_dna_list = data.get('golden_dna_list', [])
        print(f"Golden DNA Listesi ({len(golden_dna_list)} adet): {golden_dna_list[:2]}...")
    
    hist_path = f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet"
    if not os.path.exists(hist_path):
        print(f"HATA: Parquet dosyası bulunamadı: {hist_path}")
    else:
        df = pd.read_parquet(hist_path)
        print(f"Veri Aralığı: {pd.to_datetime(df['timestamp'].min(), unit='ms')} - {pd.to_datetime(df['timestamp'].max(), unit='ms')}")
