import pandas as pd
from datetime import datetime
import ccxt
from tezaver.mining.daily_radar_engine import DailyRadarEngine, RadarResult, DailyMetrics, MomentumMetrics
from tezaver.core import config, coin_cell_paths
from tezaver.data.history_service import bulk_update_history

def global_supernova_hunter():
    engine = DailyRadarEngine()
    symbols = config.DEFAULT_COINS
    
    print(f"📡 GLOBAL SUPERNOVA HUNTER: Scanning all {len(symbols)} Binance symbols...")
    print(f"Goal: Identify unmapped gems (BIFI-types) with explosive energy.")
    
    # 1. Fast Sync (Fast-Only mode)
    # We'll sync in batches or focus on just the last few bars
    print("⏳ Syncing latest market data (Fast Mode)...")
    # To save time, we might skip full bulk_update and just fetch the last few bars for everything
    # But for a reliable scan, we need at least 20-50 bars.
    
    # Let's try to sync everything
    # bulk_update_history(symbols, ["1d", "4h"], fast_only=True)
    
    results = []
    
    for i, symbol in enumerate(symbols):
        if i % 50 == 0 and i > 0:
            print(f"  Processed {i}/{len(symbols)} coins...")
            
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, "1d")
            path_4h = coin_cell_paths.get_history_file(symbol, "4h")
            
            if not path_1d.exists() or not path_4h.exists():
                continue
                
            df_1d = pd.read_parquet(path_1d)
            df_4h = pd.read_parquet(path_4h)
            
            if len(df_1d) < 20 or len(df_4h) < 20:
                continue
                
            daily = engine.calculate_daily_structure(df_1d)
            momentum = engine.calculate_4h_momentum(df_4h)
            dna = engine.dna_profiles.get(symbol, {}) # Might be empty
            
            # --- SUPERNOVA DISCOVERY LOGIC ---
            # Even if it has no DNA, if it's exploding, we want it.
            # BIFI-style: ATR% > 10, RSI > 80, 24h Change > 30%
            change_24h = (df_1d['close'].iloc[-1] / df_1d['open'].iloc[-1] - 1) * 100
            
            is_supernova = daily.atr_pct > 8.0 or change_24h > 20.0 or momentum.rsi > 80.0
            
            if is_supernova:
                score = engine.calculate_score(daily, momentum)
                results.append({
                    "symbol": symbol,
                    "tier": dna.get('tier', 'UNMAPPED'),
                    "change": change_24h,
                    "atr": daily.atr_pct,
                    "rsi": momentum.rsi,
                    "score": score
                })
        except Exception:
            continue
            
    if not results:
        print("\n📭 Global Discovery: No Supernova anomalies detected.")
        return

    print("\n" + "="*100)
    print(f"🌟 GLOBAL DISCOVERY: UNMAPPED GEMS & SUPERNOVA EVENTS ({datetime.now().strftime('%H:%M')})")
    print("="*100)
    print(f"{'Symbol':<12} | {'DNA':<8} | {'24h %':<8} | {'ATR%':<6} | {'RSI':<6} | {'Score'}")
    print("-" * 100)

    # Sort by 24h change
    results.sort(key=lambda x: x['change'], reverse=True)

    for r in results:
        char = "🔥" if r['change'] > 30 else "✨"
        print(f"{r['symbol']:<12} | {r['tier']:<8} | {r['change']:>7.1f}% | {r['atr']:>5.1f}% | {r['rsi']:>5.1f} | {r['score']:>5} {char}")
    print("="*100)

if __name__ == "__main__":
    global_supernova_hunter()
