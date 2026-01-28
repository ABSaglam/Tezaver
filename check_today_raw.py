
from tezaver.engines.tunnel_engine import TunnelEngine
import os
import pandas as pd
from tezaver.core.config import COIN_CELLS_DIR

def check_today_raw():
    print("--- 28 OCAK RAW (HAM) TÜNEL TARAMASI ---")
    print("Filtreler: KAPALI (Tüm Adaylar Gösterilecek)\n")
    
    engine = TunnelEngine()
    date_str = "2026-01-28"
    target_date = pd.Timestamp(date_str)
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    symbols.sort()
    
    results = []
    
    print(f"Taranan Coin Sayisi: {len(symbols)}")
    print("Tarama Başladı...", end="", flush=True)
    
    for i, symbol in enumerate(symbols):
        if i % 50 == 0: print(".", end="", flush=True)
        
        try:
            # Load 15m Data Directly
            path_15m = os.path.join(COIN_CELLS_DIR, symbol, "data", "history_15m.parquet")
            if not os.path.exists(path_15m): continue
            
            df_15m = pd.read_parquet(path_15m)
            df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
            df_15m.set_index('dt', inplace=True)
            df_15m.sort_index(inplace=True)
            
            # Result: df_15m has full history
            
            # 1. CRITICAL FIX: Calculate Indicators ON FULL HISTORY
            # Before, we were slicing first, which killed the lookback data for new days.
            engine._calculate_indicators(df_15m)
            
            # 2. Slice for Target Date (Now that indicators are ready)
            day_mask = (df_15m.index.normalize() == target_date)
            day_data = df_15m[day_mask].copy()
            
            if day_data.empty: continue
            
            # 3. Find Triggers (Logic checks indicators we just computed)
            triggers = engine._find_triggers(day_data)
            
            if triggers:
                for t in triggers:
                    results.append({
                        "SYM": symbol,
                        "TIME": t['time'].strftime('%H:%M'),
                        "P": f"+{t['p_change']:.1f}%",
                        "V100": f"{t['v_100']:.1f}",
                        "V21": f"{t['v_21']:.1f}",
                        "TREND": t['trend_icon'],
                        "NOTE": "RAW MATCH"
                    })
                    
        except Exception as e:
            continue
            
    print("\n\n✅ TARAMA BİTTİ.")
    
    if results:
        df_res = pd.DataFrame(results)
        # Sort by Time then V100
        df_res.sort_values(by=['TIME', 'V100'], ascending=[True, False], inplace=True)
        print(df_res.to_string(index=False))
    else:
        print("Tünel BOŞ. (Hiçbir ham sinyal yok)")

if __name__ == "__main__":
    check_today_raw()
