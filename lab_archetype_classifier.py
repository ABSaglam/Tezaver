
import pandas as pd
from pathlib import Path
from datetime import timedelta

def classify_archetypes():
    symbol = "ADAUSDT"
    path = Path(f"library/fast15_rallies/{symbol}/fast15_rallies.parquet")
    
    if not path.exists():
        print("File not found.")
        return
        
    df = pd.read_parquet(path)
    if 'event_time' in df.columns:
        df['event_time'] = pd.to_datetime(df['event_time'])
    
    # Sort by time for Phoenix detection
    df = df.sort_values('event_time').reset_index(drop=True)
    
    results = []
    
    for i, row in df.iterrows():
        # DNA Markers
        rsi = row.get('rsi_15m', 50)
        vol = row.get('volume_rel_15m', 1.0)
        dur = row.get('bars_to_peak', 10)
        gain = row.get('future_max_gain_pct', 0.1) * 100
        ts = row['event_time']
        
        archetype = "Hybrid / Generic"
        
        # 1. PHOENIX Check (Temporal)
        is_phoenix = False
        if i > 0:
            prev_row = df.iloc[i-1]
            prev_ts = prev_row['event_time']
            hours_diff = (ts - prev_ts).total_seconds() / 3600
            
            # If previous rally was recent (< 10h) and this one is arguably a "Second Wave"
            if 1.0 < hours_diff < 12.0:
                # Ideally check if prev was big, but let's assume proximity implies wave structure
                is_phoenix = True
                
        # Classification Logic (Priority Order)
        
        if rsi < 25:
            archetype = "🩸 GUILLOTINE (V-Shape)"
        elif rsi > 65:
            archetype = "🏄‍♂️ SURFER (Momentum)"
        elif vol >= 4.0:
            archetype = "💥 SUPERNOVA (Explosion)"
        elif is_phoenix:
            archetype = "🔥 PHOENIX (Second Wave)"
        elif rsi < 45 and vol < 1.8:
            # Low Vol, Low RSI
            if dur > 40:
                archetype = "🪜 GRIND (Merdiven)"
            else:
                archetype = "🥷 NINJA (Stealth)"
        else:
            # Check for pure Grind if not Ninja
            if dur > 40 and vol < 2.0:
                archetype = "🪜 GRIND (Merdiven)"
            
        
        results.append({
            'ts_utc': ts,
            'ts_tr': ts + timedelta(hours=3),
            'gain': gain,
            'archetype': archetype,
            'rsi': rsi,
            'vol': vol,
            'dur': dur
        })
        
    results_df = pd.DataFrame(results)
    
    print("🎭 RALLY ARCHETYPE DISTRIBUTION (ADAUSDT)")
    print("="*60)
    print(results_df['archetype'].value_counts())
    
    print("\n🔍 EXAMPLES BY TYPE (Top Gainers):")
    print("-" * 60)
    
    for atype in results_df['archetype'].unique():
        subset = results_df[results_df['archetype'] == atype].sort_values('gain', ascending=False).head(3)
        print(f"\n{atype}:")
        for _, r in subset.iterrows():
            print(f"  • {r['ts_tr']} | Gain: {r['gain']:.1f}% | RSI: {r['rsi']:.1f} | Vol: {r['vol']:.1f}x")

if __name__ == "__main__":
    classify_archetypes()
