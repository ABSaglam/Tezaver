
import pandas as pd
from pathlib import Path
from datetime import timedelta

def check_pattern_coverage():
    symbol = "ADAUSDT"
    path = Path(f"library/fast15_rallies/{symbol}/fast15_rallies.parquet")
    
    if not path.exists():
        print("File not found.")
        return
        
    df = pd.read_parquet(path)
    if 'event_time' in df.columns:
        df['event_time'] = pd.to_datetime(df['event_time'])
    
    # Filter for Major Rallies (> 20% Gain) - Diamond & Gold
    majors = df[df['future_max_gain_pct'] >= 0.20].copy()
    
    print(f"🔬 PATTERN COVERAGE TEST: {symbol}")
    print(f"Total Major Rallies (>20%): {len(majors)}")
    print("="*80)
    
    # Define Mechanical Patterns (Akla Yatan Kalıplar)
    # 1. High Volume (Explosion)
    # 2. Low Volume (Stealth/Grind)
    # 3. Deep Oversold (Reversal)
    
    # We will tag each rally.
    # Note: A rally can match multiple (e.g. Low RSI + High Volume)
    
    unmatched = []
    
    for i, row in majors.iterrows():
        rsi = row.get('rsi_15m', 50)
        vol = row.get('volume_rel_15m', 1.0)
        gain = row.get('future_max_gain_pct') * 100
        ts_tr = row['event_time'] + timedelta(hours=3)
        
        matches = []
        
        # PATTERN 1: HIGH VOLUME (Patlama)
        # Using 3.0x as a reasonable "Noticeable" threshold (User mentioned "Hacim Patlaması")
        if vol >= 3.0:
            matches.append("HighVol")
            
        # PATTERN 2: LOW VOLUME (Sessiz)
        # Using 1.5x as "Normal/Quiet" threshold
        if vol <= 1.5:
            matches.append("LowVol")
            
        # PATTERN 3: DEEP OVERSOLD (Dip Dönüşü)
        # RSI < 30
        if rsi < 30:
            matches.append("DeepDip")
            
        # Coverage Check
        if not matches:
            # It is "Boşta Kalan" (The Mystery)
            unmatched.append({
                'ts': ts_tr,
                'gain': gain,
                'rsi': rsi,
                'vol': vol
            })
        else:
            pass # Covered
            
    # REPORTING
    total = len(majors)
    unc = len(unmatched)
    cov = total - unc
    
    print(f"✅ COVERED: {cov} ({cov/total*100:.1f}%) -> Fit at least one pattern.")
    print(f"❓ UNMATCHED: {unc} ({unc/total*100:.1f}%) -> Don't fit ANY pattern.")
    print("-" * 80)
    
    if unmatched:
        print("🕵️‍♂️ ANALYZING THE UNMATCHED (The 'Codes' we haven't solved yet):")
        print(f"{'TIME (TR)':<20} | {'GAIN':<6} | {'RSI':<5} | {'VOL':<5} | {'WHY?'}")
        print("-" * 80)
        for u in unmatched:
            # Explain why it failed
            # It failed HighVol (>3) AND LowVol (<1.5) -> So Vol is 1.5 - 3.0 (Mid Range)
            # It failed LowRSI (<30) -> So RSI is >= 30
            reason = "Vol 1.5-3.0 (Mid) & RSI > 30 (Normal)"
            print(f"{str(u['ts']):<20} | {u['gain']:>5.1f}% | {u['rsi']:>5.1f} | {u['vol']:>5.1f} | {reason}")

if __name__ == "__main__":
    check_pattern_coverage()
