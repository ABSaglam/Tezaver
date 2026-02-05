import pandas as pd
import numpy as np
import os
import math
import glob
from datetime import datetime
import warnings
import json

warnings.filterwarnings('ignore', category=FutureWarning)

# CONFIG
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = "2026-01-01"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/RAPOR_KAHIN_SNIPER_2026.md"
KEYS_FILE_V2 = "/Users/alisaglam/TezaverMac/data/faz100_dna_keys_V2.json"

# 🏛️ V17 STANDART HEADERS
HEADERS = ["NO", "SYM", "MAX", "EXIT", "KLAS", "TIME", "SIG", "TREND", "POS", "ANG", "R-Ang", "VAL", "P", "TIER", "P-21", "BAR", "NEXT", "N-1", "CGS", "ADX", "ATR%", "Vrsi", "VBoy", "V100", "V21", "V-Mom"]

# Load DNA V2 Manifest
if os.path.exists(KEYS_FILE_V2):
    with open(KEYS_FILE_V2, 'r') as f:
        DNA_MANIFEST_V2 = json.load(f)
else:
    DNA_MANIFEST_V2 = {}

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
    
    df['atr_p'] = (tr.rolling(14).mean() / df['close']) * 100
    return df

def get_dna_v2_signature(row_15m, h1_ok, h4_ok, d1_ok):
    # RSI Fazı
    rsi = row_15m['rsi']
    if rsi <= 35: faz = "DIP"
    elif rsi <= 45: faz = "BIRIKIM"
    elif rsi <= 55: faz = "NOTR"
    elif rsi <= 65: faz = "MOM"
    elif rsi <= 75: faz = "TREND"
    else: faz = "ALIM"
    
    sq_pct = abs(row_15m['rsi_rib_20'] - row_15m['rsi_rib_55']) / (row_15m['rsi_ema'] or 1) * 100
    if sq_pct <= 0.3: aks = "TIGHT"
    elif sq_pct <= 0.8: aks = "MICRO"
    elif sq_pct <= 1.5: aks = "NORMAL"
    else: aks = "GAP"
    
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
        p_s = f"<font color='green'>+{best_max:.1f}%</font>" if best_max >= 10 else f"+{best_max:.1f}%"
        e_s = f"<font color='red'>{best_exit:.1f}%</font>" if best_exit < 0 else f"+{best_exit:.1f}%"
        if best_exit >= 3.0: e_s = f"<font color='green'>**{e_s}**</font>"
        elif best_exit >= 0.5: e_s = f"<font color='green'>{e_s}</font>"
    else: p_s, e_s = "", ""

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
    trend_str = f"{t['h4_ok'] and '🟢' or '🔴'}{t['h1_ok'] and '🟢' or '🔴'}"
    trig_val = f"+{t['trig_pct']:.1f}%" if t['trig_pct'] > 0 else f"{t['trig_pct']:.1f}%"
    sig_label = f"[🏛️KAHİN:{t['type']}]"
    p21_str = f"**%{p21_val:.1f}**"
    p21_f = f"<font color='#00FF00'>**{p21_str}**</font>" if p21_val >= 20 else f"<font color='green'>{p21_str}</font>" if p21_val >= 10 else p21_str
    klas = t.get('klasman', 'C')
    klas_f = f"<font color='#00FF00'>**{klas}**</font>" if 'A' in klas else f"<font color='green'>{klas}</font>" if 'B' in klas else f"<font color='gray'>{klas}</font>"
    
    return [str(idx) if row_sub_idx == 0 else "", symbol if row_sub_idx == 0 else "", p_s, e_s, klas_f, t['time'], sig_label, trend_str, t['pos'], t['ang'], ra_f, "💚", trig_val, tier_icon, p21_f, str(t['p_21_dist']), n_s, nn_s, cgs_f, adx_f, atr_f, vh_f, ve_f, f"{t['v100']:.1f}x", f"{t['v21']:.1f}x", f"{t['v_mom']:.1f}x"]

def run_sniper_audit_altin_vurus():
    print("🏛️ KAHİN: ALTIN VURUŞ (Refactored) Motoru Başlatılıyor...")
    symbols = sorted([d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))])
    
    report_data = {} # date -> list of coin results

    for symbol in symbols:
        try:
            print(f"📡 İşleniyor: {symbol}...")
            p15m, ph1, ph4, p1d = [f"{COIN_CELLS_DIR}/{symbol}/data/history_{tf}.parquet" for tf in ['15m', '1h', '4h', '1d']]
            if not all(os.path.exists(p) for p in [p15m, ph1, ph4, p1d]): continue
            
            df_15m = get_indicators(pd.read_parquet(p15m).set_index(pd.to_datetime(pd.read_parquet(p15m)['timestamp'], unit='ms')))
            df_h1 = get_indicators(pd.read_parquet(ph1).set_index(pd.to_datetime(pd.read_parquet(ph1)['timestamp'], unit='ms')))
            df_h4 = get_indicators(pd.read_parquet(ph4).set_index(pd.to_datetime(pd.read_parquet(ph4)['timestamp'], unit='ms')))
            df_d = get_indicators(pd.read_parquet(p1d).set_index(pd.to_datetime(pd.read_parquet(p1d)['timestamp'], unit='ms')), is_daily=True)

            # Filter 2026 for triggers
            df_triggers = df_15m[df_15m.index >= START_DATE].copy()
            if df_triggers.empty: continue
            
            # Global indicators for shift(1) consistency
            df_15m['rsi_ema_prev'] = df_15m['rsi_ema'].shift(1)
            df_15m['rsi_prev'] = df_15m['rsi'].shift(1)
            
            # Triggers
            cond_rc = (df_15m['rsi_ema'] > df_15m['rib_max']) & (df_15m['rsi_ema_prev'] <= df_15m['rib_max']) & (df_15m['rib_min_all'] > 50)
            cond_60 = (df_15m['rsi_ema'] > 60) & (df_15m['rsi_ema_prev'] <= 60) & (df_15m['rsi_rib_20'] > 50)
            cond_70 = (df_15m['rsi'] > 70) & (df_15m['rsi_ema'] > 70) & ((df_15m['rsi_prev'] <= 70) | (df_15m['rsi_ema_prev'] <= 70))
            
            all_cond = cond_rc | cond_60 | cond_70
            trigger_indices = np.where(all_cond & (df_15m.index >= START_DATE))[0]
            
            coin_trigs_by_date = {}

            for idx_f in trigger_indices:
                ts = df_15m.index[idx_f]
                row = df_15m.iloc[idx_f]
                
                # Results (Future 21)
                future_21 = df_15m.iloc[idx_f + 1 : idx_f + 22]
                if future_21.empty: continue
                
                entry_p = row['close']
                peak_p, peak_idx = future_21['high'].max(), future_21['high'].idxmax()
                p_21_dist = df_15m.index.get_loc(peak_idx) - idx_f
                exit_p = df_15m.iloc[min(len(df_15m)-1, idx_f+21)]['close']
                
                # Features for DNA
                v_hyb = min(15.0, (row['volume'] / row['vol_ma100']) * 2 * (row['rsi'] / 50.0))
                v_eff = (abs(row['close'] - row['open']) / (row['high'] - row['low'] + 1e-9)) * 10
                ang_v2 = np.degrees(np.arctan((row['rsi_ema'] - df_15m['rsi_ema'].iloc[max(0, idx_f-3)]) / 3.0))

                # Harmony
                h1_row = df_h1.loc[df_h1.index.asof(ts)] if not df_h1.index.asof(ts) is pd.NaT else None
                h4_row = df_h4.loc[df_h4.index.asof(ts)] if not df_h4.index.asof(ts) is pd.NaT else None
                d_row = df_d.loc[df_d.index.asof(ts)] if not df_d.index.asof(ts) is pd.NaT else None
                
                h1_ok = entry_p > h1_row['rsi_rib_55'] if h1_row is not None else False
                h4_ok = entry_p > h4_row['rsi_rib_55'] if h4_row is not None else False
                d1_ok = entry_p > d_row['rsi_rib_55'] if d_row is not None else False
                
                # DNA Signature
                row_dna = row.copy()
                row_dna['v_hyb'], row_dna['v_eff'], row_dna['ang_v2'] = v_hyb, v_eff, ang_v2
                dna_sig = get_dna_v2_signature(row_dna, h1_ok, h4_ok, d1_ok)
                klas = DNA_MANIFEST_V2.get(symbol, {}).get(dna_sig, {'KLAS': 'C'})['KLAS']
                
                t_ctx = {
                    'time': ts.strftime('%H:%M'),
                    'type': "RC" if cond_rc.iloc[idx_f] else ("60" if cond_60.iloc[idx_f] else "70"),
                    'klasman': klas,
                    'p_21': ((peak_p / entry_p) - 1) * 100,
                    'exit_ret': ((exit_p / entry_p) - 1) * 100,
                    'peak': ((peak_p / entry_p) - 1) * 100,
                    'p_21_dist': p_21_dist,
                    'trig_pct': ((entry_p / row['open']) - 1) * 100,
                    'rsi_p': row['rsi_ema'],
                    'rsi_angle': math.degrees(math.atan(row['rsi_ema'] - df_15m['rsi_ema'].iloc[idx_f-1])),
                    'pos': "🔴" if row['rsi_ema']<40 else "🟡" if row['rsi_ema']<60 else "🟢" if row['rsi_ema']<75 else "🟠",
                    'ang': "↗️" if (row['rsi_ema']-df_15m['rsi_ema'].iloc[idx_f-1])>0 else "↘️",
                    'h1_ok': h1_ok, 'h4_ok': h4_ok,
                    'next_pct': ((df_15m.iloc[idx_f+p_21_dist+1]['close']/peak_p)-1)*100 if idx_f+p_21_dist+1 < len(df_15m) else None,
                    'nn_pct': ((df_15m.iloc[idx_f+p_21_dist+2]['close']/df_15m.iloc[idx_f+p_21_dist+1]['close'])-1)*100 if idx_f+p_21_dist+2 < len(df_15m) else None,
                    'cgs': min(100, max(0, ((peak_p/entry_p)-1)*500 / (p_21_dist if p_21_dist > 0 else 1))),
                    'adx': d_row['adx14'] if d_row is not None else 0,
                    'atr_adj': d_row['atr_p'] if d_row is not None else 0,
                    'v100': row['v100'], 'v21': row['v21'], 'v_mom': row['v_mom'],
                    'v_eff': v_eff, 'v_hyb': v_hyb
                }
                
                date_key = ts.strftime('%Y-%m-%d')
                if date_key not in coin_trigs_by_date: coin_trigs_by_date[date_key] = []
                coin_trigs_by_date[date_key].append(t_ctx)

            for date_key, trigs in coin_trigs_by_date.items():
                if date_key not in report_data: report_data[date_key] = []
                best_t = max(trigs, key=lambda x: x['peak'])
                report_data[date_key].append({
                    'symbol': symbol,
                    'triggers': trigs,
                    'best_max': best_t['peak'],
                    'best_exit': best_t['exit_ret']
                })
        except Exception as e:
            # print(f"Error {symbol}: {e}")
            continue

    # Final Report Write
    all_dates = sorted(report_data.keys(), reverse=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# 🏛️ KAHİN: 2026 ALTIN VURUŞ HAREKÂT RAPORU\n")
        f.write(f"Rapor Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("> [!IMPORTANT]\n")
        f.write("> Bu döküm 'Altın Vuruş' nizamıyla (Saf Sinyal + DNA v2 Rütbeli) süzülmüştür. 🏛️💎⚖️\n\n")

        for date_key in all_dates:
            day_results = report_data[date_key]
            f.write(f"## 📅 {date_key} (Onay-Gruplu: {len(day_results)} Koin)\n")
            f.write("| " + " | ".join(HEADERS) + " |\n")
            f.write("| " + " | ".join(["---"] * len(HEADERS)) + " |\n")
            day_results.sort(key=lambda x: x['best_max'], reverse=True)
            for g_idx, res in enumerate(day_results, 1):
                for i, t in enumerate(res['triggers']):
                    f.write("| " + " | ".join(format_row_v17(g_idx, res['symbol'], t, i, res['best_max'], res['best_exit'])) + " |\n")
            f.write("\n")
            
    print(f"✅ Harekât Raporu Tamamlandı: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_sniper_audit_altin_vurus()
