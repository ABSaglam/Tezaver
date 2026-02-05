import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime

# CONFIG
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = "2026-01-01"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/RAPOR_KAHIN_TREND_2026.md"

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / (loss + 0.0001)
    return 100 - (100 / (1 + rs))

def get_indicators(df):
    if df.empty: return df
    # RSI & RSI-EMA
    df['rsi'] = calculate_rsi(df['close'], 14)
    df['rsi_ema'] = df['rsi'].ewm(span=14, adjust=False).mean()
    
    # EMA Ribbon (20-55) on RSI-EMA
    ribbon_cols = []
    for p in [20, 25, 30, 35, 40, 45, 50, 55]:
        col = f'ema{p}'
        df[col] = df['rsi_ema'].ewm(span=p, adjust=False).mean()
        ribbon_cols.append(col)
    
    df['rib_max'] = df[ribbon_cols].max(axis=1)
    return df

def run_scan():
    print("🚀 Kahin Trend Envanteri Tarayıcısı Başlatıldı...")
    
    symbols = sorted([d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))])
    
    all_dates = pd.date_range(start=START_DATE, end=datetime.now().date(), freq='D')
    
    # Store indicator data to avoid re-calculating inside the day loop
    coin_data = {}
    for symbol in symbols:
        w_path = f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet"
        d_path = f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet"
        
        if os.path.exists(w_path) and os.path.exists(d_path):
            try:
                df_w = pd.read_parquet(w_path)
                df_w['dt'] = pd.to_datetime(df_w['timestamp'], unit='ms')
                df_w.set_index('dt', inplace=True)
                df_w = get_indicators(df_w.sort_index())
                
                df_d = pd.read_parquet(d_path)
                df_d['dt'] = pd.to_datetime(df_d['timestamp'], unit='ms')
                df_d.set_index('dt', inplace=True)
                df_d = get_indicators(df_d.sort_index())
                
                coin_data[symbol] = {'w': df_w, 'd': df_d}
                
                # Load 4H and 1H for depth analysis
                h4_path = f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet"
                h1_path = f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet"
                if os.path.exists(h4_path) and os.path.exists(h1_path):
                    df_h4 = pd.read_parquet(h4_path)
                    df_h4['dt'] = pd.to_datetime(df_h4['timestamp'], unit='ms')
                    df_h4.set_index('dt', inplace=True)
                    coin_data[symbol]['h4'] = get_indicators(df_h4.sort_index())

                    df_h1 = pd.read_parquet(h1_path)
                    df_h1['dt'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
                    df_h1.set_index('dt', inplace=True)
                    coin_data[symbol]['h1'] = get_indicators(df_h1.sort_index())
                    
            except Exception as e:
                print(f"Error loading {symbol}: {e}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# 🏛️ KAHİN: 2026 TREND ENVANTERİ VE GÜVENLİ ALAN ANALİZİ\n")
        f.write(f"Rapor Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("> **Kural:**\n")
        f.write("> 1. **Trend Onayı (W+D):** Haftalık ve Günlük (RSI veya RSI-EMA > Rib-Max)\n")
        f.write("> 2. **Alan Açılması (4H+1H):** O gün içinde (RSI veya RSI-EMA > Rib-Max) olan saatler.\n\n")

        for current_date in all_dates:
            d_str = current_date.strftime('%Y-%m-%d')
            day_results = []
            
            for symbol, data in coin_data.items():
                df_w, df_d = data['w'], data['d']
                df_h4, df_h1 = data.get('h4'), data.get('h1')
                
                # Check Weekly (Snapshot at the start of the day)
                w_on_date = df_w[df_w.index < current_date].tail(1)
                if w_on_date.empty: continue
                w_row = w_on_date.iloc[0]
                w_ok = (w_row['rsi'] > w_row['rib_max']) or (w_row['rsi_ema'] > w_row['rib_max'])
                if not w_ok: continue
                
                # Check Daily (Snapshot at the start of the day)
                d_on_date = df_d[df_d.index < current_date].tail(1)
                if d_on_date.empty: continue
                d_row = d_on_date.iloc[0]
                d_ok = (d_row['rsi'] > d_row['rib_max']) or (d_row['rsi_ema'] > d_row['rib_max'])
                if not d_ok: continue
                
                # Depth Analysis: Find H4 and H1 'Space Open' hours within current_date
                safe_hours = []
                if df_h4 is not None and df_h1 is not None:
                    # Iterate every hour of the current day
                    day_h1 = df_h1[(df_h1.index >= current_date) & (df_h1.index < current_date + pd.Timedelta(days=1))]
                    for h1_ts, h1_row in day_h1.iterrows():
                        # H4 check for this hour
                        h4_on_time = df_h4[df_h4.index <= h1_ts].tail(1)
                        if h4_on_time.empty: continue
                        h4_row = h4_on_time.iloc[0]
                        h4_ok = (h4_row['rsi'] > h4_row['rib_max']) or (h4_row['rsi_ema'] > h4_row['rib_max'])
                        
                        # H1 check
                        h1_ok = (h1_row['rsi'] > h1_row['rib_max']) or (h1_row['rsi_ema'] > h1_row['rib_max'])
                        
                        if h4_ok and h1_ok:
                            safe_hours.append(h1_ts.strftime('%H'))
                
                safe_zone_str = ",".join(sorted(list(set(safe_hours)))) if safe_hours else "---"
                
                if current_date in df_d.index:
                    today_row = df_d.loc[current_date]
                    daily_range = ((today_row['high'] - today_row['low']) / today_row['low']) * 100
                    daily_net = ((today_row['close'] - today_row['open']) / today_row['open']) * 100
                    
                    day_results.append({
                        'symbol': symbol,
                        'range': daily_range,
                        'net': daily_net,
                        'safe_zones': safe_zone_str,
                        'high': today_row['high'],
                        'low': today_row['low']
                    })
            
            if day_results:
                f.write(f"## 📅 {d_str} (Trenddeki Koinler: {len(day_results)})\n")
                f.write("| SYM | RANGE (L-H) | NET (O-C) | SAFE HOURS (1H) | status |\n")
                f.write("|---|---|---|---|---|\n")
                
                # Sort by range
                day_results.sort(key=lambda x: x['range'], reverse=True)
                
                for r in day_results:
                    status = "🚀" if r['net'] > 5 else "✅" if r['net'] > 0 else "🔴"
                    f.write(f"| {r['symbol']} | **%{r['range']:.1f}** | %{r['net']:.1f} | `{r['safe_zones']}` | {status} |\n")
                f.write("\n")

    print(f"✅ Rapor tamamlandı: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scan()
