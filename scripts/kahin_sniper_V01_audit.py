import pandas as pd
import numpy as np
import os
import math
import glob
from datetime import datetime
import warnings
import json

warnings.filterwarnings('ignore', category=FutureWarning)

# 🏛️ V01 CONFIG
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = "2026-01-01"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/V01_RAPOR_KAHIN_SNIPER_2026.md"
KEYS_FILE_V01 = "/Users/alisaglam/TezaverMac/data/V01_dna_keys_2025_A_plus_plus.json"

# 🏛️ V17 STANDART HEADERS
HEADERS = ["NO", "SYM", "MAX", "EXIT", "KLAS", "TIME", "SIG", "TREND", "POS", "ANG", "R-Ang", "VAL", "P", "TIER", "P-21", "BAR", "NEXT", "N-1", "CGS", "ADX", "ATR%", "Vrsi", "VBoy", "V100", "V21", "V-Mom"]

# Load V01 Manifest (Elmaslar)
if os.path.exists(KEYS_FILE_V01):
    with open(KEYS_FILE_V01, 'r') as f:
        V01_MANIFEST = json.load(f)
else:
    V01_MANIFEST = {}

def calculate_rsi(series, period=11):
    delta = series.diff()
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
        df[f'rsi_rib_{p}'] = df['rsi_ema'].ewm(span=p, adjust=False).mean()
    df['rib_max'] = df[[f'rsi_rib_{p}' for p in [20, 55]]].max(axis=1)
    df['rib_min_all'] = df[[f'rsi_rib_{p}' for p in rib_periods]].min(axis=1)
    
    tr = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
    df['tr'] = tr
    
    if not is_daily:
        df['vol_ma100'] = df['volume'].rolling(window=100).mean().replace(0, 1)
        df['vol_ma50'] = df['volume'].rolling(window=50).mean().replace(0, 1)
        df['v_mom'] = df['volume'] / df['vol_ma50']
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
    
    df['atr_p'] = (tr.rolling(14).mean() / df['close']) * 100
    return df

def get_dna_v2_signature(row_15m, h1_ok, h4_ok, d1_ok):
    rsi = row_15m['rsi']
    if rsi <= 35: faz = "DIP"
    elif rsi <= 45: faz = "BIRIKIM"
    elif rsi <= 55: faz = "NOTR"
    elif rsi <= 65: faz = "MOM"
    elif rsi <= 75: faz = "TREND"
    else: faz = "ALIM"
    
    sq_pct = abs(row_15m['rsi_rib_20'] - row_15m['rsi_rib_55']) / (row_15m['rsi_ema'] or 1) * 100
    aks = "TIGHT" if sq_pct <= 0.3 else "MICRO" if sq_pct <= 0.8 else "NORMAL" if sq_pct <= 1.5 else "GAP"
    
    v_hyb = row_15m.get('v_hyb', 0)
    ritim = "NOVA" if v_hyb >= 10 else "SURGE" if v_hyb >= 7 else "READY" if v_hyb >= 4 else "DRY"
    
    v_eff = row_15m.get('v_eff', 0)
    char = "PURE" if v_eff >= 8 else "SOLID" if v_eff >= 5 else "THIN"
    
    ang = row_15m.get('ang_v2', 0)
    a_p = "SHARP" if ang >= 60 else "UP" if ang >= 45 else "FLAT"
    harmony = f"{int(h1_ok)}{int(h4_ok)}{int(d1_ok)}"
    return f"{faz}|{aks}|{ritim}|{char}|{a_p}|{harmony}"

def format_row_v17(idx, symbol, t, row_sub_idx, best_max, best_exit):
    if row_sub_idx == 0:
        p_s = f"<font color='green'>+{best_max:.1f}%</font>"
        e_s = f"<font color='red'>{best_exit:.1f}%</font>" if best_exit < 0 else f"+{best_exit:.1f}%"
        if best_exit >= 10.0: e_s = f"<font color='green'>**{e_s}**</font>"
        elif best_exit >= 5.0: e_s = f"<font color='green'>{e_s}</font>"
    else: p_s, e_s = "", ""

    p21_val = t['p_21']
    tier_icon = "💎" if p21_val >= 30 else "🥇" if p21_val >= 20 else "🥈" if p21_val >= 10 else "🥉" if p21_val >= 5 else ""
    ra_str = f"{t['rsi_angle']:.0f}°"
    ra_f = f"<font color='#00FF00'>**+{ra_str}**</font>" if t['rsi_angle'] >= 45 else f"<font color='green'>+{ra_str}</font>"
    cgs_f = f"<font color='green'>**{t['cgs']:.0f}%**</font>" if t['cgs'] >= 50 else f"<font color='gray'>{t['cgs']:.0f}%</font>"
    adx_f = f"<font color='green'>**{t['adx']:.1f}**</font>" if t['adx'] >= 25 else f"<font color='gray'>{t['adx']:.1f}</font>"
    atr_f = f"<font color='#00FF00'>**{t['atr_adj']:.1f}%**</font>" if t['atr_adj'] >= 4.0 else f"{t['atr_adj']:.1f}%"
    n_s = f"<font color='green'>+{t['next_pct']:.1f}%</font>" if t['next_pct'] and t['next_pct'] > 0 else "---"
    nn_s = f"---"
    ve_f = f"<font color='green'>**{t['v_eff']:.1f}**</font>" if t['v_eff'] >= 7.0 else f"{t['v_eff']:.1f}"
    vh_f = f"<font color='#00FF00'>**{t['v_hyb']:.1f}**</font>" if t['v_hyb'] >= 9.0 else f"{t['v_hyb']:.1f}"
    trend_str = f"{t['h4_ok'] and '🟢' or '🔴'}{t['h1_ok'] and '🟢' or '🔴'}"
    trig_val = f"+{t['trig_pct']:.1f}%"
    p21_f = f"<font color='#00FF00'>**%{p21_val:.1f}**</font>" if p21_val >= 10 else f"%{p21_val:.1f}"
    klas_f = f"<font color='#00FF00'>**A++**</font>"
    
    return [str(idx) if row_sub_idx == 0 else "", symbol if row_sub_idx == 0 else "", p_s, e_s, klas_f, t['time'], f"[V01:{t['type']}]", trend_str, t['pos'], t['ang'], ra_f, "💚", trig_val, tier_icon, p21_f, str(t['p_21_dist']), n_s, nn_s, cgs_f, adx_f, atr_f, vh_f, ve_f, f"{t['v100']:.1f}x", f"{t['v21']:.1f}x", f"{t['v_mom']:.1f}x"]

def run_V01_audit():
    print("🏛️ V01: Altın Elmas Denetim Motoru Başlatılıyor...")
    symbols = sorted([d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))])
    report_data = {}

    for symbol in symbols:
        try:
            print(f"📡 {symbol} süzülüyor...")
            p15m, ph1, ph4, p1d = [f"{COIN_CELLS_DIR}/{symbol}/data/history_{tf}.parquet" for tf in ['15m', '1h', '4h', '1d']]
            if not all(os.path.exists(p) for p in [p15m, ph1, ph4, p1d]): continue
            
            df_15m = get_indicators(pd.read_parquet(p15m).set_index(pd.to_datetime(pd.read_parquet(p15m)['timestamp'], unit='ms')))
            df_h1 = get_indicators(pd.read_parquet(ph1).set_index(pd.to_datetime(pd.read_parquet(ph1)['timestamp'], unit='ms')))
            df_h4 = get_indicators(pd.read_parquet(ph4).set_index(pd.to_datetime(pd.read_parquet(ph4)['timestamp'], unit='ms')))
            df_d = get_indicators(pd.read_parquet(p1d).set_index(pd.to_datetime(pd.read_parquet(p1d)['timestamp'], unit='ms')), is_daily=True)

            coin_manifest = V01_MANIFEST.get(symbol, {})
            if not coin_manifest: continue # Sadece manifestte olan koinler

            df_2026 = df_15m[df_15m.index >= START_DATE].copy()
            if df_2026.empty: continue
            
            # Indicators
            df_15m['rsi_ema_prev'] = df_15m['rsi_ema'].shift(1)
            df_15m['rsi_prev'] = df_15m['rsi'].shift(1)
            
            r_max = df_15m[['rsi_rib_20', 'rsi_rib_55']].max(axis=1)
            r_min = df_15m[['rsi_rib_20', 'rsi_rib_55']].min(axis=1)
            
            cond_rc = (df_15m['rsi_ema'] > r_max) & (df_15m['rsi_ema_prev'] <= r_max.shift(1)) & (r_min > 50)
            cond_60 = (df_15m['rsi_ema'] > 60) & (df_15m['rsi_ema_prev'] <= 60) & (df_15m['rsi_rib_20'] > 50)
            cond_70 = (df_15m['rsi'] > 70) & (df_15m['rsi_ema'] > 70) & (df_15m['rsi'] > df_15m['rsi_ema']) & (df_15m['rsi_prev'] <= 70)
            
            trigger_indices = np.where((cond_rc | cond_60 | cond_70) & (df_15m.index >= START_DATE))[0]
            
            for idx_f in trigger_indices:
                ts = df_15m.index[idx_f]
                row = df_15m.iloc[idx_f]
                
                # DNA
                h1_row = df_h1.loc[df_h1.index.asof(ts)] if not df_h1.index.asof(ts) is pd.NaT else None
                h4_row = df_h4.loc[df_h4.index.asof(ts)] if not df_h4.index.asof(ts) is pd.NaT else None
                d_row = df_d.loc[df_d.index.asof(ts)] if not df_d.index.asof(ts) is pd.NaT else None
                h1_ok = row['close'] > h1_row['rsi_rib_55'] if h1_row is not None else False
                h4_ok = row['close'] > h4_row['rsi_rib_55'] if h4_row is not None else False
                d1_ok = row['close'] > d_row['rsi_rib_55'] if d_row is not None else False
                
                v_hyb = min(15.0, (row['volume'] / row['vol_ma100']) * 2 * (row['rsi'] / 50.0))
                v_eff = (abs(row['close'] - row['open']) / (row['high'] - row['low'] + 1e-9)) * 10
                ang_v2 = np.degrees(np.arctan((row['rsi_ema'] - df_15m['rsi_ema'].iloc[idx_f-3]) / 3.0))

                row_dna = row.copy()
                row_dna['v_hyb'], row_dna['v_eff'], row_dna['ang_v2'] = v_hyb, v_eff, ang_v2
                dna_sig = get_dna_v2_signature(row_dna, h1_ok, h4_ok, d1_ok)
                
                meta = coin_manifest.get(dna_sig)
                if not meta: continue # Sadece A++ Elmaslar

                # Result
                future_21 = df_15m.iloc[idx_f + 1 : idx_f + 22]
                if future_21.empty: continue
                peak_p, peak_idx = future_21['high'].max(), future_21['high'].idxmax()
                p_21_dist = df_15m.index.get_loc(peak_idx) - idx_f
                exit_p = df_15m.iloc[min(len(df_15m)-1, idx_f+21)]['close']
                
                t_ctx = {
                    'time': ts.strftime('%H:%M'),
                    'type': "RC" if cond_rc.iloc[idx_f] else ("60" if cond_60.iloc[idx_f] else "70"),
                    'p_21': ((peak_p / row['close']) - 1) * 100,
                    'exit_ret': ((exit_p / row['close']) - 1) * 100,
                    'peak': ((peak_p / row['close']) - 1) * 100,
                    'p_21_dist': p_21_dist,
                    'trig_pct': ((row['close'] / row['open']) - 1) * 100,
                    'rsi_p': row['rsi_ema'],
                    'rsi_angle': math.degrees(math.atan(row['rsi_ema'] - df_15m['rsi_ema'].iloc[idx_f-1])),
                    'pos': "🔴" if row['rsi_ema']<40 else "🟡" if row['rsi_ema']<60 else "🟢" if row['rsi_ema']<75 else "🟠",
                    'ang': "↗️" if (row['rsi_ema']-df_15m['rsi_ema'].iloc[idx_f-1])>0 else "↘️",
                    'h1_ok': h1_ok, 'h4_ok': h4_ok,
                    'next_pct': ((df_15m.iloc[idx_f+p_21_dist+1]['close']/peak_p)-1)*100 if idx_f+p_21_dist+1 < len(df_15m) else None,
                    'cgs': min(100, max(0, ((peak_p/row['close'])-1)*500 / (p_21_dist if p_21_dist > 0 else 1))),
                    'adx': d_row['adx14'] if d_row is not None else 0,
                    'atr_adj': d_row['atr_p'] if d_row is not None else 0,
                    'v100': row['v100'], 'v21': row['v21'], 'v_mom': row['v_mom'],
                    'v_eff': v_eff, 'v_hyb': v_hyb
                }
                
                date_key = ts.strftime('%Y-%m-%d')
                if date_key not in report_data: report_data[date_key] = []
                report_data[date_key].append({'symbol': symbol, 'trigger': t_ctx})

        except: continue

    # Write Report
    all_dates = sorted(report_data.keys(), reverse=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# 🏛️ V01: 2026 ALTIN ELMAS (A++) HAREKÂT RAPORU\n")
        f.write(f"Rapor Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("> [!IMPORTANT]\n")
        f.write("> Bu rapor V01 nizamıyla (2025 Elmasları / %10+ Kar / Zero-Loss) tescil edilmiştir. 🏛️💎⚖️\n\n")

        for d_key in all_dates:
            day_trigs = report_data[d_key]
            # Group by symbol
            group = {}
            for item in day_trigs:
                s = item['symbol']
                if s not in group: group[s] = []
                group[s].append(item['trigger'])
            
            f.write(f"## 📅 {d_key} (Onaylı: {len(group)} Koin)\n")
            f.write("| " + " | ".join(HEADERS) + " |\n")
            f.write("| " + " | ".join(["---"] * len(HEADERS)) + " |\n")
            
            # Sort symbols by their best peak
            sorted_syms = sorted(group.keys(), key=lambda x: max(t['peak'] for t in group[x]), reverse=True)
            for g_idx, sym in enumerate(sorted_syms, 1):
                best_max = max(t['peak'] for t in group[sym])
                best_exit = max(t['exit_ret'] for t in group[sym]) # simplified
                for i, t in enumerate(group[sym]):
                    f.write("| " + " | ".join(format_row_v17(g_idx, sym, t, i, best_max, best_exit)) + " |\n")
            f.write("\n")
            f.flush()

    print(f"✅ V01 RAPOR TAMAMLANDI: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_V01_audit()
