"""
🔥 Faz-2: Advanced Daily Gate Analysis - SOLUSDT
Multi-Metric Combo Rules + Aggressive Elimination
Tetik Anı = YOK. Sadece Günlük Bazlı.
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime
from itertools import combinations

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
SYMBOL = "ENSUSDT"
REPORT_FILE = f"{SYMBOL}_faz2_advanced_gate.md"

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
    """Extended daily indicators"""
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
    df_1d['ema50'] = df_1d['close'].ewm(span=50, adjust=False).mean()
    df_1d['ema200'] = df_1d['close'].ewm(span=200, adjust=False).mean()
    
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
    
    # Volume Metrics
    df_1d['vol_avg20'] = df_1d['volume'].rolling(window=20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_avg20']
    
    # Trend Flags
    df_1d['above_ema21'] = (df_1d['close'] > df_1d['ema21']).astype(int)
    df_1d['above_ema50'] = (df_1d['close'] > df_1d['ema50']).astype(int)
    df_1d['ema9_above_21'] = (df_1d['ema9'] > df_1d['ema21']).astype(int)
    df_1d['ema21_above_50'] = (df_1d['ema21'] > df_1d['ema50']).astype(int)
    
    # Daily Return
    df_1d['daily_ret'] = df_1d['close'].pct_change() * 100
    df_1d['prev_ret'] = df_1d['daily_ret'].shift(1)
    df_1d['prev2_ret'] = df_1d['daily_ret'].shift(2)
    
    # Consecutive Reds
    df_1d['is_red'] = (df_1d['close'] < df_1d['open']).astype(int)
    df_1d['consec_reds'] = df_1d['is_red'].rolling(window=3).sum()
    
    # Momentum: 3-day sum
    df_1d['mom_3d'] = df_1d['daily_ret'].rolling(window=3).sum()
    
    # Range position (close in high-low range)
    df_1d['range_pos'] = (df_1d['close'] - df_1d['low']) / (df_1d['high'] - df_1d['low'] + 0.0001)
    
    return df_1d

def calculate_15m_indicators(df_15m):
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

def test_rule(df_days, mask, tier_col='has_tier'):
    """Test elimination rule and return detailed stats"""
    total = len(df_days)
    tier_total = df_days[tier_col].sum()
    no_tier_total = total - tier_total
    
    eliminated = mask.sum()
    kept = total - eliminated
    
    tier_lost = (mask & (df_days[tier_col] == 1)).sum()
    tier_kept = tier_total - tier_lost
    
    no_tier_elim = (mask & (df_days[tier_col] == 0)).sum()
    no_tier_kept = no_tier_total - no_tier_elim
    
    # Success rate before and after
    sr_before = (tier_total / total) * 100 if total > 0 else 0
    sr_after = (tier_kept / kept) * 100 if kept > 0 else 0
    sr_improvement = sr_after - sr_before
    
    tier_preserve_pct = (tier_kept / tier_total) * 100 if tier_total > 0 else 100
    
    return {
        'eliminated': eliminated,
        'kept': kept,
        'tier_lost': tier_lost,
        'tier_lost_pct': (tier_lost / tier_total) * 100 if tier_total > 0 else 0,
        'tier_kept': tier_kept,
        'tier_kept_pct': tier_preserve_pct,
        'no_tier_elim': no_tier_elim,
        'no_tier_elim_pct': (no_tier_elim / no_tier_total) * 100 if no_tier_total > 0 else 0,
        'no_tier_kept': no_tier_kept,
        'sr_before': sr_before,
        'sr_after': sr_after,
        'sr_improvement': sr_improvement
    }

def run_faz2_analysis():
    print(f"🔥 Faz-2 Advanced Daily Gate: {SYMBOL}")
    print(f"   Dahi Modu: MAXIMUM")
    print(f"   Tetik Anı: YOK - Sadece Günlük Bazlı")
    
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
    
    # Build day-level dataset
    day_results = []
    
    for i in range(len(df_1d) - 1):
        today = df_1d.index[i]
        tomorrow = df_1d.index[i + 1]
        
        next_day_15m = df_15m[(df_15m.index >= tomorrow) & (df_15m.index < tomorrow + pd.Timedelta(days=1))]
        triggers_next = next_day_15m[next_day_15m['trigger']]
        
        has_tier = False
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
        
        today_row = df_1d.iloc[i]
        
        day_results.append({
            'date': today,
            'has_tier': 1 if has_tier else 0,
            'best_peak': best_peak,
            'd_adx': today_row.get('adx14', np.nan),
            'd_atr_pct': today_row.get('atr_pct', np.nan),
            'd_rsi': today_row.get('rsi14', np.nan),
            'd_vol_ratio': today_row.get('vol_ratio', np.nan),
            'd_above_ema21': today_row.get('above_ema21', np.nan),
            'd_above_ema50': today_row.get('above_ema50', np.nan),
            'd_ema9_above_21': today_row.get('ema9_above_21', np.nan),
            'd_ema21_above_50': today_row.get('ema21_above_50', np.nan),
            'd_daily_ret': today_row.get('daily_ret', np.nan),
            'd_prev_ret': today_row.get('prev_ret', np.nan),
            'd_consec_reds': today_row.get('consec_reds', np.nan),
            'd_mom_3d': today_row.get('mom_3d', np.nan),
            'd_range_pos': today_row.get('range_pos', np.nan),
        })
    
    df_days = pd.DataFrame(day_results)
    
    total_days = len(df_days)
    tier_days = df_days['has_tier'].sum()
    no_tier_days = total_days - tier_days
    
    print(f"\n📊 BAŞLANGIÇ DURUMU")
    print(f"   Toplam Gün: {total_days}")
    print(f"   Tier Günler: {tier_days} ({tier_days/total_days*100:.1f}%)")
    print(f"   No-Tier Günler: {no_tier_days}")
    print(f"   Başlangıç Başarı Oranı: {tier_days/total_days*100:.2f}%")
    
    # ===== AGGRESSIVE COMBO RULES =====
    combo_rules = []
    
    # Single aggressive rules
    single_rules = [
        ('d_adx < 15', df_days['d_adx'] < 15),
        ('d_adx < 20', df_days['d_adx'] < 20),
        ('d_adx < 25', df_days['d_adx'] < 25),
        ('d_rsi < 35', df_days['d_rsi'] < 35),
        ('d_rsi < 40', df_days['d_rsi'] < 40),
        ('d_rsi < 45', df_days['d_rsi'] < 45),
        ('d_vol_ratio < 0.5', df_days['d_vol_ratio'] < 0.5),
        ('d_vol_ratio < 0.6', df_days['d_vol_ratio'] < 0.6),
        ('d_vol_ratio < 0.7', df_days['d_vol_ratio'] < 0.7),
        ('d_above_ema21 == 0', df_days['d_above_ema21'] == 0),
        ('d_above_ema50 == 0', df_days['d_above_ema50'] == 0),
        ('d_daily_ret < -3', df_days['d_daily_ret'] < -3),
        ('d_daily_ret < -5', df_days['d_daily_ret'] < -5),
        ('d_consec_reds >= 3', df_days['d_consec_reds'] >= 3),
        ('d_mom_3d < -5', df_days['d_mom_3d'] < -5),
        ('d_mom_3d < -10', df_days['d_mom_3d'] < -10),
        ('d_range_pos < 0.3', df_days['d_range_pos'] < 0.3),
    ]
    
    for name, mask in single_rules:
        stats = test_rule(df_days, mask)
        stats['rule'] = name
        combo_rules.append(stats)
    
    # COMBO RULES (2 metrics)
    combo_2 = [
        ('d_adx < 20 AND d_rsi < 45', (df_days['d_adx'] < 20) & (df_days['d_rsi'] < 45)),
        ('d_adx < 25 AND d_vol_ratio < 0.7', (df_days['d_adx'] < 25) & (df_days['d_vol_ratio'] < 0.7)),
        ('d_rsi < 45 AND d_vol_ratio < 0.7', (df_days['d_rsi'] < 45) & (df_days['d_vol_ratio'] < 0.7)),
        ('d_above_ema21 == 0 AND d_rsi < 45', (df_days['d_above_ema21'] == 0) & (df_days['d_rsi'] < 45)),
        ('d_above_ema50 == 0 AND d_vol_ratio < 0.7', (df_days['d_above_ema50'] == 0) & (df_days['d_vol_ratio'] < 0.7)),
        ('d_mom_3d < -5 AND d_adx < 25', (df_days['d_mom_3d'] < -5) & (df_days['d_adx'] < 25)),
        ('d_daily_ret < -3 AND d_rsi < 50', (df_days['d_daily_ret'] < -3) & (df_days['d_rsi'] < 50)),
        ('d_consec_reds >= 2 AND d_rsi < 45', (df_days['d_consec_reds'] >= 2) & (df_days['d_rsi'] < 45)),
        ('d_range_pos < 0.3 AND d_vol_ratio < 0.8', (df_days['d_range_pos'] < 0.3) & (df_days['d_vol_ratio'] < 0.8)),
    ]
    
    for name, mask in combo_2:
        stats = test_rule(df_days, mask)
        stats['rule'] = name
        combo_rules.append(stats)
    
    # COMBO RULES (3 metrics - AGGRESSIVE)
    combo_3 = [
        ('d_adx < 25 AND d_rsi < 50 AND d_vol_ratio < 0.8', 
         (df_days['d_adx'] < 25) & (df_days['d_rsi'] < 50) & (df_days['d_vol_ratio'] < 0.8)),
        ('d_above_ema21 == 0 AND d_rsi < 50 AND d_adx < 30',
         (df_days['d_above_ema21'] == 0) & (df_days['d_rsi'] < 50) & (df_days['d_adx'] < 30)),
        ('d_mom_3d < -3 AND d_vol_ratio < 0.8 AND d_rsi < 50',
         (df_days['d_mom_3d'] < -3) & (df_days['d_vol_ratio'] < 0.8) & (df_days['d_rsi'] < 50)),
    ]
    
    for name, mask in combo_3:
        stats = test_rule(df_days, mask)
        stats['rule'] = name
        combo_rules.append(stats)
    
    # OR RULES (Any of these = eliminate)
    or_rules = [
        ('d_adx < 15 OR d_rsi < 35', (df_days['d_adx'] < 15) | (df_days['d_rsi'] < 35)),
        ('d_adx < 15 OR d_vol_ratio < 0.5', (df_days['d_adx'] < 15) | (df_days['d_vol_ratio'] < 0.5)),
        ('d_adx < 20 OR d_rsi < 35 OR d_vol_ratio < 0.5', 
         (df_days['d_adx'] < 20) | (df_days['d_rsi'] < 35) | (df_days['d_vol_ratio'] < 0.5)),
        ('d_mom_3d < -10 OR d_consec_reds >= 3',
         (df_days['d_mom_3d'] < -10) | (df_days['d_consec_reds'] >= 3)),
    ]
    
    for name, mask in or_rules:
        stats = test_rule(df_days, mask)
        stats['rule'] = name
        combo_rules.append(stats)
    
    # Sort by SR improvement then tier preservation
    combo_rules.sort(key=lambda x: (x['sr_improvement'], x['tier_kept_pct']), reverse=True)
    
    print(f"\n🔥 EN ETKİLİ ELEME KURALLARI")
    print(f"{'Kural':<55} | Elenen | Tier Kayıp | NoTier Elenen | SR Öncesi | SR Sonrası | Artış")
    print("-" * 120)
    for r in combo_rules[:15]:
        print(f"{r['rule']:<55} | {r['eliminated']:>6} | {r['tier_lost']:>3} ({r['tier_lost_pct']:>5.1f}%) | {r['no_tier_elim']:>5} ({r['no_tier_elim_pct']:>5.1f}%) | {r['sr_before']:>7.2f}% | {r['sr_after']:>8.2f}% | {r['sr_improvement']:>+6.2f}%")
    
    # Generate Report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 🔥 {SYMBOL} Faz-2: Advanced Daily Gate\n")
        f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"> [!CAUTION]\n> Dahi Modu: MAXIMUM | Tetik Anı: YOK\n\n")
        
        f.write(f"## 📊 Başlangıç Durumu\n")
        f.write(f"| Metrik | Değer |\n|---|---|\n")
        f.write(f"| Toplam Gün | {total_days} |\n")
        f.write(f"| Tier Günler | **{tier_days}** ({tier_days/total_days*100:.1f}%) |\n")
        f.write(f"| No-Tier Günler | {no_tier_days} ({no_tier_days/total_days*100:.1f}%) |\n")
        f.write(f"| Başlangıç Başarı Oranı | **{tier_days/total_days*100:.2f}%** |\n\n")
        
        f.write(f"## 🔥 En Etkili Eleme Kuralları\n")
        f.write(f"| Kural | Elenen | Tier Kayıp | No-Tier Elenen | SR Öncesi | SR Sonrası | Artış |\n")
        f.write(f"|---|---|---|---|---|---|---|\n")
        
        for r in combo_rules[:20]:
            tier_loss_str = f"**{r['tier_lost']}** ({r['tier_lost_pct']:.1f}%)"
            no_tier_str = f"{r['no_tier_elim']} ({r['no_tier_elim_pct']:.1f}%)"
            sr_icon = "🟢" if r['sr_improvement'] > 2 else "🟡" if r['sr_improvement'] > 0 else "🔴"
            f.write(f"| {r['rule']} | {r['eliminated']} | {tier_loss_str} | {no_tier_str} | {r['sr_before']:.2f}% | {r['sr_after']:.2f}% | {sr_icon} **{r['sr_improvement']:+.2f}%** |\n")
        
        f.write("\n")
        
        # Best recommendations
        f.write(f"## 💡 Dahi Modu Önerileri\n\n")
        
        # Best single with minimal tier loss
        best_safe = [r for r in combo_rules if r['tier_lost_pct'] <= 10]
        if best_safe:
            best = max(best_safe, key=lambda x: x['sr_improvement'])
            f.write(f"### 1. En Güvenli Yüksek Etki\n")
            f.write(f"**Kural:** `{best['rule']}`\n\n")
            f.write(f"- {best['eliminated']} gün eleniyor ({best['eliminated']/total_days*100:.1f}%)\n")
            f.write(f"- **Tier Kaybı:** {best['tier_lost']}/{tier_days} ({best['tier_lost_pct']:.1f}%)\n")
            f.write(f"- **No-Tier Elenen:** {best['no_tier_elim']}/{no_tier_days} ({best['no_tier_elim_pct']:.1f}%)\n")
            f.write(f"- **Başarı Oranı:** {best['sr_before']:.2f}% → **{best['sr_after']:.2f}%** ({best['sr_improvement']:+.2f}%)\n\n")
        
        # Best aggressive
        best_agg = max(combo_rules, key=lambda x: x['sr_improvement'])
        f.write(f"### 2. En Agresif (Maksimum SR Artışı)\n")
        f.write(f"**Kural:** `{best_agg['rule']}`\n\n")
        f.write(f"- {best_agg['eliminated']} gün eleniyor ({best_agg['eliminated']/total_days*100:.1f}%)\n")
        f.write(f"- **Tier Kaybı:** {best_agg['tier_lost']}/{tier_days} ({best_agg['tier_lost_pct']:.1f}%)\n")
        f.write(f"- **No-Tier Elenen:** {best_agg['no_tier_elim']}/{no_tier_days} ({best_agg['no_tier_elim_pct']:.1f}%)\n")
        f.write(f"- **Başarı Oranı:** {best_agg['sr_before']:.2f}% → **{best_agg['sr_after']:.2f}%** ({best_agg['sr_improvement']:+.2f}%)\n\n")
        
        # Best combo that eliminates most days
        best_elim = max([r for r in combo_rules if r['tier_kept_pct'] >= 80], key=lambda x: x['eliminated'], default=None)
        if best_elim:
            f.write(f"### 3. Maksimum Eleme (≥80% Tier Koruma)\n")
            f.write(f"**Kural:** `{best_elim['rule']}`\n\n")
            f.write(f"- {best_elim['eliminated']} gün eleniyor ({best_elim['eliminated']/total_days*100:.1f}%)\n")
            f.write(f"- **Tier Kaybı:** {best_elim['tier_lost']}/{tier_days} ({best_elim['tier_lost_pct']:.1f}%)\n")
            f.write(f"- **No-Tier Elenen:** {best_elim['no_tier_elim']}/{no_tier_days} ({best_elim['no_tier_elim_pct']:.1f}%)\n")
            f.write(f"- **Başarı Oranı:** {best_elim['sr_before']:.2f}% → **{best_elim['sr_after']:.2f}%** ({best_elim['sr_improvement']:+.2f}%)\n")
    
    print(f"\n✅ Rapor oluşturuldu: {REPORT_FILE}")

if __name__ == "__main__":
    run_faz2_analysis()
