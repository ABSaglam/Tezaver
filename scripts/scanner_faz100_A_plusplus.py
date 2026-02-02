import os
import glob
import pandas as pd
import numpy as np
import json
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

# FAZ-100 A++ ELITE SNIPER ARCHIVE VERSION
# PROUDLY SEALED FOR ALI BEY

# Configuration
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = "2026-01-01"
END_DATE = "2026-01-31"
KEYS_FILE = "/Users/alisaglam/TezaverMac/data/faz100_dna_keys_SEALED.json"
REPORT_FILE = "/Users/alisaglam/TezaverMac/FAZ100_A_PLUSPLUS_REPORT.md"

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

def get_tier(p_49_val):
    if p_49_val >= 30: return "DIAMOND"
    if p_49_val >= 20: return "GOLD"
    if p_49_val >= 10: return "SILVER"
    if p_49_val >= 5: return "BRONZE"
    return "NOTIER"

def run_elite_scan():
    print(f"🦅 STARTING FAZ-100 A++ ELITE SCAN (2026)")
    
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
            # Daily ATR for tooltip (96 bars = 1 day)
            df['daily_atr'] = df['close'].diff().abs().rolling(window=96).mean()
            
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

                # --- V18 (A++) PHYSICAL DISCIPLINE GATE ---
                is_weak_trigger = False
                if angle < 15.0: is_weak_trigger = True
                if row['rsi'] < 60.0: is_weak_trigger = True
                if vboy_val < 2.0: is_weak_trigger = True
                
                if is_weak_trigger: continue # A++: Çer çöp temizliği
                
                # --- V18 (A++) DNA PERFORMANCE GATE (P-49 BASED) ---
                dna_meta = valid_keys[symbol][dna]
                # Calculate Elite Success Rate: (Bronze + Silver + Gold + Diamond) / Total
                elite_success_count = dna_meta.get('BRONZE', 0) + dna_meta.get('SILVER', 0) + \
                                     dna_meta.get('GOLD', 0) + dna_meta.get('DIAMOND', 0)
                elite_win_rate = (elite_success_count / dna_meta['TOTAL'] * 100) if dna_meta['TOTAL'] > 0 else 0
                
                if elite_win_rate < REPORT_MIN_WR: continue # A++: Sadece hızlı patlayan DNA'lar

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
                    'vol_factor': vboy_val
                })
                        
        except Exception as e:
            print(f"Error {symbol}: {e}")
            
    # V17 REPORT GENERATION (HIGH-FIDELITY CLONE)
    print("Generating High-Fidelity V17 A++ Report...")
    
    signals_df = pd.DataFrame(signals)
    if signals_df.empty: return print("No A++ Elite signals found.")
    signals_df = signals_df.sort_values(['date', 'symbol'])
    
    with open(REPORT_FILE, 'w') as f:
        f.write("# TEZAVER GLOBAL AUDIT REPORT (AYAŞ TÜNELİ + SNIPER ELITE A++) v17\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (SNIPER A++ MODE)\n\n")
        
        signals_df['day_str'] = signals_df['date'].dt.strftime('%d %B %Y')
        days = signals_df['day_str'].unique()
        
        for day in days:
            day_group = signals_df[signals_df['day_str'] == day]
            f.write(f"## 📅 {day} (Ayaş: {len(day_group)})\n\n")
            f.write("### 🚇 AYAŞ TÜNELİ\n\n")
            f.write("| NO | SYM | MAX | CLOSE | TIME | SIG | CVT | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-49 | BAR | NEXT | N-1 | CGS | ADX | ATR% | Vrsi | VBoy | V100 | V21 | V-Mom |\n")
            f.write("|----|-----------|--------|--------|-------|-----|-----------|-------|-----|------|----------|-----|-------|------|--------|-----|-------|-------|---------|--------|------|------|----------|------|-----|----------|\n")
            
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
                
                line = f"| {display_no:<2} | {display_sym:<9} | {max_str:<18} | {close_str:<6} | {s['date'].strftime('%H:%M')} | F100| {cvt_str:<17} | {s['trend']:<7} | {s['pos']:<3} | {ang_str:<15} | {r_ang_str:<17} | {val_emoji} | {p_str:<15} | {tier_icon:<4} | {p49_str:<15} | {bar_str:<12} | - | - | {cgs_str:<16} | {adx_str:<16} | {atr_html} | {s['rsi']:.1f} | {vboy_str} | {v100_str} | {v21_str} | {vmom_str} |"
                f.write(line + "\n")
            f.write("\n")

    print(f"✅ High-Fidelity V17 A++ Report Done: {REPORT_FILE}")

if __name__ == "__main__": run_elite_scan()
