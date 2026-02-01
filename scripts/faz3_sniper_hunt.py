"""
🎯 Faz-3: Sniper Hunt - ENSUSDT
"Samanlıkta İğne Avı" (Probabilistic Cluster Analysis)
Hedef: >80-90% Olasılıkla Tier Getiren Koşullar
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime
from itertools import combinations

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
SYMBOL = "ENSUSDT"
REPORT_FILE = f"{SYMBOL}_faz3_sniper_hunt.md"

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

def calculate_metrics(df_1d):
    """Deep metric extraction including Weekly context"""
    # --- WEEKLY CONTEXT (Derived from Daily) ---
    df_1w = df_1d.resample('W').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    })
    # Weekly EMA
    df_1w['w_ema21'] = df_1w['close'].ewm(span=21, adjust=False).mean()
    df_1w['w_trend'] = (df_1w['close'] > df_1w['w_ema21']).astype(int)
    
    # Weekly RSI
    delta = df_1w['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df_1w['w_rsi'] = 100 - (100 / (1 + rs))
    
    # Map Weekly back to Daily (Forward fill to avoid look-ahead bias)
    # Reindex daily to match weekly, shift 1 week to ensure we only use CLOSED week data
    df_1w_shifted = df_1w.shift(1)
    df_1d = df_1d.join(df_1w_shifted[['w_trend', 'w_rsi']], how='left')
    df_1d['w_trend'] = df_1d['w_trend'].ffill()
    df_1d['w_rsi'] = df_1d['w_rsi'].ffill()
    
    # --- DAILY METRICS ---
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
    df_1d['ema50'] = df_1d['close'].ewm(span=50, adjust=False).mean()
    df_1d['ema200'] = df_1d['close'].ewm(span=200, adjust=False).mean()
    
    # ATR & ADX
    d_tr = np.maximum(df_1d['high'] - df_1d['low'], 
                      np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), 
                                 abs(df_1d['low'] - df_1d['close'].shift(1))))
    df_1d['atr14'] = d_tr.rolling(window=14).mean()
    df_1d['atr_pct'] = (df_1d['atr14'] / df_1d['close']) * 100
    
    plus_dm = df_1d['high'].diff()
    minus_dm = -df_1d['low'].diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    tr14 = d_tr.rolling(window=14).sum()
    plus_di = 100 * (plus_dm.rolling(window=14).sum() / tr14)
    minus_di = 100 * (minus_dm.rolling(window=14).sum() / tr14)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df_1d['adx14'] = dx.rolling(window=14).mean()
    
    # RSI
    delta = df_1d['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df_1d['rsi14'] = 100 - (100 / (1 + rs))
    
    # Volume
    df_1d['vol_avg20'] = df_1d['volume'].rolling(window=20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_avg20']
    
    # Bollinger Bands
    df_1d['bb_mid'] = df_1d['close'].rolling(window=20).mean()
    df_1d['bb_std'] = df_1d['close'].rolling(window=20).std()
    df_1d['bb_upper'] = df_1d['bb_mid'] + (2 * df_1d['bb_std'])
    df_1d['bb_lower'] = df_1d['bb_mid'] - (2 * df_1d['bb_std'])
    df_1d['bb_width'] = (df_1d['bb_upper'] - df_1d['bb_lower']) / df_1d['bb_mid']
    # %B (Position within band)
    df_1d['bb_pct_b'] = (df_1d['close'] - df_1d['bb_lower']) / (df_1d['bb_upper'] - df_1d['bb_lower'])
    
    return df_1d

def calculate_15m_trigger_check(df_15m):
    """Identify if a Trigger happened in a day"""
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

def generate_conditions(df_row):
    """Generate all boolean conditions for a single day based on strict thresholds"""
    c = {}
    
    # Trend
    c['W_Trend_UP'] = df_row['w_trend'] == 1
    c['D_Above_EMA21'] = df_row['close'] > df_row['ema21']
    c['D_Above_EMA50'] = df_row['close'] > df_row['ema50']
    c['D_EMA21_gt_EMA50'] = df_row['ema21'] > df_row['ema50']
    
    # RSI Zones
    rsi = df_row['rsi14']
    c['D_RSI_lt_40'] = rsi < 40
    c['D_RSI_40_50'] = (rsi >= 40) & (rsi < 50)
    c['D_RSI_50_60'] = (rsi >= 50) & (rsi < 60)
    c['D_RSI_gt_60'] = rsi >= 60
    
    # ADX
    adx = df_row['adx14']
    c['D_ADX_lt_20'] = adx < 20
    c['D_ADX_gt_25'] = adx > 25
    c['D_ADX_gt_40'] = adx > 40
    
    # Volume
    vr = df_row['vol_ratio']
    c['D_Vol_Low'] = vr < 0.7
    c['D_Vol_High'] = vr > 1.3
    
    # Bollinger
    bb_b = df_row['bb_pct_b']
    c['D_BB_Low'] = bb_b < 0.2
    c['D_BB_High'] = bb_b > 0.8
    c['D_BB_Mid'] = (bb_b >= 0.4) & (bb_b <= 0.6)
    
    # Weekly RSI
    w_rsi = df_row['w_rsi']
    c['W_RSI_gt_50'] = w_rsi > 50
    
    return c

def run_sniper_hunt():
    print(f"🎯 Faz-3 Sniper Hunt: {SYMBOL}")
    print(f"   Hedef: >80-90% Tier Olasılığı (Precision)")
    
    base_path = os.path.join(COIN_CELLS_DIR, SYMBOL, "data")
    df_1d = load_clean(os.path.join(base_path, "history_1d.parquet"))
    df_15m = load_clean(os.path.join(base_path, "history_15m.parquet"))
    
    if df_1d.empty or df_15m.empty:
        print("❌ Veri yok")
        return
        
    start_date = pd.Timestamp("2023-01-01")
    end_date = pd.Timestamp("2025-12-31")
    df_1d = df_1d[(df_1d.index >= start_date) & (df_1d.index <= end_date)]
    df_15m = df_15m[(df_15m.index >= start_date) & (df_15m.index <= end_date)]
    
    df_1d = calculate_metrics(df_1d)
    df_15m = calculate_15m_trigger_check(df_15m)
    
    # Prepare Dataset
    dataset = []
    
    for i in range(len(df_1d) - 1):
        today = df_1d.index[i]
        tomorrow = df_1d.index[i + 1]
        
        # Check next day for Tier
        next_day_bars = df_15m[(df_15m.index >= tomorrow) & (df_15m.index < tomorrow + pd.Timedelta(days=1))]
        triggers = next_day_bars[next_day_bars['trigger']]
        
        has_tier = False
        for t_time in triggers.index:
            t_idx = df_15m.index.get_loc(t_time)
            if t_idx + 21 >= len(df_15m): continue
            entry = df_15m['close'].iloc[t_idx]
            peak = df_15m['high'].iloc[t_idx+1 : t_idx+22].max()
            if ((peak / entry) - 1) * 100 >= 5:
                has_tier = True
                break
        
        # Get conditions
        conds = generate_conditions(df_1d.iloc[i])
        entry = {'tier': 1 if has_tier else 0}
        entry.update(conds)
        dataset.append(entry)
        
    df = pd.DataFrame(dataset)
    total_days = len(df)
    tier_days = df['tier'].sum()
    base_prob = (tier_days / total_days) * 100
    
    print(f"   Toplam Veri: {total_days} gün")
    print(f"   Tier Günleri: {tier_days} ({base_prob:.2f}%)")
    
    # --- FIND HIGH PROBABILITY CLUSTERS ---
    feature_cols = [c for c in df.columns if c != 'tier']
    
    print(f"\n🚀 Cluster Taraması Başlıyor (3-4'lü Kombinasyonlar)...")
    
    found_clusters = []
    
    valid_singles = [col for col in feature_cols if df[col].sum() >= 10]
    
    # Check Doubles
    print("   Checking Doubles...")
    for c1, c2 in combinations(valid_singles, 2):
        mask = df[c1] & df[c2]
        cnt = mask.sum()
        if cnt < 5: continue # Relaxed min sample
        hits = df[mask]['tier'].sum()
        prob = (hits / cnt) * 100
        # Relaxed threshold: Save anything > 20% just to see
        if prob >= 20: 
            found_clusters.append({'rules': [c1, c2], 'cnt': cnt, 'hits': hits, 'prob': prob})
            
    print(f"   Found {len(found_clusters)} candidate doubles > 20%")

    # Check Triples (from best doubles)
    print("   Checking Triples...")
    top_doubles = sorted(found_clusters, key=lambda x: x['prob'], reverse=True)[:100] # Check more
    for d in top_doubles:
        for c3 in valid_singles:
            if c3 in d['rules']: continue
            rules = d['rules'] + [c3]
            mask = df[rules[0]] & df[rules[1]] & df[rules[2]]
            cnt = mask.sum()
            if cnt < 5: continue
            hits = df[mask]['tier'].sum()
            prob = (hits / cnt) * 100
            if prob >= 25: # Relaxed
                found_clusters.append({'rules': rules, 'cnt': cnt, 'hits': hits, 'prob': prob})
                
    # Sort by Probability
    found_clusters.sort(key=lambda x: (x['prob'], x['hits']), reverse=True)
    
    print("\n🏆 EN YÜKSEK OLASILIKLI CLUSTERLAR (Debug Mode)")
    print(f"{'Prob':<8} | {'Hit/Tot':<10} | Kurallar")
    print("-" * 80)
    
    unique_rules = set() 
    final_list = []
    
    for c in found_clusters:
        r_str = " AND ".join(sorted(c['rules']))
        if r_str in unique_rules: continue
        unique_rules.add(r_str)
        final_list.append(c)
        if len(final_list) >= 20: break
        
    for c in final_list:
        print(f"{c['prob']:<6.1f}% | {c['hits']}/{c['cnt']:<6} | {c['rules']}")
        
    # Generate Report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 🎯 {SYMBOL} Faz-3: Sniper Hunt (Probabilistic Clusters)\n")
        f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"**Hedef:** >80-90% Olasılıkla Tier Getiren Koşullar\n")
        f.write(f"**Base Rate (Rastgele):** {base_prob:.2f}%\n\n")
        
        f.write("## 🏆 Sniper Setups (Yüksek Olasılık)\n")
        f.write("| Olasılık | Başarı/Toplam | Koşullar |\n|---|---|---|\n")
        
        for c in final_list:
            cond_str = " <br>+ ".join(c['rules'])
            icon = "🔥" if c['prob'] >= 70 else "✅" if c['prob'] >= 50 else "⚠️"
            f.write(f"| {icon} **{c['prob']:.1f}%** | {c['hits']} / {c['cnt']} | {cond_str} |\n")
            
        f.write("\n## 💡 Dahi Modu Yorumu\n")
        if final_list:
            best = final_list[0]
            f.write(f"En güçlü sinyal **{best['prob']:.1f}%** ihtimalle çalışıyor:\n")
            for r in best['rules']:
                f.write(f"- {r}\n")
            f.write(f"\nBu koşullar oluştuğunda {best['cnt']} seferin {best['hits']} tanesinde Tier gelmiş.")
            
    print(f"\n✅ Rapor: {REPORT_FILE}")

if __name__ == "__main__":
    run_sniper_hunt()
