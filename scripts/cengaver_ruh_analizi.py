import pandas as pd
import numpy as np
import json
from tezaver.core.rally_store import RallyStore

# CONFIG
SYMBOL = "ACAUSDT"
TRAINING_END_DATE = pd.Timestamp("2025-09-30")

def analyze_rally_soul():
    print(f"🦅 CENGAVER RUH ANALİZCİSİ: {SYMBOL}")
    print(f"🔒 Eğitim Sınırı: {TRAINING_END_DATE}\n")
    
    # 1. LOAD ALL TIMEFRAMES
    try:
        def load_tf(tf):
            df = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_{tf}.parquet")
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df.sort_index(inplace=True)
            # Basic Indicators
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
            df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
            # RSI
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['rsi'] = 100 - (100 / (1 + gain / loss.abs().replace(0, 0.001)))
            return df

        df_15m = load_tf('15m')
        df_1h = load_tf('1h')
        df_4h = load_tf('4h')
        
    except Exception as e:
        print(f"❌ Veri Hatası: {e}")
        return

    # 2. HARVEST RALLIES (Eğitim Verisi)
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=SYMBOL, timeframe='15m')
    
    training_rallies = []
    for r in all_rallies:
        r_time = pd.Timestamp(r['event_time'])
        if r_time > TRAINING_END_DATE: continue 
        if r.get('tier') not in ['DIAMOND', 'GOLD', 'SILVER']: continue 
        training_rallies.append(r)
        
    print(f"📚 Analiz Edilen Başarılı Ralliler: {len(training_rallies)} adet\n")
    
    # 3. EXTRACT "SOUL" (Ruh Analizi)
    soul_data = {
        'h1_rsi': [],
        'h4_rsi': [],
        'h1_trend_dist': [], # Fiyatın EMA21'e uzaklığı
        'h4_trend_dist': [],
        'h1_squeeze': [], # Bollinger/EMA sıkışması
        'rally_duration': [], # Kaç mum sürdü (Zirveye kadar)
        'exit_style': [] # Spike mı (hızlı düşüş) yoksa Grind mi (yavaş)
    }
    
    for r in training_rallies:
        # Ralli Başlangıç Zamanı
        start_time = pd.Timestamp(r['event_time'])
        
        # 1H ve 4H'de o anki duruma bak (Lookup)
        # 15m zamanını H1/H4 time'a yuvarla veya reindex kullan
        # En basit yöntem: o andan önceki son kapanış
        try:
            h1_row_idx = df_1h.index.get_indexer([start_time], method='pad')[0]
            h4_row_idx = df_4h.index.get_indexer([start_time], method='pad')[0]
            
            h1_row = df_1h.iloc[h1_row_idx]
            h4_row = df_4h.iloc[h4_row_idx]
            
            # --- RUH PARAMETRELERİ ---
            
            # 1. RSI Uyumu
            soul_data['h1_rsi'].append(h1_row['rsi'])
            soul_data['h4_rsi'].append(h4_row['rsi'])
            
            # 2. Trend Mesafesi (Lastik Gerginliği)
            # Fiyat EMA21'den ne kadar uzakta? Çok uzaksa yorgundur, yakınsa güç topluyordur.
            dist_h1 = (h1_row['close'] / h1_row['ema21'] - 1) * 100
            dist_h4 = (h4_row['close'] / h4_row['ema21'] - 1) * 100
            soul_data['h1_trend_dist'].append(dist_h1)
            soul_data['h4_trend_dist'].append(dist_h4)
            
            # 3. Sıkışma (Yay Gerginliği)
            # EMA'lar birbirine ne kadar yakın?
            hi = max(h1_row['ema9'], h1_row['ema21'], h1_row['ema50'])
            lo = min(h1_row['ema9'], h1_row['ema21'], h1_row['ema50'])
            squeeze = (hi / lo - 1) * 100
            soul_data['h1_squeeze'].append(squeeze)
            
            # 4. Ralli Karakteri (Süresi)
            # Ralli ne kadar sürmüş? (Tepeye ulaşma süresi)
            # Bunu zaten RallyStore verisinden veya tekrar hesaplayarak bulabiliriz.
            # RalliStore'da 'duration' olmayabilir, hesaplayalım.
            end_time = pd.Timestamp(r.get('end_time', start_time + timedelta(hours=4))) 
            duration_candles = (end_time - start_time).total_seconds() / 900 # 15m
            soul_data['rally_duration'].append(duration_candles)
            
        except Exception as ex:
            continue

    # 4. REPORTING THE "SOUL DNA"
    print("🧬 15M RALLİSİNİN MİKRO-DNA'SI (Ortalama Değerler):")
    print("-" * 50)
    
    avg_h1_rsi = np.mean(soul_data['h1_rsi'])
    avg_h4_rsi = np.mean(soul_data['h4_rsi'])
    print(f"📡 RSI UYUMU:")
    print(f"   - 1H RSI Genelde: {avg_h1_rsi:.1f} (Aralık: {np.percentile(soul_data['h1_rsi'], 25):.1f} - {np.percentile(soul_data['h1_rsi'], 75):.1f})")
    print(f"   - 4H RSI Genelde: {avg_h4_rsi:.1f}")
    if avg_h1_rsi > 60: print("     -> Ralli genelde Momentum 1H'de halihazırda YÜKSEKKEN başlıyor. (Trend Follower)")
    else: print("     -> Ralli genelde 1H DİPTEYKEN başlıyor. (Reversal)")
    
    avg_h1_dist = np.mean(soul_data['h1_trend_dist'])
    print(f"\n📏 TREND MESAFESİ (Lastik):")
    print(f"   - 1H EMA21'e Uzaklık: %{avg_h1_dist:.2f}")
    if abs(avg_h1_dist) < 1.0: print("     -> Fiyat genelde 1H ortalamasına YAPIŞIKKEN patlıyor. (Sıkışma)")
    else: print("     -> Fiyat genelde ortalamadan UZAKKEN hareket ediyor. (Volatil)")
    
    avg_squeeze = np.mean(soul_data['h1_squeeze'])
    print(f"\n🗜️ SIKIŞMA (Yay):")
    print(f"   - 1H Sıkışma Oranı: %{avg_squeeze:.2f}")
    if avg_squeeze < 1.0: print("     -> Ralliler MUAZZAM BİR SIKIŞMA (Sessizlik) sonrası geliyor.")
    else: print("     -> Ralliler dağınık yapıda geliyor.")
    
    avg_duration = np.mean(soul_data['rally_duration'])
    print(f"\n⏱️ ZAMANLAMA (Çıkış Stratejisi İçin):")
    print(f"   - Ortalama Zirve Süresi: {avg_duration:.1f} mum ({avg_duration*15/60:.1f} Saat)")
    print(f"   - Öneri: İşleme girdikten sonra {avg_duration/2:.0f}-{avg_duration:.0f} mum arasında Çıkış Ara.")
    
    print("-" * 50)
    print("💡 ÇIKARIM:")
    print("Sadece 15m'ye bakarak kör atış yapma.")
    print(f"Sinyal gelince sor: '1H RSI {np.percentile(soul_data['h1_rsi'], 25):.0f} civarında mı? 1H Sıkışma %{avg_squeeze:.1f} altında mı?'")
    print("Eğer EVET ise -> BU GERÇEK BİR ACA RALLİSİDİR.")

if __name__ == "__main__":
    analyze_rally_soul()
