import pandas as pd
from datetime import datetime
from tezaver.mining.daily_radar_engine import DailyRadarEngine, RadarResult
from tezaver.core import config, coin_cell_paths

def generate_full_report():
    engine = DailyRadarEngine()
    symbols = config.DEFAULT_COINS
    print(f"📡 Generating Global Radar Inventory Status...")
    
    results = []
    for symbol in symbols:
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, "1d")
            path_4h = coin_cell_paths.get_history_file(symbol, "4h")
            if not path_1d.exists() or not path_4h.exists(): continue
            
            df_1d = pd.read_parquet(path_1d)
            df_4h = pd.read_parquet(path_4h)
            
            daily = engine.calculate_daily_structure(df_1d)
            momentum = engine.calculate_4h_momentum(df_4h)
            dna = engine.dna_profiles.get(symbol, {})
            
            category = engine.categorize(daily, momentum, dna)
            if category:
                score = engine.calculate_score(daily, momentum)
                results.append({
                    "Symbol": symbol,
                    "Tier": dna.get('tier', 'N/A'),
                    "Category": category,
                    "Score": score,
                    "ATR%": round(daily.atr_pct, 2),
                    "RSI": round(momentum.rsi, 2)
                })
        except Exception:
            continue

    if not results:
        print("No results to report.")
        return

    df = pd.DataFrame(results)
    
    # Create MD Report
    report_path = "analysis/current_radar_inventory.md"
    with open(report_path, "w") as f:
        f.write(f"# 📡 GEN-RADAR Global Envanter Raporu\n")
        f.write(f"**Tarih:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Toplam Taranan:** {len(symbols)} | **Kategorize Edilen:** {len(results)}\n\n")
        
        for cat in ["TREND", "BREAKOUT", "AMBUSH", "NINJA", "WATCH"]:
            cat_df = df[df['Category'] == cat].sort_values("Score", ascending=False)
            if cat_df.empty: continue
            
            f.write(f"## 📊 Kategori: {cat} ({len(cat_df)} koin)\n")
            f.write(cat_df[["Symbol", "Tier", "Score", "ATR%", "RSI"]].to_markdown(index=False))
            f.write("\n\n")
            
    print(f"✅ Full report generated at {report_path}")

if __name__ == "__main__":
    generate_full_report()
