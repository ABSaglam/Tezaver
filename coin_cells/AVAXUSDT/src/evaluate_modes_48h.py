import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Paths
BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT")
REPORTS_DIR = BASE_DIR / "output/avax_kader_v1/runs/initial_learn/reports"
DATA_DIR = BASE_DIR / "data"

# Files
FILE_A = REPORTS_DIR / "AVAX_NET_ADAY_REPORT_ELITE.csv" # Mode A (Strict)
FILE_B = REPORTS_DIR / "AVAX_NET_ADAY_REPORT_ELITE_V3.csv" # Mode B (Relaxed)

def load_price_history():
    # Helper to get T+2 data
    # We need Close(t), Close(t+1), Close(t+2), MaxHigh(t+1), MaxHigh(t+2), MinLow...
    # Load 1D history
    fpath = DATA_DIR / "history_1d.parquet"
    if not fpath.exists():
        # Fallback csv
        fpath = DATA_DIR / "AVAXUSDT_1d.csv"
        
    if fpath.suffix == '.parquet':
        df = pd.read_parquet(fpath)
    else:
        df = pd.read_csv(fpath)
        
    # Standardize
    df.columns = [c.lower() for c in df.columns]
    if 'timestamp' in df.columns:
        # Check if ms or s or ns
        # 1672531200000 is ~2023. If interpreted as ns it is 1970.
        # Simple heuristic: if max > 3e12, assume us/ns? No, 1.6e12 is ms.
        # Let's force 'ms' as observed.
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    elif 'date' in df.columns:
        df['datetime'] = pd.to_datetime(df['date'], utc=True)
        
    df = df.sort_values('datetime')
    # Normalize to date to avoid time drift issues during lookup
    df['date_only'] = df['datetime'].dt.date
    # We will index by date_only for robust lookup
    df = df.set_index('date_only')
    return df

def analyze_candidates(candidates_df, mode_name, price_df):
    results = []
    
    for _, row in candidates_df.iterrows():
        try:
            # Parse date (ISO)
            dt = pd.to_datetime(row['Date']).date()
            
            # Find in price_df (indexed by date_only)
            
            if dt not in price_df.index:
                # print(f"Date {dt} not found in price history")
                continue
                
            idx_loc = price_df.index.get_loc(dt)
            
            # Need t (decision close), t+1, t+2
            if idx_loc + 2 >= len(price_df):
                status = "INSUFFICIENT_DATA"
                # Partial data for t+1 might exist from original file?
                # Use file data if available
                max_24 = row['Max_Excursion']
                hit_24 = row['Hit_10'] == 'YES'
                max_48 = np.nan
                hit_48 = False
            else:
                p_t = price_df.iloc[idx_loc]
                p_t1 = price_df.iloc[idx_loc+1]
                p_t2 = price_df.iloc[idx_loc+2]
                
                # 24H Metrics (t close -> t+1 close/high)
                # Recalculate to confirm or use row
                ref_close = p_t['close']
                
                # 48H Metrics (t close -> t+2 bounds)
                # Max high of t+1 and t+2
                high_48 = max(p_t1['high'], p_t2['high'])
                low_48 = min(p_t1['low'], p_t2['low'])
                close_48 = p_t2['close']
                
                max_exc_48 = (high_48 / ref_close - 1) * 100
                drawdown_48 = (low_48 / ref_close - 1) * 100
                close_exc_48 = (close_48 / ref_close - 1) * 100
                
                hit_48 = (max_exc_48 >= 10.0)
                
                max_24 = row['Max_Excursion']
                hit_24 = (row['Hit_10'] == 'YES') or (max_24 >= 10.0)
                
                dd_24 = row['Drawdown']
            
            res = {
                "Mode": mode_name,
                "Date": dt,
                "Hit_24h": hit_24,
                "Hit_48h": hit_48,
                "Max_24h": max_24,
                "Max_48h": max_exc_48,
                "DD_24h": dd_24,
                "DD_48h": drawdown_48,
                "Late_Winner": (not hit_24 and hit_48)
            }
            results.append(res)
            
        except Exception as e:
            print(f"Error processing {row['Date']}: {e}")
            continue
            
    return pd.DataFrame(results)

def generate_evaluation():
    print("::: EVALUATING MODE A vs B :::")
    
    # Load Price History
    price_df = load_price_history()
    
    # Load Reports
    df_a = pd.read_csv(FILE_A)
    df_b = pd.read_csv(FILE_B)
    
    
    # Analyze
    print(f"Price History Range: {price_df.index.min()} to {price_df.index.max()}")
    print(f"Index Type: {type(price_df.index[0])}, value: {price_df.index[0]}")
    
    if not df_a.empty:
        d_a = pd.to_datetime(df_a['Date']).dt.date
        print(f"Mode A Report Range: {d_a.min()} to {d_a.max()}")
        
        # Debug first row
        first_date = d_a.iloc[0]
        print(f"Search Type: {type(first_date)}, value: {first_date}")
        print(f"Is in index? {first_date in price_df.index}")
        
    res_a = analyze_candidates(df_a, "Mode A (Strict)", price_df)
    res_b = analyze_candidates(df_b, "Mode B (Relaxed)", price_df)
    
    if res_a.empty and res_b.empty:
        print("No results to analyze")
        return

    # Combine
    full = pd.concat([res_a, res_b])
    
    # 1. SUMMARY STATS
    summary = []
    for mode in full['Mode'].unique():
        sub = full[full['Mode'] == mode]
        summary.append({
            "Mode": mode,
            "Net_Adays": len(sub),
            "HitRatio_24h": sub['Hit_24h'].mean() * 100,
            "HitRatio_48h": sub['Hit_48h'].mean() * 100,
            "AvgMax_24h": sub['Max_24h'].mean(),
            "AvgMax_48h": sub['Max_48h'].mean(),
            "AvgDD_24h": sub['DD_24h'].mean(),
            "AvgDD_48h": sub['DD_48h'].mean(),
            "Late_Winners": sub['Late_Winner'].sum()
        })
        
    df_sum = pd.DataFrame(summary)
    print("\nSUMMARY:")
    print(df_sum)
    df_sum.to_csv(REPORTS_DIR / "MODE_A_vs_MODE_B_SUMMARY.csv", index=False)
    
    # 2. LATE WINNERS
    late = full[full['Late_Winner'] == True]
    if not late.empty:
        late.to_csv(REPORTS_DIR / "LATE_EXPANSION_REPORT.csv", index=False)
    
    # 3. MARKDOWN REPORT
    # Generate AVAX_SPECIAL_FOCUS_48H.md
    
    md = "# ⚖️ AVAX KADER ANALİZİ: 24h vs 48h (A/B Test)\n\n"
    
    md += "## 📊 PERFORMANS KARŞILAŞTIRMASI\n"
    md += df_sum.to_markdown(index=False, floatfmt=".2f")
    md += "\n\n"
    
    md += "## 🕒 48 SAAT ETKİSİ (LATE BLOOMERS)\n"
    md += "24 saatte hedefe ulaşamayıp 48 saatte %10 yapanlar:\n\n"
    
    if not late.empty:
        for _, row in late.iterrows():
            md += f"- **{row['Date']}** ({row['Mode']}): 24h Max **{row['Max_24h']:.2f}%** -> 48h Max **{row['Max_48h']:.2f}%** 🚀\n"
    else:
        md += "- *Yok (Tüm hedefler 24s içinde gerçekleşti veya hiç gerçekleşmedi)*\n"
        
    md += "\n## 💡 ANALİZ SONUCU\n"
    
    # Logic for verdict
    row_a = df_sum[df_sum['Mode'].str.contains("Strict")].iloc[0] if not df_sum[df_sum['Mode'].str.contains("Strict")].empty else None
    row_b = df_sum[df_sum['Mode'].str.contains("Relaxed")].iloc[0] if not df_sum[df_sum['Mode'].str.contains("Relaxed")].empty else None
    
    if row_a is not None and row_b is not None:
        delta_candidates = row_b['Net_Adays'] - row_a['Net_Adays']
        delta_return = row_b['AvgMax_48h'] - row_a['AvgMax_48h']
        
        md += f"- **Mode B (Gevşek)**, Mode A'ya göre **{int(delta_candidates)}** adet fazla aday üretti.\n"
        md += f"- 48 Saatlik ortalama getiri farkı: **{delta_return:+.2f}%**\n"
        
        if delta_return > 0:
            md += "- **SONUÇ:** Gevşeme işe yaradı, kaçan fırsatlar yakalandı ✅\n"
        else:
            md += "- **SONUÇ:** Gevşeme performansı düşürdü, Mode A (Strict) daha verimli 🛡️\n"
            
    with open(REPORTS_DIR / "AVAX_SPECIAL_FOCUS_48H.md", "w") as f:
        f.write(md)
        
    print(f"Report saved: {REPORTS_DIR / 'AVAX_SPECIAL_FOCUS_48H.md'}")

if __name__ == "__main__":
    generate_evaluation()
