import pandas as pd
import numpy as np
import os
import math
from datetime import datetime
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

# CONFIG
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = "2026-01-01"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/RAPOR_KAHIN_SNIPER_2026.md"
MANIFEST_FILE = "/Users/alisaglam/TezaverMac/kahin_coin_dna_manifest.csv"
KEYS_FILE_V2 = "/Users/alisaglam/TezaverMac/data/faz100_dna_keys_V2.json"

# 🏛️ V17 STANDART HEADERS (Updated with KLAS)
HEADERS = ["NO", "SYM", "MAX", "EXIT", "KLAS", "TIME", "SIG", "TREND", "POS", "ANG", "R-Ang", "VAL", "P", "TIER", "P-21", "BAR", "NEXT", "N-1", "CGS", "ADX", "ATR%", "Vrsi", "VBoy", "V100", "V21", "V-Mom"]

# Load DNA Manifest (Legacy connection)
if os.path.exists(MANIFEST_FILE):
    MANIFEST_DF = pd.read_csv(MANIFEST_FILE).set_index('symbol')
else:
    MANIFEST_DF = None

# Load DNA V2 Manifest
if os.path.exists(KEYS_FILE_V2):
    import json
    with open(KEYS_FILE_V2, 'r') as f:
        DNA_MANIFEST_V2 = json.load(f)
else:
    DNA_MANIFEST_V2 = {}

def calculate_adx(df, period=14):
    df = df.copy()
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    df['up'] = df['high'] - df['high'].shift(1)
    df['down'] = df['low'].shift(1) - df['low']
    df['+dm'] = np.where((df['up'] > df['down']) & (df['up'] > 0), df['up'], 0)
    df['-dm'] = np.where((df['down'] > df['up']) & (df['down'] > 0), df['down'], 0)
    df['tr_s'] = df['tr'].rolling(window=period).mean()
    df['+dm_s'] = df['+dm'].rolling(window=period).mean()
    df['-dm_s'] = df['-dm'].rolling(window=period).mean()
    df['+di'] = 100 * (df['+dm_s'] / df['tr_s'])
    df['-di'] = 100 * (df['-dm_s'] / df['tr_s'])
    df['dx'] = 100 * (abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'] + 1e-9))
    return df['dx'].rolling(window=period).mean()

def get_dna_v2_signature(row_15m, h1_ok, h4_ok, d1_ok):
    # RSI Fazı
    rsi = row_15m['rsi']
    if rsi <= 35: faz = "DIP"
    elif rsi <= 45: faz = "BIRIKIM"
    elif rsi <= 55: faz = "NOTR"
    elif rsi <= 65: faz = "MOM"
    elif rsi <= 75: faz = "TREND"
    else: faz = "ALIM"
    
    # Sıkışma (Aks)
    sq_pct = abs(row_15m['rsi_rib_20'] - row_15m['rsi_rib_55']) / (row_15m['rsi_ema'] or 1) * 100
    if sq_pct <= 0.3: aks = "TIGHT"
    elif sq_pct <= 0.8: aks = "MICRO"
    elif sq_pct <= 1.5: aks = "NORMAL"
    else: aks = "GAP"
    
    # Hacim Ritmi (Vrsi)
    v_hyb = row_15m.get('v_hyb', 0)
    if v_hyb >= 10: ritim = "NOVA"
    elif v_hyb >= 7: ritim = "SURGE"
    elif v_hyb >= 4: ritim = "READY"
    else: ritim = "DRY"
    
    # Vuruş Karakteri (VBoy)
    v_eff = row_15m.get('v_eff', 0)
    if v_eff >= 8: char = "PURE"
    elif v_eff >= 5: char = "SOLID"
    else: char = "THIN"
    
    # RSI Açı
    ang = row_15m.get('ang_v2', 0)
    if ang >= 60: a_p = "SHARP"
    elif ang >= 45: a_p = "UP"
    else: a_p = "FLAT"

    harmony = f"{int(h1_ok)}{int(h4_ok)}{int(d1_ok)}"
    return f"{faz}|{aks}|{ritim}|{char}|{a_p}|{harmony}"

def calculate_rsi(series, period=11):
    delta = series.diff()
    # Using EMA alpha (2 / (N+1)) to match Ali Bey's TradingView EMA settings
    alpha = 2 / (period + 1)
    gain = (delta.where(delta > 0, 0)).ewm(alpha=alpha, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
    rs = gain / (loss + 0.0001)
    return 100 - (100 / (1 + rs))

def get_indicators(df, is_daily=False):
    if df.empty: return df
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], 11)
    df['rsi_ema'] = df['rsi'].ewm(span=11, adjust=False).mean()
    rib_periods = [20, 25, 30, 35, 40, 45, 50, 55]
    for p in rib_periods:
        # Ali Bey's Ribbon is 'RSI-based MA' (Source: RSI-EMA)
        df[f'rsi_rib_{p}'] = df['rsi_ema'].ewm(span=p, adjust=False).mean()
    df['rib_max'] = df[[f'rsi_rib_{p}' for p in [20, 55]]].max(axis=1)
    df['rib_min_all'] = df[[f'rsi_rib_{p}' for p in rib_periods]].min(axis=1)
    df['rib_mid'] = (df['rsi_rib_20'] + df['rsi_rib_55']) / 2
    tr = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
    df['tr'] = tr
    df['atr100'] = tr.rolling(window=100).mean().replace(0, 0.001)
    df['atr21'] = tr.rolling(window=21).mean().replace(0, 0.001)
    if not is_daily:
        df['vol_ma50'] = df['volume'].rolling(window=50).mean().replace(0, 1)
        df['v_mom'] = df['volume'] / df['vol_ma50']
        df['vol_ma100'] = df['volume'].rolling(window=100).mean().replace(0, 1)
        df['vol_ma21'] = df['volume'].rolling(window=21).mean().replace(0, 1)
        df['v100'] = df['volume'] / df['vol_ma100']
        df['v21'] = df['volume'] / df['vol_ma21']
    else:
        plus_dm, minus_dm = df['high'].diff(), -df['low'].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        tr14_sum = tr.rolling(window=14).sum().replace(0, 1)
        plus_di = 100 * (plus_dm.rolling(window=14).sum() / tr14_sum)
        minus_di = 100 * (minus_dm.rolling(window=14).sum() / tr14_sum)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.001)
        df['adx14'] = dx.rolling(window=14).mean()
    
    # ATR Calculation for ALL contexts (V17 Standard)
    df['atr_p'] = (tr.rolling(14).mean() / df['close']) * 100
    return df

def check_trend_ok(row):
    rsi_ema = row['rsi_ema']
    rib_max = row['rib_max']
    rib_min = row.get('rib_min_all', 0)
    
    # Ali Bey's Persistence Rule:
    # If Ribbon is above 50, don't cut the signal until RSI-EMA goes fully below it (Rib_Min)
    if rib_min > 50.0:
        return rsi_ema > rib_min
    
    # Standard Rule (Aggressive): Must be above Rib_Max
    return rsi_ema > rib_max

def format_row_v17(idx, symbol, t, row_sub_idx, best_max, best_exit):
    # Daily Best Metrics (Only shown on first row of coin block)
    if row_sub_idx == 0:
        p_s = f"<font color='green'>+{best_max:.1f}%</font>" if best_max >= 10 else f"+{best_max:.1f}%"
        e_s = f"<font color='red'>{best_exit:.1f}%</font>" if best_exit < 0 else f"+{best_exit:.1f}%"
        if best_exit >= 3.0: e_s = f"<font color='green'>**{e_s}**</font>"
        elif best_exit >= 0.5: e_s = f"<font color='green'>{e_s}</font>"
    else:
        p_s, e_s = "", ""

    # Tier: Based on INDIVIDUAL trigger's p_21 (per-trigger performance)
    p21_val = t['p_21']
    tier_icon = "💎" if p21_val >= 30 else "🥇" if p21_val >= 20 else "🥈" if p21_val >= 10 else "🥉" if p21_val >= 5 else ""

    ra_str = f"{t['rsi_angle']:.0f}°"
    ra_f = f"<font color='#00FF00'>**+{ra_str}**</font>" if t['rsi_angle'] >= 45 else f"<font color='green'>+{ra_str}</font>" if t['rsi_angle'] >= 10 else f"<font color='red'>{ra_str}</font>" if t['rsi_angle'] <= -10 else f"<font color='gray'>{ra_str}</font>"
    cgs_f = f"<font color='green'>**{t['cgs']:.0f}%**</font>" if t['cgs'] >= 50 else f"<font color='green'>{t['cgs']:.0f}%</font>" if t['cgs'] >= 25 else f"<font color='gray'>{t['cgs']:.0f}%</font>"
    adx_f = f"<font color='green'>**{t['adx']:.1f}**</font>" if t['adx'] >= 25 else f"<font color='green'>{t['adx']:.1f}</font>" if t['adx'] >= 20 else f"<font color='gray'>{t['adx']:.1f}</font>"
    atr_f = f"<font color='#00FF00'>**{t['atr_adj']:.1f}%**</font>" if t['atr_adj'] >= 4.0 else f"<font color='green'>{t['atr_adj']:.1f}%</font>" if t['atr_adj'] >= 1.0 else f"{t['atr_adj']:.1f}%"
    n_s = f"<font color='green'>+{t['next_pct']:.1f}%</font>" if t['next_pct'] is not None and t['next_pct'] > 0 else f"<font color='red'>{t['next_pct']:.1f}%</font>" if t['next_pct'] is not None and t['next_pct'] < 0 else "0.0%" if t['next_pct'] is not None else "---"
    nn_s = f"<font color='green'>+{t['nn_pct']:.1f}%</font>" if t['nn_pct'] is not None and t['nn_pct'] > 0 else f"<font color='red'>{t['nn_pct']:.1f}%</font>" if t['nn_pct'] is not None and t['nn_pct'] < 0 else "0.0%" if t['nn_pct'] is not None else "---"
    
    ve_s = f"{t['v_eff']:.1f}"
    ve_f = f"<font color='green'>**{ve_s}**</font>" if t['v_eff'] >= 7.0 else f"<font color='red'>{ve_s}</font>" if t['v_eff'] < 3.0 else ve_s
    
    vh_s = f"{t['v_hyb']:.1f}"
    vh_f = f"<font color='#00FF00'>**{vh_s}**</font>" if t['v_hyb'] >= 9.0 else f"<font color='green'>{vh_s}</font>" if t['v_hyb'] >= 7.0 else vh_s

    trend_str = f"{(t['h4_ok'] if 'h4_ok' in t else False) and '🟢' or '🔴'}{(t['h1_ok'] if 'h1_ok' in t else False) and '🟢' or '🔴'}"
    trig_val = f"+{t['trig_pct']:.1f}%" if t['trig_pct'] > 0 else f"{t['trig_pct']:.1f}%"
    sig_label = f"[🏛️KAHİN:{t['type']}]" if 'type' in t else "[🏛️KAHİN]"
    
    # P-21 Extra Bold & Color logic
    p21_str = f"**%{p21_val:.1f}**"
    if p21_val >= 20: p21_f = f"<font color='#00FF00'>**{p21_str}**</font>" # Super Green Extra Bold
    elif p21_val >= 10: p21_f = f"<font color='green'>{p21_str}</font>"
    else: p21_f = p21_str

    # Klasman Coloring
    klas = t.get('klasman', 'C')
    klas_f = f"<font color='#00FF00'>**{klas}**</font>" if 'A' in klas else f"<font color='green'>{klas}</font>" if 'B' in klas else f"<font color='gray'>{klas}</font>"

    row = [str(idx) if row_sub_idx == 0 else "", symbol if row_sub_idx == 0 else "", p_s, e_s, klas_f, t['time'], sig_label, trend_str, t['pos'], t['ang'], ra_f, "💚", trig_val, tier_icon, p21_f, str(t['p_21_dist']), n_s, nn_s, cgs_f, adx_f, atr_f, vh_f, ve_f, f"{t['v100']:.1f}x", f"{t['v21']:.1f}x", f"{t['v_mom']:.1f}x"]
    return row

def run_sniper_audit_optimized():
    print("🏛️ KAHİN: Rapor motoru başlatılıyor...")
    symbols = sorted([d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))])
    all_dates = pd.date_range(start=START_DATE, end=datetime.now().date(), freq='D')
    
    # 🏛️ PRE-LOAD ALL DAILY/WEEKLY DATA FOR PERFORMANCE
    print("🏛️ Veriler yükleniyor (Daily/Weekly)...")
    symbol_data = {}
    for symbol in symbols:
        try:
            p1d = f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet"
            p1w = f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet"
            if os.path.exists(p1d) and os.path.exists(p1w):
                df_d = get_indicators(pd.read_parquet(p1d).set_index(pd.to_datetime(pd.read_parquet(p1d)['timestamp'], unit='ms')), is_daily=True)
                df_w = get_indicators(pd.read_parquet(p1w).set_index(pd.to_datetime(pd.read_parquet(p1w)['timestamp'], unit='ms')), is_daily=True)
                symbol_data[symbol] = {'df_d': df_d, 'df_w': df_w}
        except: continue

    btc_df = symbol_data['BTCUSDT']['df_d'] if 'BTCUSDT' in symbol_data else None

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# 🏛️ KAHİN: 2026 MOMENTUM PIERCING HAREKÂT RAPORU\n")
        f.write(f"Rapor Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("> [!IMPORTANT]\n")
        f.write("> Bu rapor 'Muzaffer Komutan' dahi nizamıyla (Momentum Piercing + ATR > 5.0 + BTC OK) süzülmüştür. 🏛️⚡💎\n\n")

        for current_date in all_dates:
            day_str = current_date.strftime('%Y-%m-%d')
            print(f"🏛️ Harekât Günü: {day_str} süzülüyor...")
            day_results = []
            
            if btc_df is None: continue
            btc_row_m = btc_df[btc_df.index < current_date].tail(1)
            btc_ok = check_trend_ok(btc_row_m.iloc[0]) if not btc_row_m.empty else False
            
            for symbol, data in symbol_data.items():
                try:
                    df_d, df_w = data['df_d'], data['df_w']
                    d_history = df_d[df_d.index < current_date].tail(2)
                    if len(d_history) < 2: continue
                    d_row, d_prev = d_history.iloc[1], d_history.iloc[0]
                    
                    w_row = df_w[df_w.index < current_date].tail(1)
                    if w_row.empty: continue
                    
                    # 🏛️ TÜM FİLTRELER RAFA KALDIRILDI - Saf Sinyal Dökümü
                    # if d_row['atr_p'] < 5.0: continue 

                    # Load 15m/H1/H4 only when daily/weekly passed
                    p15m, ph1, ph4 = [f"{COIN_CELLS_DIR}/{symbol}/data/history_{tf}.parquet" for tf in ['15m', '1h', '4h']]
                    df_15m = get_indicators(pd.read_parquet(p15m).set_index(pd.to_datetime(pd.read_parquet(p15m)['timestamp'], unit='ms')))
                    df_h1 = get_indicators(pd.read_parquet(ph1).set_index(pd.to_datetime(pd.read_parquet(ph1)['timestamp'], unit='ms')))
                    df_h4 = get_indicators(pd.read_parquet(ph4).set_index(pd.to_datetime(pd.read_parquet(ph4)['timestamp'], unit='ms')))
                    
                    day_data = df_15m[(df_15m.index >= current_date) & (df_15m.index < current_date + pd.Timedelta(days=1))]
                    if day_data.empty: continue
                    
                    # 🏛️ TRIPLE STRIKE TRIGGERS (Ali Bey Nizamı)
                    c_rsi = day_data['rsi_ema']
                    p_rsi = day_data['rsi_ema'].shift(1)
                    
                    # 1. Ribbon Cross (RC): RSI crosses Rib_Max while Rib_Min > 50
                    cond_rc = (c_rsi > day_data['rib_max']) & (p_rsi <= day_data['rib_max']) & (day_data['rib_min_all'] > 50)
                    # 2. 60 Cross (60): RSI crosses 60 while Rib_20 > 50
                    cond_60 = (c_rsi > 60) & (p_rsi <= 60) & (day_data['rsi_rib_20'] > 50)
                    # 3. 70 Cross (70): Both RSI and RSI-EMA must be above 70, with RSI being the leader
                    cond_70 = (day_data['rsi'] > 70) & (day_data['rsi_ema'] > 70) & ((day_data['rsi'].shift(1) <= 70) | (day_data['rsi_ema'].shift(1) <= 70))
                    
                    coin_trigs = []
                    for c_type, cond in [("RC", cond_rc), ("60", cond_60), ("70", cond_70)]:
                        for ti in np.where(cond.fillna(False))[0]:
                            ts = day_data.index[ti]
                            idx_f = df_15m.index.get_loc(ts)
                            rsi_now, rsi_prev = day_data.iloc[ti]['rsi_ema'], df_15m['rsi_ema'].iloc[idx_f - 1]
                            rsi_angle = math.degrees(math.atan(rsi_now - rsi_prev))
                            v_mom = day_data.iloc[ti]['v_mom']
                            
                            h1_m, h4_m = df_h1[df_h1.index <= ts].tail(1), df_h4[df_h4.index <= ts].tail(1)
                            if h1_m.empty or h4_m.empty: continue
                            
                            # 🛡️ Final Trend Harmony (RAFA KALDIRILDI)
                            if True: # Her tetik tescil ediliyor
                                future_21 = df_15m.iloc[idx_f + 1 : idx_f + 22]
                                if future_21.empty: continue
                                
                                entry_p = day_data.iloc[ti]['close']
                                peak_p_21, peak_idx_21 = future_21['high'].max(), future_21['high'].idxmax()
                                
                                p_21_dist = df_15m.index.get_loc(peak_idx_21) - idx_f
                                peak_pos_21 = df_15m.index.get_loc(peak_idx_21)
                                
                                # VBoy (V_eff) & Vrsi (V_hyb) Perfection logic
                                row_15m = day_data.iloc[ti]
                                body = abs(row_15m['close'] - row_15m['open'])
                                candle_range = row_15m['high'] - row_15m['low']
                                v_eff = (body / (candle_range if candle_range > 0 else 0.001)) * 10.0
                                
                                # Vrsi (V_hyb) and VBoy (V_eff) calibration for DNA
                                vol_intensity = min(10.0, (row_15m['volume'] / (row_15m['vol_ma100'] or 1)) * 2)
                                v_hyb = min(15.0, vol_intensity * (row_15m['rsi'] / 50.0))
                                v_eff = ((row_15m['close'] - row_15m['open']).abs() / (row_15m['high'] - row_15m['low']).replace(0, 1e-9)) * 10
                                ang_v2 = np.degrees(np.arctan((row_15m['rsi_ema'] - df_15m['rsi_ema'].iloc[max(0, idx_f-3)]) / 3.0))

                                row_dna_input = row_15m.copy()
                                row_dna_input['v_hyb'] = v_hyb
                                row_dna_input['v_eff'] = v_eff
                                row_dna_input['ang_v2'] = ang_v2
                                
                                # Harmony check - Relative to full dataframes
                                h1_idx = df_h1.index.asof(ts)
                                h4_idx = df_h4.index.asof(ts)
                                d1_idx = df_d.index.asof(ts)
                                
                                h1_row = df_h1.loc[h1_idx] if h1_idx is not pd.NaT else None
                                h4_row = df_h4.loc[h4_idx] if h4_idx is not pd.NaT else None
                                d1_row = df_d.loc[d1_idx] if d1_idx is not pd.NaT else None

                                h1_ok = row_15m['close'] > h1_row['rsi_rib_55'] if h1_row is not None else False
                                h4_ok = row_15m['close'] > h4_row['rsi_rib_55'] if h4_row is not None else False
                                d1_ok = row_15m['close'] > d1_row['rsi_rib_55'] if d1_row is not None else False

                                # 🏛️ DNA v2 KLASMAN
                                dna_sig = get_dna_v2_signature(row_dna_input, h1_ok, h4_ok, d1_ok)
                                coin_dna_manifest = DNA_MANIFEST_V2.get(symbol, {})
                                dna_meta = coin_dna_manifest.get(dna_sig, {'KLAS': 'C'})
                                klasman = dna_meta['KLAS']

                                # 🏛️ STANDART NİZAM: Tüm tetikler tescillensin
                                coin_trigs.append({
                                    'time': ts.strftime('%H:%M'), 
                                    'type': c_type,
                                    'klasman': klasman,
                                    'peak': ((peak_p_21/entry_p)-1)*100, 
                                    # EXIT: Close price at the end of the 21-bar window
                                    'exit_ret': ((df_15m['close'].iloc[min(len(df_15m)-1, idx_f+21)]/entry_p)-1)*100,
                                    'p_21': ((peak_p_21/entry_p)-1)*100,
                                    'p_21_dist': p_21_dist,
                                    'peak_dist': p_21_dist,
                                    'trig_pct': ((entry_p/day_data.iloc[ti]['open'])-1)*100,
                                    'rsi_p': rsi_now, 'rsi_angle': rsi_angle, 
                                    'pos': "🔴" if rsi_now<40 else "🟡" if rsi_now<60 else "🟢" if rsi_now<75 else "🟠",
                                    'ang': "↗️" if (rsi_now-rsi_prev)>0 else "↘️",
                                    'h1_ok': check_trend_ok(h1_m.iloc[0]), 'h4_ok': check_trend_ok(h4_m.iloc[0]),
                                    'next_pct': ((df_15m['close'].iloc[peak_pos_21+1]/peak_p_21)-1)*100 if peak_pos_21+1<len(df_15m) else None,
                                    'nn_pct': ((df_15m['close'].iloc[peak_pos_21+2]/df_15m['close'].iloc[peak_pos_21+1])-1)*100 if peak_pos_21+2<len(df_15m) else None,
                                    'cgs': min(100, max(0, ((peak_p_21/entry_p)-1)*500 / (p_21_dist if p_21_dist > 0 else 1))), 
                                    'adx': d_row['adx14'], 
                                    'atr_adj': d_row['atr_p'], # Synced Daily ATR%
                                    'v100': day_data.iloc[ti]['v100'], 
                                    'v21': day_data.iloc[ti]['v21'], 'v_mom': v_mom,
                                    'v_eff': v_eff, 'v_hyb': v_hyb
                                })
                    if coin_trigs:
                        # Sort triggers by TIME top down (ascending)
                        coin_trigs.sort(key=lambda x: x['time'])
                        # Find best peak of the day for this coin to use as Daily Best
                        best_t = max(coin_trigs, key=lambda x: x['peak'])
                        day_results.append({
                            'symbol': symbol, 
                            'triggers': coin_trigs, 
                            'best_max': best_t['peak'], 
                            'best_exit': best_t['exit_ret']
                        })
                except Exception as e:
                    # print(f"Error processing {symbol} on {day_str}: {e}")
                    continue
                
            if day_results:
                f.write(f"## 📅 {day_str} (Onay-Gruplu: {len(day_results)} Koin)\n")
                f.write("| " + " | ".join(HEADERS) + " |\n")
                f.write("| " + " | ".join(["---"] * len(HEADERS)) + " |\n")
                # Sort coins by their BEST peak of the day (highest to lowest)
                day_results.sort(key=lambda x: x['best_max'], reverse=True)
                g_idx = 1
                for res in day_results:
                    for i, t in enumerate(res['triggers']): 
                        f.write("| " + " | ".join(format_row_v17(g_idx, res['symbol'], t, i, res['best_max'], res['best_exit'])) + " |\n")
                    g_idx += 1
                f.write("\n")
                f.flush()
    print(f"✅ Harekât Raporu Tamamlandı: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_sniper_audit_optimized()
