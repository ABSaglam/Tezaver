
import sys
import os
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from db_helper import get_rallies, TRAIN_CUTOFF

# ==========================================
# 1. SEMANTIC TRANSLATION (The 5 Dimensions)
# ==========================================

def get_time_phase(rsi, rsi_slope):
    # Boyut 1: ZAMANSAL HİS (FAZ)
    if rsi < 40: return "EARLY" # Dip, henüz ucuz
    if rsi > 70: return "LATE"  # Çok şişmiş
    if rsi_slope > 1: return "RISING" # İvmeleniyor
    if rsi_slope < -1: return "FALLING"
    return "MATURE" # Ortada ve sakin

def get_tension_state(atr_score, vol_trend):
    # Boyut 2: GERİLİM (BİRİKİM)
    # atr_score: Low means squeeze
    # vol_trend: Rising volume means accumulating pressure
    if atr_score < 1.0:
        if vol_trend > 0: return "READY_TO_BURST" # Sıkışık + Hacim artıyor
        return "COMPRESSED" # Sadece sıkışık
    if atr_score > 2.0: return "RELEASED" # Genişlemiş
    return "NEUTRAL"

def get_harmony_state(d_trend, h4_trend):
    # Boyut 3: AHENK (UYUM)
    # Are Daily and H4 aligned?
    if d_trend > 0 and h4_trend > 0: return "ALIGNED_BULL"
    if d_trend < 0 and h4_trend < 0: return "ALIGNED_BEAR"
    return "CONFLICT"

def get_rhythm_state(vol_cv):
    # Boyut 4: RİTİM
    # Low CV = Steady Rhythm
    if vol_cv < 0.5: return "STEADY"
    if vol_cv > 1.0: return "ERRATIC"
    return "DYNAMIC"

def get_context_state(w_rsi):
    # Boyut 5: BAĞLAM (HAFIZA)
    if w_rsi < 40: return "OVERSOLD_ZONE"
    if w_rsi > 70: return "OVERBOUGHT_ZONE"
    return "mid_zone" # Lowercase to ignore if needed

def calc_indicators(df):
    # RSI & Slope
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi_slope'] = df['rsi'].diff(3)
    
    # Trends (EMA)
    ema21 = df['close'].ewm(span=21).mean()
    ema50 = df['close'].ewm(span=50).mean()
    df['trend_score'] = (ema21 / ema50 - 1) * 100
    
    # Volume Stats
    df['vol_trend'] = df['volume'].diff(3) # Short term vol change
    df['vol_cv'] = df['volume'].rolling(12).std() / df['volume'].rolling(12).mean()
    
    # ATR Squeeze
    df['tr'] = np.maximum(df['high'] - df['low'], abs(df['close'].shift(1) - df['close']))
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_ratio'] = df['atr'] / df['close'] * 100
    df['atr_min'] = df['atr_ratio'].rolling(50).min()
    df['atr_score'] = df['atr_ratio'] / df['atr_min']
    
    return df

def main():
    symbol = 'ALGOUSDT'
    print(f"🧭 MASTER JOURNEY FRAMEWORK: {symbol}")
    print("="*70)
    
    # 1. LOAD DATA (H4 Base)
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    if not os.path.exists(h4_path):
        print("❌ Data not found")
        return

    df_h4 = pd.read_parquet(h4_path)
    df_h4 = df_h4.sort_values('timestamp').reset_index(drop=True)
    df_h4['datetime'] = pd.to_datetime(df_h4['timestamp'], unit='ms')
    df_h4 = df_h4[df_h4['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # 2. MULTI-TIMEFRAME CALCS
    # H4 Indicators
    df_h4 = calc_indicators(df_h4)
    # Rename for clarity
    df_h4['h4_trend'] = df_h4['trend_score']
    
    # Daily Indicators (Resampled)
    df_d = df_h4.set_index('datetime').resample('1D').agg({'close': 'last'})
    ema21_d = df_d['close'].ewm(span=21).mean()
    ema50_d = df_d['close'].ewm(span=50).mean()
    df_d['d_trend'] = (ema21_d / ema50_d - 1) * 100
    # Map back
    df_d_re = df_d.reindex(df_h4['datetime'], method='ffill')
    df_h4['d_trend'] = df_d_re['d_trend'].values
    
    # Weekly Indicators (Resampled)
    df_w = df_h4.set_index('datetime').resample('1W').agg({'close': 'last'})
    # Calc W_RSI
    delta_w = df_w['close'].diff()
    gain_w = (delta_w.where(delta_w > 0, 0)).rolling(14).mean()
    loss_w = (-delta_w.where(delta_w < 0, 0)).rolling(14).mean()
    rs_w = gain_w / loss_w
    df_w['w_rsi'] = 100 - (100 / (1 + rs_w))
    # Map back
    df_w_re = df_w.reindex(df_h4['datetime'], method='ffill')
    df_h4['w_rsi'] = df_w_re['w_rsi'].values
    
    # 3. SEMANTIC PROFILING (Creating the 'Soul')
    # unique profile string for every candle
    df_h4['profile'] = df_h4.apply(lambda row: 
        f"FAZ:{get_time_phase(row['rsi'], row['rsi_slope'])}|" +
        f"BIR:{get_tension_state(row['atr_score'], row['vol_trend'])}|" +
        f"AHNK:{get_harmony_state(row['d_trend'], row['h4_trend'])}|" +
        f"RITM:{get_rhythm_state(row['vol_cv'])}|" +
        f"CTX:{get_context_state(row['w_rsi'])}", axis=1
    )
    
    # 4. JOURNEY MEMORY (The Truth)
    # Identify Profile Families present on Rally Days (and T-1, T-3...)
    # For strictness, let's look at "Day Before" and "Day Of"
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    rally_dates = set(rally_results.keys())
    
    # Expand rally definition to "Journey" (T-1 to T+0)
    journey_dates = set()
    for d in rally_dates:
        journey_dates.add(d)
        journey_dates.add(d - pd.Timedelta(days=1))
        
    # We scan at Midnight (00:00)
    midnight = df_h4[df_h4['datetime'].dt.hour == 0].copy().reset_index(drop=True)
    midnight['is_journey'] = midnight['datetime'].dt.date.isin(journey_dates)
    
    print(f"Total Midnight Cycles: {len(midnight)}")
    print(f"Journey Days (Rally Context): {midnight['is_journey'].sum()}")
    
    # 5. ELIMINATION & EVOLUTION
    # Collect all profiles that appeared in a Journey
    candidate_profiles = midnight[midnight['is_journey']]['profile'].unique()
    print(f"Candidate Profiles found: {len(candidate_profiles)}")
    
    survivors = []
    
    for prof in candidate_profiles:
        # Check this profile's ENTIRE history
        mask = midnight['profile'] == prof
        total_occurrences = midnight[mask]
        
        # Law of Elimination: If it EVER appeared on a non-journey day, it is fake.
        failures = total_occurrences[~total_occurrences['is_journey']]
        
        if len(failures) == 0:
            # PURE PROFILE
            survivors.append({
                'profile': prof,
                'hits': len(total_occurrences), # All occurrences are journeys
                'matches': total_occurrences # Store for tier check
            })
            
    # 6. REPORT
    print("\n" + "="*70)
    print("🗝️ SURVIVING JOURNEY PROFILES (LOCK-STATES)")
    print("="*70)
    
    if not survivors:
        print("❌ NO SURVIVORS. Every profile has been tainted.")
        print("   (The resolution of 5 dimensions might be too low/high, or market is chaotic)")
    else:
        total_open_days = 0
        tier_stats = {'DIAMOND':0, 'GOLD':0, 'SILVER':0}
        
        for s in survivors:
            print(f"💎 {s['profile']}")
            print(f"   Active Days: {s['hits']} | Precision: 100%")
            total_open_days += s['hits']
            
            # Check Tiers
            for _, row in s['matches'].iterrows():
                # We need to map back to the SPECIFIC rally it belongs to
                d = row['datetime'].date()
                # Use nearest forward rally date
                # Simplified: Check exact date match or D+1
                found = False
                if d in rally_results:
                     tier_stats[rally_results[d][0]] += 1
                     print(f"   -> {d} ({rally_results[d][0]})")
                     found = True
                else:
                    # Check next day
                    d_next = d + pd.Timedelta(days=1)
                    if d_next in rally_results:
                        tier_stats[rally_results[d_next][0]] += 1
                        print(f"   -> {d} (Prep for {d_next} {rally_results[d_next][0]})")
                        found = True
            print("-" * 40)
            
        print("\n📝 FINAL REPORT")
        print(f"1. Anahtarın açıldığı TOPLAM GÜN: {total_open_days}")
        print(f"2. Sonuçlar: {tier_stats}")
        print("3. “Bu anahtar, geçmiş veride ralli olmayan hiçbir günü geçirmedi.”")

if __name__ == "__main__":
    main()
