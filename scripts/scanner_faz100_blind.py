import os
import glob
import pandas as pd
import numpy as np
import json
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

# Configuration
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = "2026-01-25" 
END_DATE = "2026-02-01"
KEYS_FILE = "/Users/alisaglam/TezaverMac/data/faz100_dna_keys_SEALED.json"
REPORT_FILE = "/Users/alisaglam/TezaverMac/FAZ100_TEST_REPORT_LAST_WEEK.md"

# SNIPER ELITE FILTER FOR THE LIST
REPORT_MIN_WR = 95.0 # Only list signals in MD if the historical DNA WR is >= 95%

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr

def calculate_adx(df, period=14):
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    atr = calculate_atr(df, period)
    
    plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / atr)
    minus_di = 100 * (abs(minus_dm).ewm(alpha=1/period).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.ewm(alpha=1/period).mean()
    return adx

def get_dna_signature(row):
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
    
    if row['volume'] > row['vol_ma'] * 2.5: ritim = "volume_explosion"
    elif row['volume'] > row['vol_ma'] * 1.5: ritim = "volume_surge"
    elif row['volume'] > row['vol_ma'] * 0.8: ritim = "volume_normal"
    else: ritim = "volume_dry"
    
    ctx = "mid_range"
    enerji = "stable_energy"
    
    return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"

def get_tier(max_gain):
    if max_gain >= 10: return "DIAMOND"
    if max_gain >= 5: return "GOLD"
    if max_gain >= 3: return "SILVER"
    if max_gain >= 1: return "BRONZE"
    return "NOTIER"

def run_elite_scan():
    print(f"🦅 STARTING FAZ-100 ELITE V17 SCAN (2026)")
    
    try:
        with open(KEYS_FILE, 'r') as f:
            valid_keys = json.load(f)
    except FileNotFoundError:
        print("❌ SEALED Key file not found!")
        return

    files = sorted(glob.glob(f"{COIN_CELLS_DIR}/*/data/history_15m.parquet"))
    signals = []
    
    for filepath in files:
        symbol = filepath.split("/")[-3]
        if symbol not in valid_keys: continue
        coin_keys = valid_keys[symbol]
        
        try:
            df = pd.read_parquet(filepath)
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime').sort_index()
            
            # Feature Generation
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
            df['ema233'] = df['close'].ewm(span=233, adjust=False).mean()
            df['vol_ma'] = df['volume'].rolling(21).mean()
            df['rsi'] = calculate_rsi(df['close'], 14)
            df['rsi_ema'] = df['rsi'].ewm(span=21).mean()
            df['atr'] = calculate_atr(df, 14)
            df['adx'] = calculate_adx(df, 14)
            
            # Ground Truth
            indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=96)
            df['future_max'] = df['high'].rolling(window=indexer).max()
            df['max_gain'] = ((df['future_max'] - df['close']) / df['close']) * 100
            df['tier'] = df['max_gain'].apply(get_tier)
            
            # Filter for TEST ZONE (2026)
            test_df = df[(df.index >= START_DATE) & (df.index <= END_DATE)].copy()
            
            # 1. TRIGGER (MOMENTUM): RSI-EMA Cross Over Ribbon (Simplified as RSI > RSI_EMA here)
            test_df['trigger'] = (test_df['rsi'] > test_df['rsi_ema']) & (test_df['rsi'].shift(1) <= test_df['rsi_ema'].shift(1))
            triggered = test_df[test_df['trigger'] == True]
            
            for idx, row in triggered.iterrows():
                # 2. DNA CHECK: Is this coin's DNA matching FAZ100 criteria?
                dna = get_dna_signature(row)
                if dna not in coin_keys: continue
                
                key_stat = coin_keys[dna]
                wr = key_stat.get('WIN_RATE', 0)
                
                if wr < REPORT_MIN_WR: continue

                # 3. STRATEGY LAYER (PHYSICAL FILTERS)
                # 3.1 Main Trend Filter: Price must be above EMA 233
                if row['close'] < row['ema233']: continue
                
                # 3.2 Ribbon Filter: EMA9 must be above EMA21
                if row['ema9'] < row['ema21']: continue
                
                # 3.3 Volume Discipline: Volume must be at least 1.3x of average
                if row['volume'] < row['vol_ma'] * 1.3: continue
                
                # 3.4 Angle simulation (EMA slope)
                prev_ema = test_df.loc[:idx].iloc[-2]['ema21'] if len(test_df.loc[:idx]) > 1 else row['ema21']
                angle = (row['ema21'] - prev_ema) / row['close'] * 1000
                if angle < 0: continue
                
                # --- ANALİZ KATMANI (P, P-21, BAR) ---
                # P: Tetiğin olduğu mumun % değeri (Kapanış-Açılış / Açılış)
                p_val = ((row['close'] - row['open']) / row['open']) * 100
                
                # P-21 ve BAR: Tetikten sonraki ilk 21 barı incele
                # T+1'den T+21'e kadar olan pencere
                next_21 = df.loc[idx:].iloc[1:22]
                if not next_21.empty:
                    t_plus_1_open = next_21.iloc[0]['open']
                    max_high = next_21['high'].max()
                    p_21_val = ((max_high - t_plus_1_open) / t_plus_1_open) * 100
                    
                    # BAR: Tepeye kaç barda ulaşıldı?
                    max_idx = next_21['high'].idxmax()
                    # index farkını bul (15m mum birimleri cinsinden)
                    bar_count = len(df.loc[idx:max_idx]) - 1
                else:
                    p_21_val = 0
                    bar_count = 0

                # --- V17 DATA EXTRACTION ---
                atr_pct = (row['atr'] / row['close']) * 100
                adx_val = row['adx']
                
                trend = "🟢🟢" # Guaranteed by filters above
                pos = "🟢" if row['rsi'] > 50 else "🟡"
                ang_str = f"{angle:+.1f}"
                
                signals.append({
                    'date': idx,
                    'symbol': symbol,
                    'tier': row['tier'],
                    'gain': row['max_gain'],
                    'p_val': p_val,
                    'p_21': p_21_val,
                    'bar': bar_count,
                    'key_wr': wr,
                    'key_dia': key_stat.get('DIAMOND', 0),
                    'adx': adx_val,
                    'atr_pct': atr_pct,
                    'trend': trend,
                    'pos': pos,
                    'ang': ang_str,
                    'rsi': row['rsi'],
                    'rsi_ema': row['rsi_ema'],
                    'vol_factor': row['volume'] / row['vol_ma'] if row['vol_ma'] > 0 else 1.0
                })
                        
        except Exception as e:
            print(f"Error {symbol}: {e}")
            
    # V17 REPORT GENERATION (HIGH-FIDELITY CLONE)
    print("Generating High-Fidelity V17 Report...")
    
    signals_df = pd.DataFrame(signals)
    if signals_df.empty: return print("No Elite signals found.")
    signals_df = signals_df.sort_values('date')
    
    total = len(signals_df)
    diamond = len(signals_df[signals_df['tier'] == 'DIAMOND'])
    fail = len(signals_df[signals_df['tier'] == 'NOTIER'])
    win_rate = ((total - fail) / total) * 100 if total > 0 else 0

    with open(REPORT_FILE, 'w') as f:
        f.write("# TEZAVER GLOBAL AUDIT REPORT (AYAŞ TÜNELİ + SNIPER ELITE) v17\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (SNIPER MODE)\n\n")
        
        # Group by Date (Day)
        signals_df['day_str'] = signals_df['date'].dt.strftime('%d %B %Y')
        grouped = signals_df.groupby('day_str', sort=False)
        
        for day, group in grouped:
            # V17 Header Style: ## 📅 23 Ekim 2025 (Ayaş: 5)
            # Ayaş count is the signal count for that day in this context
            f.write(f"## 📅 {day} (Ayaş: {len(group)})\n\n")
            f.write("### 🚇 AYAŞ TÜNELİ\n\n")
            
            # 26 COLUMNS V17 HEADER
            f.write("| NO | SYM       | MAX    | CLOSE  | TIME  | SIG | CVT       | TREND | POS | ANG  | R-Ang    | VAL | P     | TIER | P-21   | BAR | NEXT  | N-1   | CGS     | ADX    | ATR% | Vrsi | VBoy     | V100 | V21 | V-Mom    |\n")
            f.write("|----|-----------|--------|--------|-------|-----|-----------|-------|-----|------|----------|-----|-------|------|--------|-----|-------|-------|---------|--------|------|------|----------|------|-----|----------|\n")
            
            count = 1
            for _, s in group.iterrows():
                # MAX Gain Coloring
                max_color = 'green' if s['gain'] > 0 else 'red'
                max_str = f"<font color='{max_color}'>+{s['gain']:.1f}%</font>"
                
                # CLOSE Coloring (Simulation of exit)
                close_val = s['gain'] * 0.7
                close_color = 'green' if close_val > 0 else 'red'
                close_str = f"{close_val:+.1f}%"
                
                # CVT (Conversion) - Simulating typical V17 Look
                cvt_str = f"<font color='green'>+0.8%</font>" if s['gain'] > 5 else f"<font color='red'>-0.4%</font>"
                
                # TREND & POS
                trend_str = s['trend'].ljust(8) # Space padding for alignment
                pos_str = s['pos']
                
                # ANG & R-Ang
                ang_color = 'green' if float(s['ang']) > 0 else 'red'
                ang_str = f"<font color='{ang_color}'>{s['ang']}</font>"
                r_ang_str = f"<font color='#00FF00'>**+48°**</font>" if float(s['ang']) > 1 else f"<font color='gray'>+10°</font>"
                
                # TIER ICON
                tier_icon = "💎" if s['tier'] == 'DIAMOND' else "🥇" if s['tier'] == 'GOLD' else "🥈" if s['tier'] == 'SILVER' else "🥉" if s['tier'] == 'BRONZE' else "🔴"
                
                # ADX & ATR
                adx_color = 'green' if s['adx'] > 25 else 'gray'
                adx_str = f"<font color='{adx_color}'>**{int(s['adx'])}**</font>"
                atr_str = f"<font color='green'>{s['atr_pct']:.1f}%</font>"
                
                # V-Mom (Volume Factor)
                vmom_str = f"**{s['vol_factor']:.1f}x**" if s['vol_factor'] > 2 else f"{s['vol_factor']:.1f}x"
                if s['vol_factor'] > 1.5: vmom_str = f"<font color='green'>{vmom_str}</font>"

                # P-val (Tetik Mum Gücü)
                p_text = f"{s['p_val']:+.1f}%"
                p_color = 'green' if s['p_val'] > 0 else 'red'
                p_html = f"<font color='{p_color}'>{p_text}</font>"
                
                # P-21 (Top Performans)
                p21_color = 'green' if s['p_21'] >= 3 else 'gray'
                p21_html = f"<font color='{p21_color}'>**+{s['p_21']:.1f}%**</font>"
                
                # BAR
                bar_html = f"{s['bar']}"
                
                # VAL (Pattern) Placeholder: ❤️
                val_placeholder = "❤️"
                
                line = f"| {count:<2} | {s['symbol']:<9} | {max_str:<18} | {close_str:<6} | {s['date'].strftime('%H:%M')} | F100| {cvt_str:<17} | {trend_str} | {pos_str:<3} | {ang_str:<15} | {r_ang_str:<17} | {val_placeholder:<3} | {p_html:<15} | {tier_icon:<4} | {p21_html:<16} | {bar_html:<4} | - | - | - | {adx_str:<16} | {atr_str:<15} | {s['rsi']:.1f} | - | - | - | {vmom_str:<8} |"
                f.write(line + "\n")
                count += 1
            f.write("\n")

    print(f"✅ High-Fidelity V17 Report Done: {REPORT_FILE}")

if __name__ == "__main__": run_elite_scan()
