
import pandas as pd
from pathlib import Path
from datetime import timedelta

def validate_archetypes_honestly():
    symbol = "ADAUSDT"
    path = Path(f"library/fast15_rallies/{symbol}/fast15_rallies.parquet")
    
    if not path.exists():
        print("File not found.")
        return
        
    df = pd.read_parquet(path)
    if 'event_time' in df.columns:
        df['event_time'] = pd.to_datetime(df['event_time'])
    
    # Sort by time for Context check
    df = df.sort_values('event_time').reset_index(drop=True)
    
    print("🕵️‍♂️ ARCHETYPE VALIDATION REPORT (Top 20 Gainers)")
    print("Applying the '3-Step Guide' strictly...")
    print("="*80)
    print(f"{'TIME (TR)':<20} | {'GAIN':<6} | {'RSI':<5} | {'VOL':<4} | {'CONTEXT':<10} | {'VERDICT (The Guide)'}")
    print("-" * 80)
    
    # Store results to sort by gain later
    annotated = []
    
    for i, row in df.iterrows():
        # DATA
        rsi = row.get('rsi_15m', 50)
        vol = row.get('volume_rel_15m', 1.0)
        gain = row.get('future_max_gain_pct', 0.1) * 100
        ts = row['event_time']
        ts_tr = ts + timedelta(hours=3)
        
        # LOGIC ( The 3 Steps )
        verdict = "❓ UNKNOWN"
        context_note = "Flat"
        
        # Check Context (Step 3 prequel)
        is_phoenix_context = False
        if i > 0:
            prev_row = df.iloc[i-1]
            hours_diff = (ts - prev_row['event_time']).total_seconds() / 3600
            if 1.0 < hours_diff < 12.0:
                is_phoenix_context = True
                context_note = f"Prev {hours_diff:.1f}h"

        # STEP 1: RSI
        if rsi < 25:
            verdict = "🩸 GUILLOTINE"
        elif rsi > 65:
            verdict = "🏄‍♂️ SURFER"
        else:
            # RSI 30-55 -> GO TO STEP 2
            
            # STEP 2: VOLUME
            if vol >= 4.0:
                verdict = "💥 SUPERNOVA"
            elif vol < 2.0:
                # Low Vol -> GO TO STEP 3
                
                # STEP 3: CONTEXT
                if is_phoenix_context:
                    verdict = "🔥 PHOENIX"
                else:
                    verdict = "🪜 GRIND / NINJA"  # Default for low vol, flat context
            else:
                # Vol 2.0 - 4.0 -> ???
                # This is the "Grey Zone". Let's call it "Hybrid"
                if is_phoenix_context:
                    verdict = "🔥 PHOENIX (Aggressive)"
                else:
                    verdict = "⚠️ HYBRID (Mid Vol)"

        annotated.append({
            'ts_tr': ts_tr,
            'gain': gain,
            'rsi': rsi,
            'vol': vol,
            'context': context_note,
            'verdict': verdict
        })
        
    # Sort by Gain to show the "Big Ones"
    annotated_sorted = sorted(annotated, key=lambda x: x['gain'], reverse=True)
    
    for item in annotated_sorted[:25]:
        print(f"{str(item['ts_tr']):<20} | {item['gain']:>5.1f}% | {item['rsi']:>5.1f} | {item['vol']:>4.1f} | {item['context']:<10} | {item['verdict']}")

if __name__ == "__main__":
    validate_archetypes_honestly()
