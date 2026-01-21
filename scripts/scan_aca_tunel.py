import sys
import os
sys.path.append(os.getcwd())
import pandas as pd
import numpy as np

def scan_aca_tunel_only():
    symbol = "ACAUSDT"
    print(f"🚇 AYAŞ TÜNELİ - {symbol} (2023-2025) NİHAİ TARAMA")
    print("="*60)
    
    path_1d = f"coin_cells/{symbol}/data/history_1d.parquet"
    path_4h = f"coin_cells/{symbol}/data/history_4h.parquet"
    
    df_1d = pd.read_parquet(path_1d)
    df_4h = pd.read_parquet(path_4h)
    
    # ATR% Calculation (Daily)
    df_1d['dt'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d.set_index('dt', inplace=True)
    df_1d['tr'] = np.maximum(df_1d['high'] - df_1d['low'], 
                            np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), 
                                       abs(df_1d['low'] - df_1d['close'].shift(1))))
    df_1d['atr_pct'] = (df_1d['tr'].rolling(14).mean() / df_1d['close']) * 100
    
    # RSI Calculation (4H)
    df_4h['dt'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    delta = df_4h['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df_4h['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 0.001))))
    
    # Identify PASS days
    results = []
    df_target = df_1d[df_1d.index.year.isin([2023, 2024, 2025])]
    
    for day_ts in df_target.index:
        atr = df_target.loc[day_ts, 'atr_pct']
        try:
            # RSI at the start of the day (last 4H candle of prev day)
            rsi = df_4h[df_4h['dt'] <= day_ts].iloc[-1]['rsi']
        except:
            continue
            
        is_trend = atr >= 15.0 and 55 <= rsi <= 70
        is_ninja = atr >= 12.0 and 60 <= rsi <= 75
        
        if is_trend or is_ninja:
            results.append({
                'date': day_ts.strftime('%Y-%m-%d'),
                'year': day_ts.year,
                'tip': 'TREND' if is_trend else 'NINJA',
                'atr': round(atr, 1),
                'rsi': round(rsi, 1)
            })

    # Display results
    print(f"{'TARİH':12} | {'TİP':6} | {'ATR%':>6} | {'RSI':>5}")
    print("-" * 60)
    
    for r in results:
        print(f"{r['date']:12} | {r['tip']:6} | {r['atr']:>5.1f}% | {r['rsi']:>5.1f}")
        
    print("\n" + "="*60)
    summary = pd.DataFrame(results).groupby('year').size()
    print("YILLIK ÖZET:")
    print(summary)
    print(f"TOPLAM: {len(results)} Gün")

if __name__ == "__main__":
    scan_aca_tunel_only()
