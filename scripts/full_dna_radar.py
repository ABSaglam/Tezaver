import pandas as pd
from datetime import datetime
from tezaver.mining.daily_radar_engine import DailyRadarEngine
from tezaver.core import config, coin_cell_paths

def run_full_dna_radar():
    engine = DailyRadarEngine()
    # Reload DNA profiles to pick up new entries
    engine.dna_profiles = engine._load_dna_profiles()
    
    symbols = config.DEFAULT_COINS
    print(f"📡 FULL DNA RADAR (All {len(symbols)} Coins) - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    results = []
    
    for symbol in symbols:
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, "1d")
            path_4h = coin_cell_paths.get_history_file(symbol, "4h")
            if not path_1d.exists() or not path_4h.exists(): continue
            
            df_1d = pd.read_parquet(path_1d)
            df_4h = pd.read_parquet(path_4h)
            if len(df_1d) < 20 or len(df_4h) < 20: continue
            
            daily = engine.calculate_daily_structure(df_1d)
            momentum = engine.calculate_4h_momentum(df_4h)
            dna = engine.dna_profiles.get(symbol, {})
            tier = dna.get('tier', 'N/A')
            
            category = engine.categorize(daily, momentum, dna)
            # Only include TREND, BREAKOUT, NINJA, AMBUSH (skip WATCH)
            if category and category != "WATCH":
                score = engine.calculate_score(daily, momentum)
                results.append({
                    "symbol": symbol,
                    "tier": tier,
                    "cat": category,
                    "score": score,
                    "atr": daily.atr_pct
                })
        except Exception:
            continue

    if not results:
        print("📭 No active signals detected.")
        return

    # Sort by Score
    results.sort(key=lambda x: x['score'], reverse=True)

    # Group by Category
    print("\n" + "="*80)
    print("🎯 MAKUL LİSTE (Tüm Tierlar, Sadece Aktif Sinyaller)")
    print("="*80)
    
    for cat in ["TREND", "BREAKOUT", "AMBUSH", "NINJA"]:
        cat_items = [r for r in results if r['cat'] == cat]
        if not cat_items: continue
        
        print(f"\n📊 {cat} ({len(cat_items)} koin)")
        print("-" * 60)
        print(f"{'Symbol':<15} | {'Tier':<4} | {'Score':<6} | {'ATR%'}")
        print("-" * 60)
        for r in cat_items:
            print(f"{r['symbol']:<15} | {r['tier']:<4} | {r['score']:>5} | {r['atr']:>5.1f}%")
    
    print("\n" + "="*80)
    print(f"Toplam Aktif Sinyal: {len(results)}")

if __name__ == "__main__":
    run_full_dna_radar()
