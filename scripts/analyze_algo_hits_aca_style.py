import sys
import os
sys.path.append(os.getcwd())
import pandas as pd
import numpy as np
from tezaver.core.rally_store import RallyStore

def analyze_algo_tunnel_hits():
    symbol = "ALGOUSDT"
    print(f"🔬 {symbol} - Ayaş Tüneli İsabet Analizi (ACA Tekniği)")
    print("="*70)
    
    path_1d = f"coin_cells/{symbol}/data/history_1d.parquet"
    path_4h = f"coin_cells/{symbol}/data/history_4h.parquet"
    
    df_1d = pd.read_parquet(path_1d)
    df_4h = pd.read_parquet(path_4h)
    
    # ATR% Daily
    df_1d['dt'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d.set_index('dt', inplace=True)
    df_1d['tr'] = np.maximum(df_1d['high'] - df_1d['low'], 
                            np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), 
                                       abs(df_1d['low'] - df_1d['close'].shift(1))))
    df_1d['atr_pct'] = (df_1d['tr'].rolling(14).mean() / df_1d['close']) * 100
    
    # RSI 4H
    df_4h['dt'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    delta = df_4h['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df_4h['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 0.001))))
    
    # Load Reality
    store = RallyStore()
    db_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    real_rallies = [pd.Timestamp(r['event_time']).normalize() for r in db_rallies if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']]
    real_set = set(real_rallies)

    # Tunnel Signals
    df_target = df_1d[df_1d.index.year.isin([2023, 2024, 2025])]
    results = []
    
    for day_ts in df_target.index:
        atr = df_target.loc[day_ts, 'atr_pct']
        try:
            rsi = df_4h[df_4h['dt'] <= day_ts].iloc[-1]['rsi']
        except: continue
        
        is_trend = atr >= 15.0 and 55 <= rsi <= 70
        is_ninja = atr >= 12.0 and 60 <= rsi <= 75
        
        if is_trend or is_ninja:
            hit = False
            for r_day in real_set:
                if 0 <= (r_day - day_ts).days <= 2:
                    hit = True
                    break
            results.append({'date': day_ts, 'hit': hit})

    if not results:
        print("Tünelden geçen gün bulunamadı.")
        return

    df_res = pd.DataFrame(results)
    hits = df_res[df_res['hit'] == True]
    misses = df_res[df_res['hit'] == False]
    
    print(f"Toplam Tünel Geçişi: {len(df_res)}")
    print(f"Gerçekleşen Ralli (Hits): {len(hits)} (%{len(hits)/len(df_res)*100:.1f})")
    print(f"Fos Çıkan Günler (Misses): {len(misses)} (%{len(misses)/len(df_res)*100:.1f})")
    print("-" * 70)
    
    for r in results:
        status = "✅ HIT" if r['hit'] else "❌ MISS"
        print(f"- {r['date'].date()} | {status}")

if __name__ == "__main__":
    analyze_algo_tunnel_hits()
