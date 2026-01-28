import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

# CONFIG
SYMBOL = "DASHUSDT"
START_DATE = pd.Timestamp("2025-09-01")
END_DATE = pd.Timestamp("2026-01-23")

def tunnel_full_audit():
    print(f"🕵️ DASH TÜNEL TAM DENETİM RAPORU")
    
    # 1. Veri Yükleme
    try:
        df_15m = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_15m.parquet")
        df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
        df_15m.set_index('dt', inplace=True)
        
        df_w = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_1w.parquet")
        df_w['dt'] = pd.to_datetime(df_w['timestamp'], unit='ms')
        df_w.set_index('dt', inplace=True)

        df_d = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_1d.parquet")
        df_d['dt'] = pd.to_datetime(df_d['timestamp'], unit='ms')
        df_d.set_index('dt', inplace=True)
        df_d['ema21'] = df_d['close'].ewm(span=21, adjust=False).mean()

        df_h4 = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_4h.parquet")
        df_h4['dt'] = pd.to_datetime(df_h4['timestamp'], unit='ms')
        df_h4.set_index('dt', inplace=True)
        df_h4['ema21'] = df_h4['close'].ewm(span=21, adjust=False).mean()

        df_h1 = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_1h.parquet")
        df_h1['dt'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
        df_h1.set_index('dt', inplace=True)
        df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
        df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
        df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
        
        with open(f"data/golden_keys/{SYMBOL}_key.json", "r") as f:
            golden_dna_list = set(json.load(f).get('golden_dna_list', []))

    except Exception as e:
        print(f"❌ Veri Hatası: {e}")
        return

    def get_profile(day):
        try:
            sub_w = df_w[df_w.index <= day].tail(30)
            if sub_w.empty: return "neutral"
            delta = sub_w['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
            rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
            faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
            
            sub_h1_24 = df_h1[df_h1.index <= day].tail(24)
            if sub_h1_24.empty: return "neutral"
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
            vol_pulse = sub_d.iloc[-1]['volume'] / (sub_d_tail['volume'].mean()+1)
            ritim = "ignited" if vol_pulse > 2.0 else "active" if vol_pulse > 1.0 else "sleeping"
            
            v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
            enerji = "building_energy" if v_trend else "depleting_energy"
            
            yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
            retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
            ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"
            
            return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
        except: return "neutral"

    records = []
    current = START_DATE
    while current <= END_DATE:
        dna = get_profile(current)
        passed = dna in golden_dna_list
        
        day_data = df_15m[df_15m.index.normalize() == current]
        if not day_data.empty:
            rally_size = (day_data['high'].max() / day_data['low'].min() - 1) * 100
        else:
            rally_size = 0.0
            
        records.append({
            'day': current.strftime("%d %b %Y"),
            'pass': passed,
            'rally': rally_size,
            'dna': dna
        })
        current += timedelta(days=1)

    # OUTPUT TO FILE
    with open("dash_tüm_günler_denetim.md", "w") as f:
        f.write("# 🕵️ DASH TÜNEL TAM DENETİM RAPORU (GÜN GÜN)\n")
        f.write("| TARİH | TÜNEL DURUMU | RALLİ BOYU (%) | DNA PROFİLİ |\n")
        f.write("| --- | --- | --- | --- |\n")
        for r in records:
            state = "✅ **GEÇTİ**" if r['pass'] else "❌ KAPALI"
            f.write(f"| {r['day']} | {state} | %{r['rally']:.2f} | `{r['dna']}` |\n")

    print(f"✅ Rapor oluşturuldu: dash_tüm_günler_denetim.md")
    
    # 5. Analiz Özetleri
    passed_days = [r for r in records if r['pass']]
    missed_huge = [r for r in records if not r['pass'] and r['rally'] > 30]
    
    print(f"\n📢 ANALİZ ÖZETİ:")
    print(f"🔹 Toplam Gün Sayısı: {len(records)}")
    print(f"🔹 Tünel Onayı Alan Gün: {len(passed_days)}")
    print(f"🔹 Tünel'in Kaçırdığı Dev Ralliler (>%30): {len(missed_huge)}")
    for m in missed_huge:
        print(f"   ⚠️ {m['day']} | Ralli: %{m['rally']:.2f} | Sebep: DNA Tüneli Kapattı")

if __name__ == "__main__":
    tunnel_full_audit()
