import pandas as pd
from datetime import datetime
from tezaver.mining.daily_radar_engine import DailyRadarEngine, RadarResult
from tezaver.core import coin_cell_paths

def run_targeted_scan():
    engine = DailyRadarEngine()
    # Get Top-Tier coins (S and A and B+) - The "Normal" original list
    top_tier_coins = []
    for symbol, dna in engine.dna_profiles.items():
        if dna.get('tier') in ['S', 'A', 'B+']:
            top_tier_coins.append(symbol)
            
    print(f"📡 High-Profile Radar Refresh (S, A, B+ Tier Only) - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    results = []
    for symbol in top_tier_coins:
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, "1d")
            path_4h = coin_cell_paths.get_history_file(symbol, "4h")
            
            if not path_1d.exists() or not path_4h.exists():
                continue
                
            df_1d = pd.read_parquet(path_1d)
            df_4h = pd.read_parquet(path_4h)
            
            if df_1d.empty or df_4h.empty:
                continue
                
            daily = engine.calculate_daily_structure(df_1d)
            momentum = engine.calculate_4h_momentum(df_4h)
            dna = engine.dna_profiles.get(symbol, {})
            
            category = engine.categorize(daily, momentum, dna)
            if category:
                score = engine.calculate_score(daily, momentum)
                results.append(RadarResult(
                    symbol=symbol,
                    category=category,
                    daily=daily,
                    momentum=momentum,
                    score=score,
                    dna_tier=dna.get('tier', 'N/A'),
                    dna_score=dna.get('composite_score', 0.0)
                ))
        except Exception:
            continue
            
    if not results:
        print("\n📭 High-Profile radarda şu an aktif sinyal bulunamadı.")
        return

    print("\n" + "="*95)
    print(f"🎯 TODAY'S HIGH-PROFILE RADAR SIGNALS")
    print("="*95)
    print(f"{'Symbol':<15} | {'DNA':<4} | {'Category':<10} | {'Score':<6} | {'Reason'}")
    print("-" * 95)

    # Sort by Score
    sorted_res = sorted(results, key=lambda x: -x.score)

    for res in sorted_res:
        reason = "Momentum is strong"
        if res.category == "AMBUSH": reason = "Squeeze + Low Midpoint (Pusu)"
        if res.category == "NINJA": reason = "Volatile Bottom Squeeze"
        print(f"{res.symbol:<15} | {res.dna_tier:<4} | {res.category:<10} | {res.score:>6} | {reason}")
    print("="*95)

if __name__ == "__main__":
    run_targeted_scan()
