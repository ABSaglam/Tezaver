"""
🎹 FAZ-A: Multi-Timeframe Structure Analysis - ENSUSDT
"Ritim ve Ruh Analizi" (MTF Harmony & Evolution)
Goal: Predict Next Day Tier using 1D + 4H + 1H structural evolution.
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import _tree
from sklearn.metrics import precision_score, recall_score, accuracy_score
from scipy.stats import linregress

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
SYMBOL = "ENSUSDT"
REPORT_FILE = f"{SYMBOL}_faza_mtf_structure.md"

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

def calculate_slope(series):
    """Calculate slope of the last n points"""
    try:
        y = series.values
        x = np.arange(len(y))
        slope, _, _, _, _ = linregress(x, y)
        return slope
    except:
        return 0

def engineer_structure(df_1d, df_4h, df_1h):
    """
    Engineer 'Rhythm & Soul' features by analyzing 4H and 1H structure
    leading up to the daily close.
    """
    features = []
    
    print("   Özellik Mühendisliği Başlıyor (1D + 4H + 1H)...")
    
    # Pre-calculate base indicators for 4H and 1H to save time in loop
    # 4H Indicators
    df_4h['rsi'] = 100 - (100 / (1 + df_4h['close'].diff().where(df_4h['close'].diff() > 0, 0).rolling(14).mean() / (-df_4h['close'].diff().where(df_4h['close'].diff() < 0, 0)).rolling(14).mean()))
    df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
    
    # 1H Indicators
    df_1h['rsi'] = 100 - (100 / (1 + df_1h['close'].diff().where(df_1h['close'].diff() > 0, 0).rolling(14).mean() / (-df_1h['close'].diff().where(df_1h['close'].diff() < 0, 0)).rolling(14).mean()))
    df_1h['ema50'] = df_1h['close'].ewm(span=50, adjust=False).mean()
    
    valid_days = df_1d.index
    
    for i, day in enumerate(valid_days):
        # We need the close of 'day'. The structural features are derived from
        # candles ending ON or BEFORE 'day' close.
        # Daily index is usually 00:00 start of day. 
        # So for a day row '2024-01-01', it represents the day OF Jan 1st? 
        # Actually in crypto daily data usually has timestamp of open.
        # So we need data up to Next Day Open (which is This Day Close).
        
        # Correction: If df_1d index is '2024-01-01', it covers 01-01 00:00 to 01-01 23:59.
        # We want to predict effective TOMORROW (Jan 2nd).
        # So we use data strictly ending at '2024-01-01 23:59'.
        
        # Since timestamps are usually OPEN times:
        day_start = day
        day_end = day + pd.Timedelta(days=1) # The close of the day
        
        # Get 4H candles ending BEFORE or AT day_end
        # Last 6 candles of 4H (24 hours)
        mask_4h = (df_4h.index >= day_start) & (df_4h.index < day_end)
        sub_4h = df_4h[mask_4h].tail(6)
        
        # Get 1H candles
        # Last 24 candles of 1H (24 hours)
        mask_1h = (df_1h.index >= day_start) & (df_1h.index < day_end)
        sub_1h = df_1h[mask_1h].tail(24)
        
        if len(sub_4h) < 6 or len(sub_1h) < 24:
            continue
            
        feat = {'date': day}
        
        # --- 1. HARMONY (Ahenk) ---
        # Is 1H trend aligned with 4H trend?
        trend_4h = 1 if sub_4h['close'].iloc[-1] > sub_4h['ema21'].iloc[-1] else -1
        trend_1h = 1 if sub_1h['close'].iloc[-1] > sub_1h['ema50'].iloc[-1] else -1
        feat['harmony_trend'] = 1 if trend_4h == trend_1h else 0
        
        # --- 2. EVOLUTION (Gelişim/İvme) ---
        # 4H RSI Slope (Last 3 candles -> last 12 hours)
        # Is it accelerating into close?
        feat['slope_4h_rsi'] = calculate_slope(sub_4h['rsi'].tail(3))
        
        # 1H Volume Slope (Last 6 candles -> last 6 hours)
        # Is volume growing into close?
        feat['slope_1h_vol'] = calculate_slope(sub_1h['volume'].tail(6))
        
        # 1H Price Slope
        feat['slope_1h_close'] = calculate_slope(sub_1h['close'].tail(6))
        
        # --- 3. STATE (Durum) ---
        # "Sprint" finish? (Close near High)
        day_range = sub_1h['high'].max() - sub_1h['low'].min()
        if day_range > 0:
            feat['close_pos_pct'] = (sub_1h['close'].iloc[-1] - sub_1h['low'].min()) / day_range
        else:
            feat['close_pos_pct'] = 0.5
            
        # Volatility Compression? (Std dev of last 24 1H closes)
        feat['1h_volatility'] = sub_1h['close'].std() / sub_1h['close'].mean()
        
        # --- 4. DAILY CONTEXT (Re-add key daily metrics) ---
        # We can merge these later or calc simple ones here
        # Daily Simple MA trends
        d_close = sub_4h['close'].iloc[-1] # Approx daily close
        # (Assuming df_1d has metrics already calculated, allow merging later)
        
        features.append(feat)
        
    return pd.DataFrame(features).set_index('date')

def run_faza_analysis():
    print(f"🎹 FAZ-A: Ritim ve Ruh Analizi ({SYMBOL})")
    
    # Load Data
    base_path = os.path.join(COIN_CELLS_DIR, SYMBOL, "data")
    df_1d = load_clean(os.path.join(base_path, "history_1d.parquet"))
    df_4h = load_clean(os.path.join(base_path, "history_4h.parquet"))
    df_1h = load_clean(os.path.join(base_path, "history_1h.parquet"))
    df_15m = load_clean(os.path.join(base_path, "history_15m.parquet"))
    
    if df_1d.empty: return
    
    # Filter Date
    start = '2023-01-01'
    df_1d = df_1d[df_1d.index >= start]
    df_4h = df_4h[df_4h.index >= start]
    df_1h = df_1h[df_1h.index >= start]
    
    # 1. Structural Feature Engineering
    df_structure = engineer_structure(df_1d, df_4h, df_1h)
    print(f"   Çıkarılan Yapısal Veri: {len(df_structure)} gün")
    
    # 2. Add Daily Metrics (Context)
    # Calculate simple daily metrics on df_1d
    df_1d['ema50'] = df_1d['close'].ewm(span=50).mean()
    df_1d['d_above_ema50'] = (df_1d['close'] > df_1d['ema50']).astype(int)
    
    # ATR/ADX
    high_low = df_1d['high'] - df_1d['low']
    high_close = np.abs(df_1d['high'] - df_1d['close'].shift())
    low_close = np.abs(df_1d['low'] - df_1d['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df_1d['d_atr_pct'] = (true_range.rolling(14).mean() / df_1d['close']) * 100
    
    # Merge Structure with Daily Context
    # df_structure index is 'date'. Join with df_1d
    df_final = df_structure.join(df_1d[['d_above_ema50', 'd_atr_pct']], how='inner')
    
    # 3. Create Target (Next Day Tier)
    df_final['target'] = 0
    for day in df_final.index:
        tomorrow = day + pd.Timedelta(days=1)
        next_day_bars = df_15m[(df_15m.index >= tomorrow) & (df_15m.index < tomorrow + pd.Timedelta(days=1))]
        if next_day_bars.empty: continue
        
        # Check simple peak > 5% logic for efficiency (approx Tier)
        # Or detailed trigger logic? Let's use simple peak for now to find signal
        # A day is 'Tier' if it has range expansion > 5%? 
        # No, let's look for valid RSI triggers like before.
        # Re-using simplified trigger logic for speed:
        # Check if 15m RSI crossed up? Too slow to calc full ribbon for 3 years inside loop structure.
        # Using a proxy from previous Faz files or re-calc globally?
        # Let's trust the "Peak > 5%" proxy for now as "Potential Tier Day"
        # Since triggers almost always happen on big green days.
        
        open_p = next_day_bars['open'].iloc[0]
        high_p = next_day_bars['high'].max()
        if (high_p / open_p) - 1 >= 0.05:
            df_final.at[day, 'target'] = 1
            
    df_final = df_final.dropna()
    
    # 4. ML Training
    train_mask = df_final.index < '2025-01-01'
    test_mask = df_final.index >= '2025-01-01'
    
    X = df_final.drop(['target'], axis=1)
    y = df_final['target']
    
    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]
    
    print(f"   Train: {len(X_train)} | Test: {len(X_test)}")
    
    clf = RandomForestClassifier(n_estimators=100, max_depth=4, random_state=42, class_weight='balanced')
    clf.fit(X_train, y_train)
    
    y_pred = clf.predict(X_test)
    
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred)
    acc = accuracy_score(y_test, y_pred)
    
    print(f"\n📊 FAZ-A SONUÇLAR (2025 Test)")
    print(f"   Precision: {prec:.1%}")
    print(f"   Recall: {rec:.1%}")
    print(f"   Accuracy: {acc:.1%}")
    
    # Feature Importance
    imps = pd.Series(clf.feature_importances_, index=X.columns).sort_values(ascending=False)
    print("\n🔑 En Önemli 'Ruh' Değişkenleri:")
    print(imps.head(10))
    
    # Rule Extraction (Top Leaf)
    # Just look for the single best path in first tree for demo
    tree = clf.estimators_[0]
    # (Simplified rule printer)
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 🎹 FAZ-A: Ritim ve Ruh Analizi (ENSUSDT)\n")
        f.write(f"**Precision:** {prec:.1%}\n\n")
        f.write(f"## 🔑 En Önemli Faktörler\n")
        for i, v in imps.head(10).items():
            f.write(f"- **{i}**: {v:.3f}\n")
    
    print(f"\n✅ Rapor: {REPORT_FILE}")

if __name__ == "__main__":
    run_faza_analysis()
