#!/usr/bin/env python3
"""
TEZAVER STANDARD SCANNER v1.0
=============================
TEK KAYNAK DOĞRULUĞU (Single Source of Truth)

KURALLAR:
---------
1. AYAŞ TÜNELİ: 00:00'da Golden DNA'ya sahip coinler
   - Veri: target_date ÖNCESİ (strict_before=True)
   - Yani 1 Ocak için: 31 Aralık 23:59:59 ve öncesi veriler

2. AYSENTİ GEÇİDİ: Gün sonunda Golden olan AMA Ayaş'ta olmayan coinler
   - Veri: target_date DAHİL (strict_before=False)
   - Yani 1 Ocak için: 1 Ocak 23:59:59 dahil veriler
   - Entry Time: İlk Golden olduğu saat (01:00-23:00 arası tarama)

GOLDEN DNA LİSTESİ:
- data/golden_keys/v5_golden_keys.json dosyasından okunur
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================
COIN_CELLS = "/Users/alisaglam/TezaverMac/coin_cells"
GOLDEN_KEYS_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys"
OUTPUT_REPORT = "/Users/alisaglam/TezaverMac/refined_global_report_v17.md"

START_DATE = pd.Timestamp("2026-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-01-28", tz="UTC")

# ============================================================================
# GOLDEN DNA LIST LOADER (Per-Coin)
# ============================================================================
def load_coin_golden_dna(symbol):
    """Load Golden DNA patterns for a specific coin"""
    key_path = os.path.join(GOLDEN_KEYS_DIR, f"{symbol}_key.json")
    if not os.path.exists(key_path):
        return set()
    try:
        with open(key_path, 'r') as f:
            return set(json.load(f).get('golden_dna_list', []))
    except:
        return set()

# ============================================================================
# DNA PROFILER (Simplified & Standardized)
# ============================================================================
def calculate_dna(day, df_w, df_h1, df_d, df_h4, strict_before=True):
    """
    Calculate DNA profile for a coin.
    
    strict_before=True: Use data BEFORE day (for Ayaş - 00:00 check)
    strict_before=False: Use data INCLUDING day (for Aysenti - EOD check)
    """
    try:
        # Apply time filter
        if strict_before:
            sub_w = df_w[df_w.index < day].tail(30)
            sub_d = df_d[df_d.index < day]
            sub_h4 = df_h4[df_h4.index < day]
            sub_h1 = df_h1[df_h1.index < day]
        else:
            sub_w = df_w[df_w.index <= day].tail(30)
            sub_d = df_d[df_d.index <= day]
            sub_h4 = df_h4[df_h4.index <= day]
            sub_h1 = df_h1[df_h1.index <= day]
        
        if sub_w.empty or sub_d.empty or sub_h1.empty or sub_h4.empty:
            return "neutral"
        
        # FAZ (RSI-based phase)
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        
        if rsi_val < 40:
            faz = "derin_dip"
        elif rsi_val < 60:
            faz = "birikim_fazi"
        elif rsi_val < 75:
            faz = "yukselis_fazi"
        else:
            faz = "asiri_alim"
        
        # ACC (EMA compression)
        sub_h1_24 = sub_h1.tail(24)
        if sub_h1_24.empty or 'ema9' not in sub_h1_24.columns:
            return "neutral"
        
        emas = sub_h1_24[['ema9', 'ema21', 'ema50']]
        comp = (emas.max(axis=1) / emas.min(axis=1) - 1) * 100
        min_comp = comp.min()
        
        if min_comp < 0.4:
            acc = "micro_squeeze"
        elif min_comp < 0.8:
            acc = "tight_squeeze"
        elif min_comp < 1.5:
            acc = "coiling"
        else:
            acc = "loose"
        
        # HARMONY
        if 'ema21' not in sub_d.columns or 'ema21' not in sub_h4.columns or 'ema21' not in sub_h1.columns:
            return "neutral"
        
        score = (
            int(sub_d.iloc[-1]['close'] > sub_d.iloc[-1]['ema21']) +
            int(sub_h4.iloc[-1]['close'] > sub_h4.iloc[-1]['ema21']) +
            int(sub_h1.iloc[-1]['close'] > sub_h1.iloc[-1]['ema21'])
        )
        harm = f"harmony_L{score}"
        
        # RHYTHM (Volume)
        vol_avg = sub_d.tail(10)['volume'].mean() + 1
        vol_ratio = sub_d.iloc[-1]['volume'] / vol_avg
        
        if vol_ratio > 2.0:
            ritim = "ignited"
        elif vol_ratio > 1.0:
            ritim = "active"
        else:
            ritim = "sleeping"
        
        # ENERGY
        vol_recent = sub_d.tail(3)['volume'].mean()
        vol_older = sub_d.tail(10).head(7)['volume'].mean()
        enerji = "building_energy" if vol_recent > vol_older else "depleting_energy"
        
        # CONTEXT
        if len(sub_d) > 0:
            yr_high = sub_d.tail(365)['high'].max()
            retr = (sub_d.iloc[-1]['close'] / yr_high - 1) * 100
        else:
            retr = 0
        
        if retr > -20:
            ctx = "recovery_high"
        elif retr < -50:
            ctx = "deep_valley"
        else:
            ctx = "mid_zone"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    
    except Exception as e:
        return "neutral"

# ============================================================================
# MAIN SCANNER
# ============================================================================
def run_standard_scan():
    print("=" * 60)
    print("TEZAVER STANDARD SCANNER v1.0")
    print("=" * 60)
    
    # Load all coin data + their golden DNA lists
    print("📦 VERİ YÜKLENİYOR...")
    all_data = {}
    
    for symbol in os.listdir(COIN_CELLS):
        sym_path = os.path.join(COIN_CELLS, symbol)
        if not os.path.isdir(sym_path):
            continue
        
        # Load golden DNA for this coin
        golden_dna = load_coin_golden_dna(symbol)
        if not golden_dna:  # Skip coins without golden key file
            continue
        
        try:
            data_path = os.path.join(sym_path, "data")
            df_1w = pd.read_parquet(os.path.join(data_path, "history_1w.parquet"))
            df_1h = pd.read_parquet(os.path.join(data_path, "history_1h.parquet"))
            df_1d = pd.read_parquet(os.path.join(data_path, "history_1d.parquet"))
            df_4h = pd.read_parquet(os.path.join(data_path, "history_4h.parquet"))
            df_15m = pd.read_parquet(os.path.join(data_path, "history_15m.parquet"))
            
            # Convert timestamp to datetime index
            for df in [df_1w, df_1h, df_1d, df_4h, df_15m]:
                if 'timestamp' in df.columns:
                    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df.set_index('dt', inplace=True)
                    df.index = df.index.tz_localize('UTC')
            
            all_data[symbol] = {
                '1w': df_1w, '1h': df_1h, '1d': df_1d, '4h': df_4h, '15m': df_15m,
                'golden_dna': golden_dna
            }
        except:
            continue
    
    print(f"✅ {len(all_data)} Coin Yüklendi (Golden Key dosyası olanlar).")
    
    # Scan each day
    all_results = []
    current_date = START_DATE
    
    while current_date <= END_DATE:
        print(f"📅 {current_date.strftime('%Y-%m-%d')} taranıyor...")
        
        ayas_count = 0
        aysenti_count = 0
        
        for symbol, data in all_data.items():
            df_1w = data['1w']
            df_1h = data['1h']
            df_1d = data['1d']
            df_4h = data['4h']
            df_15m = data['15m']
            golden_dna_set = data['golden_dna']  # Per-coin golden DNA
            
            # Date range check
            if df_1d.empty or current_date > df_1d.index[-1] + pd.Timedelta(days=2):
                continue
            
            # ========================================
            # AYAŞ TÜNELİ: 00:00'da Golden mi?
            # ========================================
            dna_ayas = calculate_dna(current_date, df_1w, df_1h, df_1d, df_4h, strict_before=True)
            # Exclude 'neutral' - it's not a valid Golden DNA
            is_ayas = (dna_ayas != "neutral") and (dna_ayas in golden_dna_set)
            
            # ========================================
            # AYSENTİ GEÇİDİ: Gün sonunda Golden mi? (ve Ayaş değil)
            # ========================================
            dna_aysenti = calculate_dna(current_date, df_1w, df_1h, df_1d, df_4h, strict_before=False)
            is_aysenti = (not is_ayas) and (dna_aysenti != "neutral") and (dna_aysenti in golden_dna_set)
            
            if is_ayas:
                ayas_count += 1
                source = "AYAS"
                dna = dna_ayas
                entry_time = "00:00"
            elif is_aysenti:
                aysenti_count += 1
                source = "AYSENTI"
                dna = dna_aysenti
                # Find entry time
                entry_time = "00:00"
                day_start = current_date.normalize()
                for hour in range(1, 24):
                    check_time = day_start + pd.Timedelta(hours=hour)
                    dna_check = calculate_dna(check_time, df_1w, df_1h, df_1d, df_4h, strict_before=False)
                    if dna_check in golden_dna_set:
                        entry_time = f"{hour:02d}:00"
                        break
            else:
                continue
            
            # Calculate daily performance
            day_start_utc = current_date.normalize()
            day_end_utc = day_start_utc + pd.Timedelta(days=1)
            df_day = df_15m[(df_15m.index >= day_start_utc) & (df_15m.index < day_end_utc)]
            
            if df_day.empty:
                continue
            
            open_p = df_day.iloc[0]['open']
            close_p = df_day.iloc[-1]['close']
            max_h = df_day['high'].max()
            
            peak_pct = ((max_h / open_p) - 1) * 100
            ret_pct = ((close_p / open_p) - 1) * 100
            
            all_results.append({
                'date': current_date,
                'symbol': symbol,
                'source': source,
                'dna': dna,
                'entry_time': entry_time,
                'peak': peak_pct,
                'ret': ret_pct
            })
        
        print(f"   Ayaş: {ayas_count}, Aysenti: {aysenti_count}")
        current_date += pd.Timedelta(days=1)
    
    # Generate simple summary report
    print("📝 RAPOR YAZILIYOR...")
    
    with open(OUTPUT_REPORT, 'w') as f:
        f.write("# TEZAVER STANDARD REPORT v1.0\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Group by date
        df_results = pd.DataFrame(all_results)
        
        if df_results.empty:
            f.write("No data found.\n")
        else:
            for d, grp in df_results.groupby('date'):
                ayas = grp[grp['source'] == 'AYAS']
                aysenti = grp[grp['source'] == 'AYSENTI']
                
                f.write(f"## 📅 {d.strftime('%d %B %Y')} (Ayaş: {len(ayas)}, Aysenti: {len(aysenti)})\n\n")
                
                if not ayas.empty:
                    f.write("### 🚇 AYAŞ TÜNELİ\n\n")
                    f.write("| SYM | ENTRY | MAX | CLOSE |\n")
                    f.write("|-----|-------|-----|-------|\n")
                    for _, r in ayas.sort_values('peak', ascending=False).iterrows():
                        f.write(f"| {r['symbol']} | {r['entry_time']} | +{r['peak']:.1f}% | {'+' if r['ret']>=0 else ''}{r['ret']:.1f}% |\n")
                    f.write("\n")
                
                if not aysenti.empty:
                    f.write("### 🌉 AYSENTİ GEÇİDİ\n\n")
                    f.write("| SYM | ENTRY | MAX | CLOSE |\n")
                    f.write("|-----|-------|-----|-------|\n")
                    for _, r in aysenti.sort_values('peak', ascending=False).iterrows():
                        f.write(f"| {r['symbol']} | {r['entry_time']} | +{r['peak']:.1f}% | {'+' if r['ret']>=0 else ''}{r['ret']:.1f}% |\n")
                    f.write("\n")
    
    print(f"✅ RAPOR TAMAMLANDI: {OUTPUT_REPORT}")

if __name__ == "__main__":
    run_standard_scan()
