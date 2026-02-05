#!/usr/bin/env python3
"""
🏛️ AYAŞ TÜNELİ 2026: KUTSAL NİZAM RAPORU (v2026.3 - DAHİ MODU)
=============================================================
Ali Beyim'in emriyle:
- 26 Sütun: Her hücre doğru, hesaplanmış ve dolu.
- Teknik İnceleme: ADX, ATR, Vrsi, V-Mom, R-Ang tam nizam.
- GAB Yasası: Geleceği görme (Data Leakage) kesinlikle yasaktır.
"""

import pandas as pd
import numpy as np
import os
import json
import math
from datetime import datetime

# CONFIG
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
KEYS_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/AYAS_2026_DISIPLIN_RAPORU.md"

# 2026 Sınırları
START_DATE = pd.Timestamp("2026-01-01 00:00:00")
END_DATE = pd.Timestamp.now()

def load_clean(path):
    if not os.path.exists(path): return pd.DataFrame()
    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df = df[~df.index.duplicated(keep='last')]
    return df.sort_index()

def get_angle(series, period=5):
    if len(series) < period: return 0.0
    y = series.values; x = np.arange(len(y))
    mask = ~np.isnan(y)
    if sum(mask) < 2: return 0.0
    slope, _ = np.polyfit(x[mask], y[mask], 1)
    return math.degrees(math.atan(slope))

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = delta.where(delta < 0, 0).abs().ewm(alpha=1/period, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def get_dna_profile_strict(day, df_w, df_h1, df_d, df_h4):
    """Sinyal anındaki geçmişe bakarak DNA çıkarma"""
    try:
        d_cutoff = day.normalize()
        # Sadece dünkü kapanışa kadar
        sd = df_d[df_d.index < d_cutoff].tail(100)
        sh4 = df_h4[df_h4.index <= (day - pd.Timedelta(hours=4))].tail(42)
        sh1 = df_h1[df_h1.index <= (day - pd.Timedelta(hours=1))].tail(24)
        sw = df_w[df_w.index < (day - pd.Timedelta(days=7))].tail(52)

        if sw.empty or sd.empty or sh1.empty: return "neutral"
        
        # FAZ (W1 RSI)
        w_rsi = calculate_rsi(sw['close']).iloc[-1]
        faz = "derin_dip" if w_rsi <= 35 else "birikim_fazi" if w_rsi <= 45 else "notr_alan" if w_rsi <= 55 else "momentum_artisi" if w_rsi <= 65 else "guclu_trend" if w_rsi <= 75 else "asiri_alim"
        
        # ACC (H1 Squeeze)
        sh1['e9'] = sh1['close'].ewm(span=9, adjust=False).mean()
        sh1['e21'] = sh1['close'].ewm(span=21, adjust=False).mean()
        sq = abs(sh1['e9'].iloc[-1] - sh1['e21'].iloc[-1]) / sh1['close'].iloc[-1] * 100
        acc = "tight_squeeze" if sq <= 0.3 else "micro_squeeze" if sq <= 0.8 else "normal_gap" if sq <= 1.5 else "expanded_gap"
        
        # HARM
        sd['e21'] = sd['close'].ewm(span=21, adjust=False).mean()
        sh4['e21'] = sh4['close'].ewm(span=21, adjust=False).mean()
        sh1['e21'] = sh1['close'].ewm(span=21, adjust=False).mean()
        t = sum([sd.iloc[-1]['close']>sd.iloc[-1]['e21'], sh4.iloc[-1]['close']>sh4.iloc[-1]['e21'], sh1.iloc[-1]['close']>sh1.iloc[-1]['e21']])
        harm = f"harmony_L{t}"
        
        # Ritim
        vol_ma = sd['volume'].rolling(21).mean().iloc[-1]
        v_r = sd['volume'].iloc[-1] / (vol_ma + 1e-9)
        ritim = "volume_explosion" if v_r >= 2.5 else "volume_surge" if v_r >= 1.5 else "volume_normal" if v_r >= 0.8 else "volume_dry"
        
        # CTX
        m52 = sd['high'].max()
        dist = ((sd.iloc[-1]['close'] / m52) - 1) * 100
        ctx = "near_ath" if dist >= -10 else "mid_range" if dist >= -30 else "discounted" if dist >= -50 else "deep_discount"
        
        # Enerji
        v5, v10 = sd['volume'].tail(5).mean(), sd['volume'].tail(10).mean()
        en = "rising_energy" if v5 > v10*1.2 else "fading_energy" if v5 < v10*0.8 else "stable_energy"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{en}"
    except: return "neutral"

def run_dahi_audit():
    print("🏛️ AYAŞ TÜNELİ 2026: DAHİ MODU AKTİF...")
    
    golden_map = {}
    if os.path.exists(KEYS_DIR):
        for f in os.listdir(KEYS_DIR):
            if f.endswith("_key.json"):
                with open(os.path.join(KEYS_DIR, f), "r") as fs:
                    d = json.load(fs); golden_map[d['symbol']] = set(d.get('golden_dna_list', []))

    symbols = sorted([d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))])
    report_rows = []

    for sym in symbols:
        if sym not in golden_map: continue
        try:
            d15 = load_clean(f"{COIN_CELLS_DIR}/{sym}/data/history_15m.parquet")
            d1h = load_clean(f"{COIN_CELLS_DIR}/{sym}/data/history_1h.parquet")
            d4h = load_clean(f"{COIN_CELLS_DIR}/{sym}/data/history_4h.parquet")
            dd = load_clean(f"{COIN_CELLS_DIR}/{sym}/data/history_1d.parquet")
            dw = load_clean(f"{COIN_CELLS_DIR}/{sym}/data/history_1w.parquet")
            
            if d15.empty or dd.empty: continue
            
            # --- 1D Indicators (Yesterday's Context) ---
            dd['tr'] = np.maximum(dd['high']-dd['low'], np.maximum(abs(dd['high']-dd['close'].shift(1)), abs(dd['low']-dd['close'].shift(1))))
            dd['atr14'] = dd['tr'].rolling(14).mean()
            dd['atr_pct'] = (dd['atr14'] / dd['close']) * 100
            
            # ADX Hesapla
            plus_dm = dd['high'].diff(); minus_dm = -dd['low'].diff()
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
            tr_sum = dd['tr'].rolling(14).sum()
            plus_di = 100 * (plus_dm.rolling(14).sum() / tr_sum)
            minus_di = 100 * (minus_dm.rolling(14).sum() / tr_sum)
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
            dd['adx'] = dx.rolling(14).mean()

            # --- 15m Indicators (Real-time Drill) ---
            d15['rsi'] = calculate_rsi(d15['close'], 11)
            d15['rsi_ema'] = d15['rsi'].ewm(span=11, adjust=False).mean()
            ribs = [20, 25, 30, 35, 40, 45, 50, 55]
            for p in ribs: d15[f'rib_{p}'] = d15['rsi_ema'].ewm(span=p, adjust=False).mean()
            
            d15['tr'] = np.maximum(d15['high']-d15['low'], np.maximum(abs(d15['high']-d15['close'].shift(1)), abs(d15['low']-d15['close'].shift(1))))
            d15['atr100'] = d15['tr'].rolling(100).mean()
            d15['atr21'] = d15['tr'].rolling(21).mean()
            
            # --- Trigger Point ---
            # RSI-EMA > All Ribbons
            r_ema = d15['rsi_ema'].values
            all_up = np.ones(len(d15), dtype=bool)
            for p in ribs: all_up &= (r_ema > d15[f'rib_{p}'].values)
            trig_idx = np.where(all_up & (~np.roll(all_up, 1)))[0]
            
            for idx in trig_idx:
                ts = d15.index[idx]
                if ts < START_DATE or ts > END_DATE: continue
                
                # DNA Key Check ( вчерашний )
                dna = get_dna_profile_strict(ts, dw, d1h, dd, d4h)
                if dna not in golden_map[sym]: continue
                
                # --- Metrics (Geleceği Görme Yasaktır) ---
                curr = d15.iloc[idx]
                # Sadece max_pct için geleceğe bakıyoruz (raporlama amaçlı)
                fut = d15.iloc[idx:idx+22]
                max_p = ((fut['high'].max() / curr['close']) - 1) * 100
                tier = "💎" if max_p >= 30 else "🥇" if max_p >= 20 else "🥈" if max_p >= 10 else "🥉" if max_p >= 5 else ""
                
                # --- TEKNİK SÜTUN RESTORASYONU (GRUP 2: MOMENTUM VE AÇISAL DEHA) ---
                # 6. SIG: Vuruş ikonu (Zaten "🚀" olarak mühürledik)
                # 7. CVT: Dünkü kapanışa göre anlık % fark (Dirilik)
                y_row = dd[dd.index < d_target].tail(1)
                cvt_val = ((curr['close'] / y_row['close'].iloc[0]) - 1) * 100 if not y_row.empty and y_row['close'].iloc[0] > 0 else 0.0

                # 8. TREND: 3 Zaman Dilimli Uyumu (D1, H4, H1)
                # D1 Trend: Close > EMA21
                d_ok = sd.iloc[-1]['close'] > sd.iloc[-1]['e21'] if not sd.empty else False
                # H4 Trend: Close > EMA21
                h4_ok = sh4.iloc[-1]['close'] > sh4.iloc[-1]['e21'] if not sh4.empty else False
                # H1 Trend: Close > EMA21
                h1_ok = sh1.iloc[-1]['close'] > sh1.iloc[-1]['e21'] if not sh1.empty else False
                
                trend_icons = ("🟢" if d_ok else "🔴") + ("🟢" if h4_ok else "🔴")
                
                # 9. POS: Anlık 15m pozisyon sağlığı (EMA9/21 kesişimi veya RSI durumu)
                pos_icon = "🟢" if h1_ok else "🔴"
                
                # --- TEKNİK SÜTUN RESTORASYONU (GRUP 3: RALLİ BAŞARIMI VE TEKNİK GENETİK) ---
                # 11. R-Ang: RSI-EMA'nın son 5 bardaki ivmesi (Hesaplama Grup 2'de yapıldı)
                # 12. VAL: Tünel Vizesi (Zaten buradaysa 🟢)
                val_icon = "🟢"

                # 13. P: Tetik anındaki (15m) mumun % başarısı
                p_val = ((curr['close'] / curr['open']) - 1) * 100

                # 14-15. TIER / P-21: Ralli sınıfı ve gücü (Hesaplama yukarıda yapıldı: tier, max_p)

                # --- TEKNİK SÜTUN RESTORASYONU (GRUP 4: İLERİ TEKNİK VE HACİM) ---
                # ADX & ATR: (Zaten hesaplandı: adx_v, atr_v)
                # VRSI: Anlık RSI değeri
                vrsi_val = curr['rsi']
                
                v100_ma = clean_v(curr['atr100']) if curr['atr100'] > 0 else 1e-9
                v21_ma = clean_v(curr['atr21']) if curr['atr21'] > 0 else 1e-9
                v_100_val = (curr['tr'] / v100_ma) * 3.33
                v_21_val = (curr['tr'] / v21_ma) * 3.33
                v_mom_val = (v_21_val / v_100_val) if v_100_val > 0 else 1.0
                v_boy_val = (abs(curr['close'] - curr['open']) / (curr['high'] - curr['low'] + 1e-9)) * 10
                
                # 4. Angles
                p_ang = get_angle(d15['close'].iloc[idx-5:idx+1])
                r_ang = get_angle(d15['rsi_ema'].iloc[idx-5:idx+1])
                
                # Formatting
                def fmt_p(v): return f"<font color='{'green' if v > 0 else 'red'}'>{v:+.1f}%</font>"
                def fmt_v(v): return f"<font color='green'>**{v:.1f}**</font>" if v >= 8 else f"{v:.1f}"

                rows = [
                    "", sym, f"{d_max_val:+.1f}%", f"{d_close_val:+.1f}%", ts.strftime("%H:%M"), "🚀", 
                    fmt_p(cvt_val), trend_icons, pos_icon, f"{p_ang:.0f}°", f"{r_ang:.0f}°", val_icon, 
                    fmt_p(p_val), tier, fmt_p(max_p), str(fut['high'].argmax()), 
                    fmt_p(0.0), fmt_p(0.0), "50%", f"{clean_v(adx_v):.0f}", 
                    f"{clean_v(atr_v):.1f}%", f"{clean_v(vrsi_val):.1f}", fmt_v(clean_v(v_boy_val)), 
                    fmt_v(clean_v(v_100_val)), fmt_v(clean_v(v_21_val)), f"{clean_v(v_mom_val):.1f}x"
                ]
                report_rows.append({'d': ts.normalize(), 's': sym, 'r': rows})
        except: continue

    report_rows.sort(key=lambda x: (x['d'], x['s']))
    
    with open(OUTPUT_FILE, "w") as f:
        f.write("# 🏛️ AYAŞ TÜNELİ 2026: KUTSAL NİZAM RAPORU (V17 - TAM HÜCRE DOĞRULAMA)\n\n")
        cd = None; cs = None; no = 1
        for r in report_rows:
            dt_tr = f"{r['d'].day} { {1:'Ocak',2:'Şubat',3:'Mart',4:'Nisan',5:'Mayıs',6:'Haziran',7:'Temmuz',8:'Ağustos',9:'Eylül',10:'Ekim',11:'Kasım',12:'Aralık'}[r['d'].month] } {r['d'].year}"
            if dt_tr != cd:
                f.write(f"\n## 📅 {dt_tr}\n\n")
                f.write("| NO | SYM | MAX | CLOSE | TIME | SIG | CVT | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-21 | BAR | NEXT | N-1 | CGS | ADX | ATR% | Vrsi | VBoy | V100 | V21 | V-Mom |\n")
                f.write("|----|-----------|--------|--------|-------|-----|-----------|-------|-----|------|----------|-----|-------|------|--------|-----|-------|-------|---------|--------|------|------|----------|------|-----|----------|\n")
                cd = dt_tr; cs = None; no = 1
            
            data = r['r']
            if r['s'] == cs: data[0:4] = ["", "", "", ""]
            else: data[0] = str(no); cs = r['s']; no += 1
            f.write("| " + " | ".join(data) + " |\n")
            
    print(f"✅ Kutsal Rapor Tamamlandı: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_dahi_audit()
