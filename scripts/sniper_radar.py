import pandas as pd
from datetime import datetime
from tezaver.mining.daily_radar_engine import DailyRadarEngine, RadarResult
from tezaver.core import config, coin_cell_paths

def run_sniper_radar():
    engine = DailyRadarEngine()
    symbols = config.DEFAULT_COINS
    print(f"📡 SNIPER RADAR (Top 10 Selection) - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    candidates = []
    
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
            
            # --- EXTREME SELECTIVITY FILTERS (Phase 24) ---
            # 1. Tier Filter (Only High Quality)
            is_high_tier = tier in ['S', 'A', 'B+']
            
            # 2. Golden Energy Gate (Phase 16)
            min_energy = 15.0 if tier == 'A' else 20.0
            is_energetic = daily.atr_pct >= min_energy
            
            # 3. Alpha Momentum Zone (Phase 20)
            is_alpha_momentum = 50 <= momentum.rsi <= 75
            
            # 4. Global Supernova wildcard (BIFI-style)
            change_24h = (df_1d['close'].iloc[-1] / df_1d['open'].iloc[-1] - 1) * 100
            is_supernova = change_24h > 30 or (tier == 'UNMAPPED' and daily.atr_pct > 15)

            if (is_high_tier and is_energetic and is_alpha_momentum) or is_supernova:
                category = engine.categorize(daily, momentum, dna)
                score = engine.calculate_score(daily, momentum)
                
                candidates.append({
                    "symbol": symbol,
                    "tier": tier,
                    "cat": category if category else "ALPHA",
                    "score": score,
                    "atr": daily.atr_pct,
                    "rsi": momentum.rsi,
                    "change": change_24h,
                    "verdict": "🔥 SUPERNOVA" if is_supernova else "💎 SNIPER-ELITE"
                })
        except Exception:
            continue

    if not candidates:
        print("📭 Sniper-Elite: Bugün tüm filtrelerden (%80+ isabet) geçen 'kusursuz' bir sinyal bulunamadı.")
        print("Not: Piyasa şu an dinlenme veya düşük enerji evresinde olabilir.")
        return

    # Sort by Score & Change
    candidates.sort(key=lambda x: (x['verdict'] == '🔥 SUPERNOVA', x['score']), reverse=True)
    top_5 = candidates[:5]

    print("\n" + "💎" * 35)
    print("🎯 SNIPER-ELITE: NO-NOISE / %80+ CONFIDENCE")
    print("💎" * 35)
    print(f"{'Symbol':<15} | {'Tier':<4} | {'Category':<10} | {'ATR%':<6} | {'RSI':<6} | {'Verdict'}")
    print("-" * 88)
    
    for r in top_5:
        print(f"{r['symbol']:<15} | {r['tier']:<4} | {r['cat']:<10} | {r['atr']:>5.1f}% | {r['rsi']:>5.1f} | {r['verdict']}")
    print("=" * 88)

if __name__ == "__main__":
    run_sniper_radar()
