import os
import sys
import pandas as pd
import numpy as np
import json
from datetime import datetime
import glob
import warnings
warnings.filterwarnings('ignore')

# Configuration
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = "2023-01-01"
END_DATE = "2025-12-31"

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_tier(max_gain):
    if max_gain >= 10: return "DIAMOND"
    if max_gain >= 5: return "GOLD"
    if max_gain >= 3: return "SILVER"
    if max_gain >= 1: return "BRONZE"
    return "NOTIER"

def get_dna_signature(row):
    # Extract Raw DNA components from the row
    # DNA Format: faz|acc|harm|ritim|ctx|enerji
    
    # 1. Faz (RSI Region & Trend)
    rsi = row['rsi']
    if rsi <= 35: faz = "derin_dip"
    elif rsi <= 45: faz = "birikim_fazi"
    elif rsi <= 55: faz = "notr_alan"
    elif rsi <= 65: faz = "momentum_artisi"
    elif rsi <= 75: faz = "guclu_trend"
    else: faz = "asiri_alim"
    
    # 2. Acc (Ribbon Squeeze) - Using ema9/ema21 proxy
    sq_pct = abs(row['ema9'] - row['ema21']) / row['close'] * 100
    if sq_pct <= 0.3: acc = "tight_squeeze"
    elif sq_pct <= 0.8: acc = "micro_squeeze"
    elif sq_pct <= 1.5: acc = "normal_gap"
    else: acc = "expanded_gap"
    
    # 3. Harm (Trend Harmony) - Simplified (using single ema21 check as proxy for now)
    harm = "harmony_L1" # Default proxy
    if row['close'] > row['ema21']: harm = "harmony_L2"
    
    # 4. Ritim (Volume Spike)
    if row['volume'] > row['vol_ma'] * 2.5: ritim = "volume_explosion"
    elif row['volume'] > row['vol_ma'] * 1.5: ritim = "volume_surge"
    elif row['volume'] > row['vol_ma'] * 0.8: ritim = "volume_normal"
    else: ritim = "volume_dry"
    
    # 5. Ctx (ATH dist) - Proxy
    # Need high/low history, approximating "mid_range"
    ctx = "mid_range"
    
    # 6. Enerji
    enerji = "stable_energy"
    
    return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"

def process_coin_pure_dna(filepath):
    try:
        symbol = filepath.split("/")[-3]
        df = pd.read_parquet(filepath)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime').sort_index()
        
        # Filter Date Range (2023-2025)
        df = df[(df.index >= START_DATE) & (df.index <= END_DATE)]
        if df.empty: return None

        # Feature Gen
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema233'] = df['close'].ewm(span=233, adjust=False).mean() # For strategy filter
        df['vol_ma'] = df['volume'].rolling(21).mean()
        df['rsi'] = calculate_rsi(df['close'], 14)
        
        # Determine Rallies (Truth Labeling)
        indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=96) # 24h
        df['future_max'] = df['high'].rolling(window=indexer).max()
        df['max_gain'] = ((df['future_max'] - df['close']) / df['close']) * 100
        df['tier'] = df['max_gain'].apply(get_tier)
        
        # Base Trigger: RSI Cross EMA (The moment we check DNA)
        df['rsi_ema'] = df['rsi'].ewm(span=21).mean()
        df['signal'] = (df['rsi'] > df['rsi_ema']) & (df['rsi'].shift(1) <= df['rsi_ema'].shift(1))
        
        signals = df[df['signal'] == True].copy()
        if len(signals) == 0: return None
        
        # DNA Extraction
        signals['dna'] = signals.apply(get_dna_signature, axis=1)
        
        # Group by DNA and analyze performance across Tiers
        dna_stats = signals.groupby('dna')['tier'].value_counts().unstack(fill_value=0)
        
        # Ensure all columns exist
        for col in ['DIAMOND', 'GOLD', 'SILVER', 'BRONZE', 'NOTIER']:
            if col not in dna_stats.columns: dna_stats[col] = 0
            
        dna_stats['TOTAL'] = dna_stats.sum(axis=1)
        dna_stats['SUCCESS'] = dna_stats['DIAMOND'] + dna_stats['GOLD'] + dna_stats['SILVER'] + dna_stats['BRONZE']
        dna_stats['FAIL'] = dna_stats['NOTIER']
        dna_stats['WIN_RATE'] = (dna_stats['SUCCESS'] / dna_stats['TOTAL']) * 100
        
        # Identify "Golden DNA" candidates (DNA patterns with high success)
        # Criteria: Min 3 occurrences, Min 70% Win Rate OR Any Diamond Presence
        golden_dnas = dna_stats[
            ((dna_stats['TOTAL'] >= 3) & (dna_stats['WIN_RATE'] >= 70)) | 
            (dna_stats['DIAMOND'] > 0) # Diamond DNA is always valuable
        ]
        
        # Save Golden DNAs to JSON
        os.makedirs("data/faz100_keys_temp", exist_ok=True)
        if not golden_dnas.empty:
            keys_export = golden_dnas.to_dict(orient='index')
            with open(f"data/faz100_keys_temp/{symbol}_keys.json", 'w') as f:
                json.dump(keys_export, f, indent=2)
        
        # --- YELLOW / GREEN SIMULATION ---
        yellow_wr, yellow_signals, yellow_loss = 0, 0, 0
        green_wr, green_signals, green_loss = 0, 0, 0

        # Load Rules (Needs global vars or reloading, simplistic here)
        try:
            with open("/Users/alisaglam/TezaverMac/data/dna_mujde_rules.json", 'r') as f: y_rules = json.load(f)
            with open("/Users/alisaglam/TezaverMac/data/dna_mujde_rules_green_v3.json", 'r') as f: g_rules = json.load(f)
            
            y_rule = y_rules.get(symbol, {})
            g_rule = g_rules.get(symbol, {})
            
            # Helper to apply rule
            def apply_rule(df, rule):
                if not rule: return 0, 0, 0
                mask = pd.Series(True, index=df.index)
                if rule.get('trend_filter'): mask &= (df['close'] > df['ema233'])
                if rule.get('vol_filter'): mask &= (df['volume'] > df['vol_ma'] * 1.5) # Approx
                # Adx filter requires accurate ADX calc, skipping for simplicity/speed or assuming pass
                if rule.get('val_filter'): mask &= (df['rsi'] < 50)
                
                filtered = df[mask]
                if len(filtered) == 0: return 0, 0, 0
                
                tiers = filtered['tier'].value_counts()
                success = tiers.get('DIAMOND',0) + tiers.get('GOLD',0) + tiers.get('SILVER',0) + tiers.get('BRONZE',0)
                total = len(filtered)
                wr = (success/total)*100
                
                total_diamonds = len(df[df['tier'] == 'DIAMOND'])
                caught_diamonds = tiers.get('DIAMOND', 0)
                loss = total_diamonds - caught_diamonds
                return wr, total, loss

            yellow_wr, yellow_signals, yellow_loss = apply_rule(signals, y_rule)
            green_wr, green_signals, green_loss = apply_rule(signals, g_rule)
        except: pass
        
        return {
            'symbol': symbol,
            'total_signals': len(signals),
            'unique_dna_patterns': len(dna_stats),
            'golden_dna_patterns': len(golden_dnas),
            'diamond_dna_count': len(golden_dnas[golden_dnas['DIAMOND'] > 0]),
            'top_dna': golden_dnas.sort_values('WIN_RATE', ascending=False).head(5).to_dict(orient='index'),
            'y_stats': {'wr': yellow_wr, 'sig': yellow_signals, 'loss': yellow_loss},
            'g_stats': {'wr': green_wr, 'sig': green_signals, 'loss': green_loss}
        }

    except Exception as e:
        return {'symbol': symbol, 'error': str(e)}

def generate_report_pure(batch_results, letter):
    filename = f"PURE_DNA_REPORT_{letter}.md"
    
    with open(filename, 'w') as f:
        f.write(f"# 🧬 PURE DNA vs FILTERED COMPARISON (2023-2025): Letter {letter}\n")
        f.write(f"Generated: {datetime.now()}\n\n")
        f.write("| Coin | 🧬 SAF DNA (Stratejisiz) | | | 🟡 SARI LİSTE (Mevcut) | | | 🟢 YEŞİL LİSTE (Mevcut) | | |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        f.write("| **Sembol** | **En İyi DNA WR** | **Sinyal** | **💎 Elmas** | **WR** | **Sinyal** | **Kayıp** | **WR** | **Sinyal** | **Kayıp** |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        
        for res in batch_results:
            if 'error' in res:
                f.write(f"| {res['symbol']} | ERROR: {res['error']} | - | - | - | - | - | - | - | - |\n")
                continue
            
            top_wr = "-"
            pure_note = "-"
            pure_wr = "-"
            pure_sig = 0
            pure_diamond = 0
            
            if res['top_dna']:
                dna_key = list(res['top_dna'].keys())[0]
                vals = res['top_dna'][dna_key]
                pure_wr = f"%{vals['WIN_RATE']:.1f}"
                pure_sig = vals['TOTAL']
                pure_diamond = vals['DIAMOND']
            else:
                pure_wr = "%0.0"
            
            # Yellow/Green
            y = res.get('y_stats', {'wr':0, 'sig':0, 'loss':0})
            g = res.get('g_stats', {'wr':0, 'sig':0, 'loss':0})
            
            y_wr = f"%{y['wr']:.1f}" if y['sig'] > 0 else "-"
            g_wr = f"%{g['wr']:.1f}" if g['sig'] > 0 else "-"
            
            f.write(f"| **{res['symbol']}** | {pure_wr} | {pure_sig} | 💎{pure_diamond} | {y_wr} | {y['sig']} | 🔻{y['loss']} | {g_wr} | {g['sig']} | 🔻{g['loss']} |\n")

    print(f"✅ Report saved: {filename}")

def main():
    print("🚀 STARTING PURE DNA EXTRACTION (2023-2025)")
    files = sorted(glob.glob(f"{COIN_CELLS_DIR}/*/data/history_15m.parquet"))
    
    current_letter = None
    batch_results = []
    
    for filepath in files:
        symbol = filepath.split("/")[-3]
        letter = symbol[0].upper()
        if not letter.isalpha(): letter = "#"
        
        if current_letter != letter:
            if batch_results:
                generate_report_pure(batch_results, current_letter)
                batch_results = []
            current_letter = letter
            print(f"👉 Processing Letter: {current_letter}...")
            
        res = process_coin_pure_dna(filepath)
        if res:
            batch_results.append(res)
            
    if batch_results:
        generate_report_pure(batch_results, current_letter)

if __name__ == "__main__":
    main()
