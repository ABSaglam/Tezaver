import pandas as pd
from datetime import datetime
from tezaver.mining.daily_radar_engine import DailyRadarEngine
from tezaver.core import coin_cell_paths
from tezaver.data.history_service import update_history

def audit_bifi_with_sync():
    symbol = "BIFIUSDT"
    print(f"📡 Syncing {symbol} data from Binance...")
    
    try:
        update_history(symbol, "1d", fast_only=True)
        update_history(symbol, "4h", fast_only=True)
    except Exception as e:
        print(f"❌ Failed to sync {symbol}: {e}")
        return

    engine = DailyRadarEngine()
    path_1d = coin_cell_paths.get_history_file(symbol, "1d")
    
    if not path_1d.exists():
        print(f"❌ Still no history for {symbol} after sync.")
        return
        
    df = pd.read_parquet(path_1d)
    print(f"✅ Sync complete. {len(df)} bars found.")
    
    daily = engine.calculate_daily_structure(df)
    dna = engine.dna_profiles.get(symbol, {})
    
    if daily:
        print("\n--- BIFI Technical Audit ---")
        print(f"ATR% (Energy): {daily.atr_pct:.2f}%")
        print(f"Midpoint % (Position): {daily.midpoint_pct:.2f}%")
        print(f"Category: {engine.categorize(daily, {}, dna)}")
    else:
        print("❌ Failed to calculate Daily Metrics.")

if __name__ == "__main__":
    audit_bifi_with_sync()
