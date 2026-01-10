"""
Coin DNA Profiler V4 - PERCENTILE Based Classification
=======================================================
Uses RELATIVE ranking (percentiles) instead of fixed thresholds.
Results in balanced groups that are actually useful for strategy selection.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from tezaver.core import config, coin_cell_paths
import json


def calculate_metrics(symbol: str) -> Optional[Dict]:
    """Calculate raw metrics for a coin."""
    try:
        path = coin_cell_paths.get_history_file(symbol, "1d")
        if not path.exists():
            return None
        
        df = pd.read_parquet(path)
        if len(df) < 30:
            return None
        
        # 1. VOLATILITY (Ortalama günlük range)
        df['range_pct'] = (df['high'] - df['low']) / df['open'] * 100
        volatility = float(df['range_pct'].mean())
        
        # 2. PUMP SUSTAINABILITY (Yeşil gün sonrası tutunma)
        # +5% gün sonrası, ertesi gün de yeşil mi?
        df['big_green'] = (df['close'] - df['open']) / df['open'] > 0.05
        df['next_green'] = (df['close'].shift(-1) > df['open'].shift(-1))
        big_greens = df[df['big_green']].copy()
        if len(big_greens) > 0:
            pump_sustain = float(big_greens['next_green'].mean() * 100)
        else:
            pump_sustain = 50.0
        
        # 3. DUMP SEVERITY (Kırmızı günler ne kadar sert?)
        df['red_pct'] = np.where(df['close'] < df['open'], 
                                  (df['open'] - df['close']) / df['open'] * 100, 0)
        dump_severity = float(df[df['red_pct'] > 0]['red_pct'].mean())
        
        # 4. TREND CONSISTENCY (EMA20 üzerinde kalma oranı)
        df['ema20'] = df['close'].ewm(span=20).mean()
        trend_consistency = float((df['close'] > df['ema20']).mean() * 100)
        
        # 5. LIQUIDITY (Hacim stabilitesi - CV'nin tersi)
        vol_cv = df['volume'].std() / (df['volume'].mean() + 0.0001)
        liquidity = max(0, min(100, 100 - vol_cv * 25))
        
        # 6. BTC CORRELATION
        btc_corr = 0.5
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
        
        return {
            'symbol': symbol,
            'volatility': round(volatility, 2),
            'pump_sustain': round(pump_sustain, 1),
            'dump_severity': round(dump_severity, 2),
            'trend_consistency': round(trend_consistency, 1),
            'liquidity': round(liquidity, 1),
            'btc_corr': round(btc_corr, 3)
        }
    except:
        return None


def classify_by_percentile(profiles: List[Dict]) -> List[Dict]:
    """Classify coins using percentile-based ranking."""
    
    # Extract metrics into arrays
    n = len(profiles)
    vol = np.array([p['volatility'] for p in profiles])
    pump = np.array([p['pump_sustain'] for p in profiles])
    dump = np.array([p['dump_severity'] for p in profiles])
    trend = np.array([p['trend_consistency'] for p in profiles])
    liq = np.array([p['liquidity'] for p in profiles])
    btc = np.array([p['btc_corr'] for p in profiles])
    
    # Calculate percentiles for each coin
    def percentile_rank(arr):
        from scipy.stats import rankdata
        return rankdata(arr, method='average') / len(arr) * 100
    
    # Manual percentile calculation (no scipy dependency)
    def manual_percentile_rank(arr):
        sorted_idx = np.argsort(arr)
        ranks = np.empty_like(sorted_idx)
        ranks[sorted_idx] = np.arange(len(arr))
        return (ranks + 1) / len(arr) * 100
    
    vol_pct = manual_percentile_rank(vol)
    pump_pct = manual_percentile_rank(pump)
    dump_pct = manual_percentile_rank(-dump)  # Lower dump is better
    trend_pct = manual_percentile_rank(trend)
    liq_pct = manual_percentile_rank(liq)
    btc_pct = manual_percentile_rank(btc)
    
    # Composite score: Higher = Better for trading
    # Good: Low volatility, High pump sustain, Low dump, High trend, High liq
    composite = (
        (100 - vol_pct) * 0.15 +  # Lower vol = better
        pump_pct * 0.25 +          # Higher pump sustain = better
        dump_pct * 0.15 +          # Lower dump severity = better (already inverted)
        trend_pct * 0.25 +         # Higher trend consistency = better
        liq_pct * 0.20             # Higher liquidity = better
    )
    
    # Classify into 6 tiers based on composite score percentile
    for i, p in enumerate(profiles):
        p['vol_rank'] = round(vol_pct[i], 1)
        p['pump_rank'] = round(pump_pct[i], 1)
        p['trend_rank'] = round(trend_pct[i], 1)
        p['liq_rank'] = round(liq_pct[i], 1)
        p['composite_score'] = round(composite[i], 1)
        
        # 6 Tiers (roughly equal distribution)
        score = composite[i]
        if score >= 83:
            p['tier'] = 'S'
            p['tier_name'] = 'S-TIER (Elite)'
        elif score >= 67:
            p['tier'] = 'A'
            p['tier_name'] = 'A-TIER (Premium)'
        elif score >= 50:
            p['tier'] = 'B'
            p['tier_name'] = 'B-TIER (Standard)'
        elif score >= 33:
            p['tier'] = 'C'
            p['tier_name'] = 'C-TIER (Risky)'
        elif score >= 17:
            p['tier'] = 'D'
            p['tier_name'] = 'D-TIER (Dangerous)'
        else:
            p['tier'] = 'F'
            p['tier_name'] = 'F-TIER (Avoid)'
    
    return profiles


def main():
    print("=== COIN DNA PROFILER V4 (PERCENTILE BASED) ===")
    print("Creating balanced tier distribution...\n")
    
    coins = config.DEFAULT_COINS
    profiles = []
    
    for i, symbol in enumerate(coins):
        if i % 10 == 0:
            print(f"Processing {i}/{len(coins)}...", end='\r')
        result = calculate_metrics(symbol)
        if result:
            profiles.append(result)
            
    print(f"\n\nAnalyzed {len(profiles)} coins.\n")
    
    # Classify
    profiles = classify_by_percentile(profiles)
    
    # Sort by composite score
    profiles.sort(key=lambda x: -x['composite_score'])
    
    # ====== TIER DISTRIBUTION ======
    print("=" * 70)
    print("TIER DISTRIBUTION")
    print("=" * 70)
    
    tiers = {}
    for p in profiles:
        t = p['tier']
        if t not in tiers:
            tiers[t] = []
        tiers[t].append(p)
    
    tier_info = {
        'S': ('🏆', 'Elite - En iyi %17', 'Trend takip, büyük pozisyon'),
        'A': ('⭐', 'Premium - %17-33', 'Trend/Swing, orta pozisyon'),
        'B': ('✅', 'Standard - %33-50', 'Scalp/Swing, dikkatli'),
        'C': ('⚠️', 'Risky - %50-67', 'Sadece scalp, dar stop'),
        'D': ('🔴', 'Dangerous - %67-83', 'Çok riskli, küçük poz'),
        'F': ('💀', 'Avoid - En kötü %17', 'KAÇIN'),
    }
    
    for tier, (emoji, desc, strategy) in tier_info.items():
        if tier not in tiers:
            continue
        group = tiers[tier]
        
        # Averages
        avg_vol = np.mean([p['volatility'] for p in group])
        avg_pump = np.mean([p['pump_sustain'] for p in group])
        avg_trend = np.mean([p['trend_consistency'] for p in group])
        avg_liq = np.mean([p['liquidity'] for p in group])
        
        examples = [p['symbol'] for p in group[:6]]
        
        print(f"\n{emoji} {tier}-TIER: {desc}")
        print(f"   Sayı: {len(group)}")
        print(f"   Vol: {avg_vol:.1f}% | Pump Tutma: {avg_pump:.0f}% | Trend: {avg_trend:.0f}% | Liq: {avg_liq:.0f}")
        print(f"   Strateji: {strategy}")
        print(f"   Örnekler: {', '.join(examples)}")
    
    # ====== SAVE ======
    output_path = "library/coin_dna_definitive.json"
    with open(output_path, 'w') as f:
        json.dump(profiles, f, indent=2)
    print(f"\n\nSaved to {output_path}")
    
    # Top 10 and Bottom 10
    print("\n" + "=" * 70)
    print("TOP 10 COINS (Best for Trading)")
    print("=" * 70)
    for p in profiles[:10]:
        print(f"  {p['symbol']:15} | Score: {p['composite_score']:.0f} | Pump: {p['pump_sustain']:.0f}% | Trend: {p['trend_consistency']:.0f}%")
    
    print("\n" + "=" * 70)
    print("BOTTOM 10 COINS (Avoid)")
    print("=" * 70)
    for p in profiles[-10:]:
        print(f"  {p['symbol']:15} | Score: {p['composite_score']:.0f} | Pump: {p['pump_sustain']:.0f}% | Trend: {p['trend_consistency']:.0f}%")


if __name__ == "__main__":
    main()
