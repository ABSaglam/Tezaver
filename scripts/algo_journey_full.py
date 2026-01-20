
import sys
import os
import pandas as pd
import numpy as np
from datetime import timedelta

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from db_helper import get_rallies, TRAIN_CUTOFF

# ==========================================
# AŞAMA 2 — YOLCULUK TEMSİLİ (5 BOYUT)
# ==========================================

def get_faz(rsi, rsi_slope):
    """1) ZAMANSAL HİS (FAZ): erken / olgun / eşik / geç"""
    if rsi < 35: return "erken"
    if rsi > 70: return "geç"
    if 35 <= rsi < 50 and rsi_slope > 0: return "eşik"
    return "olgun"

def get_birikim(atr_score, vol_change):
    """2) GERİLİM–BOŞALMA (BİRİKİM): rahat / bastırılmış / taşmak üzere"""
    if atr_score < 1.2:
        if vol_change > 0: return "taşmak_üzere"
        return "bastırılmış"
    return "rahat"

def get_uyum(w_trend, d_trend, h4_trend):
    """3) AHENK (UYUM): uyumsuz / kısmi uyum / itirazsız"""
    directions = [1 if t > 0 else -1 if t < 0 else 0 for t in [w_trend, d_trend, h4_trend]]
    unique_dirs = len(set(directions))
    if unique_dirs == 1: return "itirazsız"
    if unique_dirs == 2: return "kısmi_uyum"
    return "uyumsuz"

def get_tempo(vol_cv):
    """4) RİTİM (TEMPO): kesik / dengeli / aceleci"""
    if vol_cv < 0.4: return "dengeli"
    if vol_cv > 0.8: return "kesik"
    return "aceleci"

def get_hafiza(w_rsi):
    """5) BAĞLAM (HAFIZA): anlamsız / tanıdık / anlamlı"""
    if w_rsi < 35: return "anlamlı_dip"
    if w_rsi > 70: return "anlamlı_tepe"
    return "tanıdık"

def calc_indicators(df):
    # RSI & Slope
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi_slope'] = df['rsi'].diff(3)
    
    # Trends (EMA)
    ema21 = df['close'].ewm(span=21).mean()
    ema50 = df['close'].ewm(span=50).mean()
    df['h4_trend'] = (ema21 / ema50 - 1) * 100
    
    # Volume Stats
    df['vol_change'] = df['volume'].diff(3)
    df['vol_cv'] = df['volume'].rolling(12).std() / df['volume'].rolling(12).mean()
    
    # ATR Squeeze
    df['tr'] = np.maximum(df['high'] - df['low'], abs(df['close'].shift(1) - df['close']))
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_ratio'] = df['atr'] / df['close'] * 100
    df['atr_min'] = df['atr_ratio'].rolling(50).min()
    df['atr_score'] = df['atr_ratio'] / df['atr_min']
    
    return df

def main():
    symbol = 'ALGOUSDT'
    print(f"🧭 MASTER JOURNEY FRAMEWORK: {symbol}")
    print("="*70)
    
    # AŞAMA 1 — YOLCULUK HAFIZASINI OLUŞTUR
    print("\n[AŞAMA 1] Yolculuk Hafızasını Oluştur")
    
    # Load H4 Data
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    if not os.path.exists(h4_path):
        print("❌ H4 Data not found")
        return

    df_h4 = pd.read_parquet(h4_path)
    df_h4 = df_h4.sort_values('timestamp').reset_index(drop=True)
    df_h4['datetime'] = pd.to_datetime(df_h4['timestamp'], unit='ms')
    df_h4 = df_h4[df_h4['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Calc H4 Indicators
    df_h4 = calc_indicators(df_h4)
    
    # Daily Trend
    df_d = df_h4.set_index('datetime').resample('1D').agg({'close': 'last'})
    ema21_d = df_d['close'].ewm(span=21).mean()
    ema50_d = df_d['close'].ewm(span=50).mean()
    df_d['d_trend'] = (ema21_d / ema50_d - 1) * 100
    df_d_re = df_d.reindex(df_h4['datetime'], method='ffill')
    df_h4['d_trend'] = df_d_re['d_trend'].values
    
    # Weekly RSI & Trend
    df_w = df_h4.set_index('datetime').resample('1W').agg({'close': 'last'})
    delta_w = df_w['close'].diff()
    gain_w = (delta_w.where(delta_w > 0, 0)).rolling(14).mean()
    loss_w = (-delta_w.where(delta_w < 0, 0)).rolling(14).mean()
    rs_w = gain_w / loss_w
    df_w['w_rsi'] = 100 - (100 / (1 + rs_w))
    ema21_w = df_w['close'].ewm(span=21).mean()
    ema50_w = df_w['close'].ewm(span=50).mean()
    df_w['w_trend'] = (ema21_w / ema50_w - 1) * 100
    df_w_re = df_w.reindex(df_h4['datetime'], method='ffill')
    df_h4['w_rsi'] = df_w_re['w_rsi'].values
    df_h4['w_trend'] = df_w_re['w_trend'].values
    
    # Get All Rallies
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    rally_dates = list(rally_results.keys())
    print(f"Toplam Ralli Sayısı: {len(rally_dates)}")
    
    # Define Journey Windows: T-1, T-3, T-5, T-7, T-14, T-21
    journey_offsets = [1, 3, 5, 7, 14, 21]
    journey_dates = set()
    for rd in rally_dates:
        journey_dates.add(rd) # T-0
        for offset in journey_offsets:
            journey_dates.add(rd - timedelta(days=offset))
    
    print(f"Yolculuk Günleri (T-0 + Offsets): {len(journey_dates)}")
    
    # AŞAMA 2 — YOLCULUK TEMSİLİNİ ÇIKAR
    print("\n[AŞAMA 2] Yolculuk Profillerini Oluştur")
    
    # Work with Midnight Candles (Daily Open)
    midnight = df_h4[df_h4['datetime'].dt.hour == 0].copy().reset_index(drop=True)
    midnight['date'] = midnight['datetime'].dt.date
    
    # Create Profiles
    midnight['profile'] = midnight.apply(lambda row: 
        f"FAZ:{get_faz(row['rsi'], row['rsi_slope'])}|" +
        f"BIR:{get_birikim(row['atr_score'], row['vol_change'])}|" +
        f"UYNM:{get_uyum(row['w_trend'], row['d_trend'], row['h4_trend'])}|" +
        f"TMPO:{get_tempo(row['vol_cv'])}|" +
        f"HFZA:{get_hafiza(row['w_rsi'])}", axis=1
    )
    
    # Mark Journey Days
    midnight['is_journey'] = midnight['date'].isin(journey_dates)
    midnight['is_rally_day'] = midnight['date'].isin(rally_dates)
    
    print(f"Toplam Gün: {len(midnight)}")
    print(f"Yolculuk Günü: {midnight['is_journey'].sum()}")
    
    # AŞAMA 3 — RALLİ PROFİL AİLELERİNİ KUR
    print("\n[AŞAMA 3] Profil Ailelerini Kur")
    
    candidate_profiles = midnight[midnight['is_journey']]['profile'].unique()
    print(f"Aday Profil Sayısı: {len(candidate_profiles)}")
    
    # AŞAMA 4-6 — EŞLEŞTİRME YASASI + YOK ETME
    print("\n[AŞAMA 4-6] Eşleştirme + Eliminasyon")
    
    survivors = []
    eliminated_count = 0
    
    for prof in candidate_profiles:
        mask = midnight['profile'] == prof
        occurrences = midnight[mask]
        
        # Law 7: If this profile EVER appeared on a non-journey day, it's contaminated.
        non_journey_appearances = occurrences[~occurrences['is_journey']]
        
        if len(non_journey_appearances) == 0:
            # PURE PROFILE
            rally_hits = occurrences[occurrences['is_rally_day']]
            survivors.append({
                'profile': prof,
                'total_days': len(occurrences),
                'rally_hits': len(rally_hits),
                'matches': occurrences
            })
        else:
            eliminated_count += 1
            
    print(f"Elemenen Profil: {eliminated_count}")
    print(f"Hayatta Kalan Profil: {len(survivors)}")
    
    # AŞAMA 7 — ÇIKTI (RAPOR)
    print("\n" + "="*70)
    print("📜 AŞAMA 7 — NİHAİ RAPOR")
    print("="*70)
    
    if not survivors:
        print("❌ HİÇBİR PROFİL HAYATTA KALMADI.")
        print("   (Tüm profiller en az bir kez ralli olmayan günde görünmüş)")
        return
    
    total_open_days = 0
    tier_stats = {'DIAMOND':0, 'GOLD':0, 'SILVER':0}
    
    print("\n1) NİHAİ ANAHTAR TANIMI (YOLCULUK HALLERİ):")
    print("-" * 50)
    
    for s in survivors:
        print(f"\n💎 {s['profile']}")
        print(f"   Aktif Gün: {s['total_days']}")
        total_open_days += s['total_days']
        
        # Check Tier Matches
        for _, row in s['matches'].iterrows():
            d = row['date']
            if d in rally_results:
                tier = rally_results[d][0]
                tier_stats[tier] += 1
                print(f"   -> {d} ({tier})")
    
    print("\n" + "-" * 50)
    print(f"\n2) ANAHTARIN AÇILDIĞI TOPLAM GÜN: {total_open_days}")
    
    print(f"\n3) SONUÇLAR:")
    print(f"   - DIAMOND: {tier_stats['DIAMOND']}")
    print(f"   - GOLD:    {tier_stats['GOLD']}")
    print(f"   - SILVER:  {tier_stats['SILVER']}")
    
    print("\n4) 'Bu anahtar, geçmiş veride ralli olmayan hiçbir günü geçirmedi.'")

if __name__ == "__main__":
    main()
