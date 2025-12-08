
import pandas as pd
import numpy as np
import glob
from pathlib import Path

# Try to use ta, else manual
try:
    import pandas_ta as ta
except ImportError:
    pass

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_deep_dip():
    print("🧪 FORWARD TEST: What happens after RSI < 25?")
    
    files = glob.glob("coin_cells/*/data/history_15m.parquet")
    if not files:
        # Fallback to absolute path search if CWD varies
        files = glob.glob("/Users/alisaglam/TezaverMac/coin_cells/*/data/history_15m.parquet")
        
    if not files:
        print("❌ No history data found in coin_cells/")
        return

    total_signals = 0
    wins = 0
    losses = 0
    total_gain_sum = 0
    
    results = []

    for f in files:
        symbol = Path(f).name.replace("_15m.parquet", "")
        # print(f"Scanning {symbol}...")
        
        try:
            df = pd.read_parquet(f)
        except Exception:
            continue
            
        if 'close' not in df.columns:
            continue
            
        # Calculate RSI
        # If pandas_ta is available use it, else manual
        if 'ta' in globals() and hasattr(df, 'ta'):
             df['rsi'] = df.ta.rsi(length=14)
        else:
             df['rsi'] = calculate_rsi(df['close'])
             
        # Find candidates: RSI < 25
        # We want the *first* touch of 25 to avoid standard signal spam
        # Condition: RSI < 25 AND Shift(1) >= 25
        mask = (df['rsi'] < 25) & (df['rsi'].shift(1) >= 25)
        indices = df.index[mask]
        
        if len(indices) == 0:
            continue
            
        # Analyze Outcomes
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        n = len(df)
        
        for idx in indices:
            # Look ahead 192 bars (48 Hours)
            end_idx = min(idx + 192, n)
            if end_idx <= idx:
                continue
                
            entry_price = close[idx]
            
            # Future Max High
            future_highs = high[idx+1:end_idx]
            if len(future_highs) == 0: continue
            max_price = np.max(future_highs)
            
            # Future Min Low (Drawdown checks)
            future_lows = low[idx+1:end_idx]
            min_price = np.min(future_lows)
            
            # Metrics
            max_gain_pct = (max_price - entry_price) / entry_price * 100
            max_drawdown_pct = (min_price - entry_price) / entry_price * 100
            
            # Criteria: Did it hit +5% before hitting -10%?
            # Simple metric: Just max potential gain
            
            results.append({
                'symbol': symbol,
                "rsi": df['rsi'].iloc[idx],
                "gain": max_gain_pct,
                "drawdown": max_drawdown_pct
            })
    
    if not results:
        print("No signals found.")
        return

    df_res = pd.DataFrame(results)
    
    print(f"\n📊 PROCESSED {len(df_res)} SIGNALS (RSI < 25)")
    print("-" * 40)
    print(f"Average Potential Gain (48h):  +{df_res['gain'].mean():.2f}%")
    print(f"Average DrownDown (Risk):      {df_res['drawdown'].mean():.2f}%")
    
    win_rate = len(df_res[df_res['gain'] > 5]) / len(df_res) * 100
    print(f"Win Rate (>5% Gain):           {win_rate:.1f}%")
    
    super_wins = len(df_res[df_res['gain'] > 20])
    print(f"Jackpots (>20% Gain):          {super_wins} ({super_wins/len(df_res)*100:.1f}%)")
    
    print("\n💡 VERDICT:")
    if win_rate > 60:
        print("✅ This is a highly profitable setup!")
    elif win_rate > 40:
        print("⚠️ Decent, but needs confirmation (Volume/Pattern).")
    else:
        print("❌ Dangerous knife catching. Most trades fail.")

if __name__ == "__main__":
    analyze_deep_dip()
