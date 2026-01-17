
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tezaver.core import coin_cell_paths, config
from tezaver.mining.ayas_tuneli import tunelden_gec
from tezaver.core.rally_store import RallyStore

def audit_rally_linkage():
    """
    Audits the linkage between Ayaş Tüneli signals and Mined Rallies.
    Check if we are attributing gains that happened BEFORE the signal to the signal itself.
    """
    store = RallyStore()
    start_q4 = datetime(2025, 11, 1) # Focusing on November
    end_q4 = datetime(2025, 11, 30, 23, 59)
    
    print(f"🔬 AUDITING SIGNAL-RALLY LINKAGE (NOVEMBER 2025)...")
    
    # Using coins that were active in Nov 2025
    test_symbols = ["0GUSDT", "ACTUSDT", "ASTERUSDT", "ALCXUSDT", "2ZUSDT", "AIUSDT"]
    
    audit_results = []
    
    for symbol in test_symbols:
        try:
            print(f"-- Auditing {symbol} --")
            path_1d = coin_cell_paths.get_history_file(symbol, '1d')
            path_4h = coin_cell_paths.get_history_file(symbol, '4h')
            path_15m = coin_cell_paths.get_history_file(symbol, '15m')
            
            if not all(p.exists() for p in [path_1d, path_4h, path_15m]):
                continue
                
            df_1d = pd.read_parquet(path_1d)
            df_1d['datetime'] = df_1d['datetime'].dt.tz_localize(None)
            df_4h = pd.read_parquet(path_4h)
            df_4h['datetime'] = df_4h['datetime'].dt.tz_localize(None)
            df_15m = pd.read_parquet(path_15m)
            df_15m['datetime'] = df_15m['datetime'].dt.tz_localize(None)
            
            q4_data = df_1d[(df_1d['datetime'] >= start_q4) & (df_1d['datetime'] <= end_q4)]
            
            for i, row in q4_data.iterrows():
                sig_time = row['datetime']
                check = tunelden_gec(symbol, df_1d[df_1d['datetime'] <= sig_time], df_4h[df_4h['datetime'] <= sig_time])
                
                if check['passed']:
                    entry_price = row['close']
                    
                    # 2. Find Linked Rally in RallyStore (The "Optimistic" way)
                    # We usually find rallis where rally_start <= sig_time <= rally_end
                    # BUT since we store event_time (the breakout/entry), we look for rallies 
                    # whose event_time is near our signal time or before it.
                    matched_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
                    linked_rally = None
                    for r in matched_rallies:
                        raw = r['raw_data']
                        if not raw: continue
                        
                        r_start = pd.to_datetime(raw.get('start_time') or r['event_time']).tz_localize(None)
                        r_end = pd.to_datetime(raw.get('end_time') or r['event_time']).tz_localize(None)
                        
                        # Check if signal is within the rally bounds
                        if r_start <= sig_time <= r_end:
                            linked_rally = r
                            break
                    
                    if linked_rally:
                        raw = linked_rally['raw_data']
                        r_gain = raw.get('gain', 0)
                        r_low = raw.get('low', 0)
                        r_high = raw.get('high', 0)
                        
                        # 3. Calculate REAL AFTER-SIGNAL GAIN (96h)
                        window_15m = df_15m[(df_15m['datetime'] > sig_time) & (df_15m['datetime'] <= sig_time + timedelta(hours=96))]
                        if window_15m.empty:
                            real_max_gain = 0
                        else:
                            max_f_high = window_15m['high'].max()
                            real_max_gain = ((max_f_high - entry_price) / entry_price) * 100
                            
                        # Calculate gain that already happened BEFORE signal
                        pre_sig_gain = ((entry_price - r_low) / r_low) * 100 if r_low > 0 else 0
                        
                        audit_results.append({
                            'time': sig_time,
                            'symbol': symbol,
                            'entry_price': entry_price,
                            'rally_low': r_low,
                            'rally_peak': r_high,
                            'store_gain': r_gain,
                            'pre_sig_gain': pre_sig_gain,
                            'post_sig_96h_gain': real_max_gain,
                            'is_deceptive': r_gain > 10.0 and real_max_gain < 10.0
                        })
                        
        except Exception as e:
            continue

    df_audit = pd.DataFrame(audit_results)
    if df_audit.empty:
        print("No linked rallies found for audit.")
        return
        
    print("\n=== RALLY LINKAGE AUDIT RESULTS ===")
    print(df_audit[['time', 'symbol', 'store_gain', 'pre_sig_gain', 'post_sig_96h_gain', 'is_deceptive']].head(20))
    
    deceptive_count = df_audit['is_deceptive'].sum()
    total_audited = len(df_audit)
    print(f"\nDeceptive Signals: {deceptive_count} / {total_audited} ({deceptive_count/total_audited*100:.1f}%)")
    print("\n'Deceptive' means: Store says >10% Success, but real 96h post-signal gain is <10%.")
    
    df_audit.to_csv('library/rally_linkage_audit.csv', index=False)

if __name__ == "__main__":
    audit_rally_linkage()
