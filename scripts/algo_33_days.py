
import sys
import os
import pandas as pd
import numpy as np
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from db_helper import get_rallies, TRAIN_CUTOFF

def get_faz(rsi, rsi_slope):
    if rsi < 35: return "erken"
    if rsi > 70: return "geç"
    if 35 <= rsi < 50 and rsi_slope > 0: return "eşik"
    return "olgun"

def get_birikim(atr_score, vol_change):
    if atr_score < 1.2:
        if vol_change > 0: return "taşmak_üzere"
        return "bastırılmış"
    return "rahat"

def get_uyum(w_trend, d_trend, h4_trend):
    directions = [1 if t > 0 else -1 if t < 0 else 0 for t in [w_trend, d_trend, h4_trend]]
    unique_dirs = len(set(directions))
    if unique_dirs == 1: return "itirazsız"
    if unique_dirs == 2: return "kısmi_uyum"
    return "uyumsuz"

def get_tempo(vol_cv):
    if vol_cv < 0.4: return "dengeli"
    if vol_cv > 0.8: return "kesik"
    return "aceleci"

def get_hafiza(w_rsi):
    if w_rsi < 35: return "anlamlı_dip"
    if w_rsi > 70: return "anlamlı_tepe"
    return "tanıdık"

def calc_indicators(df):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi_slope'] = df['rsi'].diff(3)
    
    ema21 = df['close'].ewm(span=21).mean()
    ema50 = df['close'].ewm(span=50).mean()
    df['h4_trend'] = (ema21 / ema50 - 1) * 100
    
    df['vol_change'] = df['volume'].diff(3)
    df['vol_cv'] = df['volume'].rolling(12).std() / df['volume'].rolling(12).mean()
    
    df['tr'] = np.maximum(df['high'] - df['low'], abs(df['close'].shift(1) - df['close']))
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_ratio'] = df['atr'] / df['close'] * 100
    df['atr_min'] = df['atr_ratio'].rolling(50).min()
    df['atr_score'] = df['atr_ratio'] / df['atr_min']
    
    return df

def main():
    symbol = 'ALGOUSDT'
    
    # Load data
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    df_h4 = pd.read_parquet(h4_path)
    df_h4 = df_h4.sort_values('timestamp').reset_index(drop=True)
    df_h4['datetime'] = pd.to_datetime(df_h4['timestamp'], unit='ms')
    df_h4 = df_h4[df_h4['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_h4 = calc_indicators(df_h4)
    
    # Daily/Weekly
    df_d = df_h4.set_index('datetime').resample('1D').agg({'close': 'last'})
    ema21_d = df_d['close'].ewm(span=21).mean()
    ema50_d = df_d['close'].ewm(span=50).mean()
    df_d['d_trend'] = (ema21_d / ema50_d - 1) * 100
    df_d_re = df_d.reindex(df_h4['datetime'], method='ffill')
    df_h4['d_trend'] = df_d_re['d_trend'].values
    
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
    
    # Rallies
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    rally_dates = list(rally_results.keys())
    
    journey_offsets = [1, 3, 5, 7, 14, 21]
    journey_dates = set()
    journey_map = {}
    for rd in rally_dates:
        journey_dates.add(rd)
        journey_map[rd] = f"T-0 ({rally_results[rd][0]})"
        for offset in journey_offsets:
            prep_day = rd - timedelta(days=offset)
            journey_dates.add(prep_day)
            if prep_day not in journey_map:
                journey_map[prep_day] = f"T-{offset} -> {rd} ({rally_results[rd][0]})"
    
    # Midnight
    midnight = df_h4[df_h4['datetime'].dt.hour == 0].copy().reset_index(drop=True)
    midnight['date'] = midnight['datetime'].dt.date
    
    midnight['profile'] = midnight.apply(lambda row: 
        f"FAZ:{get_faz(row['rsi'], row['rsi_slope'])}|" +
        f"BIR:{get_birikim(row['atr_score'], row['vol_change'])}|" +
        f"UYNM:{get_uyum(row['w_trend'], row['d_trend'], row['h4_trend'])}|" +
        f"TMPO:{get_tempo(row['vol_cv'])}|" +
        f"HFZA:{get_hafiza(row['w_rsi'])}", axis=1
    )
    
    midnight['is_journey'] = midnight['date'].isin(journey_dates)
    midnight['is_rally_day'] = midnight['date'].isin(rally_dates)
    
    # Find surviving profiles
    candidate_profiles = midnight[midnight['is_journey']]['profile'].unique()
    
    survivors = []
    for prof in candidate_profiles:
        mask = midnight['profile'] == prof
        occurrences = midnight[mask]
        non_journey = occurrences[~occurrences['is_journey']]
        if len(non_journey) == 0:
            survivors.append(prof)
    
    # Get all days with surviving profiles
    surviving_days = midnight[midnight['profile'].isin(survivors)].copy()
    
    print(f"📊 HAYATTA KALAN PROFİLLERİN GÖRÜNDÜĞü TOPLAM GÜN: {len(surviving_days)}")
    
    rally_days = surviving_days[surviving_days['is_rally_day']]
    non_rally_days = surviving_days[~surviving_days['is_rally_day']]
    
    print(f"\n🎯 RALLİ GÜNLERİ (T-0): {len(rally_days)}")
    print(f"⏳ RALLİ OLMAYAN GÜNLER: {len(non_rally_days)}")
    
    print("\n" + "="*80)
    print("📅 33 RALLİ OLMAYAN GÜNÜN DETAYI:")
    print("="*80)
    
    for _, row in non_rally_days.sort_values('date').iterrows():
        d = row['date']
        prof = row['profile']
        
        # What is this day's relationship to rallies?
        if d in journey_map:
            relation = journey_map[d]
        else:
            relation = "❓ Bilinmiyor"
            
        print(f"\n📆 {d}")
        print(f"   Profil: {prof}")
        print(f"   İlişki: {relation}")

if __name__ == "__main__":
    main()
