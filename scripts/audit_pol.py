import pandas as pd
from datetime import datetime
from tezaver.mining.daily_radar_engine import DailyRadarEngine
from tezaver.core import coin_cell_paths

def deep_audit_pol():
    engine = DailyRadarEngine()
    symbol = "POLUSDT"
    
    path_1d = coin_cell_paths.get_history_file(symbol, "1d")
    if not path_1d.exists():
        print(f"❌ No history for {symbol}")
        return
        
    df = pd.read_parquet(path_1d) # Get all history
    if len(df) < 50:
        print(f"❌ Not enough bars for {symbol}")
        return
        
    # Calculate returns for each day
    df['returns'] = (df['close'] - df['open']) / df['open'] * 100
    df['is_green'] = df['close'] > df['open']
    
    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    print(f"\n📊 {symbol} Daily Structure (Last 10 Days):")
    print("-" * 60)
    for i, row in df.tail(10).iterrows():
        status = "🟢 GREEN" if row['is_green'] else "🔴 RED"
        print(f"Date: {row['timestamp'].strftime('%Y-%m-%d')} | {status} | Change: {row['returns']:.2f}% | Close: {row['close']:.4f}")
    
    daily = engine.calculate_daily_structure(df)
    dna = engine.dna_profiles.get(symbol, {})
    
    if daily:
        print("\n--- Radar Logic Check ---")
        print(f"DNA Tier: {dna.get('tier')}")
        print(f"Consecutive Green (Last 3): {daily.green_days}")
        print(f"ATR% (Energy): {daily.atr_pct:.2f}%")
        print(f"Midpoint % (Position): {daily.midpoint_pct:.2f}%")
        print(f"Near Resistance: {daily.near_resistance}")
        
        # Check passes_daily_filter logic
        passes_daily = engine.passes_daily_filter(daily, dna)
        print(f"Passes Daily Filter: {passes_daily}")
    else:
        print("❌ calculate_daily_structure failed.")

if __name__ == "__main__":
    deep_audit_pol()
