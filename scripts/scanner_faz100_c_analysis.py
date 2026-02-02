import os
import glob
import pandas as pd
import numpy as np
import json
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

# FAZ-100 C-SERIES DEEP ANALYSIS TOOL
# Focus: C++, C+, C Class Analysis (Fake Rate & Tier Distribution)

# Configuration
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = "2026-01-01"
END_DATE = "2026-01-31"
KEYS_FILE = "/Users/alisaglam/TezaverMac/data/faz100_dna_keys_SEALED.json"
REPORT_FILE = "/Users/alisaglam/TezaverMac/FAZ100_C_SERIES_ANALYSIS.md"
REPORT_MIN_WR = 0.0 # Analyze ALL logic

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_dna_signature(row, vol_ma):
    rsi = row['rsi']
    if rsi <= 35: faz = "derin_dip"
    elif rsi <= 45: faz = "birikim_fazi"
    elif rsi <= 55: faz = "notr_alan"
    elif rsi <= 65: faz = "momentum_artisi"
    elif rsi <= 75: faz = "guclu_trend"
    else: faz = "asiri_alim"
    
    sq_pct = abs(row['ema9'] - row['ema21']) / row['close'] * 100
    if sq_pct <= 0.3: acc = "tight_squeeze"
    elif sq_pct <= 0.8: acc = "micro_squeeze"
    elif sq_pct <= 1.5: acc = "normal_gap"
    else: acc = "expanded_gap"
    
    harm = "harmony_L1" 
    if row['close'] > row['ema21']: harm = "harmony_L2"
    
    # DNA function in blind script passed row, but vol_ma was column. 
    # Let's rely on row access inside or passed arg. 
    # In blind script: get_dna_signature(row) and uses row['vol_ma']
    # Checking blind script... yes row['vol_ma'] exists.
    
    if row['volume'] > row['vol_ma'] * 2.5: ritim = "volume_explosion"
    elif row['volume'] > row['vol_ma'] * 1.5: ritim = "volume_surge"
    elif row['volume'] > row['vol_ma'] * 0.8: ritim = "volume_normal"
    else: ritim = "volume_dry"
    
    ctx = "mid_range"
    enerji = "stable_energy"
    
    return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"

def get_tier(p_49_val):
    if p_49_val >= 30: return "DIAMOND"
    if p_49_val >= 20: return "GOLD"
    if p_49_val >= 10: return "SILVER"
    if p_49_val >= 5: return "BRONZE"
    return "NOTIER"

def run_c_analysis():
    print(f"🦅 STARTING FAZ-100 C-SERIES ANALYSIS (2026)")
    
    try:
        with open(KEYS_FILE, 'r') as f:
            valid_keys = json.load(f)
    except FileNotFoundError:
        print("❌ SEALED Key file not found!")
        return

    files = sorted(glob.glob(f"{COIN_CELLS_DIR}/*/data/history_15m.parquet"))
    
    # Stats Container
    stats = {
        "C++": {"total":0, "fake":0, "confirmed":0, "diamond":0, "gold":0, "silver":0, "bronze":0, "notier":0},
        "C+":  {"total":0, "fake":0, "confirmed":0, "diamond":0, "gold":0, "silver":0, "bronze":0, "notier":0},
        "C":   {"total":0, "fake":0, "confirmed":0, "diamond":0, "gold":0, "silver":0, "bronze":0, "notier":0}
    }
    
    for filepath in files:
        symbol = filepath.split("/")[-3]
        if symbol not in valid_keys: continue
        coin_keys = valid_keys[symbol]
        
        try:
            df = pd.read_parquet(filepath)
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime').sort_index()
            
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
            df['ema233'] = df['close'].ewm(span=233, adjust=False).mean()
            df['vol_ma'] = df['volume'].rolling(21).mean()
            df['rsi'] = calculate_rsi(df['close'], 14)
            df['rsi_ema'] = df['rsi'].ewm(span=21).mean()
            
            test_df = df[(df.index >= START_DATE) & (df.index <= END_DATE)].copy()
            test_df['trigger'] = (test_df['rsi'] > test_df['rsi_ema']) & (test_df['rsi'].shift(1) <= test_df['rsi_ema'].shift(1))
            triggered = test_df[test_df['trigger'] == True]
            
            for idx, row in triggered.iterrows():
                # DNA Check
                dna = get_dna_signature(row, 0) # Argument unused in sub-func but signature requires row logic
                if dna not in coin_keys: continue
                
                # Physical Check
                if row['close'] < row['ema233']: continue
                if row['ema9'] < row['ema21']: continue
                if row['volume'] < row['vol_ma'] * 1.3: continue
                
                prev_ema = test_df.loc[:idx].iloc[-2]['ema21'] if len(test_df.loc[:idx]) > 1 else row['ema21']
                angle = (row['ema21'] - prev_ema) / row['close'] * 1000
                if angle < 0: continue

                # Metrics
                next_49 = df.loc[idx:].iloc[1:50] 
                if not next_49.empty:
                    t_plus_1_open = next_49.iloc[0]['open']
                    max_high = next_49['high'].max()
                    p_49_val = ((max_high - t_plus_1_open) / t_plus_1_open) * 100
                    
                    vol_4_avg = next_49['volume'].iloc[:4].mean()
                    vol_4_score = vol_4_avg / row['vol_ma'] if row['vol_ma'] > 0 else 0
                else:
                    p_49_val = 0
                    vol_4_score = 0
                
                vboy_val = row['volume'] / row['vol_ma'] if row['vol_ma'] > 0 else 1.0

                # Classification
                dna_meta = valid_keys[symbol][dna]
                elite_success_count = dna_meta.get('BRONZE', 0) + dna_meta.get('SILVER', 0) + \
                                     dna_meta.get('GOLD', 0) + dna_meta.get('DIAMOND', 0)
                elite_win_rate = (elite_success_count / dna_meta['TOTAL'] * 100) if dna_meta['TOTAL'] > 0 else 0
                
                klasman = "OUT"
                # Same V22 logic for C-Series
                if angle >= 3.0 and row['rsi'] >= 45.0 and vboy_val >= 1.1 and elite_win_rate >= 75.0:
                    klasman = "C++"
                elif angle >= 2.0 and row['rsi'] >= 40.0 and vboy_val >= 1.0 and elite_win_rate >= 72.0:
                    klasman = "C+"
                elif angle >= 0.0 and elite_win_rate >= 70.0:
                    klasman = "C"

                if klasman not in stats: continue # Skip A/B series
                
                # Confirmation Check
                is_confirmed = "WAIT"
                if vol_4_score >= 1.5: is_confirmed = "CONFIRMED"
                elif vol_4_score >= 1.0: is_confirmed = "WEAK" # Technically confirmed but weak
                else: is_confirmed = "FAKE"
                
                current_tier = get_tier(p_49_val)
                
                # Update Stats
                stats[klasman]['total'] += 1
                if is_confirmed == "FAKE": 
                    stats[klasman]['fake'] += 1
                else:
                    stats[klasman]['confirmed'] += 1
                    # Tier stats only for non-fakes? Or all? User asked "C... serilerinin fake ve tier olarak analiz".
                    # Let's count tiers for FAKES vs CONFIRMED separately?
                    # For simplicity, let's just count ALL tiers to see if FAKEs yield success, 
                    # BUT usually we care about "If I entered, what would happen?" and we filter fakes.
                    # Let's count tiers for the TOTAL population to see the "Garbage Ratio".
                    stats[klasman][current_tier.lower()] += 1
                        
        except Exception as e:
            # print(f"Error {symbol}: {e}")
            pass

    # Report Generation
    with open(REPORT_FILE, 'w') as f:
        f.write("# FAZ-100 C-SERIES DEEP ANALYSIS (V22 LOGIC)\n\n")
        f.write("| CLASS | TOTAL | FAKE (Vol-4<1.0) | FAKE % | DIAMOND | GOLD | SILVER | BRONZE | NOTIER | SUCCESS % |\n")
        f.write("|-------|-------|------------------|--------|---------|------|--------|--------|--------|-----------|\n")
        
        for k in ["C++", "C+", "C"]:
            s = stats[k]
            total = s['total']
            if total == 0: continue
            
            fake_pct = (s['fake'] / total) * 100
            
            success_count = s['diamond'] + s['gold'] + s['silver'] + s['bronze']
            success_pct = (success_count / total) * 100
            
            f.write(f"| **{k}** | {total} | {s['fake']} | {fake_pct:.1f}% | {s['diamond']} | {s['gold']} | {s['silver']} | {s['bronze']} | {s['notier']} | **{success_pct:.1f}%** |\n")
            
        f.write("\n## INTELLIGENCE SUMMARY\n")
        f.write("- **FAKE FILTER:** Vol-4 < 1.0 olan sinyaller 'FAKE' kabul edilmiştir.\n")
        f.write("- **SUCCESS:** P-49 >= %5 (Bronze ve üzeri) kazanç sağlayanlar.\n")

if __name__ == "__main__": run_c_analysis()
