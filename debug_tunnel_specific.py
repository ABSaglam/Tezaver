
from tezaver.engines.tunnel_engine import TunnelEngine
import pandas as pd

# Force show all columns
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

def check_0000():
    print("--- 27 OCAK 2026 00:00 TARAMASI BAŞLIYOR ---")
    engine = TunnelEngine()
    
    # Run full scan for the day
    results_df = engine.scan_tunnel_day("2026-01-27")
    
    if results_df.empty:
        print("SONUÇ: O gün için hiç sinyal yok.")
        return

    # Filter for exact time 00:00
    midnight_signals = results_df[results_df['TIME'] == '00:00']
    
    print(f"Toplam Günlük Sinyal Sayısı: {len(results_df)}")
    
    if not midnight_signals.empty:
        print(f"\nBULUNAN 00:00 SINYALLERİ ({len(midnight_signals)} ADET):")
        print(midnight_signals[['SYM', 'TIME', 'P', 'V100', 'V21', 'MAX', 'CLOSE']].to_string())
    else:
        print("\n00:00 İÇİN HİÇBİR SİNYAL BULUNAMADI.")
        print("En yakın ilk sinyaller:")
        print(results_df.sort_values('TIME').head(5)[['SYM', 'TIME', 'P', 'V100']].to_string())

if __name__ == "__main__":
    check_0000()
