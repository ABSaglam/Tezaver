import pandas as pd
import numpy as np
import os
import json
import re
import math
from datetime import datetime

# CONFIG
START_DATE = pd.Timestamp("2025-10-16")
END_DATE = pd.Timestamp("2026-02-28")
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

def strip_tags(s):
    return re.sub(r'<[^>]+>', '', str(s))

def format_cell(val, width):
    s = str(val)
    content_len = len(strip_tags(s))
    padding = max(0, width - content_len)
    return " " + s + " " * padding + " "

def write_aligned_table(f, rows, headers):
    if not rows: return
    
    # Calculate widths based on VISIBLE string length (stripping HTML)
    col_widths = [len(h) for h in headers]
    for r in rows:
        for i, val in enumerate(r):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(strip_tags(str(val))))
    
    # Header
    header_line = "|"
    sep_line = "|"
    for i, h in enumerate(headers):
        header_line += format_cell(h, col_widths[i]) + "|"
        sep_line += "-" * (col_widths[i] + 2) + "|"
    
    f.write(header_line + "\n")
    f.write(sep_line + "\n")
    
    # Rows
    for r in rows:
        row_line = "|"
        for i, val in enumerate(r):
            if i < len(col_widths):
                row_line += format_cell(val, col_widths[i]) + "|"
        f.write(row_line + "\n")

def classify_dna(dna):
    if not dna or dna == "neutral": return "YENİ/BELİRSİZ"
    parts = dna.split('|')
    faz = parts[0].replace('_', ' ').title()
    harm = parts[2].replace('harmony_', '')
    return f"{faz} ({harm})"

def get_profile_simple(day, df_w, df_h1, df_d, df_h4):
    try:
        sub_w = df_w[df_w.index <= day].tail(30)
        if sub_w.empty: return "neutral"
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
        
        sub_h1_24 = df_h1[df_h1.index <= day].tail(24)
        if sub_h1_24.empty or 'ema9' not in sub_h1_24: return "neutral"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        
        sub_d = df_d[df_d.index <= day]
        sub_h4 = df_h4[df_h4.index <= day]
        sub_h1_sub = df_h1[df_h1.index <= day]
        if sub_d.empty or sub_h4.empty or sub_h1_sub.empty: return "neutral"
        
        s = int(sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21']) + int(sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21']) + int(sub_h1_sub.iloc[-1]['close']>sub_h1_sub.iloc[-1]['ema21'])
        harm = f"harmony_L{s}"
        
        sub_d_tail = sub_d.tail(10)
        vol_p = sub_d.iloc[-1]['volume'] / (sub_d_tail['volume'].mean()+1)
        ritim = "ignited" if vol_p > 2.0 else "active" if vol_p > 1.0 else "sleeping"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
        retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
        ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except: return "neutral"

def run_audit():
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    all_passed_days = []
    processed_pairs = set()

    for symbol in symbols:
        try:
            key_path = f"/Users/alisaglam/TezaverMac/data/golden_keys/{symbol}_key.json"
            if not os.path.exists(key_path): continue
            with open(key_path, "r") as f:
                golden_dna_list = set(json.load(f).get('golden_dna_list', []))
            
            def load_clean(path):
                df = pd.read_parquet(path)
                df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('dt', inplace=True)
                df = df[~df.index.duplicated(keep='last')]
                return df.sort_index()

            df_1d = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
            df_4h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
            df_1h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
            df_1w = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")
            df_15m = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet")

            df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
            df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
            for p in [9, 21, 50]: df_1h[f'ema{p}'] = df_1h['close'].ewm(span=p, adjust=False).mean()

            delta = df_15m['close'].diff()
            alpha = 1 / 11
            gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
            df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
            df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
            
            ribbon_periods = [20, 25, 30, 35, 40, 45, 50, 55]
            rsi_ribbon_cols = []
            for p in ribbon_periods:
                # TradingView'deki 'RSI-based MA' (Double Smooth) yapısı
                df_15m[f'rsi_rib_{p}'] = df_15m['rsi_ema'].ewm(span=p, adjust=False).mean()
                rsi_ribbon_cols.append(f'rsi_rib_{p}')
            
            ema12 = df_15m['close'].ewm(span=12, adjust=False).mean()
            ema26 = df_15m['close'].ewm(span=26, adjust=False).mean()
            df_15m['macd_hist'] = (ema12 - ema26) - (ema12 - ema26).ewm(span=9, adjust=False).mean()
            tr = np.maximum(df_15m['high'] - df_15m['low'], np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)), abs(df_15m['low'] - df_15m['close'].shift(1))))
            df_15m['atr100'] = tr.rolling(window=100).mean()
            df_15m['atr21'] = tr.rolling(window=21).mean()
            df_15m['atr14'] = tr.rolling(window=14).mean()
            df_15m['tr'] = tr

            current = START_DATE
            while current <= END_DATE:
                try:
                    pair_key = (symbol, current)
                    if pair_key in processed_pairs:
                        current += pd.Timedelta(days=1); continue

                    dna = get_profile_simple(current, df_1w, df_1h, df_1d, df_4h)
                    if dna not in golden_dna_list:
                        current += pd.Timedelta(days=1); continue

                    current_utc = current.normalize()
                    day_mask = (df_15m.index.normalize() == current_utc)
                    target_day_data = df_15m[day_mask]
                    if target_day_data.empty:
                        current += pd.Timedelta(days=1); continue

                    open_p, max_h, close_p = target_day_data.iloc[0]['open'], target_day_data['high'].max(), target_day_data.iloc[-1]['close']
                    
                    # Tüm tetik indekslerini önceden saptanması (Aralık Tepe kuralı için)
                    rsi_vals = df_15m['rsi'].values
                    all_trigger_indices = np.where((rsi_vals[:-1] <= 70) & (rsi_vals[1:] > 70))[0] + 1
                    
                    trigger_events = []
                    day_indices = np.where(day_mask)[0]
                    for i in day_indices:
                        if i < 21: continue
                        
                        # Check if this index is a trigger (Std)
                        is_trigger = i in all_trigger_indices
                        if is_trigger:
                            # Macro Trend (4H & 1H)
                            trig_time = df_15m.index[i]
                            
                            # 4H Trend
                            last_4h = df_4h[df_4h.index <= trig_time]
                            t4 = "🟢" if not last_4h.empty and last_4h.iloc[-1]['close'] > last_4h.iloc[-1]['ema21'] else "🔴"
                            
                            # 1H Trend
                            last_1h = df_1h[df_1h.index <= trig_time]
                            t1 = "🟢" if not last_1h.empty and last_1h.iloc[-1]['close'] > last_1h.iloc[-1]['ema21'] else "🔴"
                            
                            
                            m_tr = f"{t4}{t1}"

                            # Bir sonraki tetiği bul (Aralık Tepe Sınırı)
                            next_triggers = all_trigger_indices[all_trigger_indices > i]
                            next_t_idx = next_triggers[0] if len(next_triggers) > 0 else len(df_15m)
                            
                            # Arama sınırı: En fazla 21 bar VEYA bir sonraki tetiğe kadar
                            search_limit = min(i + 22, next_t_idx) 
                            
                            h_t, h_p = df_15m['macd_hist'].values[i], df_15m['macd_hist'].values[i-1]
                            mac_c = "🟢" if h_t > 0 and h_t > h_p else "🟣" if h_t > 0 else "🔴" if h_t < h_p else "🟡"
                            
                            # Hacim Analizi Verileri
                            v_t, v_p = df_15m['volume'].values[i], df_15m['volume'].values[i-1] or 0.001
                            v_a21 = np.mean(df_15m['volume'].values[i-21:i]) or 0.001
                            v_a5 = np.mean(df_15m['volume'].values[i-5:i]) or 0.001
                            
                            # 1. Vol-Trend: Son 5 barın genel 21 bara göre ivmesi
                            v_trend = (v_a5 / v_a21)
                            
                            # 2. Vol-Spread: Hacim başına üretilen fiyat hareketi (Efficiency)
                            # TR (True Range) / Hacim -> 1M hacim başına ne kadar % hareket üretildi
                            price_range = df_15m['tr'].values[i]
                            v_spread = (price_range / (v_t or 0.001)) * 1000000 # Normalize çarpan
                            
                            v_idx = min(10.0, (df_15m['tr'].values[i] / (df_15m['atr100'].values[i] or 0.001)) * 3.33)
                            
                            # 1. V-Dyn (Dinamik Hafıza): ATR 21 üzerinden
                            v_dyn = min(10.0, (df_15m['tr'].values[i] / (df_15m['atr21'].values[i] or 0.001)) * 3.33)
                            
                            # 2. V-Mom (İvme): Son 3 bardaki V-Idx ortalamasına göre değişim
                            past_vidx = []
                            for k in range(1, 4):
                                if i-k >= 0:
                                    p_tr = df_15m['tr'].values[i-k]
                                    p_atr = df_15m['atr100'].values[i-k] or 0.001
                                    past_vidx.append((p_tr/p_atr)*3.33)
                            avg_past_vidx = np.mean(past_vidx) if past_vidx else 0.001
                            v_mom = (v_idx / avg_past_vidx) if avg_past_vidx > 0 else 0
                            
                            # 3. V-Eff (Efficiency): Mum Gövdesi / Mum Boyu (0-10)
                            body_size = abs(df_15m['close'].values[i] - df_15m['open'].values[i])
                            candle_range = df_15m['tr'].values[i] or 0.001
                            v_eff = (body_size / candle_range) * 10.0
                            
                            # 4. V-Hyb (Rsi Hibrit): V-Idx * (RSI Gücü)
                            rsi_power = df_15m['rsi'].values[i] / 50.0 # 50=1x, 70=1.4x
                            v_hyb = min(15.0, v_idx * rsi_power)
                            
                            # Aralıktaki tepeyi (ENTRY SONRASI) ve o tepeye ulaşma süresini (bar) bul
                            # Fix: Start from i+1 to avoid "Phantom Wick" profit
                            if i + 1 < len(df_15m):
                                val_slice = df_15m['high'].values[i + 1 : search_limit + 1]
                                if len(val_slice) > 0:
                                    peak_idx_rel = np.argmax(val_slice)
                                    peak_p = val_slice[peak_idx_rel]
                                    peak_dist = peak_idx_rel + 1 # +1 because we started from i+1
                                else:
                                    peak_p = df_15m['close'].values[i]
                                    peak_dist = 0
                            else:
                                peak_p = df_15m['close'].values[i]
                                peak_dist = 0
                            
                            is_new = (dna == "neutral")
                            strat_signal = "🚀" if v_idx >= 7.0 and (v_t/v_p > 11 or v_t/v_a21 > 11) else ""
                            if is_new:
                                strat_signal += "🆕"

                            is_stuck = df_15m['close'].values[i] < open_p
                            is_limited = (next_t_idx - i <= 21) # Ali Bey'in talimatı: 21 bar dolmadan yeni tetik var mı?

                            # NEXT Candle Analysis (Peak + 1)
                            next_idx = i + peak_dist + 1
                            if next_idx < len(df_15m):
                                n_o = df_15m['open'].values[next_idx]
                                n_c = df_15m['close'].values[next_idx]
                                # Yeni Mantık (Ali Bey Revizyonu): Zirveye (High) göre değişim
                                next_pct = ((n_c - peak_p) / peak_p) * 100
                            else:
                                next_pct = None
                            
                            # Trigger Candle Size (Fix: Use specific candle open, not day open)
                            candle_open = df_15m['open'].values[i]
                            trig_pct = ((df_15m['close'].values[i] - candle_open) / candle_open) * 100

                            # RIBBON ANGLE (Eğim) Analizi - Görsel Senkronizasyon
                            # Sadece son barın akış yönüne (anlık eğim) bakıyoruz.
                            # DINAMIK RIBBON KAYNAĞI ve İKON SEÇİMİ (EMA 20 vs EMA 55)
                            # Kural: Hangisi üstteyse (daha büyükse) referans o olacak.
                            val_20 = df_15m['rsi_rib_20'].values[i]
                            val_55 = df_15m['rsi_rib_55'].values[i]
                            
                            val_20_prev = df_15m['rsi_rib_20'].values[i-1] if i>=1 else val_20
                            val_55_prev = df_15m['rsi_rib_55'].values[i-1] if i>=1 else val_55
                            
                            if val_20 > val_55:
                                # EMA 20 Üstte -> YEŞİL (Boğa/Güçlü)
                                curr_v = val_20
                                prev_v = val_20_prev
                                src_icon = "🟢"
                            else:
                                # EMA 55 Üstte -> KIRMIZI (Ayı/Direnç)
                                curr_v = val_55
                                prev_v = val_55_prev
                                src_icon = "🔴"


                            # EĞİM ve PUAN HESABI
                            if i >= 1:
                                slope = (curr_v - prev_v) / 2.0
                                angle_deg = math.degrees(math.atan(slope))
                            else:
                                angle_deg = 0.0

                            # SAYISAL SKALA (0-10)
                            ang_score = angle_deg / 4.5
                            
                            # FORMATLAMA
                            # VAL (Kalp) Sütunu: Kaynağı gösterir (❤️ EMA 20, 💚 EMA 55)
                            # ANG Sütunu: Eğimi gösterir (Yeşil/Kırmızı Sayı)
                            val_str = f"{ang_score:+.1f}"
                            num_color = "green" if ang_score >= 0 else "red"
                            
                            # İkon Seçimi - Kalp Seti
                            # Kırmızı Ribbon (EMA 20) Üstteyse: ❤️
                            # Yeşil Ribbon (EMA 55) Üstteyse: 💚
                            # Şimdilik ana mantık bu ikisi. İleride sarı/siyah/altın eklenebilir.
                            src_heart = "❤️" if src_icon == "🔴" else "💚"
                            
                            # HTML Oluşturma (Sadece Sayı)
                            if abs(ang_score) > 5.0:
                                ang_e = f"<font color='{num_color}'>**{val_str}**</font>"
                            else:
                                ang_e = f"<font color='{num_color}'>{val_str}</font>"

                            # POS (Konum) İkonu - Renk Paleti Uyumu (5 Renk: Siyah, Kırmızı, Sarı, Yeşil, Altın)
                            # Kaynak: 'curr_v' (O anki lider ribbon değeri)
                            # Set: ⚫ (Siyah) -> 🔴 (Kırmızı) -> 🟡 (Sarı) -> 🟢 (Yeşil) -> 🟠 (Turuncu/Altın)
                            # Bu set hem görünürlük garantilidir hem de kullanıcının renk paletine uyar.
                            if curr_v < 30:
                                pos_icon = "⚫" # Siyah (Dip)
                            elif curr_v < 50:
                                pos_icon = "🔴" # Kırmızı (Alt Bölge)
                            elif curr_v < 60:
                                pos_icon = "🟡" # Sarı (Geçiş/Orta)
                            elif curr_v < 70:
                                pos_icon = "🟢" # Yeşil (Güçlü)
                            else:
                                pos_icon = "🟠" # Turuncu/Altın (Zirve)

                            trigger_events.append({
                                'time': df_15m.index[i].strftime("%H:%M"), 'mac_color': mac_c, 'v_index': v_idx,
                                'strat': strat_signal,
                                # RSI-EMA Ribbon'ın tamamen üstünde mi? (Orijinal Mantık)
                                'rsi_rib': "Yes" if all(df_15m['rsi_ema'].values[i] > df_15m[c].values[i] for c in rsi_ribbon_cols) else "",
                                'v_ch': ((v_t/v_p)-1)*100, 'v_avg': ((v_t/v_a21)-1)*100, 'v_trend': v_trend, 'v_spread': v_spread,
                                'peak': ((peak_p/df_15m['close'].values[i])-1)*100,
                                'peak_dist': peak_dist,
                                'is_stuck': is_stuck,
                                'is_limited': is_limited,
                                'peak_price': peak_p,
                                'open_price': open_p,
                                'v_dyn': v_dyn, 'v_mom': v_mom, 'v_eff': v_eff, 'v_hyb': v_hyb,
                                'm_tr': m_tr,
                                'next_pct': next_pct,
                                'trig_pct': trig_pct,
                                'trig_pct': trig_pct,
                                'ang_emoji': ang_e,
                                'val_icon': src_heart,
                                'pos_icon': pos_icon,
                                'ang_val': angle_deg
                            })

                    all_passed_days.append({
                        'date': current, 'symbol': symbol, 'dna': dna, 'peak': ((max_h/open_p)-1)*100, 'ret': ((close_p/open_p)-1)*100,
                        'triggers': trigger_events,
                        'is_stuck_day': (close_p < open_p),
                        'prio': min([{"🟢":1,"🟣":2,"🟡":3,"🔴":4}.get(t['mac_color'],5) for t in trigger_events]) if trigger_events else 5
                    })
                    processed_pairs.add(pair_key)
                except Exception as e:
                    print(f"Error processing {symbol}: {e}")
                current += pd.Timedelta(days=1)
        except: continue

    df = pd.DataFrame(all_passed_days)
    if df.empty: return print("Boş Rapor.")
    df['frek'] = df.groupby(['date', 'dna'])['symbol'].transform('count')
    df.sort_values(by=['date', 'prio', 'peak'], ascending=[True, True, False], inplace=True)

    # Save to file
    with open("refined_global_report_v16.md", "w", encoding="utf-8") as f:
        f.write("# TEZAVER GLOBAL AUDIT REPORT (REFINED v16)\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        months = {1:"Ocak", 2:"Şubat", 3:"Mart", 4:"Nisan", 5:"Mayıs", 6:"Haziran", 7:"Temmuz", 8:"Ağustos", 9:"Eylül", 10:"Ekim", 11:"Kasım", 12:"Aralık"}
        curr_d = None
        day_rows = []
        for _, r in df.iterrows():
            d_str = f"{r['date'].day:02d} {months[r['date'].month]} {r['date'].year}"
            if d_str != curr_d:
                # Flush previous day
                if curr_d is not None and day_rows:
                     hdrs = ["NO", "SYM", "MAX", "CLOSE", "TIME", "SIG", "TREND", "POS", "ANG", "VAL", "P", "P-21", "BAR", "NEXT", "R-Rib", "Vrsi", "V100", "V21", "V-Mom", "VBoy", "V-Ch", "V-Avg"]
                     write_aligned_table(f, day_rows, hdrs)
                     day_rows = []

                f.write(f"\n## 📅 {d_str} (Geçen: {len(df[df['date']==r['date']])} Kalan: {len(df[(df['date']==r['date']) & (df['prio']<5)])})\n")
                curr_d, idx = d_str, 1
                day_rows = []

            p_s = f"<font color='green'>+{r['peak']:.1f}%</font>" if r['peak']>10 else f"+{r['peak']:.1f}%"
            c_s = f"<font color='red'>{r['ret']:.1f}%</font>" if r['ret']<0 else f"+{r['ret']:.1f}%"
            is_new = (r['dna'] == "neutral")
            
            # Ali Bey'in talimatı: Yeni koinleri ve tetiksiz koinleri gizle
            if is_new or not r['triggers']:
                continue
            
            # Stuck Filtresi: Tamamı ⛔ olanları gizle
            if all(t['is_stuck'] for t in r['triggers']):
                continue
            
            # Koin tecrübeli ve tetikliyse dökümü yap (⛔ uyarısı dahil)
            for i, t in enumerate(r['triggers']):
                # Vol-Change Renk Mantığı
                v_ch_val = t['v_ch']
                if v_ch_val > 1000:
                    v_c = f"<font color='green'>+{v_ch_val:.1f}%</font>"
                elif v_ch_val > 500:
                    v_c = f"<font color='orange'>+{v_ch_val:.1f}%</font>"
                else:
                    v_c = f"+{v_ch_val:.1f}%"

                # Vol-Avg Renk Mantığı
                v_avg_val = t['v_avg']
                if v_avg_val > 1000:
                    v_a = f"<font color='green'>+{v_avg_val:.1f}%</font>"
                elif v_avg_val > 500:
                    v_a = f"<font color='orange'>+{v_avg_val:.1f}%</font>"
                else:
                    v_a = f"+{v_avg_val:.1f}%"
                    
                # V-Index Renk Skalası (0-10 Dürüstlük)
                v_index = t['v_index']
                v_idx_s = f"{v_index:.1f}"
                if v_index >= 10.0:
                    v_i = f"<font color='#00FF00'>**{v_idx_s}**</font>"
                elif v_index >= 8.0:
                    v_i = f"<font color='green'>{v_idx_s}</font>"
                elif v_index >= 4.0:
                    v_i = v_idx_s
                elif v_index >= 2.0:
                    v_i = f"<font color='gray'>{v_idx_s}</font>"
                else:
                    v_i = f"<font color='#888888'>{v_idx_s}</font>"

                # V-Trend Renk Mantığı (İvme)
                vt_v = t['v_trend']
                if vt_v > 2.0: vt_s = f"<font color='green'>**{vt_v:.1f}x**</font>"
                elif vt_v > 1.2: vt_s = f"<font color='green'>{vt_v:.1f}x</font>"
                elif vt_v < 0.8: vt_s = f"<font color='red'>{vt_v:.1f}x</font>"
                else: vt_s = f"{vt_v:.1f}x"

                # V-Spread (Verimlilik)
                vs_v = t['v_spread']
                if vs_v > 50: vs_s = f"⚡ {vs_v:.1f}"
                elif vs_v < 10: vs_s = f"🐢 {vs_v:.1f}"
                else: vs_s = f"{vs_v:.1f}"
                    
                # P-21 Renk Skalası (Basitleştirilmiş: Sadece Artı/Eksi)
                pk_val = t['peak']
                
                if pk_val < 0:
                    pk = f"<font color='red'>{pk_val:.1f}%</font>" # Negatif = Kırmızı
                elif pk_val > 0:
                    pk = f"<font color='green'>+{pk_val:.1f}%</font>" # Pozitif = Yeşil
                else:
                    pk = f"0.0%"
                
                # BAR: İnterval Sinyali (Kısıtlı Aralık = Mavi, 0 = Kırmızı Bold)
                bar_val = str(t['peak_dist'])
                if t['peak_dist'] == 0:
                     bar_val = f"<font color='red'>**0**</font>"
                elif t['is_limited']:
                    bar_val = f"<font color='blue'>{bar_val}</font>"
                
                s1_val = t['strat']
                s2_val = "⛔" if t['is_stuck'] else ""
                sig_val = f"{s1_val}{s2_val}"
                
                # V-Dyn Renk
                vd_s = f"{t['v_dyn']:.1f}"
                if t['v_dyn'] >= 8.0: vd_f = f"<font color='green'>**{vd_s}**</font>"
                else: vd_f = vd_s
                
                # V-Mom Renk
                vm_s = f"{t['v_mom']:.1f}x"
                if t['v_mom'] > 1.5: vm_f = f"<font color='green'>**{vm_s}**</font>"
                else: vm_f = vm_s
                
                # V-Eff Renk
                ve_s = f"{t['v_eff']:.1f}"
                if t['v_eff'] >= 7.0: ve_f = f"<font color='green'>**{ve_s}**</font>" # Dolu mum
                elif t['v_eff'] < 3.0: ve_f = f"<font color='red'>{ve_s}</font>" # Doji/Fitil
                else: ve_f = ve_s
                
                # V-Hyb Renk
                vh_s = f"{t['v_hyb']:.1f}"
                if t['v_hyb'] >= 10.0: vh_f = f"<font color='#00FF00'>**{vh_s}**</font>"
                elif t['v_hyb'] >= 7.0: vh_f = f"<font color='green'>{vh_s}</font>"
                else: vh_f = vh_s

                # Prepare for Aligned Table
                # NEXT
                next_val = "-"
                if t['next_pct'] is not None:
                    nv = t['next_pct']
                    nv_abs = abs(nv)
                    
                    # Format String
                    if nv > 0: val_str = f"+{nv:.1f}%"
                    elif nv < 0: val_str = f"{nv:.1f}%"
                    else: val_str = "0.0%"
                    
                    # Logit: Bold if > 10%
                    if nv_abs > 10.0:
                        val_str = f"**{val_str}**"
                    
                    # Color Mapping
                    if nv > 0: next_val = f"<font color='green'>{val_str}</font>"
                    elif nv < 0: next_val = f"<font color='red'>{val_str}</font>"
                    else: next_val = val_str
                
                # R-Rib (RSI Ribbon Check) - Buton Style (Emoji)
                if t['rsi_rib'] == "Yes":
                    r_rib = "🟢"
                else:
                    r_rib = "🔴"
                
                # P (Trigger Size)
                tp = t['trig_pct']
                tp_str = f"+{tp:.1f}%" if tp > 0 else f"{tp:.1f}%"
                
                if abs(tp) > 20.0:
                    trig_val = f"<font color='red'>**{tp_str}**</font>"
                elif abs(tp) > 10.0:
                    trig_val = f"<font color='red'>{tp_str}</font>"
                else:
                    trig_val = tp_str # Black/Default

                # Headers: NO, SYM, MAX, CLOSE, TIME, SIG, TREND, R-Rib, SRC, ANG, P, P-21, BAR, NEXT, ...
                if i==0:
                    row = [
                        str(idx), r['symbol'], p_s, c_s, 
                        t['time'], sig_val, t['m_tr'], t['pos_icon'], t['ang_emoji'], t['val_icon'], trig_val, pk, bar_val, next_val, r_rib,
                        vh_f, v_i, vd_f, vm_f, ve_f, v_c, v_a
                    ]
                else:
                    row = [
                        "", "", "", "",
                        t['time'], sig_val, t['m_tr'], t['pos_icon'], t['ang_emoji'], t['val_icon'], trig_val, pk, bar_val, next_val, r_rib,
                        vh_f, v_i, vd_f, vm_f, ve_f, v_c, v_a
                    ]
                day_rows.append(row)
            
            idx += 1
            
        # Flush last day
        # Flush last day
        if curr_d is not None and day_rows:
             hdrs = ["NO", "SYM", "MAX", "CLOSE", "TIME", "SIG", "TREND", "POS", "ANG", "VAL", "P", "P-21", "BAR", "NEXT", "R-Rib", "Vrsi", "V100", "V21", "V-Mom", "VBoy", "V-Ch", "V-Avg"]
             write_aligned_table(f, day_rows, hdrs)

    print("Rapor: refined_global_report_v16.md")

if __name__ == "__main__":
    run_audit()
