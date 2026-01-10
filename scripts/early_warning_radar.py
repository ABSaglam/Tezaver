import pandas as pd
from datetime import datetime
from tezaver.mining.daily_radar_engine import DailyRadarEngine, RadarResult
from tezaver.core import config, coin_cell_paths

def run_early_warning_radar():
    engine = DailyRadarEngine()
    symbols = config.DEFAULT_COINS
    print(f"📡 EARLY WARNING RADAR (Pusu Modu) - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("Hedef: Coşmadan önceki 'Sıkışma' ve 'Dip Dönüş' evresini yakalamak.")
    
    pre_pump_signals = []
    
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
            
            # --- PRE-PUMP (EARLY WARNING) CRITERIA ---
            # 1. BB Squeeze is essential for 'coiling'
            is_coiling = daily.bb_squeeze
            
            # 2. Early Momentum (Not yet overbought)
            is_early_momentum = 45 < momentum.rsi < 62
            
            # 3. Low Energy (Not yet expanded)
            is_low_energy = 2.0 < daily.atr_pct < 8.0
            
            # 4. Position (Not too high yet)
            is_good_position = daily.midpoint_pct < 65
            
            priority = 0
            if is_coiling: priority += 30
            if tier in ['S', 'A', 'B+']: priority += 20
            if momentum.rsi_rising: priority += 10
            
            if (is_coiling or (tier in ['S', 'A'] and is_early_momentum)) and is_low_energy and is_good_position:
                pre_pump_signals.append({
                    "symbol": symbol,
                    "tier": tier,
                    "cat": engine.categorize(daily, momentum, dna),
                    "atr": daily.atr_pct,
                    "rsi": momentum.rsi,
                    "mid": daily.midpoint_pct,
                    "priority": priority
                })
        except Exception:
            continue

    if not pre_pump_signals:
        print("📭 Şu an 'Pusu' (Early Warning) kriterlerine uyan koin bulunamadı.")
        return

    # Sort by Priority
    pre_pump_signals.sort(key=lambda x: x['priority'], reverse=True)
    top_picks = pre_pump_signals[:10]

    print("\n" + "🛡️" * 30)
    print("🔍 PRE-PUMP EARLY WARNING (Potansiyel Supernovalar)")
    print("🛡️" * 30)
    print(f"{'Symbol':<12} | {'Tier':<4} | {'State':<10} | {'ATR%':<6} | {'RSI':<6} | {'Mid%'}")
    print("-" * 75)
    
    for r in top_picks:
        state = r['cat'] if r['cat'] else "COILING"
        print(f"{r['symbol']:<12} | {r['tier']:<4} | {state:<10} | {r['atr']:>5.1f}% | {r['rsi']:>5.1f} | {r['mid']:>5.1f}%")
    print("=" * 75)
    print("💡 Not: Bu koinler henüz 'coşmamış', enerjisi içinde biriken (Squeeze) adaylardır.")

if __name__ == "__main__":
    run_early_warning_radar()
