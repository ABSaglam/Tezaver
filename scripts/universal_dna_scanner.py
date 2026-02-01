"""
🌍 Universal DNA Scanner - ALL COINS
"The Industrial Genius"
Iterates through EVERY coin, finds its specific 'Soul' parameters, and generates a DNA Manifest.
"""
import os
import pandas as pd
import numpy as np
import json
from datetime import datetime

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
MANIFEST_FILE = "universal_dna_manifest.json"
REPORT_FILE = "universal_dna_report.md"

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
    
    return {
        'is_positive': is_positive,
        'pos_pct': pos_pct,
        'vol_ratio': vol_ratio
    }

def optimize_coin(symbol):
    """Find best parameters for a single coin"""
    base_path = os.path.join(COIN_CELLS_DIR, symbol, "data")
    
    # Load required data
    df_1d = load_clean(os.path.join(base_path, "history_1d.parquet"))
    df_1h = load_clean(os.path.join(base_path, "history_1h.parquet"))
    df_15m = load_clean(os.path.join(base_path, "history_15m.parquet"))
    
    if df_1d.empty or df_1h.empty or df_15m.empty:
        return None

    # Filter to last 365 days for relevant optimization (or full history?)
    # Using full history 2023-2025 like before for robustness
    start_date = '2023-01-01'
    df_1d = df_1d[df_1d.index >= start_date]
    if df_1d.empty: return None

    # 1. Identify Valid Days and Tiers
    valid_days = [] # List of {date, metrics, is_tier}
    
    for i in range(len(df_1d) - 1):
        day = df_1d.index[i]
        tomorrow = day + pd.Timedelta(days=1)
        
        # Check Soul Metrics
        metrics = get_soul_metrics(df_1h, tomorrow)
        if not metrics: continue
        
        # Check Result (Next Day Tier)
        next_day_bars = df_15m[(df_15m.index >= tomorrow) & (df_15m.index < tomorrow + pd.Timedelta(days=1))]
        is_tier = False
        if not next_day_bars.empty:
            open_p = next_day_bars['open'].iloc[0]
            high_p = next_day_bars['high'].max()
            gain = (high_p / open_p) - 1
            if gain >= 0.05:
                is_tier = True
                
        valid_days.append({'metrics': metrics, 'is_tier': is_tier})
        
    if not valid_days: return None
    
    total_tiers = sum(1 for d in valid_days if d['is_tier'])
    if total_tiers < 5: return None # Not enough signal to optimize
    
    # 2. Grid Search
    pos_thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]
    vol_thresholds = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    
    best_score = -1
    best_config = None
    
    for pos in pos_thresholds:
        for vol in vol_thresholds:
            signals = 0
            hits = 0
            
            for d in valid_days:
                m = d['metrics']
                if m['is_positive'] and m['pos_pct'] > pos and m['vol_ratio'] > vol:
                    signals += 1
                    if d['is_tier']:
                        hits += 1
            
            if signals < 5: continue # Ignore tiny sample size
            
            precision = hits / signals
            recall = hits / total_tiers
            
            # Safety Floor: Precision must be somewhat decent (e.g. > 15-20%)
            # We prioritize Recall (Market Share) but not if Precision is trash (<15%)
            if precision < 0.15: continue
            
            # Score: Weighted Recall vs Precision
            # We liked YOLO which had High Recall. So weight Recall more.
            # Score = Recall * 2 + Precision
            score = (recall * 2) + precision
            
            if score > best_score:
                best_score = score
                best_config = {
                    'pos_pct': pos, 
                    'vol_ratio': vol, 
                    'precision': precision, 
                    'recall': recall,
                    'signals': signals,
                    'hits': hits,
                    'total_tiers': total_tiers
                }
                
    return best_config

def run_universal_scanner():
    print(f"🌍 Universal DNA Scanner Başlatılıyor (Tüm Coinler)...")
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d)) and d.endswith('USDT')]
    symbols = sorted(symbols)
    
    print(f"   Toplam Hedef: {len(symbols)} coin")
    
    manifest = {}
    report_lines = []
    
    processed = 0
    for symbol in symbols:
        processed += 1
        print(f"   [{processed}/{len(symbols)}] Taranıyor: {symbol}...", end="\r")
        
        try:
            res = optimize_coin(symbol)
            if res:
                manifest[symbol] = {
                    'pos_threshold': res['pos_pct'],
                    'vol_threshold': res['vol_ratio'],
                    'stats': {
                        'precision': round(res['precision'] * 100, 1),
                        'recall': round(res['recall'] * 100, 1),
                        'total_tiers': res['total_tiers']
                    }
                }
                report_lines.append({
                    'symbol': symbol,
                    'pos': res['pos_pct'],
                    'vol': res['vol_ratio'],
                    'prec': res['precision'] * 100,
                    'rec': res['recall'] * 100,
                    'tiers': res['total_tiers']
                })
        except Exception as e:
            # print(f"Error on {symbol}: {e}")
            pass
            
    print("\n✅ Tarama Tamamlandı.")
    
    # Save Manifest
    with open(os.path.join(COIN_CELLS_DIR, MANIFEST_FILE), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)
        
    # Generate Report sorted by Recall (Capture Rate)
    # Sort by 'Score' (Recall*2 + Precision) roughly desc
    report_lines.sort(key=lambda x: (x['rec']*2 + x['prec']), reverse=True)
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# 🌍 Universal DNA Manifest (Coin-Specific Optimization)\n")
        f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Toplam Optimize Edilen Coin: {len(manifest)}\n\n")
        f.write("| Coin | Pos Eşiği | Vol Eşiği | Recall (Pay) | Precision (İsabet) | Tier Gücü |\n")
        f.write("|---|---|---|---|---|---|\n")
        
        for r in report_lines:
            # Give a star to high performers
            icon = "🌟" if r['rec'] > 50 and r['prec'] > 25 else ""
            f.write(f"| {r['symbol']} {icon} | > {r['pos']} | > {r['vol']} | **{r['rec']:.1f}%** | {r['prec']:.1f}% | {r['tiers']} |\n")
            
    print(f"✅ Manifest Kaydedildi: {os.path.join(COIN_CELLS_DIR, MANIFEST_FILE)}")
    print(f"✅ Rapor Oluşturuldu: {REPORT_FILE}")

if __name__ == "__main__":
    run_universal_scanner()
