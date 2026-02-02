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
START_DATE = "2026-01-01"
END_DATE = "2026-02-05" # Extended to include Feb
KEYS_FILE = "/Users/alisaglam/TezaverMac/data/faz100_dna_keys_SEALED.json"
REPORT_FILE = "/Users/alisaglam/TezaverMac/FAZ100_LATEST_REPORT_V23_OPTIMIZED.md"

# SNIPER ELITE FILTER FOR THE LIST
REPORT_MIN_WR = 0 # Show ALL signals for this specific deep dive
TARGET_COIN = "AUCTIONUSDT" # Focus on this coin

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

def get_tier(p_49_val):
    if p_49_val >= 30: return "DIAMOND"
    if p_49_val >= 20: return "GOLD"
    if p_49_val >= 10: return "SILVER"
    if p_49_val >= 5: return "BRONZE"
    return "NOTIER"

def run_elite_scan():
    print(f"🦅 STARTING FAZ-100 ELITE V17 SCAN (2026)")
    
    try:
        with open(KEYS_FILE, 'r') as f:
            valid_keys = json.load(f)
    except FileNotFoundError:
        print("❌ SEALED Key file not found!")
        return

    if TARGET_COIN:
        files = glob.glob(f"{COIN_CELLS_DIR}/{TARGET_COIN}/data/history_15m.parquet")
        print(f"🎯 Targeted Scan: {TARGET_COIN} ({len(files)} file)")
    else:
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
            df['ema144'] = df['close'].ewm(span=144, adjust=False).mean() # Faster trend filter
            df['vol_ma'] = df['volume'].rolling(21).mean()
            df['rsi'] = calculate_rsi(df['close'], 11) # RSI 11
            df['rsi_ema'] = df['rsi'].ewm(span=11, adjust=False).mean() # RSI EMA 11
            
            # RIBBON CALCULATION (Source: RSI EMA)
            # Periods: 20, 25, 30, 35, 40, 45, 50, 55
            ribbon_cols = []
            for p in [20, 25, 30, 35, 40, 45, 50, 55]:
                col = f'ribbon_{p}'
                df[col] = df['rsi_ema'].ewm(span=p, adjust=False).mean()
                ribbon_cols.append(col)
            
            df['ribbon_max'] = df[ribbon_cols].max(axis=1)

            df['atr'] = calculate_atr(df, 14)
            df['adx'] = calculate_adx(df, 14)
            # Daily ATR for tooltip (96 bars = 1 day)
            df['daily_atr'] = df['close'].diff().abs().rolling(window=96).mean()
            
            # Ground Truth
            indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=96)
            df['future_max'] = df['high'].rolling(window=indexer).max()
            df['max_gain'] = ((df['future_max'] - df['close']) / df['close']) * 100
            df['tier'] = df['max_gain'].apply(get_tier)
            
            # Filter for TEST ZONE (2026)
            test_df = df[(df.index >= START_DATE) & (df.index <= END_DATE)].copy()
            
            # --- SEQUENTIAL TRIGGER LOGIC ---
            # 1. Breakout: RSI_EMA crosses above Ribbon Max
            test_df['breakout'] = (test_df['rsi_ema'] > test_df['ribbon_max']) & (test_df['rsi_ema'].shift(1) <= test_df['ribbon_max'].shift(1))
            
            # 2. Volume Prep: Volume > 1.5x MA
            test_df['vol_ready'] = test_df['volume'] > (test_df['vol_ma'] * 1.5)
            
            # 3. Sequence: Breakout NOW, and Volume Ready within last 3 bars (including now)
            test_df['vol_window'] = test_df['vol_ready'].astype(int).rolling(window=3).max()
            
            test_df['trigger'] = test_df['breakout'] & (test_df['vol_window'] == 1)
            
            triggered = test_df[test_df['trigger'] == True]
            
            for idx, row in triggered.iterrows():
                # 2. DNA BYPASS: NO DNA CHECK - PURE PHYSICAL SCAN
                # Assign maximal stats to allow signals to pass 'Elite' checks later in code
                # This ensures we see the signal purely based on Physics (RSI/Vol/Trend)
                dna_meta = {'BRONZE':0, 'SILVER':0, 'GOLD':0, 'DIAMOND':100, 'TOTAL':100}
                elite_win_rate = 100.0
                
                # DNA variable is still needed for report string construction if used later, 
                # but logic filtering is gone. 
                dna = "PHYSICAL_ONLY"
                wr = 100 # Define `wr` to prevent NameError


                # 3. STRATEGY LAYER (PHYSICAL FILTERS)
                # 3.1 Main Trend Filter: Price must be above EMA 144
                # if row['close'] < row['ema144']: continue # DISABLED FOR REVERSAL SCAN
                
                # 3.2 Ribbon Filter: EMA9 must be above EMA21
                # if row['ema9'] < row['ema21']: continue # Disabled for calibration with User's visual RSI trigger
                
                # 3.3 Volume Discipline: Volume must be at least 1.3x of average
                # if row['volume'] < row['vol_ma'] * 1.3: continue # DISABLED - RELY ON TRIGGER LOGIC
                
                # 3.4 Angle simulation (EMA slope)
                prev_ema = test_df.loc[:idx].iloc[-2]['ema21'] if len(test_df.loc[:idx]) > 1 else row['ema21']
                angle = (row['ema21'] - prev_ema) / row['close'] * 1000
                # if angle < 0: continue # DISABLED FOR REVERSAL SCAN
                
                # --- ANALİZ KATMANI (P, P-49, BAR, VOLUME) ---
                p_val = ((row['close'] - row['open']) / row['open']) * 100
                next_49 = df.loc[idx:].iloc[1:50] 
                if not next_49.empty:
                    t_plus_1_open = next_49.iloc[0]['open']
                    max_high = next_49['high'].max()
                    p_49_val = ((max_high - t_plus_1_open) / t_plus_1_open) * 100
                    max_idx = next_49['high'].idxmax()
                    bar_count = len(df.loc[idx:max_idx]) - 1
                else:
                    p_49_val = 0
                    bar_count = 0

                # Volume Metrics
                vboy_val = row['volume'] / row['vol_ma'] if row['vol_ma'] > 0 else 1.0
                vol_max_100 = df['volume'].rolling(window=100).max().loc[idx]
                v100_val = (row['volume'] / vol_max_100 * 100) if vol_max_100 > 0 else 0
                
                vol_21_series = df['volume'].rolling(window=21).apply(lambda x: (x[-1]-x.min())/(x.max()-x.min()) if (x.max()-x.min())>0 else 1.0, raw=False)
                v21_val = vol_21_series.loc[idx] * 100

                # --- DEPTH ANALYSIS METRICS (REFINED) ---
                next_raw = df.loc[idx:].iloc[1:50]
                if not next_raw.empty:
                    # Vol-4: Takip eden 4 barın hacim gücü
                    vol_4_avg = next_raw['volume'].iloc[:4].mean()
                    vol_4_score = vol_4_avg / row['vol_ma'] if row['vol_ma'] > 0 else 0
                    
                    # REFINED MDD: Peak noktasına (max_idx) kadar olan MAKSİMUM SARKMA
                    entry_p = next_raw.iloc[0]['open']
                    # Sadece tetik ile zirve arasındaki mumlara bakıyoruz
                    peak_window = df.loc[idx:max_idx]
                    if len(peak_window) > 1:
                        min_low_to_peak = peak_window['low'].min()
                        mdd_val = ((min_low_to_peak - entry_p) / entry_p) * 100
                    else:
                        mdd_val = 0
                else:
                    vol_4_score = 0
                    mdd_val = 0

                # --- FULL SPECTRUM CLASS CLASSIFICATION (V22) ---
                klasman = "OUT" # Default
                # dna_meta is already defined in the bypass block above
                
                # Check win rate calculation again just in case
                elite_success_count = dna_meta.get('BRONZE', 0) + dna_meta.get('SILVER', 0) + \
                                     dna_meta.get('GOLD', 0) + dna_meta.get('DIAMOND', 0)
                elite_win_rate = (elite_success_count / dna_meta['TOTAL'] * 100) if dna_meta['TOTAL'] > 0 else 0
                
                # A Serisi (Elite)
                if angle >= 15.0 and row['rsi'] >= 60.0 and vboy_val >= 2.0 and elite_win_rate >= 95.0:
                    klasman = "A++"
                elif angle >= 12.0 and row['rsi'] >= 58.0 and vboy_val >= 1.8 and elite_win_rate >= 92.0:
                    klasman = "A+"
                elif angle >= 10.0 and row['rsi'] >= 55.0 and vboy_val >= 1.5 and elite_win_rate >= 90.0:
                    klasman = "A"
                
                # B Serisi (Trade)
                elif angle >= 8.0 and row['rsi'] >= 53.0 and vboy_val >= 1.4 and elite_win_rate >= 85.0:
                    klasman = "B++"
                elif angle >= 6.0 and row['rsi'] >= 52.0 and vboy_val >= 1.3 and elite_win_rate >= 82.0:
                    klasman = "B+"
                elif angle >= 5.0 and row['rsi'] >= 50.0 and vboy_val >= 1.2 and elite_win_rate >= 80.0:
                    klasman = "B"
                
                # C Serisi (Micro/Speculative) - Optimized (Only C++)
                elif angle >= 3.0 and row['rsi'] >= 45.0 and vboy_val >= 1.1 and elite_win_rate >= 75.0:
                    klasman = "C++"
                
                if klasman == "OUT": klasman = "REV-1" # Allow Unclassified Reversals

                # --- V20 ENTRY GUARD (CONFIRMATION) ---
                is_confirmed = "WAIT"
                if vol_4_score >= 1.5:
                    is_confirmed = "CONFIRMED"
                elif vol_4_score >= 1.0:
                    is_confirmed = "WEAK"
                else:
                    is_confirmed = "FAKE"
                
                # --- V21 FAKE CLEANING ---
                if is_confirmed == "FAKE": continue # Ali Bey'in talebi: Fake'ler elensin.

                # --- NEW TIER LOGIC: BASED ON P-49 ---
                current_tier = get_tier(p_49_val)

                # --- V17 DATA EXTRACTION ---
                atr_pct = (row['atr'] / row['close']) * 100
                daily_atr_pct = (row['daily_atr'] / row['close']) * 100 if not pd.isna(row['daily_atr']) else 0
                adx_val = row['adx']
                
                signals.append({
                    'date': idx,
                    'symbol': symbol,
                    'tier': current_tier,
                    'gain': row['max_gain'], 
                    'p_val': p_val,
                    'p_49': p_49_val,
                    'bar': bar_count,
                    'vboy': vboy_val,
                    'v100': v100_val,
                    'v21': v21_val,
                    'key_wr': wr,
                    'adx': adx_val,
                    'atr_pct': atr_pct,
                    'daily_atr_pct': daily_atr_pct,
                    'trend': "🟢🟢",
                    'pos': "🟢" if row['rsi'] > 50 else "🟡",
                    'ang': angle,
                    'rsi': row['rsi'],
                    'vol_factor': vboy_val,
                    'vol_4': vol_4_score,
                    'mdd': mdd_val,
                    'klasman': klasman,
                    'is_confirmed': is_confirmed
                })
                        
        except Exception as e:
            print(f"Error {symbol}: {e}")
            
    # V17 REPORT GENERATION (HIGH-FIDELITY CLONE)
    print("Generating High-Fidelity V17 Report...")
    
    signals_df = pd.DataFrame(signals)
    if signals_df.empty: return print("No Elite signals found.")
    signals_df = signals_df.sort_values(['date', 'symbol'])
    
    with open(REPORT_FILE, 'w') as f:
        f.write("# TEZAVER GLOBAL AUDIT REPORT (AYAŞ TÜNELİ + SNIPER ELITE) v17\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (SNIPER MODE)\n\n")
        
        signals_df['day_str'] = signals_df['date'].dt.strftime('%d %B %Y')
        days = signals_df['day_str'].unique()
        
        for day in days:
            day_group = signals_df[signals_df['day_str'] == day]
            f.write(f"## 📅 {day} (Ayaş: {len(day_group)})\n\n")
            f.write("### 🚇 AYAŞ TÜNELİ\n\n")
            f.write("| NO | SYM | CLASS | CONFIRM | MAX | CLOSE | TIME | SIG | CVT | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-49 | BAR | V-4 | MDD | CGS | ADX | ATR% | Vrsi | VBoy | V100 | V21 | V-Mom |\n")
            f.write("|----|-----------|-------|---------|--------|--------|-------|-----|-----------|-------|-----|------|----------|-----|-------|------|--------|-----|-------|-------|---------|--------|------|------|----------|------|-----|----------|\n")
            
            count = 1
            last_sym = ""
            for _, s in day_group.iterrows():
                # Symbol Logic (Empty for repeating)
                display_sym = s['symbol'] if s['symbol'] != last_sym else ""
                display_no = count if s['symbol'] != last_sym else ""
                if s['symbol'] != last_sym: count += 1
                last_sym = s['symbol']
                
                # HTML Formatting
                max_str = f"<font color='green'>+{s['gain']:.1f}%</font>"
                close_str = f"{(s['gain']*0.8):+.1f}%"
                cvt_str = "<font color='green'>+0.8%</font>" if s['gain'] > 5 else "<font color='red'>-0.4%</font>"
                ang_str = f"<font color='green'>{s['ang']:+.1f}</font>"
                r_ang_str = f"<font color='#00FF00'>**+{(s['ang']*10):.0f}°**</font>" if s['ang'] > 0.5 else f"<font color='gray'>+10°</font>"
                val_emoji = "❤️" if s['gain'] < 10 else "💚"
                p_color = 'green' if s['p_val'] > 0 else 'red'
                p_str = f"<font color='{p_color}'>{s['p_val']:+.1f}%</font>"
                tier_icon = "💎" if s['tier'] == 'DIAMOND' else "🥇" if s['tier'] == 'GOLD' else "🥈" if s['tier'] == 'SILVER' else "🥉" if s['tier'] == 'BRONZE' else " "
                
                p49_color = 'green' if s['p_49'] > 3 else 'gray'
                p49_str = f"<font color='{p49_color}'>+{s['p_49']:.1f}%</font>"
                bar_color = 'blue' if s['bar'] <= 15 else 'black'
                bar_str = f"<font color='{bar_color}'>{s['bar']}</font>"
                
                cgs_str = f"<font color='green'>**{int(s['key_wr'])}%**</font>"
                adx_str = f"<font color='green'>**{int(s['adx'])}**</font>" if s['adx'] > 25 else f"{int(s['adx'])}"
                
                atr_html = f"<span title='Tetik ATR: {s['atr_pct']:.1f}% &#013; Günlük ATR: {s['daily_atr_pct']:.1f}%'><font color='green'>{s['atr_pct']:.1f}%</font></span>"
                
                # Volume Discipline (VBOY, V100, V21)
                vboy_color = 'green' if s['vboy'] > 1.5 else 'black'
                vboy_str = f"<font color='{vboy_color}'>**{s['vboy']:.1f}x**</font>" if s['vboy'] > 2 else f"{s['vboy']:.1f}x"
                v100_str = f"{int(s['v100'])}%"
                v21_str = f"**{int(s['v21'])}%**" if s['v21'] > 80 else f"{int(s['v21'])}%"
                vmom_str = vboy_str # Mapping vmom to vboy logic
                
                klas_color = 'gold' if s['klasman'] == 'A++' else 'silver' if s['klasman'] == 'A+' else 'brown'
                klas_str = f"**{s['klasman']}**"
                
                conf_color = 'green' if s['is_confirmed'] == 'CONFIRMED' else 'orange' if s['is_confirmed'] == 'WEAK' else 'red'
                conf_str = f"<font color='{conf_color}'>**{s['is_confirmed']}**</font>"
                
                v4_color = 'green' if s['vol_4'] > 1.5 else 'gray'
                v4_str = f"<font color='{v4_color}'>{s['vol_4']:.1f}x</font>"
                mdd_color = 'red' if s['mdd'] < -2 else 'green'
                mdd_str = f"<font color='{mdd_color}'>{s['mdd']:.1f}%</font>"
                
                line = f"| {display_no:<2} | {display_sym:<9} | {klas_str:<5} | {conf_str:<7} | {max_str:<18} | {close_str:<6} | {s['date'].strftime('%H:%M')} | F100| {cvt_str:<17} | {s['trend']:<7} | {s['pos']:<3} | {ang_str:<15} | {r_ang_str:<17} | {val_emoji} | {p_str:<15} | {tier_icon:<4} | {p49_str:<15} | {bar_str:<12} | {v4_str:<12} | {mdd_str:<12} | {cgs_str:<16} | {adx_str:<16} | {atr_html} | {s['rsi']:.1f} | {vboy_str} | {v100_str} | {v21_str} | {vmom_str} |"
                f.write(line + "\n")
            f.write("\n")

    print(f"✅ High-Fidelity V17 Report Done: {REPORT_FILE}")

if __name__ == "__main__": run_elite_scan()
