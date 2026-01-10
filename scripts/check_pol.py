import pandas as pd
from tezaver.mining.daily_radar_engine import DailyRadarEngine
from tezaver.core import coin_cell_paths

def check_pol_radar():
    engine = DailyRadarEngine()
    symbol = "POLUSDT"
    
    print(f"🔍 Analyzing {symbol} technical status...")
    
    path_1d = coin_cell_paths.get_history_file(symbol, "1d")
    path_4h = coin_cell_paths.get_history_file(symbol, "4h")
    
    if not path_1d.exists() or not path_4h.exists():
        print(f"❌ History files not found for {symbol}.")
        return
        
    df_1d = pd.read_parquet(path_1d)
    df_4h = pd.read_parquet(path_4h)
    
    daily = engine.calculate_daily_structure(df_1d)
    momentum = engine.calculate_4h_momentum(df_4h)
    dna = engine.dna_profiles.get(symbol, {})
    
    category = engine.categorize(daily, momentum, dna)
    score = engine.calculate_score(daily, momentum)
    
    print("\n--- Technical Metrics ---")
    print(f"DNA Tier: {dna.get('tier', 'N/A')}")
    print(f"Daily ATR%: {daily.atr_pct:.2f}%")
    print(f"Daily Midpoint: {daily.midpoint_pct:.2f}%")
    print(f"4H RSI: {momentum.rsi:.2f}")
    print(f"Category: {category}")
    print(f"Score: {score}")

if __name__ == "__main__":
    check_pol_radar()
