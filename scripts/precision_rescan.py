"""
Full Rescan Script - Precision Rally Miner
Tüm coin'leri yeniden tarar ve RallyStore'a kaydeder.
"""

from tezaver.rally.rally_utils import detect_rallies_oracle_mode
from tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct
from tezaver.core.rally_store import RallyStore
from tezaver.core import coin_cell_paths
import pandas as pd
from datetime import datetime

COINS = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'DOTUSDT', 
         'LINKUSDT', 'AVAXUSDT', 'ATOMUSDT', 'LTCUSDT', 'UNIUSDT', 'NEARUSDT',
         'APTUSDT', 'ARBUSDT', 'OPUSDT', 'INJUSDT', 'SUIUSDT', 'BNBUSDT', 'POLUSDT']

TIMEFRAMES = ['15m', '1h', '4h']

def generate_rally_id(symbol: str, timeframe: str, tier: str, timestamp) -> str:
    """Generate unique rally ID."""
    if isinstance(timestamp, (int, float)):
        ts = int(timestamp // 1000)  # ms to seconds
    else:
        ts = int(timestamp.timestamp())
    return f"{symbol}_{timeframe}_{tier[0]}_{ts}"


def rescan_all():
    store = RallyStore()
    
    print("=" * 70)
    print("PRECISION MINER - FULL RESCAN")
    print("=" * 70)
    
    # Eski verileri temizle
    print("\n📦 Eski veriler temizleniyor...")
    # store.clear_all()  # Dikkat: Bu tüm verileri siler!
    
    total_rallies = 0
    tier_counts = {"DIAMOND": 0, "GOLD": 0, "SILVER": 0, "BRONZE": 0}
    
    for coin in COINS:
        print(f"\n🔍 {coin} taranıyor...")
        
        for tf in TIMEFRAMES:
            try:
                path = coin_cell_paths.get_history_file(coin, tf)
                if not path.exists():
                    print(f"  ⚠️ {tf} veri yok, atlanıyor")
                    continue
                
                df = pd.read_parquet(path)
                
                # Precision Miner ile tespit
                events = detect_rallies_oracle_mode(df, min_gain=0.05)
                
                if events.empty:
                    print(f"  {tf}: 0 rally")
                    continue
                
                # Her rally için tier hesapla ve kaydet
                rally_count = 0
                for _, row in events.iterrows():
                    gain = row['future_max_gain_pct']
                    tier = compute_tier_from_gain_pct(gain)
                    
                    if tier is None:
                        continue
                    
                    # Rally ID oluştur
                    rally_id = generate_rally_id(coin, tf, tier, row['event_time'])
                    
                    # Timestamp'i düzgün formata çevir
                    if isinstance(row['event_time'], (int, float)):
                        event_time_str = pd.Timestamp(row['event_time'], unit='ms').strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        event_time_str = str(row['event_time'])
                    
                    # Rally verisi hazırla
                    rally_data = {
                        'symbol': coin,
                        'timeframe': tf,
                        'tier': tier,
                        'rally_grade': tier,
                        'event_time': event_time_str,
                        'future_max_gain_pct': gain,
                        'bars_to_peak': int(row['bars_to_peak']),
                        'event_index': int(row['raw_dip_idx']),  # Grafik için dip noktası
                        'peak_index': int(row['peak_index']),
                        'dip_price': float(row['dip_price']),
                        'raw_dip_idx': int(row['raw_dip_idx']),  # Ham dip
                        'raw_peak_idx': int(row['raw_peak_idx']),  # Ham peak
                        'entry_idx': int(row['entry_idx']),  # Impulse giriş
                        'exit_idx': int(row['exit_idx']),  # Impulse çıkış
                        'impulse_gain_pct': float(row['impulse_gain_pct']),
                        'event_tf': tf,
                    }
                    
                    # Store'a kaydet - doğru API: upsert_rally(rally_id, data, layer)
                    store.upsert_rally(rally_id, rally_data, layer='raw')
                    
                    rally_count += 1
                    tier_counts[tier] = tier_counts.get(tier, 0) + 1
                
                total_rallies += rally_count
                print(f"  {tf}: {rally_count} rally")
                
            except Exception as e:
                print(f"  ❌ {tf} hata: {e}")
    
    print("\n" + "=" * 70)
    print("TAMAMLANDI!")
    print("=" * 70)
    print(f"Toplam Rally: {total_rallies}")
    print(f"  DIAMOND: {tier_counts['DIAMOND']}")
    print(f"  GOLD: {tier_counts['GOLD']}")
    print(f"  SILVER: {tier_counts['SILVER']}")
    print(f"  BRONZE: {tier_counts['BRONZE']}")
    

if __name__ == "__main__":
    rescan_all()
