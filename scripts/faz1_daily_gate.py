"""
🚪 Faz-1: Daily Gate Analysis - SOLUSDT
"Gün kapanışında ne oldu da ertesi gün başarılı/başarısız oldu?"
Amaç: Tier'leri kaybetmeden kötü günleri elemek
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
SYMBOL = "SOLUSDT"
REPORT_FILE = f"{SYMBOL}_faz1_daily_gate.md"

def load_clean(path):
    try:
        df = pd.read_parquet(path)
        if 'timestamp' in df.columns:
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df = df[~df.index.duplicated(keep='last')]
            return df.sort_index()
    except:
        return pd.DataFrame()

def calculate_daily_metrics(df_1d):
    """Calculate daily indicators"""
    df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
    df_1d['ema50'] = df_1d['close'].ewm(span=50, adjust=False).mean()
    
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
    
    # Volume Ratio
    df_1d['vol_avg20'] = df_1d['volume'].rolling(window=20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_avg20']
    
    # Trend Flags
    df_1d['above_ema21'] = (df_1d['close'] > df_1d['ema21']).astype(int)
    df_1d['above_ema50'] = (df_1d['close'] > df_1d['ema50']).astype(int)
    df_1d['ema21_above_50'] = (df_1d['ema21'] > df_1d['ema50']).astype(int)
    
    # Daily Return
    df_1d['daily_ret'] = df_1d['close'].pct_change() * 100
    
    # Candle Body %
    df_1d['body_pct'] = ((df_1d['close'] - df_1d['open']) / df_1d['open']) * 100
    
    return df_1d

def calculate_15m_indicators(df_15m):
    """RSI-EMA and Ribbon for trigger detection"""
    alpha_rsi = 1/11
    delta = df_15m['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta.where(delta < 0, 0))
    avg_gain = gain.ewm(alpha=alpha_rsi, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha_rsi, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df_15m['rsi'] = 100 - (100 / (1 + rs))
    df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
    
    ribbon_spans = [20, 25, 30, 35, 40, 45, 50, 55]
    for span in ribbon_spans:
        df_15m[f'ribbon_{span}'] = df_15m['rsi_ema'].ewm(span=span, adjust=False).mean()
    
    ribbon_cols = [f'ribbon_{s}' for s in ribbon_spans]
    df_15m['ribbon_max'] = df_15m[ribbon_cols].max(axis=1)
    
    cond_now = df_15m['rsi_ema'] >= df_15m['ribbon_max']
    cond_prev = df_15m['rsi_ema'].shift(1) < df_15m['ribbon_max'].shift(1)
    df_15m['trigger'] = cond_now & cond_prev
    
    return df_15m

def run_faz1_analysis():
    print(f"🚪 Faz-1 Daily Gate Analysis: {SYMBOL}")
    print(f"   Perspektif: 'Gün kapanışı → Ertesi gün tier oldu mu?'")
    
    base_path = os.path.join(COIN_CELLS_DIR, SYMBOL, "data")
    df_1d = load_clean(os.path.join(base_path, "history_1d.parquet"))
    df_15m = load_clean(os.path.join(base_path, "history_15m.parquet"))
    
    if df_1d.empty or df_15m.empty:
        print(f"❌ Veri bulunamadı")
        return
    
    start_date = pd.Timestamp("2023-01-01")
    end_date = pd.Timestamp("2025-12-31")
    df_1d = df_1d[(df_1d.index >= start_date) & (df_1d.index <= end_date)]
    df_15m = df_15m[(df_15m.index >= start_date) & (df_15m.index <= end_date)]
    
    df_1d = calculate_daily_metrics(df_1d)
    df_15m = calculate_15m_indicators(df_15m)
    
    print(f"   Günlük Veri: {len(df_1d)} gün")
    
    # For each day: Did next day have a Tier trigger?
    day_results = []
    
    for i in range(len(df_1d) - 1):
        today = df_1d.index[i]
        tomorrow = df_1d.index[i + 1]
        
        # Next day's 15m data
        next_day_15m = df_15m[(df_15m.index >= tomorrow) & (df_15m.index < tomorrow + pd.Timedelta(days=1))]
        
        # Find triggers in next day
        triggers_next = next_day_15m[next_day_15m['trigger']]
        
        has_tier = False
        best_tier = '❌'
        best_peak = 0
        
        for trig_time in triggers_next.index:
            trig_idx = df_15m.index.get_loc(trig_time)
            if trig_idx + 21 >= len(df_15m):
                continue
            entry_price = df_15m['close'].iloc[trig_idx]
            future_bars = df_15m.iloc[trig_idx+1 : trig_idx+22]
            if future_bars.empty:
                continue
            peak_price = future_bars['high'].max()
            peak_pct = ((peak_price / entry_price) - 1) * 100
            
            if peak_pct >= 5:
                has_tier = True
                if peak_pct > best_peak:
                    best_peak = peak_pct
                    if peak_pct >= 30: best_tier = '💎'
                    elif peak_pct >= 20: best_tier = '🥇'
                    elif peak_pct >= 10: best_tier = '🥈'
                    else: best_tier = '🥉'
        
        # Today's CLOSED metrics (what we know at end of day)
        today_row = df_1d.iloc[i]
        
        day_results.append({
            'date': today,
            'next_date': tomorrow,
            'has_tier': 1 if has_tier else 0,
            'best_tier': best_tier,
            'best_peak': best_peak,
            # Daily Metrics (CLOSED)
            'd_adx': today_row.get('adx14', np.nan),
            'd_atr_pct': today_row.get('atr_pct', np.nan),
            'd_rsi': today_row.get('rsi14', np.nan),
            'd_vol_ratio': today_row.get('vol_ratio', np.nan),
            'd_above_ema21': today_row.get('above_ema21', np.nan),
            'd_above_ema50': today_row.get('above_ema50', np.nan),
            'd_ema21_above_50': today_row.get('ema21_above_50', np.nan),
            'd_daily_ret': today_row.get('daily_ret', np.nan),
            'd_body_pct': today_row.get('body_pct', np.nan),
        })
    
    df_days = pd.DataFrame(day_results)
    
    total_days = len(df_days)
    tier_days = df_days['has_tier'].sum()
    no_tier_days = total_days - tier_days
    
    print(f"\n📊 SONUÇLAR")
    print(f"   Toplam Gün: {total_days}")
    print(f"   Tier Olan Günler: {tier_days} ({tier_days/total_days*100:.1f}%)")
    print(f"   Tier Olmayan Günler: {no_tier_days} ({no_tier_days/total_days*100:.1f}%)")
    
    # Compare Tier Days vs No-Tier Days
    tier_df = df_days[df_days['has_tier'] == 1]
    no_tier_df = df_days[df_days['has_tier'] == 0]
    
    metrics = ['d_adx', 'd_atr_pct', 'd_rsi', 'd_vol_ratio', 'd_above_ema21', 'd_above_ema50', 'd_ema21_above_50', 'd_daily_ret', 'd_body_pct']
    
    print(f"\n🔬 GÜNLÜK METRİK KARŞILAŞTIRMASI")
    analysis = []
    for m in metrics:
        tier_mean = tier_df[m].mean() if not tier_df.empty else 0
        no_tier_mean = no_tier_df[m].mean() if not no_tier_df.empty else 0
        diff = tier_mean - no_tier_mean
        analysis.append({'metric': m, 'tier_avg': tier_mean, 'no_tier_avg': no_tier_mean, 'diff': diff})
        print(f"   {m}: Tier={tier_mean:.2f} | No-Tier={no_tier_mean:.2f} | Fark={diff:+.2f}")
    
    # Find Elimination Rules
    print(f"\n🚪 ELEME KURALLARI ARAŞTIRMASI")
    
    # Test different thresholds for each metric
    elimination_tests = []
    
    # ADX tests
    for thresh in [15, 20, 25, 30, 35]:
        mask = df_days['d_adx'] < thresh
        eliminated = mask.sum()
        tier_lost = (mask & (df_days['has_tier'] == 1)).sum()
        no_tier_eliminated = (mask & (df_days['has_tier'] == 0)).sum()
        if eliminated > 0:
            tier_preservation = 1 - (tier_lost / tier_days) if tier_days > 0 else 1
            elimination_tests.append({
                'rule': f'd_adx < {thresh}',
                'eliminated': eliminated,
                'tier_lost': tier_lost,
                'no_tier_elim': no_tier_eliminated,
                'tier_preserved_pct': tier_preservation * 100
            })
    
    # RSI tests
    for thresh in [30, 35, 40, 45]:
        mask = df_days['d_rsi'] < thresh
        eliminated = mask.sum()
        tier_lost = (mask & (df_days['has_tier'] == 1)).sum()
        no_tier_eliminated = (mask & (df_days['has_tier'] == 0)).sum()
        if eliminated > 0:
            tier_preservation = 1 - (tier_lost / tier_days) if tier_days > 0 else 1
            elimination_tests.append({
                'rule': f'd_rsi < {thresh}',
                'eliminated': eliminated,
                'tier_lost': tier_lost,
                'no_tier_elim': no_tier_eliminated,
                'tier_preserved_pct': tier_preservation * 100
            })
    
    # Volume ratio tests
    for thresh in [0.5, 0.6, 0.7, 0.8]:
        mask = df_days['d_vol_ratio'] < thresh
        eliminated = mask.sum()
        tier_lost = (mask & (df_days['has_tier'] == 1)).sum()
        no_tier_eliminated = (mask & (df_days['has_tier'] == 0)).sum()
        if eliminated > 0:
            tier_preservation = 1 - (tier_lost / tier_days) if tier_days > 0 else 1
            elimination_tests.append({
                'rule': f'd_vol_ratio < {thresh}',
                'eliminated': eliminated,
                'tier_lost': tier_lost,
                'no_tier_elim': no_tier_eliminated,
                'tier_preserved_pct': tier_preservation * 100
            })
    
    # EMA trend tests
    mask = df_days['d_above_ema21'] == 0
    eliminated = mask.sum()
    tier_lost = (mask & (df_days['has_tier'] == 1)).sum()
    no_tier_eliminated = (mask & (df_days['has_tier'] == 0)).sum()
    if eliminated > 0:
        tier_preservation = 1 - (tier_lost / tier_days) if tier_days > 0 else 1
        elimination_tests.append({
            'rule': 'd_above_ema21 == 0',
            'eliminated': eliminated,
            'tier_lost': tier_lost,
            'no_tier_elim': no_tier_eliminated,
            'tier_preserved_pct': tier_preservation * 100
        })
    
    # Sort by best tier preservation + most elimination
    elimination_tests.sort(key=lambda x: (x['tier_preserved_pct'], x['no_tier_elim']), reverse=True)
    
    print(f"\n📋 EN İYİ ELEME KURALLARI (Tier'leri Koruyarak)")
    for e in elimination_tests[:10]:
        print(f"   {e['rule']}: {e['eliminated']} gün elendi | {e['tier_lost']} tier kaybı | Tier Koruma: {e['tier_preserved_pct']:.1f}%")
    
    # Generate Report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 🚪 {SYMBOL} Faz-1: Daily Gate Analizi\n")
        f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"> [!NOTE]\n> Perspektif: 'Gün kapanışında ne oldu da ertesi gün tier oldu/olmadı?'\n\n")
        
        f.write(f"## 📊 Özet\n")
        f.write(f"| Metrik | Değer |\n|---|---|\n")
        f.write(f"| Toplam Gün | {total_days} |\n")
        f.write(f"| Tier Olan Günler | {tier_days} ({tier_days/total_days*100:.1f}%) |\n")
        f.write(f"| Tier Olmayan Günler | {no_tier_days} ({no_tier_days/total_days*100:.1f}%) |\n\n")
        
        f.write(f"## 🔬 Günlük Kapanış Metrikleri\n")
        f.write(f"| Metrik | Tier Günleri Ort | No-Tier Günleri Ort | Fark |\n|---|---|---|---|\n")
        for a in analysis:
            sign = "🟢" if a['diff'] > 0 else "🔴" if a['diff'] < 0 else "⚪"
            f.write(f"| {a['metric']} | {a['tier_avg']:.2f} | {a['no_tier_avg']:.2f} | {sign} {a['diff']:+.2f} |\n")
        f.write("\n")
        
        f.write(f"## 🚪 Eleme Kuralları (Tier Koruma Öncelikli)\n")
        f.write(f"| Kural | Elenen Gün | Kaybedilen Tier | No-Tier Elenen | Tier Koruma |\n|---|---|---|---|---|\n")
        for e in elimination_tests[:10]:
            icon = "✅" if e['tier_preserved_pct'] >= 95 else "⚠️" if e['tier_preserved_pct'] >= 90 else "❌"
            f.write(f"| {e['rule']} | {e['eliminated']} | {e['tier_lost']} | {e['no_tier_elim']} | {icon} {e['tier_preserved_pct']:.1f}% |\n")
        f.write("\n")
        
        # Best rule recommendation
        best_rules = [e for e in elimination_tests if e['tier_preserved_pct'] >= 95]
        if best_rules:
            f.write(f"## 💡 Dahi Modu Önerisi\n")
            best = max(best_rules, key=lambda x: x['no_tier_elim'])
            f.write(f"**En İyi Kural:** `{best['rule']}`\n\n")
            f.write(f"- {best['eliminated']} gün eleniyor\n")
            f.write(f"- Sadece {best['tier_lost']} tier kaybediliyor\n")
            f.write(f"- {best['no_tier_elim']} başarısız gün elemden geçiyor\n")
            f.write(f"- Tier Koruma: **{best['tier_preserved_pct']:.1f}%**\n")
    
    print(f"\n✅ Rapor oluşturuldu: {REPORT_FILE}")

if __name__ == "__main__":
    run_faz1_analysis()
