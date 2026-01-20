
import sys
import os
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from db_helper import get_rallies, TRAIN_CUTOFF

# ==========================================
# 1. SEMANTIC TRANSLATION (The 'Reading' Layer)
# ==========================================

def get_rsi_state(val):
    if val < 30: return "OVERSOLD"
    if val < 45: return "WEAK"
    if val < 55: return "NEUTRAL"
    if val < 70: return "STRONG"
    return "OVERBOUGHT"

def get_trend_state(val):
    if val < -5: return "BEAR"
    if val < 5:  return "FLAT"
    if val < 15: return "BULL"
    return "ROCKET"

def get_vol_state(val):
    if val < 0.8: return "DEAD"
    if val < 1.5: return "QUIET"
    if val < 3.0: return "ACTIVE"
    return "CHAOS"

def get_tension_state(atr_val, close_val):
    # Simplified relative ATR
    ratio = atr_val / close_val * 100
    if ratio < 1.0: return "SQUEEZE" # Very tight
    if ratio < 3.0: return "NORMAL"
    return "LOOSE"

def calc_indicators(df):
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Trend (EMA 21/50 Dist)
    ema21 = df['close'].ewm(span=21).mean()
    ema50 = df['close'].ewm(span=50).mean()
    df['trend_score'] = (ema21 / ema50 - 1) * 100
    
    # Volume Ratio
    df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    
    # Tension (ATR)
    df['tr'] = np.maximum(df['high'] - df['low'], abs(df['close'].shift(1) - df['close']))
    df['atr'] = df['tr'].rolling(14).mean()
    
    return df

def main():
    symbol = 'ALPACAUSDT'
    print(f"⚖️ THE LAW OF ELIMINATION: {symbol}")
    print("="*70)
    
    # 1. LOAD DATA
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    if not os.path.exists(h4_path):
        print("❌ 4H Data not found")
        return

    df = pd.read_parquet(h4_path)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # 2. CALCULATE METRICS (Instruments)
    df = calc_indicators(df)
    
    # Add Higher Timeframe Context
    # (Simplified: We just sample daily context via 4H aggregations for now to keep 'Profile' clean)
    # Ideally we'd merge D/W but let's start with a rich 4H profile which dictates the 'Moment'.
    
    # 3. GENERATE JOURNEY PROFILES (The DNA)
    # We create a 'Signature' string for every candle.
    
    df['profile'] = df.apply(lambda row: 
        f"RSI:{get_rsi_state(row['rsi'])}|" +
        f"TRD:{get_trend_state(row['trend_score'])}|" +
        f"VOL:{get_vol_state(row['vol_ratio'])}|" +
        f"TEN:{get_tension_state(row['atr'], row['close'])}", axis=1
    )
    
    # 4. DEFINE TARGETS (The History)
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    rally_dates = set(rally_results.keys())
    
    # We check at Midnight (00:00)
    # Identify Midnight Candles
    midnight = df[df['datetime'].dt.hour == 0].copy().reset_index(drop=True)
    midnight['is_rally'] = midnight['datetime'].dt.date.isin(rally_dates)
    
    print(f"Total Cycles: {len(midnight)}")
    print(f"Total Rallies: {midnight['is_rally'].sum()}")
    
    # 5. THE LEARNING (Memorize Success)
    # Collect all profiles that appeared on Rally Days
    success_profiles = midnight[midnight['is_rally']]['profile'].unique()
    print(f"Candidate Families (Success Stories): {len(success_profiles)}")
    
    # 6. THE PURGE (Law 7)
    # Check if these profiles EVER appeared on a Non-Rally day.
    
    survivors = []
    
    for prof in success_profiles:
        # Get all days with this profile
        occurrences = midnight[midnight['profile'] == prof]
        total_days = len(occurrences)
        rally_days = occurrences['is_rally'].sum()
        fail_days = total_days - rally_days
        
        # ELIMINATION LOGIC
        if fail_days == 0:
            # PURE PROFILE
            survivors.append({
                'profile': prof,
                'hits': rally_days,
                'precision': 100.0
            })
        else:
            # TAINTED PROFILE - ELIMINATED
            pass
            
    # 7. REPORT SURVIVORS
    print("\n" + "="*70)
    print("🛡️ SURVIVING PROFILES (THE LOCK-STATES)")
    print("="*70)
    
    if not survivors:
        print("❌ NO SURVIVORS. Every profile has been tainted by at least one failure.")
        print("   (This means the resolution is too low, or the market is chaotic at this level.)")
    else:
        for s in survivors:
            print(f"💎 {s['profile']}")
            print(f"   Hits: {s['hits']} | Precision: 100%")
            # Identify which rallies
            matches = midnight[(midnight['profile'] == s['profile']) & (midnight['is_rally'])]
            for _, r in matches.iterrows():
                d = r['datetime'].date()
                tier = rally_results[d][0]
                print(f"   -> {d} ({tier})")
            print("-" * 40)

if __name__ == "__main__":
    main()
