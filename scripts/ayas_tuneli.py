"""
🚇 AYAŞ TÜNELİ - Günlük Koin Filtreleme Sistemi
===============================================

Tünelden geçiş kriterleri:
- ATR% >= 15 + RSI 55-70 (TREND-V2)
- ATR% >= 12 + RSI 60-75 (NINJA-V2)

Tarihsel Performans (2 yıl, 6,608 sinyal):
- Hit Oranı: %74 (D+G+S)
- Diamond+Gold: %22.5
- Ağır Kayıp Riski: %0.2

Günlük Ortalama: ~3-4 koin tünelden geçiyor.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from tezaver.core import config, coin_cell_paths

# Ayaş Tüneli Kriterleri
TUNEL_KRITERLERI = {
    'TREND': {'atr_min': 15.0, 'rsi_min': 55, 'rsi_max': 70},
    'NINJA': {'atr_min': 12.0, 'rsi_min': 60, 'rsi_max': 75}
}

def tunel_tara():
    """Bugün tünelden geçen koinleri listele."""
    gecenler = []
    
    for symbol in config.DEFAULT_COINS:
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, '1d')
            path_4h = coin_cell_paths.get_history_file(symbol, '4h')
            if not path_1d.exists() or not path_4h.exists(): continue
            
            df_1d = pd.read_parquet(path_1d)
            df_4h = pd.read_parquet(path_4h)
            if len(df_1d) < 20 or len(df_4h) < 20: continue
            
            # ATR hesapla
            df_1d['tr'] = np.maximum(df_1d['high'] - df_1d['low'], 
                                    np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), 
                                               abs(df_1d['low'] - df_1d['close'].shift(1))))
            atr_pct = (df_1d['tr'].rolling(14).mean().iloc[-1] / df_1d['close'].iloc[-1]) * 100
            
            # RSI hesapla
            delta = df_4h['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = (100 - (100 / (1 + (gain / loss.replace(0, 0.001))))).iloc[-1]
            
            # Tünel kontrolü
            t = TUNEL_KRITERLERI['TREND']
            n = TUNEL_KRITERLERI['NINJA']
            
            is_trend = atr_pct >= t['atr_min'] and t['rsi_min'] <= rsi <= t['rsi_max']
            is_ninja = atr_pct >= n['atr_min'] and n['rsi_min'] <= rsi <= n['rsi_max']
            
            if is_trend or is_ninja:
                tip = 'TREND' if is_trend else 'NINJA'
                gecenler.append({
                    'symbol': symbol,
                    'tip': tip,
                    'atr': round(atr_pct, 1),
                    'rsi': round(rsi, 1)
                })
        except:
            continue
    
    # Sonuçları göster
    print(f"\n🚇 AYAŞ TÜNELİ - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)
    
    if not gecenler:
        print("📭 Bugün tünelden geçen koin yok.")
        return []
    
    print(f"{'Symbol':<15} | {'Tip':<6} | {'ATR%':>6} | {'RSI':>5}")
    print("-" * 55)
    
    for g in sorted(gecenler, key=lambda x: -x['atr']):
        print(f"{g['symbol']:<15} | {g['tip']:<6} | {g['atr']:>5.1f}% | {g['rsi']:>5.1f}")
    
    print("=" * 55)
    print(f"Toplam: {len(gecenler)} koin tüneli geçti 🚇")
    
    return gecenler

if __name__ == "__main__":
    tunel_tara()
