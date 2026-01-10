"""
Coin Multi-Dimensional DNA Profiler
====================================
Calculates 5 scores (0-100) for each coin and clusters them naturally.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from tezaver.core import config, coin_cell_paths
import json


def calculate_scores(symbol: str) -> Optional[Dict]:
    """Calculate 5-axis scores for a coin."""
    try:
        path = coin_cell_paths.get_history_file(symbol, "1d")
        if not path.exists():
            return None
        
        df = pd.read_parquet(path)
        if len(df) < 30:  # Lowered from 100 to 30
            return None
            
        # === VOLATILITY SCORE ===
        df['daily_move'] = (df['high'] - df['low']) / df['open'] * 100
        avg_daily_move = df['daily_move'].mean()
        max_daily_move = df['daily_move'].max()
        vol_score = min(100, avg_daily_move * 10 + max_daily_move * 0.5)
        
        # === TREND SCORE ===
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['ema50'] = df['close'].ewm(span=min(50, len(df)-1)).mean()
        df['trend'] = np.where(df['ema20'] > df['ema50'], 1, -1)
        df['trend_change'] = df['trend'] != df['trend'].shift(1)
        trend_changes = df['trend_change'].sum()
        avg_trend_duration = len(df) / max(trend_changes, 1)
        trend_score = min(100, avg_trend_duration * 3)
        
        # === INDEPENDENCE SCORE (inverse BTC correlation) ===
        independence_score = 50  # Default
        if symbol != "BTCUSDT":
            try:
                btc_path = coin_cell_paths.get_history_file("BTCUSDT", "1d")
                if btc_path.exists():
                    btc_df = pd.read_parquet(btc_path)
                    btc_df['returns'] = btc_df['close'].pct_change()
                    df['returns'] = df['close'].pct_change()
                    
                    # Align by taking last N rows
                    min_len = min(len(df) - 1, len(btc_df) - 1, 200)
                    if min_len > 20:
                        coin_ret = df['returns'].iloc[-min_len:].values
                        btc_ret = btc_df['returns'].iloc[-min_len:].values
                        
                        # Clean NaN
                        valid = ~(np.isnan(coin_ret) | np.isnan(btc_ret))
                        if valid.sum() > 20:
                            corr = np.corrcoef(coin_ret[valid], btc_ret[valid])[0, 1]
                            if not np.isnan(corr):
                                independence_score = max(0, min(100, (1 - corr) * 50))
            except:
                pass
        
        # === RECOVERY SCORE ===
        recovery_score = 50  # Default
        try:
            df['cummax'] = df['close'].cummax()
            df['drawdown'] = (df['close'] - df['cummax']) / df['cummax']
            big_drops = df[df['drawdown'] <= -0.15].index.tolist()
            recovery_days = []
            for drop_idx in big_drops[:5]:
                drop_pos = df.index.get_loc(drop_idx)
                drop_price = df.iloc[drop_pos]['close']
                for i in range(drop_pos + 1, min(drop_pos + 30, len(df))):
                    if df.iloc[i]['close'] >= drop_price:
                        recovery_days.append(i - drop_pos)
                        break
            if recovery_days:
                avg_recovery = np.mean(recovery_days)
                recovery_score = max(0, min(100, 100 - avg_recovery * 3))
        except:
            pass
        
        # === LIQUIDITY SCORE ===
        liquidity_score = 50  # Default
        try:
            vol_mean = df['volume'].mean()
            vol_std = df['volume'].std()
            if vol_mean > 0:
                cv = vol_std / vol_mean
                liquidity_score = max(0, min(100, 100 - cv * 20))
        except:
            pass
        
        return {
            'symbol': symbol,
            'volatility': round(float(vol_score), 1),
            'trend': round(float(trend_score), 1),
            'independence': round(float(independence_score), 1),
            'recovery': round(float(recovery_score), 1),
            'liquidity': round(float(liquidity_score), 1)
        }
    except Exception as e:
        return None


def kmeans_simple(data, k=8, max_iter=100):
    """Simple K-means clustering without sklearn."""
    np.random.seed(42)
    # Random initial centroids
    indices = np.random.choice(len(data), k, replace=False)
    centroids = data[indices].copy()
    
    for _ in range(max_iter):
        # Assign points to nearest centroid
        distances = np.sqrt(((data[:, np.newaxis] - centroids) ** 2).sum(axis=2))
        labels = distances.argmin(axis=1)
        
        # Update centroids
        new_centroids = np.array([data[labels == i].mean(axis=0) if (labels == i).sum() > 0 else centroids[i] for i in range(k)])
        
        if np.allclose(centroids, new_centroids):
            break
        centroids = new_centroids
        
    return labels, centroids


def main():
    print("=== MULTI-DIMENSIONAL DNA PROFILER ===")
    print("Calculating 5-axis scores for all coins...")
    
    coins = config.DEFAULT_COINS
    profiles = []
    
    for i, symbol in enumerate(coins):
        if i % 10 == 0:
            print(f"Processing {i}/{len(coins)}...", end='\r')
        result = calculate_scores(symbol)
        if result:
            profiles.append(result)
            
    print(f"\n\nAnalyzed {len(profiles)} coins.")
    
    # Convert to matrix for clustering
    data = np.array([[p['volatility'], p['trend'], p['independence'], p['recovery'], p['liquidity']] for p in profiles])
    
    # Normalize for clustering
    data_norm = (data - data.mean(axis=0)) / (data.std(axis=0) + 1e-9)
    
    # Cluster into 8 groups
    labels, centroids = kmeans_simple(data_norm, k=8)
    
    # Analyze clusters
    print("\n=== CLUSTER ANALYSIS (8 Groups) ===\n")
    
    cluster_names = {}
    for cluster_id in range(8):
        mask = labels == cluster_id
        count = mask.sum()
        if count == 0:
            continue
            
        cluster_data = data[mask]
        avg_scores = cluster_data.mean(axis=0)
        
        # Name cluster based on dominant traits
        vol, trend, indep, recov, liq = avg_scores
        
        traits = []
        if vol > 60: traits.append("Volatil")
        elif vol < 30: traits.append("Sakin")
        
        if trend > 60: traits.append("Trendli")
        if indep > 60: traits.append("Bağımsız")
        if recov > 60: traits.append("Hızlı Toparlar")
        elif recov < 30: traits.append("Yavaş Toparlar")
        if liq > 70: traits.append("Likit")
        elif liq < 30: traits.append("Düşük Liq")
        
        cluster_name = " + ".join(traits) if traits else "Ortalama"
        cluster_names[cluster_id] = cluster_name
        
        # Get sample coins
        cluster_coins = [profiles[j]['symbol'] for j in range(len(profiles)) if labels[j] == cluster_id]
        sample = cluster_coins[:5]
        
        print(f"GRUP {cluster_id+1}: {cluster_name}")
        print(f"  Sayı: {count} coin")
        print(f"  Volatilite: {vol:.0f} | Trend: {trend:.0f} | Bağımsız: {indep:.0f} | Toparlanma: {recov:.0f} | Likidite: {liq:.0f}")
        print(f"  Örnekler: {', '.join(sample)}")
        print()
        
    # Save profiles with cluster assignments
    for i, p in enumerate(profiles):
        p['cluster'] = int(labels[i]) + 1
        p['cluster_name'] = cluster_names.get(labels[i], "Unknown")
        
    with open("library/coin_dna_profiles_v2.json", 'w') as f:
        json.dump(profiles, f, indent=2)
    print(f"Saved to library/coin_dna_profiles_v2.json")


if __name__ == "__main__":
    main()
