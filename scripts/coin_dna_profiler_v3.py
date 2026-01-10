"""
Coin DNA Profiler V3 - Definitive Reference Edition
====================================================
More thoughtful metrics focused on TRADING STRATEGY FIT.
Groups: TITAN, SURFER, NEEDLE, WAVE, ZOMBIE, GHOST
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from tezaver.core import config, coin_cell_paths
import json


def calculate_dna(symbol: str) -> Optional[Dict]:
    """Calculate comprehensive DNA profile for a coin."""
    try:
        path = coin_cell_paths.get_history_file(symbol, "1d")
        if not path.exists():
            return None
        
        df = pd.read_parquet(path)
        if len(df) < 30:
            return None
        
        # ====== CORE METRICS ======
        
        # 1. VOLATILITY (Ortalama günlük hareket)
        df['range_pct'] = (df['high'] - df['low']) / df['open'] * 100
        avg_volatility = float(df['range_pct'].mean())
        
        # 2. WICK RATIO (İğne vs Gövde - Ne kadar "needle" atıyor?)
        df['body'] = abs(df['close'] - df['open'])
        df['upper_wick'] = df['high'] - df[['close', 'open']].max(axis=1)
        df['lower_wick'] = df[['close', 'open']].min(axis=1) - df['low']
        df['total_wick'] = df['upper_wick'] + df['lower_wick']
        df['wick_ratio'] = df['total_wick'] / (df['body'] + 0.0001)
        avg_wick_ratio = float(df['wick_ratio'].replace([np.inf, -np.inf], np.nan).dropna().mean())
        avg_wick_ratio = min(10, avg_wick_ratio)  # Cap at 10
        
        # 3. PUMP SUSTAINABILITY (Yükselişler tutunuyor mu?)
        df['green'] = df['close'] > df['open']
        df['green_streak'] = df['green'].astype(int)
        streaks = []
        current = 0
        for g in df['green'].values:
            if g:
                current += 1
            else:
                if current > 0:
                    streaks.append(current)
                current = 0
        avg_green_streak = float(np.mean(streaks)) if streaks else 1.0
        
        # 4. DUMP SPEED (Düşüşler ne kadar sert?)
        df['returns'] = df['close'].pct_change()
        negative_returns = df[df['returns'] < 0]['returns']
        avg_dump_speed = float(abs(negative_returns.mean()) * 100) if len(negative_returns) > 0 else 0
        
        # 5. TREND STABILITY (Trend ne kadar stabil?)
        df['ema10'] = df['close'].ewm(span=10).mean()
        df['ema30'] = df['close'].ewm(span=min(30, len(df)-1)).mean()
        df['above_ema'] = df['close'] > df['ema30']
        trend_stability = float(df['above_ema'].tail(30).mean() * 100)  # % of last 30 days above EMA30
        
        # 6. LIQUIDITY SCORE (Hacim stabilitesi)
        vol_cv = df['volume'].std() / (df['volume'].mean() + 0.0001)
        liquidity_score = max(0, min(100, 100 - vol_cv * 25))
        
        # 7. BTC CORRELATION
        btc_corr = 0.5  # Default
        if symbol != "BTCUSDT":
            try:
                btc_path = coin_cell_paths.get_history_file("BTCUSDT", "1d")
                if btc_path.exists():
                    btc_df = pd.read_parquet(btc_path)
                    btc_df['ret'] = btc_df['close'].pct_change()
                    df['ret'] = df['close'].pct_change()
                    min_len = min(len(df)-1, len(btc_df)-1, 100)
                    if min_len > 20:
                        c1 = df['ret'].iloc[-min_len:].values
                        c2 = btc_df['ret'].iloc[-min_len:].values
                        valid = ~(np.isnan(c1) | np.isnan(c2))
                        if valid.sum() > 20:
                            corr = np.corrcoef(c1[valid], c2[valid])[0, 1]
                            if not np.isnan(corr):
                                btc_corr = float(corr)
            except:
                pass
        
        # 8. MAX SINGLE DAY MOVE
        max_daily_move = float(df['range_pct'].max())
        
        # ====== CLASSIFICATION ======
        character = classify_character(
            avg_volatility, avg_wick_ratio, avg_green_streak,
            avg_dump_speed, trend_stability, liquidity_score,
            btc_corr, max_daily_move
        )
        
        return {
            'symbol': symbol,
            'character': character,
            'volatility': round(avg_volatility, 2),
            'wick_ratio': round(avg_wick_ratio, 2),
            'pump_streak': round(avg_green_streak, 2),
            'dump_speed': round(avg_dump_speed, 2),
            'trend_stability': round(trend_stability, 1),
            'liquidity': round(liquidity_score, 1),
            'btc_corr': round(btc_corr, 3),
            'max_move': round(max_daily_move, 1)
        }
    except Exception as e:
        return None


def classify_character(vol, wick, streak, dump, trend, liq, btc, max_mv):
    """
    Classify into 6 distinct, actionable categories:
    
    TITAN:   Düşük volatilite, yüksek likidite, stabil trend (BTC, ETH, BNB)
    SURFER:  Orta volatilite, iyi trend tutma, BTC ile uyumlu (Trend takip için ideal)
    NEEDLE:  Yüksek wick ratio, hızlı spike/crash (Scalp tehlikeli, trap riski)  
    WAVE:    Yüksek volatilite, düzgün dalgalanma (Swing trade için ideal)
    ZOMBIE:  Düşük trend stability, tahmin edilemez (Kaçın)
    GHOST:   Düşük likidite (Kayma riski, küçük pozisyon)
    """
    
    # GHOST: Çok düşük likidite - her şeyden önce kontrol et
    if liq < 30:
        return "GHOST"
    
    # TITAN: Düşük volatilite + Yüksek likidite + İyi trend
    if vol < 5 and liq > 70 and trend > 50:
        return "TITAN"
    
    # NEEDLE: Yüksek wick ratio (iğne atan)
    if wick > 2.5 or (wick > 1.5 and dump > 4):
        return "NEEDLE"
    
    # ZOMBIE: Düşük trend stability (tahmin edilemez)
    if trend < 35 and btc < 0.4:
        return "ZOMBIE"
    
    # SURFER: Orta volatilite, iyi BTC korelasyon
    if vol < 10 and btc > 0.6 and streak > 1.5:
        return "SURFER"
    
    # WAVE: Yüksek volatilite ama düzgün (wick düşük)
    if vol > 8 and wick < 1.5 and streak > 1.3:
        return "WAVE"
    
    # Default: En yaygın - volatil ama ortalama
    if vol > 7:
        return "WAVE"
    
    return "SURFER"


def main():
    print("=== COIN DNA PROFILER V3 (DEFINITIVE) ===")
    print("Creating permanent reference profiles...")
    print()
    
    coins = config.DEFAULT_COINS
    profiles = []
    
    for i, symbol in enumerate(coins):
        if i % 10 == 0:
            print(f"Processing {i}/{len(coins)}...", end='\r')
        result = calculate_dna(symbol)
        if result:
            profiles.append(result)
            
    print(f"\n\nAnalyzed {len(profiles)} coins.\n")
    
    # ====== CHARACTER DISTRIBUTION ======
    print("=" * 60)
    print("CHARACTER DISTRIBUTION")
    print("=" * 60)
    
    char_groups = {}
    for p in profiles:
        c = p['character']
        if c not in char_groups:
            char_groups[c] = []
        char_groups[c].append(p)
    
    # Define order and descriptions
    char_info = {
        'TITAN': ('🏛️', 'Ağır Kanlı Devler', 'Trend takip, Trailing SL'),
        'SURFER': ('🏄', 'Dalga Sürücüler', 'Trend takip, BTC ile uyumlu'),
        'WAVE': ('🌊', 'Volatil Dalgalar', 'Swing trade, %5-10 TP'),
        'NEEDLE': ('💉', 'İğne Atıcılar', 'DİKKAT: Trap riski, dar stop'),
        'ZOMBIE': ('🧟', 'Tahmin Edilemez', 'KAÇIN: Trend yok, rastgele'),
        'GHOST': ('👻', 'Hayaletler', 'KÜÇÜK POZ: Düşük likidite'),
    }
    
    for char, (emoji, desc, strategy) in char_info.items():
        if char not in char_groups:
            continue
        group = char_groups[char]
        
        # Calculate averages
        avg_vol = np.mean([p['volatility'] for p in group])
        avg_wick = np.mean([p['wick_ratio'] for p in group])
        avg_liq = np.mean([p['liquidity'] for p in group])
        avg_btc = np.mean([p['btc_corr'] for p in group])
        
        print(f"\n{emoji} {char}: {desc}")
        print(f"   Sayı: {len(group)} coin")
        print(f"   Vol: {avg_vol:.1f}% | Wick: {avg_wick:.1f}x | Liq: {avg_liq:.0f} | BTC Korr: {avg_btc:.2f}")
        print(f"   Strateji: {strategy}")
        
        # Show examples
        examples = [p['symbol'] for p in group[:8]]
        print(f"   Örnekler: {', '.join(examples)}")
    
    # ====== SAVE ======
    output_path = "library/coin_dna_definitive.json"
    with open(output_path, 'w') as f:
        json.dump(profiles, f, indent=2)
    print(f"\n\nSaved to {output_path}")
    
    # ====== SUMMARY TABLE ======
    print("\n" + "=" * 60)
    print("QUICK REFERENCE")
    print("=" * 60)
    for char, (emoji, desc, strategy) in char_info.items():
        if char in char_groups:
            print(f"{emoji} {char:8} → {strategy}")


if __name__ == "__main__":
    main()
