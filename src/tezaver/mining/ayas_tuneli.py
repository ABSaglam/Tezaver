"""
🚇 AYAŞ TÜNELİ - Resmi Koin Filtreleme Sistemi
===============================================
Mühür Tarihi: 2026-01-10
Versiyon: 1.0.0

Bu filtrenin parametreleri SABİTTİR. Değiştirmeyin.

Tarihsel Performans (3 Ay, 1,581 Sinyal):
- Ralli (D+G+S): %68.4
- Nötr (Bronze+Iron): %21.4
- Kayıp (-tierlar): %10.2

Kriterler:
- TREND: ATR% >= 15, RSI 55-70
- NINJA: ATR% >= 12, RSI 60-75
"""

# ⚠️ MÜHÜRLÜ PARAMETterLER - DEĞİŞTİRMEYİN ⚠️
AYAS_TUNELI_V1 = {
    'version': '1.0.0',
    'sealed_date': '2026-01-10',
    'criteria': {
        'TREND': {
            'atr_min': 15.0,
            'rsi_min': 55,
            'rsi_max': 70
        },
        'NINJA': {
            'atr_min': 12.0,
            'rsi_min': 60,
            'rsi_max': 75
        }
    },
    'performance': {
        'test_period_days': 90,
        'total_signals': 1581,
        'rally_rate': 68.4,
        'neutral_rate': 21.4,
        'loss_rate': 10.2
    }
}

import pandas as pd
import numpy as np
from datetime import datetime
from tezaver.core import config, coin_cell_paths


def tunelden_gec(symbol: str, df_1d: pd.DataFrame, df_4h: pd.DataFrame) -> dict:
    """
    Bir koinin Ayaş Tünelinden geçip geçmediğini kontrol eder.
    
    Returns:
        dict: {'passed': bool, 'type': 'TREND'|'NINJA'|None, 'atr': float, 'rsi': float}
    """
    if len(df_1d) < 20 or len(df_4h) < 20:
        return {'passed': False, 'type': None, 'atr': 0, 'rsi': 0}
    
    # ATR hesapla
    df_1d = df_1d.copy()
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
    criteria = AYAS_TUNELI_V1['criteria']
    
    t = criteria['TREND']
    is_trend = atr_pct >= t['atr_min'] and t['rsi_min'] <= rsi <= t['rsi_max']
    
    n = criteria['NINJA']
    is_ninja = atr_pct >= n['atr_min'] and n['rsi_min'] <= rsi <= n['rsi_max']
    
    if is_trend:
        return {'passed': True, 'type': 'TREND', 'atr': round(atr_pct, 1), 'rsi': round(rsi, 1)}
    elif is_ninja:
        return {'passed': True, 'type': 'NINJA', 'atr': round(atr_pct, 1), 'rsi': round(rsi, 1)}
    else:
        return {'passed': False, 'type': None, 'atr': round(atr_pct, 1), 'rsi': round(rsi, 1)}


def tunel_tara() -> list:
    """Tüm koinleri tarar ve tünelden geçenleri listeler."""
    gecenler = []
    
    for symbol in config.DEFAULT_COINS:
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, '1d')
            path_4h = coin_cell_paths.get_history_file(symbol, '4h')
            if not path_1d.exists() or not path_4h.exists(): 
                continue
            
            df_1d = pd.read_parquet(path_1d)
            df_4h = pd.read_parquet(path_4h)
            
            result = tunelden_gec(symbol, df_1d, df_4h)
            
            if result['passed']:
                gecenler.append({
                    'symbol': symbol,
                    'type': result['type'],
                    'atr': result['atr'],
                    'rsi': result['rsi']
                })
        except:
            continue
    
    return gecenler


def yazdir():
    """Tünelden geçenleri konsolda gösterir."""
    gecenler = tunel_tara()
    
    print(f"\n🚇 AYAŞ TÜNELİ v{AYAS_TUNELI_V1['version']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)
    
    if not gecenler:
        print("📭 Bugün tünelden geçen koin yok.")
        return
    
    print(f"{'Symbol':<15} | {'Tip':<6} | {'ATR%':>6} | {'RSI':>5}")
    print("-" * 55)
    
    for g in sorted(gecenler, key=lambda x: -x['atr']):
        print(f"{g['symbol']:<15} | {g['type']:<6} | {g['atr']:>5.1f}% | {g['rsi']:>5.1f}")
    
    print("=" * 55)
    print(f"Toplam: {len(gecenler)} koin tüneli geçti 🚇")


if __name__ == "__main__":
    yazdir()
