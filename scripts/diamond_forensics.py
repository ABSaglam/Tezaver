"""
Diamond Forensic Analysis - Pre-Rally Behavior
Analyzes the 15m window BEFORE a Diamond rally starts to identify common precursors.
"""
import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from tezaver.core import coin_cell_paths
from tezaver.features.indicator_engine import compute_rsi

def analyze_pre_rally(symbol, event_time_str):
    event_time = pd.to_datetime(event_time_str).tz_localize(None)
    path_15m = coin_cell_paths.get_history_file(symbol, '15m')
    if not path_15m.exists(): return None
    
    df = pd.read_parquet(path_15m)
    df['datetime'] = df['datetime'].dt.tz_localize(None)
    
    # Get window: 48 hours before the rally
    window_start = event_time - timedelta(hours=48)
    pre_df = df[(df['datetime'] >= window_start) & (df['datetime'] < event_time)].copy()
    
    if pre_df.empty: return None
    
    # Metrics
    # 1. Pullback before start? (Max Drawdown in the last 24h)
    recent_24h = pre_df[pre_df['datetime'] >= event_time - timedelta(hours=24)].copy()
    if not recent_24h.empty:
        max_high = recent_24h['high'].max()
        last_low = recent_24h['low'].min()
        pullback_pct = (last_low - max_high) / max_high * 100
        
        # Timing: How long ago was the low?
        low_time = recent_24h.loc[recent_24h['low'] == last_low, 'datetime'].iloc[-1]
        hours_since_low = (event_time - low_time).total_seconds() / 3600
        
        # 2. RSI Pre-Rally
        pre_df['rsi'] = compute_rsi(pre_df['close'])
        avg_rsi_last_4 = pre_df['rsi'].tail(4).mean()
        min_rsi_24h = pre_df['rsi'].tail(96).min() # 96 bars = 24h
    else:
        pullback_pct = 0
        hours_since_low = 0
        avg_rsi_last_4 = 50
        min_rsi_24h = 50

    # 3. Volatility (ATR relative to price)
    # Manual ATR
    pre_df['tr'] = np.maximum(pre_df['high'] - pre_df['low'], 
                             np.maximum(abs(pre_df['high'] - pre_df['close'].shift(1)), 
                                        abs(pre_df['low'] - pre_df['close'].shift(1))))
    avg_tr = pre_df['tr'].tail(20).mean()
    vol_pct = (avg_tr / pre_df['close'].iloc[-1]) * 100
    
    # 3. Volume Trend (last 4 bars vs last 40 bars)
    short_vol = pre_df['volume'].tail(4).mean()
    long_vol = pre_df['volume'].tail(40).mean()
    vol_ratio = short_vol / long_vol if long_vol > 0 else 1
    
    return {
        'symbol': symbol,
        'event_time': event_time_str,
        'pullback_24h': round(pullback_pct, 2),
        'hours_since_low': round(hours_since_low, 1),
        'min_rsi_24h': round(min_rsi_24h, 1) if min_rsi_24h else 50,
        'last_rsi': round(avg_rsi_last_4, 1) if avg_rsi_last_4 else 50,
        'vol_pct': round(vol_pct, 2),
        'vol_ratio': round(vol_ratio, 2)
    }

def main():
    conn = sqlite3.connect('library/rallies.db')
    # Filter for DIAMOND rallies
    query = "SELECT symbol, event_time, tier FROM rallies WHERE tier = 'DIAMOND' LIMIT 100"
    diamonds = pd.read_sql(query, conn)
    conn.close()
    
    print(f"Analyzing {len(diamonds)} Diamond events...")
    
    stats = []
    for _, row in diamonds.iterrows():
        res = analyze_pre_rally(row['symbol'], row['event_time'])
        if res:
            stats.append(res)
            
    if not stats:
        print("No data found for pre-rally analysis.")
        return
        
    df_stats = pd.DataFrame(stats)
    
    print("\n=== DIAMOND PRE-RALLY SUMMARY ===")
    print(f"Avg 24h Pullback: {df_stats['pullback_24h'].mean():.2f}%")
    print(f"Avg Hours Since Low: {df_stats['hours_since_low'].mean():.1f}h")
    print(f"Avg Min RSI (24h): {df_stats['min_rsi_24h'].mean():.1f}")
    print(f"Avg Start RSI: {df_stats['last_rsi'].mean():.1f}")
    print(f"Avg Volume Ratio (Short/Long): {df_stats['vol_ratio'].mean():.2f}")
    
    report_path = 'analysis/diamond_forensics.md'
    with open(report_path, 'w') as f:
        f.write('# 🔎 DIAMOND RALLİ ÖNCESİ ANALİZ (ADN)\n\n')
        f.write('Bir rallinin "Diamond" (+%30) olmadan hemen evvel 15 dakikalık periyotta ne yaptığını inceler.\n\n')
        f.write(f'**Örneklem:** {len(df_stats)} Diamond Olayı\n\n')
        
        f.write('## Genel İstatistikler\n\n')
        f.write(f'- **Ortalama Geri Çekilme (Son 24s):** %{df_stats["pullback_24h"].mean():.2f}\n')
        f.write(f'- **Dipten Ralliye Geçen Süre:** {df_stats["hours_since_low"].mean():.1f} saat\n')
        f.write(f'- **En Düşük RSI (24s):** {df_stats["min_rsi_24h"].mean():.1f}\n')
        f.write(f'- **Başlangıç RSI:** {df_stats["last_rsi"].mean():.1f}\n')
        f.write(f'- **Hacim Oranı (Yakın/Uzak):** {df_stats["vol_ratio"].mean():.2f}\n')
        f.write(f'- **Oynaklık (ATR %):** %{df_stats["vol_pct"].mean():.2f}\n\n')
        
        f.write('## Örnek Olaylar Detayı\n\n')
        f.write('| Sembol | Zaman | Geri % | Saat (Dip) | Min RSI | Bas. RSI | Hacim |\n')
        f.write('| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n')
        for _, r in df_stats.head(50).iterrows():
            f.write(f'| {r["symbol"]} | {r["event_time"]} | {r["pullback_24h"]}% | {r["hours_since_low"]}s | {r["min_rsi_24h"]} | {r["last_rsi"]} | {r["vol_ratio"]} |\n')

    print(f"\nForensic raporu kaydedildi: {report_path}")

if __name__ == "__main__":
    main()
