"""
🧬 SOLUSDT DNA Analyzer (Pilot)
Strict Look-Ahead Bias Prevention
"""
import os
import pandas as pd
import numpy as np
import math
from datetime import datetime

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
SYMBOL = "SOLUSDT"
REPORT_FILE = f"{SYMBOL}_dna_report.md"

# Tier Thresholds
TIER_THRESHOLDS = {'💎': 30.0, '🥇': 20.0, '🥈': 10.0, '🥉': 5.0}

def load_clean(path):
    try:
        df = pd.read_parquet(path)
        if 'timestamp' in df.columns:
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df = df[~df.index.duplicated(keep='last')]
            return df.sort_index()
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return pd.DataFrame()

def calculate_daily_metrics(df_1d):
    """Calculate daily indicators for Gate 1 analysis"""
    # EMA21
    df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
    
    # ATR14 %
    d_tr = np.maximum(df_1d['high'] - df_1d['low'], 
                      np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), 
                                 abs(df_1d['low'] - df_1d['close'].shift(1))))
    df_1d['atr14'] = d_tr.rolling(window=14).mean()
    df_1d['atr_pct'] = (df_1d['atr14'] / df_1d['close']) * 100
    
    # ADX14
    plus_dm = df_1d['high'].diff()
    minus_dm = -df_1d['low'].diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    tr14 = d_tr.rolling(window=14).sum()
    plus_di = 100 * (plus_dm.rolling(window=14).sum() / tr14)
    minus_di = 100 * (minus_dm.rolling(window=14).sum() / tr14)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df_1d['adx14'] = dx.rolling(window=14).mean()
    
    # RSI14
    delta = df_1d['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df_1d['rsi14'] = 100 - (100 / (1 + rs))
    
    # Volume Ratio (vs 20-day avg)
    df_1d['vol_avg20'] = df_1d['volume'].rolling(window=20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_avg20']
    
    # Trend: Close > EMA21?
    df_1d['above_ema21'] = (df_1d['close'] > df_1d['ema21']).astype(int)
    
    return df_1d

def calculate_15m_indicators(df_15m):
    """RSI-EMA and Ribbon for trigger detection"""
    # RSI
    alpha_rsi = 1/11
    delta = df_15m['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta.where(delta < 0, 0))
    avg_gain = gain.ewm(alpha=alpha_rsi, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha_rsi, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df_15m['rsi'] = 100 - (100 / (1 + rs))
    
    # RSI-EMA (Signal Line)
    df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
    
    # Ribbon (8 lines)
    ribbon_spans = [20, 25, 30, 35, 40, 45, 50, 55]
    for span in ribbon_spans:
        df_15m[f'ribbon_{span}'] = df_15m['rsi_ema'].ewm(span=span, adjust=False).mean()
    
    ribbon_cols = [f'ribbon_{s}' for s in ribbon_spans]
    df_15m['ribbon_max'] = df_15m[ribbon_cols].max(axis=1)
    df_15m['ribbon_min'] = df_15m[ribbon_cols].min(axis=1)
    df_15m['ribbon_spread'] = df_15m['ribbon_max'] - df_15m['ribbon_min']
    
    # Trigger Condition
    cond_now = df_15m['rsi_ema'] >= df_15m['ribbon_max']
    cond_prev = df_15m['rsi_ema'].shift(1) < df_15m['ribbon_max'].shift(1)
    df_15m['trigger'] = cond_now & cond_prev
    
    # ATR21 %
    tr = np.maximum(df_15m['high'] - df_15m['low'],
                    np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)),
                               abs(df_15m['low'] - df_15m['close'].shift(1))))
    df_15m['atr21'] = tr.rolling(window=21).mean()
    df_15m['atr_adj'] = (df_15m['atr21'] / df_15m['close']) * 100
    
    # RSI Angle
    df_15m['rsi_angle'] = np.degrees(np.arctan(df_15m['rsi_ema'].diff()))
    
    # Volume metrics (simplified)
    df_15m['vol_avg21'] = df_15m['volume'].rolling(window=21).mean()
    df_15m['vol_ratio_15m'] = df_15m['volume'] / df_15m['vol_avg21']
    
    # Hour of day
    df_15m['hour'] = df_15m.index.hour
    
    return df_15m

def run_dna_analysis():
    print(f"🧬 DNA Analizi Başlıyor: {SYMBOL}")
    print(f"   Dahi Modu: AKTIF")
    print(f"   Look-Ahead Bias Koruması: AKTIF (strict_before=True)")
    
    # Load Data
    base_path = os.path.join(COIN_CELLS_DIR, SYMBOL, "data")
    df_1d = load_clean(os.path.join(base_path, "history_1d.parquet"))
    df_15m = load_clean(os.path.join(base_path, "history_15m.parquet"))
    
    if df_1d.empty or df_15m.empty:
        print(f"❌ Veri bulunamadı: {SYMBOL}")
        return
    
    # Filter to 2023-2025
    start_date = pd.Timestamp("2023-01-01")
    end_date = pd.Timestamp("2025-12-31")
    df_1d = df_1d[(df_1d.index >= start_date) & (df_1d.index <= end_date)]
    df_15m = df_15m[(df_15m.index >= start_date) & (df_15m.index <= end_date)]
    
    print(f"   15m Veri: {df_15m.index.min()} -> {df_15m.index.max()} ({len(df_15m):,} bar)")
    print(f"   1D Veri: {df_1d.index.min()} -> {df_1d.index.max()} ({len(df_1d):,} gün)")
    
    # Calculate Indicators
    df_1d = calculate_daily_metrics(df_1d)
    df_15m = calculate_15m_indicators(df_15m)
    
    # Find Triggers
    trigger_indices = df_15m[df_15m['trigger']].index.tolist()
    print(f"\n📍 Bulunan Tetik Sayısı: {len(trigger_indices)}")
    
    # Analyze Each Trigger
    results = []
    for i, trig_time in enumerate(trigger_indices):
        try:
            trig_idx = df_15m.index.get_loc(trig_time)
            if trig_idx + 21 >= len(df_15m):
                continue  # Skip if not enough future bars
            
            entry_price = df_15m['close'].iloc[trig_idx]
            future_bars = df_15m.iloc[trig_idx+1 : trig_idx+22]
            peak_price = future_bars['high'].max()
            peak_pct = ((peak_price / entry_price) - 1) * 100
            
            # Tier Assignment
            if peak_pct >= 30: tier = '💎'
            elif peak_pct >= 20: tier = '🥇'
            elif peak_pct >= 10: tier = '🥈'
            elif peak_pct >= 5: tier = '🥉'
            else: tier = '❌'
            
            is_success = 1 if peak_pct >= 5 else 0
            
            # ===== GATE 1: Daily Context (STRICT_BEFORE) =====
            # Get PREVIOUS DAY's CLOSED data only
            trig_date = trig_time.normalize()
            daily_before = df_1d[df_1d.index < trig_date]
            
            if daily_before.empty:
                d_adx, d_atr_pct, d_rsi, d_above_ema, d_vol_ratio = np.nan, np.nan, np.nan, np.nan, np.nan
            else:
                last_day = daily_before.iloc[-1]
                d_adx = last_day.get('adx14', np.nan)
                d_atr_pct = last_day.get('atr_pct', np.nan)
                d_rsi = last_day.get('rsi14', np.nan)
                d_above_ema = last_day.get('above_ema21', np.nan)
                d_vol_ratio = last_day.get('vol_ratio', np.nan)
            
            # ===== GATE 2: Trigger Moment =====
            trig_row = df_15m.iloc[trig_idx]
            t_rsi_angle = trig_row.get('rsi_angle', 0)
            t_atr_adj = trig_row.get('atr_adj', 0)
            t_ribbon_spread = trig_row.get('ribbon_spread', 0)
            t_vol_ratio = trig_row.get('vol_ratio_15m', 0)
            t_hour = trig_row.get('hour', 0)
            t_rsi = trig_row.get('rsi', 50)
            
            results.append({
                'time': trig_time,
                'entry_price': entry_price,
                'peak_pct': peak_pct,
                'tier': tier,
                'success': is_success,
                # Gate 1 (Daily - Previous Day CLOSED)
                'd_adx': d_adx,
                'd_atr_pct': d_atr_pct,
                'd_rsi': d_rsi,
                'd_above_ema': d_above_ema,
                'd_vol_ratio': d_vol_ratio,
                # Gate 2 (Trigger Moment)
                't_rsi_angle': t_rsi_angle,
                't_atr_adj': t_atr_adj,
                't_ribbon_spread': t_ribbon_spread,
                't_vol_ratio': t_vol_ratio,
                't_hour': t_hour,
                't_rsi': t_rsi
            })
            
        except Exception as e:
            continue
    
    df_results = pd.DataFrame(results)
    
    if df_results.empty:
        print("❌ Sonuç bulunamadı.")
        return
    
    # ========== ANALYSIS ==========
    total = len(df_results)
    successes = df_results['success'].sum()
    success_rate = (successes / total) * 100
    
    tier_counts = df_results['tier'].value_counts()
    
    print(f"\n📊 SONUÇLAR ({SYMBOL})")
    print(f"   Toplam Tetik: {total}")
    print(f"   Başarılı (≥5%): {successes} ({success_rate:.1f}%)")
    print(f"\n   Tier Dağılımı:")
    for t in ['💎', '🥇', '🥈', '🥉', '❌']:
        cnt = tier_counts.get(t, 0)
        pct = (cnt / total) * 100 if total > 0 else 0
        print(f"      {t}: {cnt} ({pct:.1f}%)")
    
    # Compare Winners vs Losers (Gate 1 - Daily)
    winners = df_results[df_results['success'] == 1]
    losers = df_results[df_results['success'] == 0]
    
    print(f"\n🔬 GATE 1 ANALİZİ (Günlük - Önceki Gün Kapanış)")
    gate1_metrics = ['d_adx', 'd_atr_pct', 'd_rsi', 'd_above_ema', 'd_vol_ratio']
    gate1_analysis = []
    for m in gate1_metrics:
        w_mean = winners[m].mean() if not winners.empty else 0
        l_mean = losers[m].mean() if not losers.empty else 0
        diff = w_mean - l_mean
        gate1_analysis.append({'metric': m, 'winner_avg': w_mean, 'loser_avg': l_mean, 'diff': diff})
        print(f"   {m}: Kazanan Ort={w_mean:.2f} | Kaybeden Ort={l_mean:.2f} | Fark={diff:+.2f}")
    
    print(f"\n⚡ GATE 2 ANALİZİ (Tetik Anı - 15m)")
    gate2_metrics = ['t_rsi_angle', 't_atr_adj', 't_ribbon_spread', 't_vol_ratio', 't_hour', 't_rsi']
    gate2_analysis = []
    for m in gate2_metrics:
        w_mean = winners[m].mean() if not winners.empty else 0
        l_mean = losers[m].mean() if not losers.empty else 0
        diff = w_mean - l_mean
        gate2_analysis.append({'metric': m, 'winner_avg': w_mean, 'loser_avg': l_mean, 'diff': diff})
        print(f"   {m}: Kazanan Ort={w_mean:.2f} | Kaybeden Ort={l_mean:.2f} | Fark={diff:+.2f}")
    
    # Generate Report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 🧬 {SYMBOL} DNA Raporu\n")
        f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"> [!IMPORTANT]\n> Look-Ahead Bias Koruması: **AKTİF** (Günlük veri sadece önceki gün kapanışından alındı)\n\n")
        
        f.write(f"## 📊 Genel Başarı\n")
        f.write(f"| Metrik | Değer |\n|---|---|\n")
        f.write(f"| Toplam Tetik | **{total}** |\n")
        f.write(f"| Başarılı (≥5%) | **{successes}** ({success_rate:.1f}%) |\n")
        f.write(f"| Başarısız (<5%) | **{total - successes}** ({100-success_rate:.1f}%) |\n\n")
        
        f.write(f"## 🏅 Tier Dağılımı\n")
        f.write(f"| Tier | Adet | Oran |\n|---|---|---|\n")
        for t in ['💎', '🥇', '🥈', '🥉', '❌']:
            cnt = tier_counts.get(t, 0)
            pct = (cnt / total) * 100 if total > 0 else 0
            f.write(f"| {t} | {cnt} | {pct:.1f}% |\n")
        f.write("\n")
        
        f.write(f"## 🚪 GATE 1: Günlük Eleme (Önceki Gün Kapanış)\n")
        f.write(f"| Metrik | Kazanan Ort | Kaybeden Ort | Fark |\n|---|---|---|---|\n")
        for a in gate1_analysis:
            sign = "🟢" if a['diff'] > 0 else "🔴" if a['diff'] < 0 else "⚪"
            f.write(f"| {a['metric']} | {a['winner_avg']:.2f} | {a['loser_avg']:.2f} | {sign} {a['diff']:+.2f} |\n")
        f.write("\n")
        
        f.write(f"## ⚡ GATE 2: Tetik Anı (15m)\n")
        f.write(f"| Metrik | Kazanan Ort | Kaybeden Ort | Fark |\n|---|---|---|---|\n")
        for a in gate2_analysis:
            sign = "🟢" if a['diff'] > 0 else "🔴" if a['diff'] < 0 else "⚪"
            f.write(f"| {a['metric']} | {a['winner_avg']:.2f} | {a['loser_avg']:.2f} | {sign} {a['diff']:+.2f} |\n")
        f.write("\n")
        
        # Insights
        f.write(f"## 💡 Dahi Modu Yorumları\n")
        
        # Find strongest Gate 1 signal
        gate1_sorted = sorted(gate1_analysis, key=lambda x: abs(x['diff']), reverse=True)
        if gate1_sorted:
            top_g1 = gate1_sorted[0]
            f.write(f"### Gate 1 En Güçlü Sinyal\n")
            f.write(f"**{top_g1['metric']}**: Kazananlar ortalama **{top_g1['winner_avg']:.2f}**, kaybedenler **{top_g1['loser_avg']:.2f}**.\n")
            if top_g1['diff'] > 0:
                f.write(f"→ Bu metrik **yüksekse** başarı şansı artıyor.\n\n")
            else:
                f.write(f"→ Bu metrik **düşükse** başarı şansı artıyor.\n\n")
        
        # Find strongest Gate 2 signal
        gate2_sorted = sorted(gate2_analysis, key=lambda x: abs(x['diff']), reverse=True)
        if gate2_sorted:
            top_g2 = gate2_sorted[0]
            f.write(f"### Gate 2 En Güçlü Sinyal\n")
            f.write(f"**{top_g2['metric']}**: Kazananlar ortalama **{top_g2['winner_avg']:.2f}**, kaybedenler **{top_g2['loser_avg']:.2f}**.\n")
            if top_g2['diff'] > 0:
                f.write(f"→ Bu metrik **yüksekse** başarı şansı artıyor.\n\n")
            else:
                f.write(f"→ Bu metrik **düşükse** başarı şansı artıyor.\n\n")

    print(f"\n✅ Rapor oluşturuldu: {REPORT_FILE}")

if __name__ == "__main__":
    run_dna_analysis()
