
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ---------------------------------------------------------
# 1. THE SENSES (Feature Generator)
# Calculates EVERY possible indicator to let data speak.
# ---------------------------------------------------------
def add_all_indicators(df):
    # Price Transforms
    df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
    
    # 1. TREND
    for window in [20, 50, 200]:
        ma = df['close'].rolling(window).mean()
        df[f'dist_ma{window}'] = (df['close'] - ma) / ma * 100
        
    # 2. MOMENTUM (RSI & Friends)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    
    avg_gain = gain.ewm(com=13, min_periods=14).mean()
    avg_loss = loss.ewm(com=13, min_periods=14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi_ema'] = df['rsi'].ewm(span=14).mean()
    df['rsi_delta'] = df['rsi'] - df['rsi_ema']
    
    # ROC (Rate of Change)
    df['roc_12'] = df['close'].pct_change(12) * 100
    
    # 3. VOLATILITY
    # Bollinger
    sma20 = df['close'].rolling(20).mean()
    std20 = df['close'].rolling(20).std()
    df['bb_width'] = (std20 * 2) / sma20 * 100
    df['bb_pos'] = (df['close'] - (sma20 - 2*std20)) / (4*std20) # 0 to 1 position
    
    # ATR (True Range)
    h_l = df['high'] - df['low']
    h_pc = (df['high'] - df['close'].shift(1)).abs()
    l_pc = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
    df['atr_14'] = tr.rolling(14).mean()
    df['natr'] = df['atr_14'] / df['close'] * 100 # Normalized ATR
    
    # 4. VOLUME
    df['vol_ma50'] = df['volume'].rolling(50).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma50']
    
    # 5. CANDLE SHAPE
    df['body_size'] = (df['close'] - df['open']).abs() / df['open'] * 100
    df['upper_shadow'] = (df['high'] - df[['close', 'open']].max(axis=1)) / df['open'] * 100
    df['lower_shadow'] = (df[['close', 'open']].min(axis=1) - df['low']) / df['open'] * 100
    
    return df

# ---------------------------------------------------------
# 2. THE JUDGE (Event Extraction)
# Finds huge rallies and compares them to failed moves.
# ---------------------------------------------------------
def run_oracle():
    path = Path("coin_cells/ADAUSDT/data/history_15m.parquet")
    if not path.exists():
        print("Data not found.")
        return

    print("🌊 ORACLE AWAKENING: Reading History...")
    df = pd.read_parquet(path)
    if 'timestamp' in df.columns and 'open_time' not in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    elif 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'])
    df = df.sort_values('open_time').reset_index(drop=True)
    
    # Enrich Data
    print("🧠 BRAIN: Calculating 20+ Dimensions of Market Reality...")
    df = add_all_indicators(df)
    df = df.dropna() # Drop warmup period
    
    # Define Ground Truth (The "God" View)
    # We look 32 bars ahead (8 hours).
    # IF MaxGain > 5% AND MinLoss > -2% -> SUPER WINNER (Diamond Candidate)
    # IF MaxGain < 1% AND MinLoss < -2% -> LOSER
    
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=32)
    df['future_max'] = df['close'].rolling(window=indexer).max()
    df['future_min'] = df['close'].rolling(window=indexer).min()
    
    df['gain_pot'] = (df['future_max'] - df['close']) / df['close'] * 100
    df['risk_pot'] = (df['future_min'] - df['close']) / df['close'] * 100
    
    # CLASSIFICATION
    # Class 1: WINNERS (The Cipher We Want)
    # Gain > 4% is a solid 15m pump.
    winners = df[df['gain_pot'] > 4.0].copy()
    
    # Class 0: LOSERS (The Noise)
    # Gain < 1% AND Risk < -1% (Went down immediately)
    losers = df[(df['gain_pot'] < 1.0) & (df['risk_pot'] < -1.0)].copy()
    
    print(f"\n🧪 SAMPLES COLLECTED:")
    print(f"   - WINNERS (Diamonds): {len(winners)}")
    print(f"   - LOSERS (Dust):      {len(losers)}")
    print("   Total Universe Analyzed: 5 Years of 15m bars.")

    # ---------------------------------------------------------
    # 3. THE REVELATION (Statistical Divergence)
    # Which features scream "WINNER" the loudest?
    # ---------------------------------------------------------
    feature_cols = [
        'dist_ma20', 'dist_ma50', 'dist_ma200', # Trend
        'rsi', 'rsi_ema', 'rsi_delta', 'roc_12', # Momentum
        'bb_width', 'bb_pos', 'natr',            # Volatility
        'vol_ratio',                             # Volume
        'body_size', 'upper_shadow'              # Candle
    ]
    
    print("\n" + "="*60)
    print("👁️ ORACLE'S INSIGHT: The Hidden Differences")
    print("   (Positive Diff = Higher in Winners)")
    print("="*60)
    print(f"{'FEATURE':<15} | {'WINNER':<10} | {'LOSER':<10} | {'DIFF':<10} | {'POWER'}")
    print("-" * 65)
    
    insights = []
    
    for f in feature_cols:
        w_mean = winners[f].mean()
        l_mean = losers[f].mean()
        diff = w_mean - l_mean
        
        # Power Score: How big is the diff relative to standard deviation? (Effect Size)
        # pooled_std = np.sqrt((winners[f].std()**2 + losers[f].std()**2) / 2)
        # cohen_d = diff / pooled_std if pooled_std != 0 else 0
        
        # Simple % difference for readability
        pct_diff = (diff / abs(l_mean)) * 100 if l_mean != 0 else 0
        power = abs(pct_diff)
        
        insights.append({
            'feature': f,
            'w_mean': w_mean,
            'l_mean': l_mean,
            'diff': diff,
            'power': power
        })
        
    # Sort by Power (Most distinguishing features first)
    insights.sort(key=lambda x: x['power'], reverse=True)
    
    for i in insights:
        print(f"{i['feature']:<15} | {i['w_mean']:<10.2f} | {i['l_mean']:<10.2f} | {i['diff']:<+10.2f} | {i['power']:.0f}%")

    print("\n" + "="*60)
    print("📜 THE DECODED CIPHER (Top 3 Rules)")
    top3 = insights[:3]
    for idx, item in enumerate(top3):
        direction = "HIGHER" if item['diff'] > 0 else "LOWER"
        print(f"{idx+1}. {item['feature'].upper()} should be {direction} (Impact: {item['power']:.0f}%)")

if __name__ == "__main__":
    run_oracle()
