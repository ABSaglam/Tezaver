#!/usr/bin/env python3
"""
DASH Zeplin Kontrolü
"""
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

SYMBOL = "DASHUSDT"

path = coin_cell_paths.get_history_file(SYMBOL, '1d')
if not path.exists():
    print(f"❌ {SYMBOL} verisi yok")
    sys.exit()

df = pd.read_parquet(path)
if 'datetime' in df.columns:
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime')

# Daily RSI
df['rsi_d'] = calculate_rsi(df['close'])

# Weekly RSI (from daily resampled to weekly)
df_weekly = df.resample('W-MON').agg({'close': 'last'}).dropna()
df_weekly['rsi_w'] = calculate_rsi(df_weekly['close'])

print(f"🔍 {SYMBOL} - GÜNLÜK + HAFTALIK RSI RAPORU")
print("="*70)
print(f"{'TARİH':<12} {'CLOSE':<10} {'RSI_D':<8} {'RSI_W (O Hafta)':<15} {'DURUM'}")
print("-"*70)

# Son 15 gün
for d in df.index[-15:]:
    row = df.loc[d]
    rsi_d = row['rsi_d']
    
    # Get weekly RSI (previous completed week)
    prior_weeks = df_weekly[:d]
    if len(prior_weeks) > 0:
        rsi_w = prior_weeks.iloc[-1]['rsi_w']
    else:
        rsi_w = np.nan
    
    # Determine status
    status = ""
    atr_pct = 0  # Not calculating ATR here for simplicity
    
    if 55 < rsi_d < 70:
        status = "📗 NORMAL TÜNEL BÖLGESİ"
    elif rsi_d > 70:
        if not np.isnan(rsi_w) and rsi_w >= 50:
            status = "🛸 ZEPLİN (Girilebilir)"
        elif not np.isnan(rsi_w) and rsi_w < 50:
            status = "🎈 BALON (Kaçın)"
        else:
            status = "⚠️ RSI > 70 ama Haftalık bilinmiyor"
    else:
        status = "❄️ Soğuk"
    
    print(f"{d.strftime('%Y-%m-%d'):<12} {row['close']:<10.2f} {rsi_d:<8.1f} {rsi_w:<15.1f} {status}")

print("-"*70)
print("\n📅 HAFTALIK RSI DETAYI (Son 8 Hafta):")
print(df_weekly[['close', 'rsi_w']].tail(8).to_string())
