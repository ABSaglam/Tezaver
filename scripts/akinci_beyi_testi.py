import pandas as pd
import numpy as np
import json
from datetime import timedelta

# CONFIG
SYMBOL = "DASHUSDT"
TRAINING_END_DATE = pd.Timestamp("2025-09-30") # KÖR BÖLGE BAŞLANGICI

def akinci_beyi_saha_testi():
    print(f"🦅 AKINCI BEYİ SAHA TESTİ: {SYMBOL}")
    print(f"🔒 Eğitim Sınırı: {TRAINING_END_DATE}")
    
    # 1. Veri Yükleme
    try:
        # 15 Dakikalık Veri (Saha)
        df_15m = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_15m.parquet")
        df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
        df_15m.set_index('dt', inplace=True)
        df_15m.sort_index(inplace=True)
        
        # İndikatörler
        # RSI Hesapla
        delta = df_15m['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        df_15m['rsi'] = 100 - (100 / (1 + gain / loss))
        
        # Hacim Oranı (Önceki 20 mumun ortalamasına göre)
        df_15m['vol_mean_20'] = df_15m['volume'].rolling(20).mean().shift(1)
        df_15m['vol_ratio'] = df_15m['volume'] / df_15m['vol_mean_20'].replace(0, 1)
        
        # Mum Gövde Yüzdesi
        df_15m['body_pct'] = (df_15m['close'] / df_15m['open'] - 1) * 100
        
        # --- RSI-BASED EMA RIBBON (MOMENTUM GÖKKUŞAĞI) ---
        # Kaynak: RSI
        # Periyotlar: 20, 25, 30, 35, 40, 45, 50, 55
        
        rsi_series = df_15m['rsi']
        
        df_15m['rsi_ema20'] = rsi_series.ewm(span=20, adjust=False).mean()
        df_15m['rsi_ema25'] = rsi_series.ewm(span=25, adjust=False).mean()
        df_15m['rsi_ema30'] = rsi_series.ewm(span=30, adjust=False).mean()
        df_15m['rsi_ema35'] = rsi_series.ewm(span=35, adjust=False).mean()
        df_15m['rsi_ema40'] = rsi_series.ewm(span=40, adjust=False).mean()
        df_15m['rsi_ema45'] = rsi_series.ewm(span=45, adjust=False).mean()
        df_15m['rsi_ema50'] = rsi_series.ewm(span=50, adjust=False).mean()
        df_15m['rsi_ema55'] = rsi_series.ewm(span=55, adjust=False).mean()
        
        # İstihbarat Verisi (Ayaş Tüneli için Günlük/Saatlik)
        df_d = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_1d.parquet")
        df_d['dt'] = pd.to_datetime(df_d['timestamp'], unit='ms')
        df_d.set_index('dt', inplace=True)
        df_d['ema21'] = df_d['close'].ewm(span=21, adjust=False).mean()
        
        # ... Diğer TF'ler profil için gerekli ama burada basitleştirilmiş profil kullanacağız
        # Tam set yükleme simülasyonu
        # (Önceki kodlardan helper fonksiyonu entegre ediyoruz)
        
    except Exception as e:
        print(f"❌ Veri Hatası: {e}")
        return

    # 2. İstihbarat Anahtarı (Golden Key)
    with open(f"data/golden_keys/{SYMBOL}_key.json", "r") as f:
        golden_dna_list = set(json.load(f).get('golden_dna_list', []))

    # --- BASİTLEŞTİRİLMİŞ PROFİL HESAPLAYICI (Kopyalanmış) ---
    # Profil hesaplamak için gerekli macro veriler
    def load_macro_data():
        try:
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
            
            # RSI Calculation for H1
            delta = df_h1['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
            df_h1['rsi'] = 100 - (100 / (1 + gain / loss))
            
            return df_w, df_d, df_h4, df_h1
        except: return None, None, None, None

    df_w, df_d, df_h4, df_h1 = load_macro_data()

    def get_profile_simple(day):
        if df_d is None: return "neutral"
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

    # 3. KÖR TEST (Dinamik Çıkışlı + İstihbaratlı)
    print("\n⚔️ SAVAŞ SİMÜLASYONU: İSTİHBARAT DESTEKLİ (Ekim 2025 - Ocak 2026)")
    
    test_df = df_15m[df_15m.index > TRAINING_END_DATE].copy()
    
    MIN_VOL = 1.26
    MIN_RSI = 55.0
    MIN_BODY = 0.50
    
    trades = []
    active_trade = None
    
    daily_profiles = {}
    
    for i in range(len(test_df)):
        idx = test_df.index[i]
        row = test_df.iloc[i]
        current_day = idx.normalize()
        
        # Eğer işlemdeysek -> YÖNET (Çıkış Mantığı)
        if active_trade:
             # (Aynı çıkış mantığı korunuyor)
            current_price = row['close']
            entry_price = active_trade['entry_price']
            pnl_pct = (current_price / entry_price - 1) * 100
            
            if i > 5:
                price_5_ago = test_df.iloc[i-5]['close']
                current_velocity = (current_price / price_5_ago - 1) * 100
                if current_velocity > active_trade['max_velocity']:
                    active_trade['max_velocity'] = current_velocity
            else:
                current_velocity = 0
            
            # Max Potansiyel Takibi
            potential_gain = (row['high'] / active_trade['entry_price'] - 1) * 100
            if potential_gain > active_trade['max_potential']:
                active_trade['max_potential'] = potential_gain
            
            exit_signal = False
            reason = ""
            
            if pnl_pct < -3.0:
                exit_signal = True
                reason = "ZORUNLU STOP (Hasar %3)"
            elif active_trade['max_velocity'] > 2.0: 
                if current_velocity < active_trade['max_velocity'] * 0.4:
                    exit_signal = True
                    reason = "NEFES KESİLDİ (Hız Düşüşü)"
            elif pnl_pct > 15.0 and row['rsi'] < 70:
                exit_signal = True
                reason = "DOYGUNLUK (Kâr > %15)"
            elif active_trade['candles_held'] > 16 and pnl_pct < 1.0:
                exit_signal = True
                reason = "ZAMAN AŞIMI (Yorgunluk)"

            if exit_signal:
                trades.append({
                    'entry_time': active_trade['entry_time'],
                    'exit_time': idx,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'pnl': pnl_pct,
                    'max_pot': active_trade['max_potential'],
                    'reason': reason,
                    'duration': active_trade['candles_held'] * 15,
                    'dna': active_trade['dna']
                })
                active_trade = None
            else:
                active_trade['candles_held'] += 1
                
        # Eğer işlemde DEĞİLSEK -> GİRİŞ ARA
        else:
            # 1. TÜNEL İZNİ (İSTİHBARAT)
            if current_day not in daily_profiles:
                daily_profiles[current_day] = get_profile_simple(current_day)
            
            dna = daily_profiles[current_day]
            if dna not in golden_dna_list:
                continue # İZİN YOK!
            
            # 2. RUH ANALİZİ (BAĞLAM KONTROLÜ - DASH İÇİN)
            
            # Not: Test scriptinde df_h1 yüklü.
            h1_idx = test_df.index[i]
            # En yakın önceki H1 mumu bul
            h1_loc = df_h1.index.get_indexer([h1_idx], method='pad')[0]
            if h1_loc == -1: continue
            h1_val = df_h1.iloc[h1_loc]
            h1_rsi = h1_val['rsi']
            
            # BASİT KORUMA: 1H RSI < 80 (Aşırı Alım Değil)
            if h1_rsi > 80:
                continue 

            # 3. AKINCI SİNYALİ (TETİK - DASH KALİBRASYONU)
            # DASH Parametreleri: Vol > 1.26
            if (row['vol_ratio'] >= MIN_VOL and 
                row['rsi'] >= MIN_RSI and
                row['body_pct'] >= MIN_BODY):
                
                active_trade = {
                    'entry_time': idx,
                    'entry_price': row['close'],
                    'max_velocity': 0.0,
                    'max_potential': 0.0,
                    'candles_held': 0,
                    'dna': dna
                }


    # 4. SONUÇLAR VE RAPORLAMA
    print(f"\n🏁 TEST TAMAMLANDI. Toplam İşlem: {len(trades)}")
    
    toplam_pnl = sum([t['pnl'] for t in trades])
    kazananlar = [t for t in trades if t['pnl'] > 0]
    win_rate = len(kazananlar) / len(trades) * 100 if trades else 0
    
    # Ekrana Özet
    print(f"📊 GENEL PERFORMANS:")
    print(f"   Net Kâr: %{toplam_pnl:.2f}")
    print(f"   Win Rate: %{win_rate:.1f}")
    
    # Markdown Raporu Oluştur
    report_path = "dash_operasyon_kayitlari.md"
    with open(report_path, "w") as f:
        f.write(f"# 🦅 CENGAVER DASH OPERASYON KAYITLARI (GÜN GÜN)\n")
        f.write(f"**Sembol:** {SYMBOL}\n")
        f.write(f"**Tarih Aralığı:** Ekim 2025 - Ocak 2026\n")
        f.write(f"**Toplam İşlem:** {len(trades)} | **Net Kâr:** %{toplam_pnl:.2f} | **Win Rate:** %{win_rate:.1f}\n\n")
        
        f.write("| Tarih (Giriş) | Profil (DNA) | Sonuç | Potansiyel | Realize | Fark | Süre |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- |\n")
        
        trades.sort(key=lambda x: x['entry_time'])
        
        for t in trades:
            date_str = str(t['entry_time'])
            pot = t['max_pot']
            realized = t['pnl']
            diff = pot - realized
            dna_short = t['dna'].split('|')[0] + "|" + t['dna'].split('|')[1] # Faz|Sıkışma
            
            icon = "✅" if realized > 0 else "🔻"
            reason_short = t['reason'].split('(')[0].strip()
            
            row_str = f"| **{date_str}** | `{dna_short}` | {icon} {reason_short} | %{pot:.2f} | **%{realized:.2f}** | %{diff:.2f} | {t['duration']}dk |"
            f.write(row_str + "\n")
            
            # Konsola da bas
            print(f"{date_str:<20} | {dna_short:<25} | %{realized:<6.2f}")

    print(f"\n📄 Detaylı Rapor Oluşturuldu: {report_path}")
    print("Tam listeyi bu dosyada inceleyebilirsiniz.")

if __name__ == "__main__":
    akinci_beyi_saha_testi()
