import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

# CONFIG
SYMBOL = "DASHUSDT"
with open(f"data/golden_keys/{SYMBOL}_key.json", "r") as f:
    golden_dna_list = set(json.load(f).get('golden_dna_list', []))

def load_data():
    df = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_15m.parquet")
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
    df['rsi'] = 100 - (100 / (1 + gain / loss))
    
    # metrics
    df['body_pct'] = (df['close'] / df['open'] - 1) * 100
    df['vol_ma'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma']
    
    # 1. Body Purity
    df['purity'] = abs(df['close'] - df['open']) / (df['high'] - df['low'] + 0.000001)
    
    # 2. RSI Overdrive (ROC)
    df['rsi_roc'] = df['rsi'].diff(1)
    df['price_roc'] = df['close'].pct_change(1) * 100
    df['overdrive'] = df['rsi_roc'] / (df['price_roc'].replace(0, 0.001))
    
    # 3. Stealth Volume (Slope of last 3)
    df['vol_slope'] = df['volume'].diff(1) > 0 
    df['stealth'] = (df['volume'] > df['volume'].shift(1)) & (df['volume'].shift(1) > df['volume'].shift(2))
    
    return df

def run_brainstorm_sim():
    df = load_data()
    
    # Mock Tunnel DNA Calculation (Simplified for this test)
    # Normally we would use the full get_profile, but here we just need to target the 22 days we already know.
    # To be precise, let's load the audit report to get the exact days.
    # Analysis logic already has approved_dates list.
    # I'll just use the dates I extracted earlier.
    approved_dates = [
        "2025-09-30", "2025-10-01", "2025-10-02", "2025-10-04", "2025-10-07",
        "2025-10-08", "2025-10-09", "2025-10-10", "2025-10-12", "2025-10-13",
        "2025-10-14", "2025-10-17", "2025-10-19", "2025-10-20", "2025-10-29",
        "2025-11-01", "2025-11-05", "2025-11-14", "2025-11-15", "2025-11-16",
        "2025-11-18", "2026-01-13"
    ]
    
    results = []
    
    for date_str in approved_dates:
        day_ts = pd.Timestamp(date_str)
        day_data = df[df.index.normalize() == day_ts]
        
        if day_data.empty: continue
        
        # Original Akinci Thresholds for DASH
        # MIN_VOL = 1.26, MIN_RSI = 55.0, MIN_BODY = 0.50
        
        akinci_candidates = day_data[(day_data['vol_ratio'] >= 1.26) & 
                                     (day_data['rsi'] >= 55) & 
                                     (day_data['body_pct'] >= 0.50)]
        
        if akinci_candidates.empty:
            first_akinci = None
        else:
            first_akinci = akinci_candidates.index[0]
            
        # Analyze performance of new metrics on this day
        # 1. Does Purity > 0.90 catch the move better?
        purity_hits = day_data[day_data['purity'] > 0.90]
        
        # 2. Does Overdrive > 10 (High RSI jump per price) catch it earlier?
        overdrive_hits = day_data[day_data['overdrive'] > 10]
        
        # 3. Does Stealth (3 rising volume candles) precede Akinci?
        stealth_hits = day_data[day_data['stealth'] == True]
        
        results.append({
            "day": date_str,
            "akinci_time": first_akinci.strftime("%H:%M") if first_akinci else "N/A",
            "max_purity": day_data['purity'].max(),
            "avg_purity": day_data['purity'].mean(),
            "overdrive_peaks": len(overdrive_hits),
            "stealth_count": len(stealth_hits),
            "rally_size": (day_data['high'].max() / day_data['low'].min() - 1) * 100
        })

    # FINAL REPORT
    print(f"| GÜN | AKINCI | SAFİYET (Δ) | OVERDRIVE (Δ) | SİNSİ (Δ) | RALLİ |")
    print(f"| --- | --- | --- | --- | --- | --- |")
    
    for date_str in approved_dates:
        day_ts = pd.Timestamp(date_str)
        day_data = df[df.index.normalize() == day_ts]
        if day_data.empty: continue
        
        # Original Akinci
        akinci_cand = day_data[(day_data['vol_ratio'] >= 1.26) & (day_data['rsi'] >= 55) & (day_data['body_pct'] >= 0.50)]
        t_akinci = akinci_cand.index[0] if not akinci_cand.empty else None
        
        # 1. Purity > 0.90
        purity_cand = day_data[day_data['purity'] > 0.90]
        t_purity = purity_cand.index[0] if not purity_cand.empty else None
        
        # 2. Overdrive > 10
        overdrive_cand = day_data[day_data['overdrive'] > 10]
        t_overdrive = overdrive_cand.index[0] if not overdrive_cand.empty else None
        
        # 3. Stealth (3 rising)
        stealth_cand = day_data[day_data['stealth'] == True]
        t_stealth = stealth_cand.index[0] if not stealth_cand.empty else None
        
        def get_delta(t_new, t_ref):
            if not t_new or not t_ref: return "-"
            diff = (t_new - t_ref).total_seconds() / 60
            if diff == 0: return "0"
            return f"{int(diff)}dk"

        r_size = (day_data['high'].max() / day_data['low'].min() - 1) * 100
        
        print(f"| {date_str} | {t_akinci.strftime('%H:%M') if t_akinci else 'N/A'} | {get_delta(t_purity, t_akinci)} | {get_delta(t_overdrive, t_akinci)} | {get_delta(t_stealth, t_akinci)} | %{r_size:.1f} |")

if __name__ == "__main__":
    run_brainstorm_sim()
