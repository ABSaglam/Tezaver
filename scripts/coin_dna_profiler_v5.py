"""
Coin DNA Profiler V5 - FINAL DEFINITIVE VERSION
================================================
- Excludes stablecoins and derivatives
- Percentile-based balanced tiers
- Validated for trading use
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from tezaver.core import config, coin_cell_paths
import json

# Coins to EXCLUDE (stablecoins, derivatives, non-tradeable)
EXCLUDED_COINS = {
    'USDCUSDT', 'USDTUSDT', 'BUSDUSDT', 'TUSDUSDT', 'DAIUSDT',  # Stablecoins
    'PAXGUSDT',  # Gold-backed
    'BTCDOMUSDT',  # Derivative index
}


def calculate_metrics(symbol: str) -> Optional[Dict]:
    """Calculate trading-relevant metrics for a coin."""
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
        
        # 2. PUMP SUSTAINABILITY (Büyük yeşil günden sonra tutunma)
        df['green_pct'] = np.where(df['close'] > df['open'], 
                                    (df['close'] - df['open']) / df['open'] * 100, 0)
        df['next_close'] = df['close'].shift(-1)
        df['pump_held'] = df['next_close'] >= df['close']
        big_pumps = df[df['green_pct'] >= 5].copy()
        pump_sustain = float(big_pumps['pump_held'].mean() * 100) if len(big_pumps) > 0 else 50.0
        
        # 3. DUMP RECOVERY (Büyük düşüş sonrası toparlanma)
        df['red_pct'] = np.where(df['close'] < df['open'], 
                                  (df['open'] - df['close']) / df['open'] * 100, 0)
        df['next_green'] = df['close'].shift(-1) > df['open'].shift(-1)
        big_dumps = df[df['red_pct'] >= 5].copy()
        dump_recovery = float(big_dumps['next_green'].mean() * 100) if len(big_dumps) > 0 else 50.0
        
        # 4. TREND QUALITY (Trend tutarlılığı)
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['ema50'] = df['close'].ewm(span=min(50, len(df)-1)).mean()
        df['trend_aligned'] = ((df['close'] > df['ema20']) & (df['ema20'] > df['ema50']))
        trend_quality = float(df['trend_aligned'].tail(60).mean() * 100)
        
        # 5. LIQUIDITY (Hacim stabilitesi)
        vol_cv = df['volume'].std() / (df['volume'].mean() + 0.0001)
        liquidity = max(0, min(100, 100 - vol_cv * 20))
        
        # 6. BTC SYNC (BTC ile aynı yönde hareket)
        btc_sync = 50.0
        if symbol != "BTCUSDT":
            try:
                btc_path = coin_cell_paths.get_history_file("BTCUSDT", "1d")
                if btc_path.exists():
                    btc_df = pd.read_parquet(btc_path)
                    btc_df['btc_green'] = btc_df['close'] > btc_df['open']
                    df['coin_green'] = df['close'] > df['open']
                    min_len = min(len(df), len(btc_df), 100)
                    btc_dir = btc_df['btc_green'].iloc[-min_len:].values
                    coin_dir = df['coin_green'].iloc[-min_len:].values
                    btc_sync = float((btc_dir == coin_dir).mean() * 100)
            except:
                pass
        
        return {
            'symbol': symbol,
            'volatility': round(volatility, 2),
            'pump_sustain': round(pump_sustain, 1),
            'dump_recovery': round(dump_recovery, 1),
            'trend_quality': round(trend_quality, 1),
            'liquidity': round(liquidity, 1),
            'btc_sync': round(btc_sync, 1)
        }
    except:
        return None


def classify_coins(profiles: List[Dict]) -> List[Dict]:
    """Classify using percentile-based composite score."""
    n = len(profiles)
    
    # Extract arrays
    vol = np.array([p['volatility'] for p in profiles])
    pump = np.array([p['pump_sustain'] for p in profiles])
    dump = np.array([p['dump_recovery'] for p in profiles])
    trend = np.array([p['trend_quality'] for p in profiles])
    liq = np.array([p['liquidity'] for p in profiles])
    btc = np.array([p['btc_sync'] for p in profiles])
    
    # Percentile ranks
    def pct_rank(arr):
        sorted_idx = np.argsort(arr)
        ranks = np.empty_like(sorted_idx)
        ranks[sorted_idx] = np.arange(len(arr))
        return (ranks + 1) / len(arr) * 100
    
    vol_pct = 100 - pct_rank(vol)  # Lower vol = higher rank
    pump_pct = pct_rank(pump)
    dump_pct = pct_rank(dump)
    trend_pct = pct_rank(trend)
    liq_pct = pct_rank(liq)
    btc_pct = pct_rank(btc)
    
    # Composite score (weighted)
    composite = (
        vol_pct * 0.10 +      # Düşük volatilite
        pump_pct * 0.25 +     # Pump sonrası tutunma
        dump_pct * 0.15 +     # Dump sonrası toparlanma
        trend_pct * 0.25 +    # Trend kalitesi
        liq_pct * 0.15 +      # Likidite
        btc_pct * 0.10        # BTC sync
    )
    
    # Assign tiers (10 tiers for finer granularity)
    for i, p in enumerate(profiles):
        p['composite'] = round(composite[i], 1)
        p['vol_rank'] = round(vol_pct[i], 1)
        p['trend_rank'] = round(trend_pct[i], 1)
        
        score = composite[i]
        if score >= 90:
            p['tier'] = 'S'
        elif score >= 80:
            p['tier'] = 'A'
        elif score >= 70:
            p['tier'] = 'B+'
        elif score >= 60:
            p['tier'] = 'B'
        elif score >= 50:
            p['tier'] = 'B-'
        elif score >= 40:
            p['tier'] = 'C+'
        elif score >= 30:
            p['tier'] = 'C'
        elif score >= 20:
            p['tier'] = 'C-'
        elif score >= 10:
            p['tier'] = 'D'
        else:
            p['tier'] = 'F'
    
    return profiles


def main():
    print("=== COIN DNA PROFILER V5 (FINAL) ===")
    print(f"Excluding: {', '.join(EXCLUDED_COINS)}\n")
    
    coins = [c for c in config.DEFAULT_COINS if c not in EXCLUDED_COINS]
    profiles = []
    
    for i, symbol in enumerate(coins):
        if i % 20 == 0:
            print(f"Processing {i}/{len(coins)}...", end='\r')
        result = calculate_metrics(symbol)
        if result:
            profiles.append(result)
    
    print(f"\n\nAnalyzed {len(profiles)} tradeable coins.\n")
    
    # Classify
    profiles = classify_coins(profiles)
    profiles.sort(key=lambda x: -x['composite'])
    
    # ====== TIER SUMMARY ======
    print("=" * 70)
    print("TIER DISTRIBUTION (Trading Coins Only)")
    print("=" * 70)
    
    tiers = {}
    for p in profiles:
        t = p['tier']
        if t not in tiers:
            tiers[t] = []
        tiers[t].append(p)
    
    tier_meta = {
        'S': ('🏆', 'Elite', 'Trend+Swing büyük poz'),
        'A': ('⭐', 'Premium', 'Trend/Swing'),
        'B+': ('✅', 'Üst-Orta', 'Swing/Scalp'),
        'B': ('🔷', 'Orta', 'Scalp+Swing'),
        'B-': ('🔹', 'Alt-Orta', 'Scalp dikkatli'),
        'C+': ('⚠️', 'Üst-Risk', 'Sadece Scalp'),
        'C': ('🟠', 'Riskli', 'Scalp dar stop'),
        'C-': ('🔴', 'Yüksek Risk', 'Küçük poz'),
        'D': ('❌', 'Tehlikeli', 'Çok küçük poz'),
        'F': ('💀', 'Kaçın', 'TRADE ETME'),
    }
    
    for tier in ['S', 'A', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F']:
        if tier not in tiers:
            continue
        group = tiers[tier]
        emoji, name, strategy = tier_meta[tier]
        
        avg_vol = np.mean([p['volatility'] for p in group])
        avg_pump = np.mean([p['pump_sustain'] for p in group])
        avg_trend = np.mean([p['trend_quality'] for p in group])
        avg_liq = np.mean([p['liquidity'] for p in group])
        
        examples = [p['symbol'].replace('USDT', '') for p in group[:8]]
        
        print(f"\n{emoji} {tier}-TIER ({name}): {len(group)} coin")
        print(f"   Vol: {avg_vol:.1f}% | Pump Tutma: {avg_pump:.0f}% | Trend: {avg_trend:.0f}% | Liq: {avg_liq:.0f}")
        print(f"   Strateji: {strategy}")
        print(f"   → {', '.join(examples)}")
    
    # ====== TOP & BOTTOM ======
    print("\n" + "=" * 70)
    print("TOP 15 COINS")
    print("=" * 70)
    for p in profiles[:15]:
        name = p['symbol'].replace('USDT', '')
        print(f"  {name:12} | Score: {p['composite']:.0f} | Pump: {p['pump_sustain']:.0f}% | Trend: {p['trend_quality']:.0f}% | Liq: {p['liquidity']:.0f}")
    
    print("\n" + "=" * 70)
    print("BOTTOM 15 COINS (AVOID)")
    print("=" * 70)
    for p in profiles[-15:]:
        name = p['symbol'].replace('USDT', '')
        print(f"  {name:12} | Score: {p['composite']:.0f} | Pump: {p['pump_sustain']:.0f}% | Trend: {p['trend_quality']:.0f}% | Liq: {p['liquidity']:.0f}")
    
    # ====== SAVE ======
    output_path = "library/coin_dna_definitive.json"
    with open(output_path, 'w') as f:
        json.dump(profiles, f, indent=2)
    print(f"\n\nSaved {len(profiles)} profiles to {output_path}")


if __name__ == "__main__":
    main()
