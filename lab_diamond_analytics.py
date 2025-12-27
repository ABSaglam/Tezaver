
import pandas as pd
from pathlib import Path
from datetime import timedelta

def analyze_diamonds():
    symbol = "ADAUSDT"
    path = Path(f"library/fast15_rallies/{symbol}/fast15_rallies.parquet")
    
    if not path.exists():
        print("File not found.")
        return
        
    df = pd.read_parquet(path)
    if 'event_time' in df.columns:
        df['event_time'] = pd.to_datetime(df['event_time'])
        
    # Filter Diamonds (Gain >= 30%)
    diamonds = df[df['future_max_gain_pct'] >= 0.30].copy()
    
    if diamonds.empty:
        print("No Diamonds found to analyze.")
        return
        
    print(f"💎 DIAMOND DNA ANALYSIS ({len(diamonds)} Events)")
    print("="*60)
    
    # 1. Timing Analysis (UTC+3)
    diamonds['tr_time'] = diamonds['event_time'] + timedelta(hours=3)
    diamonds['hour_tr'] = diamonds['tr_time'].dt.hour
    
    print("\n⏰ TIMING (Start Hours TR):")
    print(diamonds['hour_tr'].value_counts().sort_index().to_string())
    
    # 2. Indicator Profile at Start
    print("\n📊 INDICATOR DNA (Entry Conditions):")
    cols = ['rsi_15m', 'rsi_ema_15m', 'volume_rel_15m', 'atr_pct_15m', 'bars_to_peak']
    
    # Check existence
    valid_cols = [c for c in cols if c in diamonds.columns]
    stats = diamonds[valid_cols].describe().loc[['mean', 'min', 'max', '50%']]
    print(stats)
    
    # 3. MACD Phase
    if 'macd_phase_15m' in diamonds.columns:
        print("\n🌊 MACD PHASE:")
        print(diamonds['macd_phase_15m'].value_counts())
        
    print("\n📜 INDIVIDUAL PROFILES:")
    for _, row in diamonds.iterrows():
        ts_tr = row['tr_time']
        gain = row['future_max_gain_pct'] * 100
        rsi = row.get('rsi_15m', 0)
        vol = row.get('volume_rel_15m', 0)
        dur = row.get('bars_to_peak', 0)
        
        print(f"• {ts_tr}: {gain:.1f}% Gain")
        print(f"  RSI: {rsi:.1f} | Vol: {vol:.1f}x | Duration: {dur/4:.1f} hours")
        print("-" * 40)

if __name__ == "__main__":
    analyze_diamonds()
