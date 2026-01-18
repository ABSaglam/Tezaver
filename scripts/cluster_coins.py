"""
Coin Structural Clustering Analysis
====================================
Analyzes and categorizes all 443 coins based on their structural characteristics.
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sqlite3
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

def extract_coin_features(symbol):
    """Extract comprehensive features for a single coin."""
    features = {'symbol': symbol}
    
    try:
        # Load data
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        path_15m = coin_cell_paths.get_history_file(symbol, '15m')
        
        if not path_1d.exists() or not path_15m.exists():
            return None
        
        df_1d = pd.read_parquet(path_1d).sort_values('timestamp')
        df_15m = pd.read_parquet(path_15m).sort_values('timestamp')
        
        # === VOLATILITY FEATURES ===
        df_1d['returns'] = df_1d['close'].pct_change()
        df_1d['atr'] = (df_1d['high'] - df_1d['low']) / df_1d['close'] * 100
        
        features['daily_atr_mean'] = df_1d['atr'].mean()
        features['daily_atr_std'] = df_1d['atr'].std()
        features['daily_volatility'] = df_1d['returns'].std() * 100
        
        # 15m volatility
        df_15m['atr_15m'] = (df_15m['high'] - df_15m['low']) / df_15m['close'] * 100
        features['intraday_atr_mean'] = df_15m['atr_15m'].mean()
        
        # Spike frequency (bars with >2x avg volatility)
        spike_threshold = features['daily_atr_mean'] * 2
        features['spike_frequency'] = (df_1d['atr'] > spike_threshold).sum() / len(df_1d)
        
        # === TREND FEATURES ===
        df_1d['ema20'] = df_1d['close'].ewm(span=20).mean()
        df_1d['ema50'] = df_1d['close'].ewm(span=50).mean()
        
        # Trend strength (% of time above EMA)
        features['uptrend_pct'] = (df_1d['close'] > df_1d['ema20']).sum() / len(df_1d)
        
        # EMA crossover frequency (trend changes)
        df_1d['trend'] = (df_1d['close'] > df_1d['ema20']).astype(int)
        features['trend_changes'] = df_1d['trend'].diff().abs().sum() / len(df_1d)
        
        # Average trend duration
        trend_groups = (df_1d['trend'] != df_1d['trend'].shift()).cumsum()
        trend_durations = df_1d.groupby(trend_groups).size()
        features['avg_trend_duration'] = trend_durations.mean()
        
        # === VOLUME FEATURES ===
        features['avg_volume'] = df_1d['volume'].mean()
        features['volume_std'] = df_1d['volume'].std()
        features['volume_cv'] = features['volume_std'] / (features['avg_volume'] + 1)  # Coefficient of variation
        
        # Volume spike frequency
        volume_threshold = df_1d['volume'].mean() * 2
        features['volume_spike_freq'] = (df_1d['volume'] > volume_threshold).sum() / len(df_1d)
        
        # === RALLY BEHAVIOR (from rallies.db) ===
        conn = sqlite3.connect(DB_PATH)
        query = f"SELECT * FROM rallies WHERE symbol = '{symbol}' AND tier IN ('DIAMOND', 'GOLD', 'SILVER')"
        df_rallies = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df_rallies.empty:
            features['rally_count'] = len(df_rallies)
            features['rally_frequency'] = len(df_rallies) / (len(df_1d) / 365)  # per year
            
            # Parse raw data for gains
            gains = []
            for _, row in df_rallies.iterrows():
                raw = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
                gains.append(raw.get('gain', 0))
            
            if gains:
                features['avg_rally_gain'] = np.mean(gains)
                features['max_rally_gain'] = np.max(gains)
            else:
                features['avg_rally_gain'] = 0
                features['max_rally_gain'] = 0
            
            # Tier distribution
            tier_counts = df_rallies['tier'].value_counts()
            features['diamond_count'] = tier_counts.get('DIAMOND', 0)
            features['gold_count'] = tier_counts.get('GOLD', 0)
            features['silver_count'] = tier_counts.get('SILVER', 0)
        else:
            features['rally_count'] = 0
            features['rally_frequency'] = 0
            features['avg_rally_gain'] = 0
            features['max_rally_gain'] = 0
            features['diamond_count'] = 0
            features['gold_count'] = 0
            features['silver_count'] = 0
        
        return features
        
    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return None

def run_clustering():
    print("=" * 80)
    print(f"🧬 COIN STRUCTURAL CLUSTERING ANALYSIS")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    print(f"\nExtracting features for {len(DEFAULT_COINS)} coins...\n")
    
    all_features = []
    
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        if i % 50 == 0:
            print(f"Progress: {i}/{len(DEFAULT_COINS)} coins analyzed...")
        
        features = extract_coin_features(symbol)
        if features:
            all_features.append(features)
    
    if len(all_features) < 10:
        print("\n❌ Insufficient data")
        return
    
    df = pd.DataFrame(all_features)
    
    # Prepare for clustering (exclude symbol column)
    feature_cols = [col for col in df.columns if col != 'symbol']
    X = df[feature_cols].fillna(0)
    
    # Normalize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Determine optimal cluster count using silhouette score
    print(f"\n{'─' * 80}")
    print("Finding optimal cluster count...")
    
    best_k = 5
    best_score = -1
    
    for k in range(4, 9):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        score = silhouette_score(X_scaled, labels)
        print(f"K={k}: Silhouette Score = {score:.3f}")
        
        if score > best_score:
            best_score = score
            best_k = k
    
    print(f"\nOptimal K: {best_k} (Score: {best_score:.3f})")
    
    # Final clustering
    print(f"\n{'─' * 80}")
    print(f"Clustering with K={best_k}...")
    
    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    df['cluster'] = kmeans.fit_predict(X_scaled)
    
    # Analyze clusters
    print(f"\n{'═' * 80}")
    print("📊 CLUSTER ANALYSIS")
    print(f"{'═' * 80}")
    
    for cluster_id in range(best_k):
        cluster_df = df[df['cluster'] == cluster_id]
        
        print(f"\n{'─' * 80}")
        print(f"🔹 CLUSTER {cluster_id} ({len(cluster_df)} coins)")
        print(f"{'─' * 80}")
        
        # Key characteristics
        print(f"Volatility: Daily ATR={cluster_df['daily_atr_mean'].mean():.2f}%, Spike Freq={cluster_df['spike_frequency'].mean():.3f}")
        print(f"Trend: Uptrend={cluster_df['uptrend_pct'].mean()*100:.1f}%, Avg Duration={cluster_df['avg_trend_duration'].mean():.1f} days")
        print(f"Volume: Avg={cluster_df['avg_volume'].mean():.0f}, CV={cluster_df['volume_cv'].mean():.2f}")
        print(f"Rallies: Count={cluster_df['rally_count'].mean():.1f}, Avg Gain={cluster_df['avg_rally_gain'].mean():.1f}%")
        print(f"DSG: D={cluster_df['diamond_count'].mean():.1f}, G={cluster_df['gold_count'].mean():.1f}, S={cluster_df['silver_count'].mean():.1f}")
        
        # Sample coins
        sample = cluster_df['symbol'].head(10).tolist()
        print(f"Sample: {', '.join(sample)}")
    
    # Save results
    output_file = coin_cell_paths.get_library_root() / "coin_clusters.csv"
    df[['symbol', 'cluster'] + feature_cols].to_csv(output_file, index=False)
    
    print(f"\n{'═' * 80}")
    print(f"✅ Clustering Complete")
    print(f"Results saved to: {output_file}")
    print(f"{'═' * 80}")

if __name__ == "__main__":
    run_clustering()
