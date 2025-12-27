
import pandas as pd
from pathlib import Path
from datetime import timedelta

def generate_tier_matrix():
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
        tier = row.get('rally_bucket', 'Unknown')
        
        archetype = "❓ GENERIC (Boşta)"
        
        # 1. PHOENIX Check (Temporal)
        is_phoenix = False
        if i > 0:
            prev_row = df.iloc[i-1]
            prev_ts = prev_row['event_time']
            hours_diff = (ts - prev_ts).total_seconds() / 3600
            if 1.0 < hours_diff < 12.0:
                is_phoenix = True
                
        # Classification Logic
        if rsi < 25:
            archetype = "🩸 GUILLOTINE"
        elif rsi > 65:
            archetype = "🏄‍♂️ SURFER"
        elif vol >= 4.0:
            archetype = "💥 SUPERNOVA"
        elif is_phoenix:
            archetype = "🔥 PHOENIX"
        elif rsi < 45 and vol < 1.8:
            if dur > 40:
                archetype = "🪜 GRIND"
            else:
                archetype = "🥷 NINJA"
        elif dur > 40 and vol < 2.0:
             archetype = "🪜 GRIND"
            
        results.append({
            'ts_tr': ts + timedelta(hours=3),
            'gain': gain,
            'tier': tier,
            'archetype': archetype,
            'rsi': rsi,
            'vol': vol
        })
        
    df_res = pd.DataFrame(results)
    
    # Map buckets to human names
    tier_map = {
        "30p_plus": "💎 DIAMOND",
        "20p_30p": "🥇 GOLD",
        "10p_20p": "🥈 SILVER",
        "5p_10p": "🥉 BRONZE"
    }
    df_res['tier_name'] = df_res['tier'].map(tier_map).fillna(df_res['tier'])
    
    print("📊 TIER vs ARCHETYPE MATRISI")
    print("="*60)
    
    # Process only Top Tiers
    for tier_id in ["30p_plus", "20p_30p", "10p_20p"]:
        subset = df_res[df_res['tier'] == tier_id]
        if subset.empty: continue
        
        t_name = tier_map.get(tier_id, tier_id)
        print(f"\n{t_name} (Toplam: {len(subset)})")
        print("-" * 60)
        
        counts = subset['archetype'].value_counts()
        print(counts.to_string())
        
        # Show "Generic" (Boşta) reasons
        generics = subset[subset['archetype'] == "❓ GENERIC (Boşta)"]
        if not generics.empty:
            print(f"\n⚠️ {len(generics)} Tane {t_name} Açıkta Kaldı (Generic):")
            for _, r in generics.iterrows():
                print(f"  • {r['ts_tr']} | Gain: {r['gain']:.1f}% | RSI: {r['rsi']:.1f} | Vol: {r['vol']:.1f}x")
                print("    -> (Volume 1.8-4.0 arası veya RSI 45-65 arası - Yani 'Araf'ta)")

if __name__ == "__main__":
    generate_tier_matrix()
