import pandas as pd
from datetime import datetime
from tezaver.mining.daily_radar_engine import DailyRadarEngine, RadarResult
from tezaver.core import config, coin_cell_paths

def run_unified_radar():
    engine = DailyRadarEngine()
    symbols = config.DEFAULT_COINS
    print(f"📡 UNIFIED RADAR REFRESH: Combining Elite HP + Global Discovery - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    elite_results = []
    discovery_results = []
    
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
            tier = dna.get('tier', 'UNMAPPED')
            
            # --- 1. TACTICAL HP LOGIC (Phase 16) ---
            min_energy = 15.0 if tier == 'A' else 20.0
            category = engine.categorize(daily, momentum, dna)
            
            if daily.atr_pct >= min_energy and category:
                score = engine.calculate_score(daily, momentum)
                elite_results.append({
                    "symbol": symbol, "tier": tier, "cat": category, 
                    "atr": daily.atr_pct, "score": score, "conf": "80% (HP)"
                })
                
            # --- 2. GLOBAL SUPERNOVA LOGIC (Phase 22) ---
            change_24h = (df_1d['close'].iloc[-1] / df_1d['open'].iloc[-1] - 1) * 100
            if (daily.atr_pct > 8.0 or change_24h > 20.0 or momentum.rsi > 80.0) and tier == 'UNMAPPED':
                discovery_results.append({
                    "symbol": symbol, "change": change_24h, "atr": daily.atr_pct, 
                    "rsi": momentum.rsi, "type": "SUPERNOVA" if change_24h > 30 else "GEM"
                })
        except Exception:
            continue

    # --- OUTPUT ---
    print("\n" + "💎" * 30)
    print("🎯 ELITE TACTICAL SELECTIONS (%80+ Success Probability)")
    print("💎" * 30)
    if elite_results:
        elite_results.sort(key=lambda x: x['score'], reverse=True)
        print(f"{'Symbol':<12} | {'Tier':<4} | {'Category':<10} | {'ATR%':<6} | {'Confidence'}")
        print("-" * 60)
        for r in elite_results:
            print(f"{r['symbol']:<12} | {r['tier']:<4} | {r['cat']:<10} | {r['atr']:>5.1f}% | {r['conf']}")
    else:
        print("📭 No elite tactical signals meet the HP Energy threshold (ATR > 15-20%) today.")

    print("\n" + "🚀" * 30)
    print("🌟 GLOBAL DISCOVERY (Unmapped Supernovas & Gems)")
    print("🚀" * 30)
    if discovery_results:
        discovery_results.sort(key=lambda x: x['change'], reverse=True)
        print(f"{'Symbol':<12} | {'Type':<10} | {'24h %':<8} | {'ATR%':<6} | {'RSI'}")
        print("-" * 60)
        for r in discovery_results:
            print(f"{r['symbol']:<12} | {r['type']:<10} | {r['change']:>7.1f}% | {r['atr']:>5.1f}% | {r['rsi']:>5.1f}")
    else:
        print("📭 No new unmapped gems detected in global discovery.")

if __name__ == "__main__":
    run_unified_radar()
