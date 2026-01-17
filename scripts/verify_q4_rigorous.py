
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tezaver.core import coin_cell_paths, config
from tezaver.mining.ayas_tuneli import tunelden_gec

def verify_q4_rigorous():
    """
    Rigorously verifies Q4 2025 Ayaş Tüneli performance.
    - Scans all coins for signals in Oct, Nov, Dec 2025.
    - For each signal, look ahead exactly 96 hours (4 days) in 15m data.
    - Calculate max gain percentage during that 96h window.
    - Classify as success if gain >= 10%.
    """
    start_q4 = datetime(2025, 10, 1)
    end_q4 = datetime(2025, 12, 31, 23, 59)
    
    results = []
    
    print(f"🕵️ RIGOROUS Q4 VERIFICATION STARTING...")
    
    for symbol in config.DEFAULT_COINS:
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, '1d')
            path_4h = coin_cell_paths.get_history_file(symbol, '4h')
            path_15m = coin_cell_paths.get_history_file(symbol, '15m')
            
            if not all(p.exists() for p in [path_1d, path_4h, path_15m]):
                continue
                
            df_1d = pd.read_parquet(path_1d)
            if 'datetime' in df_1d.columns:
                df_1d['datetime'] = df_1d['datetime'].dt.tz_localize(None)
            
            df_4h = pd.read_parquet(path_4h)
            if 'datetime' in df_4h.columns:
                df_4h['datetime'] = df_4h['datetime'].dt.tz_localize(None)

            df_15m = pd.read_parquet(path_15m)
            if 'datetime' in df_15m.columns:
                df_15m['datetime'] = df_15m['datetime'].dt.tz_localize(None)
            
            # Find signals in Q4 range
            q4_data = df_1d[(df_1d['datetime'] >= start_q4) & (df_1d['datetime'] <= end_q4)]
            
            for i, row in q4_data.iterrows():
                # Slice history up to signal and 4h up to signal
                sig_time = row['datetime']
                history_1d = df_1d[df_1d['datetime'] <= sig_time]
                history_4h = df_4h[df_4h['datetime'] <= sig_time]
                
                check = tunelden_gec(symbol, history_1d, history_4h)
                
                if check['passed']:
                    # CHECK OUTCOME (96 Hours)
                    window_start = sig_time
                    window_end = sig_time + timedelta(hours=96)
                    
                    window_15m = df_15m[(df_15m['datetime'] > window_start) & (df_15m['datetime'] <= window_end)]
                    
                    if window_15m.empty:
                        continue
                        
                    entry_price = row['close']
                    max_future_price = window_15m['high'].max()
                    max_gain_pct = ((max_future_price - entry_price) / entry_price) * 100
                    
                    results.append({
                        'month': sig_time.month,
                        'symbol': symbol,
                        'time': sig_time,
                        'gain': max_gain_pct,
                        'success': max_gain_pct >= 10.0
                    })
                    
        except Exception as e:
            # print(f"Error processing {symbol}: {e}")
            continue

    if not results:
        print("❌ No signals found in Q4.")
        return

    df_res = pd.DataFrame(results)
    
    # Monthly Stats
    stats = df_res.groupby('month').agg(
        total_signals=('success', 'count'),
        success_count=('success', 'sum'),
        avg_gain=('gain', 'mean')
    )
    stats['success_rate'] = (stats['success_count'] / stats['total_signals']) * 100
    
    print("\n=== VERIFIED Q4 2025 PERFORMANCE (STRICT 96H WINDOW) ===")
    print(stats)
    
    # Save to CSV for persistent proof
    df_res.to_csv('library/q4_2025_rigorous_verification.csv', index=False)
    print(f"\nSaved detailed results to library/q4_2025_rigorous_verification.csv")

if __name__ == "__main__":
    verify_q4_rigorous()
