import json
import pandas as pd
import numpy as np

def diagnose_aca_dna():
    symbol = "ACAUSDT"
    print(f"🧬 Diagnosing ACA's 362 Rally Ancestors...")
    
    with open("data/aca_journey_memory.json", "r") as f:
        memory = json.load(f)
    
    # Load OHLCV for raw metrics
    df_h1 = pd.read_parquet(f"coin_cells/{symbol}/data/history_1h.parquet")
    df_h1['dt'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
    df_h1.set_index('dt', inplace=True)
    
    # Indicators for raw analysis
    df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
    df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
    df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
    
    def get_comp(row):
        emas = [row['ema9'], row['ema21'], row['ema50']]
        return (max(emas) / min(emas) - 1) * 100

    stats = []
    for r in memory:
        t_1_day = (pd.Timestamp(r['rally_date']) - pd.Timedelta(days=1))
        # Analysis for the 24h window before the rally
        window = df_h1[(df_h1.index >= t_1_day) & (df_h1.index < t_1_day + pd.Timedelta(days=1))]
        
        if not window.empty:
            comps = window.apply(get_comp, axis=1)
            stats.append({
                'min_comp': comps.min(),
                'avg_comp': comps.mean(),
                'max_vol': window['volume'].max(),
                'avg_vol': window['volume'].mean()
            })
            
    df_stats = pd.DataFrame(stats)
    print("\n📊 ACA PRE-RALLY SQUEEZE STATS (H1):")
    print(df_stats['min_comp'].describe(percentiles=[0.25, 0.5, 0.75, 0.9]))
    
    print("\n💡 OBSERVATION:")
    print(f"ALGO's median squeeze was ~4.1%.")
    print(f"ACA's median squeeze is {df_stats['min_comp'].median():.2f}%.")
    
    # Re-evaluating 'Phase' and 'Rhythm' for ACA
    df_d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
    df_d['dt'] = pd.to_datetime(df_d['timestamp'], unit='ms')
    df_d.set_index('dt', inplace=True)
    df_d['atr_pct'] = ((df_d['high'] - df_d['low']).rolling(14).mean() / df_d['close']) * 100
    
    print(f"\n📊 ACA DAILY ATR% (VOLATILITY):")
    print(df_d['atr_pct'].describe())

if __name__ == "__main__":
    diagnose_aca_dna()
