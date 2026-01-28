import pandas as pd
import numpy as np
import os
import json

# CONFIG
START_DATE = pd.Timestamp("2025-10-16")
END_DATE = pd.Timestamp("2026-01-24")
COIN_CELLS_DIR = "coin_cells"

def load_clean(path):
    if not os.path.exists(path): return None
    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df = df[~df.index.duplicated(keep='last')]
    return df.sort_index()

def run_simulation():
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    results = []

    print(f"Süreci Başlatıyorum: {len(symbols)} koin taranacak...")

    for symbol in symbols:
        try:
            df_15m = load_clean(f"coin_cells/{symbol}/data/history_15m.parquet")
            if df_15m is None: continue

            # Indicators
            delta = df_15m['close'].diff()
            alpha = 1 / 11
            gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
            df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
            
            ema12 = df_15m['close'].ewm(span=12, adjust=False).mean()
            ema26 = df_15m['close'].ewm(span=26, adjust=False).mean()
            df_15m['macd_hist'] = (ema12 - ema26) - (ema12 - ema26).ewm(span=9, adjust=False).mean()
            
            tr = np.maximum(df_15m['high'] - df_15m['low'], np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)), abs(df_15m['low'] - df_15m['close'].shift(1))))
            df_15m['atr100'] = tr.rolling(window=100).mean()
            df_15m['tr'] = tr

            # RSI triggers
            rsi_vals = df_15m['rsi'].values
            trigger_indices = np.where((rsi_vals[:-1] <= 70) & (rsi_vals[1:] > 70))[0] + 1

            for idx in trigger_indices:
                t_time = df_15m.index[idx]
                if t_time < START_DATE or t_time > END_DATE: continue

                # Daily Open
                day_start = t_time.normalize()
                day_data = df_15m[df_15m.index.normalize() == day_start]
                if day_data.empty: continue
                open_p = day_data.iloc[0]['open']
                curr_p = df_15m.iloc[idx]['close']
                
                # Filters
                is_stuck = curr_p < open_p
                if not is_stuck: continue # Sadece ⛔ durumlarını test ediyoruz

                v_t = df_15m['volume'].values[idx]
                v_avg = np.mean(df_15m['volume'].values[max(0, idx-21):idx]) or 0.001
                v_idx = min(10.0, (df_15m['tr'].values[idx] / (df_15m['atr100'].values[idx] or 0.001)) * 3.33)
                
                # 🎯 Criteria
                is_target = v_idx >= 7.0 and (v_t / v_avg >= 5.0) and ((open_p - curr_p) / open_p <= 0.10)
                
                # Peak/Drawdown in 21 bars window (or until next trigger)
                next_triggers = trigger_indices[trigger_indices > idx]
                next_t_idx = next_triggers[0] if len(next_triggers) > 0 else len(df_15m)
                search_limit = min(idx + 22, next_t_idx)
                
                window_data = df_15m.iloc[idx+1:search_limit]
                if window_data.empty: 
                    p_gain = 0
                    drawdown = 0
                else:
                    peak_p = window_data['high'].max()
                    low_p = window_data['low'].min()
                    p_gain = ((peak_p / curr_p) - 1) * 100
                    drawdown = ((low_p / curr_p) - 1) * 100

                # Did it break Daily Open within 21 bars?
                recovered = window_data['high'].max() >= open_p if not window_data.empty else False

                results.append({
                    'symbol': symbol,
                    'time': t_time,
                    'is_target': is_target,
                    'p_gain': p_gain,
                    'drawdown': drawdown,
                    'recovered': recovered
                })
        except Exception as e:
            continue

    if not results:
        print("Sonuç bulunamadı.")
        return

    sim_df = pd.DataFrame(results)
    
    # Analysis
    target_group = sim_df[sim_df['is_target'] == True]
    non_target_group = sim_df[sim_df['is_target'] == False]

    print("\n--- 🎯 KURTARMA (RECOVERY) SİMÜLASYON RAPORU ---")
    print(f"Toplam Takılan (⛔) Vaka: {len(sim_df)}")
    print(f"🎯 Kriterine Uyanlar: {len(target_group)}")
    
    print("\n[🎯 KURTARICILAR PERFORMANSI]")
    print(f"Başarı Oranı (Açılışı Kırma): {target_group['recovered'].mean()*100:.2f}%")
    print(f"Ortalama Peak: +{target_group['p_gain'].mean():.2f}%")
    print(f"Ortalama Risk (Drawdown): {target_group['drawdown'].mean():.2f}%")
    
    print("\n[STANDART ⛔ PERFORMANSI]")
    print(f"Başarı Oranı (Açılışı Kırma): {non_target_group['recovered'].mean()*100:.2f}%")
    print(f"Ortalama Peak: +{non_target_group['p_gain'].mean():.2f}%")
    print(f"Ortalama Risk (Drawdown): {non_target_group['drawdown'].mean():.2f}%")

if __name__ == "__main__":
    run_simulation()
