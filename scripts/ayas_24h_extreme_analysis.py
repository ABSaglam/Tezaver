
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tezaver.core import coin_cell_paths, config
from tezaver.mining.ayas_tuneli import tunelden_gec
import os

def get_spread_tier(spread_pct):
    """Classifies the 24h spread into tiers."""
    if spread_pct >= 30: return "DIAMOND"
    if spread_pct >= 20: return "GOLD"
    if spread_pct >= 10: return "SILVER"
    if spread_pct >= 5: return "BRONZE"
    if spread_pct > 0: return "IRON"
    return "NEUTRAL"

def run_24h_spread_analysis():
    """
    2025 Ayaş Tüneli: 24 Saat İçi Mutlak Yayılım (Spread) Analizi.
    Her sinyalden sonraki 24 saat içindeki EN DİP ile EN TEPE arasındaki farkı hesaplar.
    """
    start_2025 = datetime(2025, 1, 1)
    end_2025 = datetime(2025, 12, 31, 23, 59)
    
    results = []
    
    print(f"🚀 STARTING 24H SPREAD ANALYSIS (MaxHigh - MinLow) FOR 2025...")
    
    symbols = config.DEFAULT_COINS
    total_symbols = len(symbols)
    
    for idx, symbol in enumerate(symbols):
        if idx % 50 == 0:
            print(f"Processing {idx}/{total_symbols} symbols...")
            
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, '1d')
            path_4h = coin_cell_paths.get_history_file(symbol, '4h')
            path_15m = coin_cell_paths.get_history_file(symbol, '15m')
            
            if not all(p.exists() for p in [path_1d, path_4h, path_15m]):
                continue
                
            df_1d = pd.read_parquet(path_1d)
            if 'datetime' in df_1d.columns:
                df_1d['datetime'] = df_1d['datetime'].dt.tz_localize(None)
            
            df_4h = pd.read_parquet(path_4h)
            if 'datetime' in df_4h.columns:
                df_4h['datetime'] = df_4h['datetime'].dt.tz_localize(None)

            df_15m = pd.read_parquet(path_15m)
            if 'datetime' in df_15m.columns:
                df_15m['datetime'] = df_15m['datetime'].dt.tz_localize(None)
            
            # 2025 içindeki günleri tara
            data_2025 = df_1d[(df_1d['datetime'] >= start_2025) & (df_1d['datetime'] <= end_2025)]
            
            for i, row in data_2025.iterrows():
                sig_time = row['datetime']
                history_1d = df_1d[df_1d['datetime'] <= sig_time]
                history_4h = df_4h[df_4h['datetime'] <= sig_time]
                
                check = tunelden_gec(symbol, history_1d, history_4h)
                
                if check['passed']:
                    window_end = sig_time + timedelta(hours=24)
                    
                    # 15m verisinden 24 saatlik pencereyi al
                    window_15m = df_15m[(df_15m['datetime'] > sig_time) & (df_15m['datetime'] <= window_end)]
                    
                    if window_15m.empty:
                        continue
                        
                    # 24 saat içindeki mutlak DİP ve TEPE
                    max_high = window_15m['high'].max()
                    min_low = window_15m['low'].min()
                    
                    # Yayılım (Spread) = (TEPE - DİP) / DİP * 100
                    if min_low > 0:
                        spread_pct = ((max_high - min_low) / min_low) * 100
                    else:
                        spread_pct = 0
                    
                    results.append({
                        'month': sig_time.month,
                        'symbol': symbol,
                        'time': sig_time,
                        'max_high': max_high,
                        'min_low': min_low,
                        'spread_pct': spread_pct,
                        'spread_tier': get_spread_tier(spread_pct)
                    })
                    
        except Exception as e:
            continue

    if not results:
        print("❌ No signals found in 2025.")
        return

    df_res = pd.DataFrame(results)
    
    # Save detailed data
    output_dir = "analysis"
    os.makedirs(output_dir, exist_ok=True)
    df_res.to_csv(f'{output_dir}/ayas_24h_spread_2025.csv', index=False)
    
    # Tier Distribution
    print("\n=== 24H SPREAD (MaxHigh - MinLow) TIER DISTRIBUTION ===")
    tier_counts = df_res['spread_tier'].value_counts()
    tier_order = ["DIAMOND", "GOLD", "SILVER", "BRONZE", "IRON", "NEUTRAL"]
    for t in tier_order:
        if t in tier_counts.index:
            count = tier_counts[t]
            pct = count / len(df_res) * 100
            print(f"{t:<10}: {count:>5} signals ({pct:.1f}%)")
    
    # Total Summary
    print(f"\nTotal Signals: {len(df_res)}")
    print(f"Average Spread: {df_res['spread_pct'].mean():.2f}%")
    
    # Monthly Breakdown
    monthly = df_res.groupby('month').agg(
        signals=('spread_pct', 'count'),
        avg_spread=('spread_pct', 'mean'),
        silver_plus_rate=('spread_pct', lambda x: (x >= 10).mean() * 100)
    ).round(2)
    
    print("\n=== 24H MONTHLY SPREAD SUMMARY ===")
    print(monthly)
    
    print(f"\nSaved detailed results to {output_dir}/ayas_24h_spread_2025.csv")

if __name__ == "__main__":
    run_24h_spread_analysis()
