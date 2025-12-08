
import pandas as pd
import numpy as np
import glob
from pathlib import Path
from tezaver.core import coin_cell_paths

# The "Sweet Spots" extracted from the previous Analysis
DNA_PROFILES = {
    "INJUSDT": 33.3,
    "LTCUSDT": 33.7,
    "ETHUSDT": 34.5,
    "SOLUSDT": 35.1,
    "BTCUSDT": 36.0,
    "UNIUSDT": 38.0,
    "DOGEUSDT": 37.5,
    "XRPUSDT": 36.6,
    "BNBUSDT": 34.5, # Assumed approx
    "MATICUSDT": 35.0, # Assumed
    "POLUSDT": 35.7,
    "ADAUSDT": 36.0,
    "LINKUSDT": 37.3,
    "AVAXUSDT": 35.0 # Average
}

def validate_dna_precision():
    print("🔬 DNA VALIDATION: Checking 'False Positive' Rates...")
    print(f"Testing {len(DNA_PROFILES)} specific coin profiles.")
    
    results = []

    for symbol, threshold in DNA_PROFILES.items():
        # Find file
        f = coin_cell_paths.get_history_file(symbol, "15m")
        if not f.exists():
            continue
            
        try:
            df = pd.read_parquet(f)
        except: continue
        
        # Datetime & Sort
        if 'open_time' in df.columns:
            if pd.api.types.is_numeric_dtype(df['open_time']):
                 sample = df['open_time'].iloc[0] if len(df) > 0 else 0
                 unit = 'ms' if sample > 1e11 else 's'
                 df['timestamp'] = pd.to_datetime(df['open_time'], unit=unit)
            else:
                 df['timestamp'] = df['open_time']
        elif 'timestamp' in df.columns:
             if pd.api.types.is_numeric_dtype(df['timestamp']):
                 sample = df['timestamp'].iloc[0] if len(df) > 0 else 0
                 unit = 'ms' if sample > 1e11 else 's'
                 df['timestamp'] = pd.to_datetime(df['timestamp'], unit=unit)
             else:
                 df['timestamp'] = pd.to_datetime(df['timestamp'])
        else:
             df['timestamp'] = pd.to_datetime(df.index)

        df = df.sort_values('timestamp').reset_index(drop=True)
        if len(df) < 500: continue
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 1. Total Visits (Entries)
        # Condition: RSI crosses BELOW threshold
        # We use a broader check: RSI < thresh AND RSI_shift > thresh to count "events"
        visits_mask = (df['rsi'] < threshold) & (df['rsi'].shift(1) >= threshold)
        visit_indices = df.index[visits_mask]
        
        total_visits = len(visit_indices)
        if total_visits == 0: continue
        
        # 2. Check Outcomes for each visit
        # Success = >10% gain within 24h
        success_count = 0
        
        high = df['high'].values
        close = df['close'].values
        n = len(df)
        lookahead = 96 # 24h
        
        for idx in visit_indices:
            if idx >= n - lookahead: continue
            
            entry_price = close[idx]
            window_high = np.max(high[idx+1 : idx+1+lookahead])
            max_gain = (window_high - entry_price) / entry_price
            
            if max_gain >= 0.10:
                success_count += 1
                
        win_rate = (success_count / total_visits) * 100
        
        results.append({
            'Coin': symbol,
            'Trigger_RSI': threshold,
            'Total_Signals': total_visits,
            'Rallies_Found': success_count,
            'Win_Rate_Pct': win_rate
        })

    # Report
    df_res = pd.DataFrame(results).sort_values('Win_Rate_Pct', ascending=False)
    
    print(f"\n📊 PRECISION REPORT (>10% Gain vs Total Visits)")
    print("-" * 80)
    print(df_res.to_string(index=False, float_format="%.1f"))
    print("-" * 80)
    
    avg_win = df_res['Win_Rate_Pct'].mean()
    print(f"\n💡 Global Insight: On average, buying at 'Sweet Spot' yields a >10% rally {avg_win:.1f}% of the time.")
    print("    (This is the raw probability without any other confirmation like Volume or Trend.)")

if __name__ == "__main__":
    validate_dna_precision()
