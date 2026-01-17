
import pandas as pd
from datetime import datetime, timedelta
from tezaver.core import coin_cell_paths
from tezaver.mining.ayas_tuneli import tunelden_gec

def prove_error_act():
    symbol = "ACTUSDT"
    print(f"🔬 PROVING LINKAGE ERROR FOR {symbol} (NOVEMBER 2025)")
    
    path_1d = coin_cell_paths.get_history_file(symbol, '1d')
    path_4h = coin_cell_paths.get_history_file(symbol, '4h')
    path_15m = coin_cell_paths.get_history_file(symbol, '15m')
    
    df_1d = pd.read_parquet(path_1d)
    df_1d['datetime'] = df_1d['datetime'].dt.tz_localize(None)
    df_4h = pd.read_parquet(path_4h)
    df_4h['datetime'] = df_4h['datetime'].dt.tz_localize(None)
    df_15m = pd.read_parquet(path_15m)
    df_15m['datetime'] = df_15m['datetime'].dt.tz_localize(None)
    
    # Let's find a signal in late November
    start_search = datetime(2025, 11, 20)
    end_search = datetime(2025, 11, 30)
    
    signals = []
    q4_data = df_1d[(df_1d['datetime'] >= start_search) & (df_1d['datetime'] <= end_search)]
    for i, row in q4_data.iterrows():
        sig_time = row['datetime']
        if tunelden_gec(symbol, df_1d[df_1d['datetime'] <= sig_time], df_4h[df_4h['datetime'] <= sig_time])['passed']:
            signals.append((sig_time, row['close']))
            
    if not signals:
        print("No signals found for ACT in this period.")
        return
        
    print(f"Found {len(signals)} signals.")
    
    # THE MISMATCH EXAMPLE:
    # Mined Rally in Store: 2025-11-26 15:45:00 (Success SILVER)
    rally_trigger_time = datetime(2025, 11, 26, 15, 45)
    
    for sig_time, entry_price in signals:
        diff_hours = (rally_trigger_time - sig_time).total_seconds() / 3600
        
        # 96-hour outcome from SIGNAL
        window_sig = df_15m[(df_15m['datetime'] > sig_time) & (df_15m['datetime'] <= sig_time + timedelta(hours=96))]
        if not window_sig.empty:
            max_p = window_sig['high'].max()
            gain_sig = ((max_p - entry_price) / entry_price) * 100
        else:
            gain_sig = 0
            
        print(f"\nSignal Time: {sig_time}")
        print(f"  Hours until next 'Mined Rally': {diff_hours:.1f}h")
        print(f"  Real 96h Gain from Signal: {gain_sig:.1f}%")
        
        if diff_hours > 0 and diff_hours < 72: # If signal is before but near rally
            print(f"  ❌ HATA TESPİTİ: Bu sinyal ralliye {diff_hours:.1f} saat uzakta.")
            print(f"  İyimser Metod: 'Ralli yakında, o zaman başarılı!'")
            print(f"  Gerçek Metod: '96 saat bekledi, kazanç %{gain_sig:.1f}.")
            if gain_sig < 10:
                print(f"  SONUÇ: Tradeden bıkıp çıktı veya SL oldu. SİNYAL BAŞARISIZ!")
            else:
                print(f"  SONUÇ: Geç de olsa hedefe ulaştı. SİNYAL BAŞARILI.")

if __name__ == "__main__":
    prove_error_act()
