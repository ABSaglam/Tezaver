import pandas as pd
from datetime import datetime
import ccxt
from tezaver.mining.daily_radar_engine import DailyRadarEngine, RadarResult
from tezaver.core import coin_cell_paths

def force_bifi_audit():
    symbol = "BIFIUSDT"
    print(f"📡 Force fetching {symbol} data from Binance...")
    
    # 1. Direct Fetch
    binance = ccxt.binance()
    timeframes = ["1d", "4h"]
    for tf in timeframes:
        print(f"  Fetching {tf}...")
        bars = binance.fetch_ohlcv('BIFI/USDT', tf, limit=100)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Save to coin_cell
        data_dir = coin_cell_paths.get_coin_data_dir(symbol)
        path = data_dir / f"history_{tf}.parquet"
        df.to_parquet(path)
        print(f"  Saved {len(df)} bars to {path}")

    # 2. Audit with Engine
    engine = DailyRadarEngine()
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, "1d"))
    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, "4h"))
    
    daily = engine.calculate_daily_structure(df_1d)
    momentum = engine.calculate_4h_momentum(df_4h)
    
    # BIFI has no DNA, we'll see how engine reacts
    dna = engine.dna_profiles.get(symbol, {})
    
    if daily:
        print("\n" + "="*80)
        print(f"🔥 BIFI (Beefy) EMERGENCY AUDIT")
        print("="*80)
        print(f"ATR% (Energy): {daily.atr_pct:.2f}% (ULTRA HIGH)")
        print(f"4H RSI: {momentum.rsi:.2f}")
        print(f"Price: {df_1d['close'].iloc[-1]:.2f}")
        print(f"24h Change: {(df_1d['close'].iloc[-1]/df_1d['open'].iloc[-1] - 1)*100:.1f}%")
        
        category = engine.categorize(daily, momentum, dna)
        print(f"Radar Category: {category if category else 'NONE (Filters too strict?)'}")
        
    else:
        print("❌ Failed to calculate Daily Metrics.")

if __name__ == "__main__":
    force_bifi_audit()
