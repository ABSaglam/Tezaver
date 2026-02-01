"""
🌉 Sırat V17 History Scanner
Generates a V17-style report for all "Bridge Crossing" events in the last 100 days.
Uses per-coin DNA rules from universal_dna_manifest.json.
"""
import os
import pandas as pd
import numpy as np
import json
from datetime import datetime

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
MANIFEST_FILE = "universal_dna_manifest.json"
REPORT_FILE = "SIRAT_V17_HISTORY.md"

def load_clean(path):
    try:
        if not os.path.exists(path): return pd.DataFrame()
        df = pd.read_parquet(path)
        if 'timestamp' in df.columns:
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df = df[~df.index.duplicated(keep='last')]
            return df.sort_index()
    except:
        return pd.DataFrame()

def get_soul_metrics(df_1h, day_close_time):
    # Analyze 24h leading up to close
    start_time = day_close_time - pd.Timedelta(hours=24)
    mask = (df_1h.index > start_time) & (df_1h.index <= day_close_time)
    sub = df_1h[mask]
    
    if len(sub) < 24: return None
    
    open_p = sub['open'].iloc[0]
    close_p = sub['close'].iloc[-1]
    is_positive = close_p > open_p
    
    high_p = sub['high'].max()
    low_p = sub['low'].min()
    range_p = high_p - low_p
    if range_p == 0: pos_pct = 0.5
    else: pos_pct = (close_p - low_p) / range_p
    
    vol_start = sub['volume'].iloc[:6].mean()
    vol_end = sub['volume'].iloc[-6:].mean()
    if vol_start == 0: vol_ratio = 1.0
    else: vol_ratio = vol_end / vol_start
    
    # Calculate approx ATR% (from high-low range of the day)
    day_range_pct = (range_p / open_p) * 100
    
    return {
        'is_positive': is_positive,
        'pos_pct': pos_pct,
        'vol_ratio': vol_ratio,
        'close': close_p,
        'atr_pct': day_range_pct
    }

def format_v17_row(idx, date, symbol, m, gain_next_day):
    # | NO | SYM | MAX | CLOSE | TIME | SIG | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-21 | BAR | NEXT | N-1 | CGS | ATR% | ADX |
    
    # Simplify format for history report
    # We will use keys:
    # NO, SYM, TIME: standard
    # SIG: "BRIDGE"
    # POS: pos_pct
    # VAL: vol_ratio
    # MAX: gain_next_day (The Result)
    # TIER: Icon if gain > 5%
    # CLOSE: Close Price
    
    gain_str = f"{gain_next_day*100:.1f}%"
    if gain_next_day > 0: gain_str = f"+{gain_str}"
    
    tier_icon = ""
    if gain_next_day >= 0.30: tier_icon = "💎"
    elif gain_next_day >= 0.20: tier_icon = "🥇"
    elif gain_next_day >= 0.10: tier_icon = "🥈"
    elif gain_next_day >= 0.05: tier_icon = "🥉"
    
    pos_icon = "🟩" if m['pos_pct'] > 0.6 else "🟨"
    
    # Fake/Approx columns for V17 feel
    trend = "UP" # By definition we are in bridge
    
    # Formatting
    row = f"| {idx} | {symbol} | **{gain_str}** | {m['close']:.4f} | {date.strftime('%Y-%m-%d')} | BRIDGE 🌉 | {trend} | {m['pos_pct']:.2f} {pos_icon} | - | - | {m['vol_ratio']:.2f} | - | {tier_icon} | - | - | - | - | - | {m['atr_pct']:.1f}% | - |"
    return row

def run_history_scanner():
    print("🌉 Sırat V17 History Scanner Başlatılıyor...")
    
    # Load Manifest
    try:
        with open(os.path.join(COIN_CELLS_DIR, MANIFEST_FILE), "r") as f:
            manifest = json.load(f)
    except:
        print("Manifest bulunamadı!")
        return

    # Filter symbols to only those in manifest
    symbols = sorted(list(manifest.keys()))
    print(f"   Hedef: {len(symbols)} coin (Manifesto'da olanlar)")
    
    # Date Range: Last 100 Days
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=100)
    
    events = []
    
    processed = 0
    for symbol in symbols:
        processed += 1
        if processed % 10 == 0:
            print(f"   [{processed}/{len(symbols)}] Taranıyor...", end="\r")
            
        rules = manifest[symbol]
        pos_thresh = rules['pos_threshold']
        vol_thresh = rules['vol_threshold']
        
        base_path = os.path.join(COIN_CELLS_DIR, symbol, "data")
        df_1h = load_clean(os.path.join(base_path, "history_1h.parquet"))
        df_15m = load_clean(os.path.join(base_path, "history_15m.parquet"))
        
        if df_1h.empty: continue
        
        # We need "Day Close" times to check bridge
        # Let's iterate days in df_1h roughly (resample 1D)
        # Or better: get unique dates from df_1h index normalized
        
        # Iterate last 100 dates
        current = start_date.normalize()
        while current < end_date:
            # Check bridge for 'current' (meaning data ending at current + 1 day close usually? )
            # In previous scripts:
            # day = index
            # tomorrow = day + 1 day (Close Time)
            # check stats ending at tomorrow
            
            # For iteration here, let's treat 'current' as the Open Day.
            # So Close Time is current + 1 Day.
            tomorrow = current + pd.Timedelta(days=1)
            
            # Check Metrics
            metrics = get_soul_metrics(df_1h, tomorrow)
            if not metrics: 
                current += pd.Timedelta(days=1)
                continue
                
            # Check Rules (Coin Specific)
            pass_rule = (
                metrics['is_positive'] and
                metrics['pos_pct'] > pos_thresh and
                metrics['vol_ratio'] > vol_thresh
            )
            
            if pass_rule:
                # Get Result (Next Day Gain)
                # Next day is 'tomorrow' to 'tomorrow+1'
                next_day_start = tomorrow
                next_day_end = next_day_start + pd.Timedelta(days=1)
                
                gain = 0.0
                next_bars = df_15m[(df_15m.index >= next_day_start) & (df_15m.index < next_day_end)]
                if not next_bars.empty:
                    open_p = next_bars['open'].iloc[0]
                    high_p = next_bars['high'].max()
                    gain = (high_p / open_p) - 1
                
                events.append({
                    'date': current,
                    'symbol': symbol,
                    'metrics': metrics,
                    'gain': gain
                })
            
            current += pd.Timedelta(days=1)
            
    # Sort events by Date (descending)
    events.sort(key=lambda x: x['date'], reverse=True)
    
    # Generate MD
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# 🌉 Sırat V17 Geçmişi (Son 100 Gün)\n")
        f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Toplam Geçiş: {len(events)}\n\n")
        
        f.write("| NO | SYM | MAX (Sonuç) | CLOSE | TIME | SIG | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-21 | BAR | NEXT | N-1 | CGS | ATR% | ADX |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        
        for i, e in enumerate(events):
            row = format_v17_row(i+1, e['date'], e['symbol'], e['metrics'], e['gain'])
            f.write(row + "\n")
            
    print(f"\n✅ Rapor Oluşturuldu: {REPORT_FILE}")

if __name__ == "__main__":
    run_history_scanner()
