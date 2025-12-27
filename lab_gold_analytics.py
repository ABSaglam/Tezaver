
import pandas as pd
from pathlib import Path
from datetime import timedelta

def analyze_gold():
    symbol = "ADAUSDT"
    path = Path(f"library/fast15_rallies/{symbol}/fast15_rallies.parquet")
    
    if not path.exists():
        print("File not found.")
        return
        
    df = pd.read_parquet(path)
    if 'event_time' in df.columns:
        df['event_time'] = pd.to_datetime(df['event_time'])
        
    # Filter Gold (20% <= Gain < 30%)
    # Also check rally_bucket label if useful, but gain is more precise
    gold = df[(df['future_max_gain_pct'] >= 0.20) & (df['future_max_gain_pct'] < 0.30)].copy()
    
    if gold.empty:
        print("No Gold Rallies found to analyze.")
        return
        
    print(f"🥇 GOLD DNA ANALYSIS ({len(gold)} Events)")
    print("="*60)
    
    # 1. Timing Analysis (UTC+3)
    gold['tr_time'] = gold['event_time'] + timedelta(hours=3)
    gold['hour_tr'] = gold['tr_time'].dt.hour
    
    print("\n⏰ TIMING (Start Hours TR):")
    print(gold['hour_tr'].value_counts().sort_index().to_string())
    
    # 2. Indicator Profile at Start
    print("\n📊 INDICATOR DNA (Entry Conditions):")
    cols = ['rsi_15m', 'rsi_ema_15m', 'volume_rel_15m', 'atr_pct_15m', 'bars_to_peak']
    
    # Check existence
    valid_cols = [c for c in cols if c in gold.columns]
    stats = gold[valid_cols].describe().loc[['mean', 'min', 'max', '50%']]
    print(stats)
    
    # 3. MACD Phase
    if 'macd_phase_15m' in gold.columns:
        print("\n🌊 MACD PHASE:")
        print(gold['macd_phase_15m'].value_counts())
        
    print("\n📜 INDIVIDUAL PROFILES (Top 10):")
    for _, row in gold.sort_values('future_max_gain_pct', ascending=False).head(10).iterrows():
        ts_tr = row['tr_time']
        gain = row['future_max_gain_pct'] * 100
        rsi = row.get('rsi_15m', 0)
        vol = row.get('volume_rel_15m', 0)
        dur = row.get('bars_to_peak', 0)
        
        print(f"• {ts_tr}: {gain:.1f}% Gain")
        print(f"  RSI: {rsi:.1f} | Vol: {vol:.1f}x | Duration: {dur/4:.1f} hours")
        print("-" * 40)

if __name__ == "__main__":
    analyze_gold()
