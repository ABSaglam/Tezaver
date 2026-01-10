import pandas as pd
from datetime import datetime
from tezaver.mining.daily_radar_engine import DailyRadarEngine, RadarResult
from tezaver.core import coin_cell_paths

def run_tactical_playbook_scan():
    engine = DailyRadarEngine()
    print(f"📡 GEN-RADAR: Tactical Playbook Scan (%80+ Win Probability) - {datetime.now().strftime('%Y-%m-%d')}")
    
    results = []
    # Full scan but with tactical filters
    for symbol in engine.coins:
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
            tier = dna.get('tier', 'N/A')
            
            # --- TACTICAL PLAYBOOK RULES (Phase 16) ---
            # Rule 1: Energy Thresholds
            if tier == 'A':
                min_energy = 15.0
            else:
                min_energy = 20.0
                
            # Rule 2: Pass/Fail based on Golden Ratio
            passed_energy = daily.atr_pct >= min_energy
            
            # Rule 3: Character filter (NINJA/TREND/AMBUSH)
            category = engine.categorize(daily, momentum, dna)
            
            # Special Rule: Standard-Alpha Identification
            is_alpha = daily.atr_pct > 14 and momentum.rsi > 60
            
            if passed_energy and category:
                score = engine.calculate_score(daily, momentum)
                results.append({
                    "symbol": symbol,
                    "tier": tier,
                    "category": category,
                    "atr": daily.atr_pct,
                    "rsi": momentum.rsi,
                    "score": score,
                    "is_alpha": is_alpha
                })
        except Exception:
            continue
            
    if not results:
        print("\n📭 Tactical Playbook: Bugün %80+ isabetli 'Altın Kapı' sinyali bulunamadı.")
        print("Piyasada 'Patlayıcı Enerji' (ATR > %15-20) henüz yeterli seviyede değil.")
        return

    print("\n" + "="*95)
    print(f"🚀 TACTICAL PLAYBOOK APPROVED SIGNALS (%80 Confidence Zone)")
    print("="*95)
    print(f"{'Symbol':<12} | {'Tier':<4} | {'Cat':<10} | {'ATR%':<6} | {'RSI':<6} | {'Confidence'}")
    print("-" * 95)

    # Sort by Confidence (Alpha first, then Score)
    results.sort(key=lambda x: (x['is_alpha'], x['score']), reverse=True)

    for r in results:
        conf = "VERY HIGH" if r['is_alpha'] else "HIGH"
        print(f"{r['symbol']:<12} | {r['tier']:<4} | {r['category']:<10} | {r['atr']:>5.1f}% | {r['rsi']:>5.1f} | {conf}")
    print("="*95)

if __name__ == "__main__":
    run_tactical_playbook_scan()
