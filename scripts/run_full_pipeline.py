#!/usr/bin/env python3
"""
Full pipeline: Build Features + Rally Scan for all symbols with history data.

1. Find all symbols with history_15m but missing features_15m
2. Build features for those symbols
3. Run rally scan on ALL symbols with features

Usage:
    nohup python scripts/run_full_pipeline.py > logs/full_pipeline.log 2>&1 &
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tezaver.features.indicator_engine import build_features_for_symbol_timeframe
from tezaver.rally.fast15_rally_scanner import run_fast15_scan_for_symbol
from tezaver.ony.auto_approver import OnyAutoApprover
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def get_symbols_needing_features():
    """Find symbols with history_15m but no features_15m."""
    coin_cells = Path("coin_cells")
    symbols = []
    
    for d in coin_cells.iterdir():
        if d.is_dir() and d.name.endswith("USDT"):
            history_15m = d / "data" / "history_15m.parquet"
            features_15m = d / "data" / "features_15m.parquet"
            
            if history_15m.exists() and not features_15m.exists():
                symbols.append(d.name)
    
    return sorted(symbols)


def get_symbols_with_features():
    """Find symbols with features_15m."""
    coin_cells = Path("coin_cells")
    symbols = []
    
    for d in coin_cells.iterdir():
        if d.is_dir() and d.name.endswith("USDT"):
            features_15m = d / "data" / "features_15m.parquet"
            if features_15m.exists():
                symbols.append(d.name)
    
    return sorted(symbols)


def get_scanned_symbols():
    """Get already scanned symbols."""
    fast15_dir = Path("library/fast15_rallies")
    scanned = set()
    
    if fast15_dir.exists():
        for d in fast15_dir.iterdir():
            if d.is_dir():
                parquet = d / "fast15_rallies.parquet"
                if parquet.exists():
                    scanned.add(d.name)
    
    return scanned


def main():
    start_time = datetime.now()
    
    print("=" * 80)
    print("🚀 FULL PIPELINE: FEATURES + RALLY SCAN")
    print("=" * 80)
    print(f"Başlangıç: {start_time}")
    
    # Phase 1: Build missing features
    symbols_need_features = get_symbols_needing_features()
    print(f"\n📊 PHASE 1: Feature Hesaplama")
    print(f"Features eksik sembol: {len(symbols_need_features)}")
    
    feature_errors = []
    for i, symbol in enumerate(symbols_need_features, 1):
        print(f"  [{i}/{len(symbols_need_features)}] {symbol} features hesaplanıyor...")
        try:
            # Build features for all timeframes needed
            for tf in ['15m', '1h', '4h', '1d']:
                build_features_for_symbol_timeframe(symbol, tf)
            print(f"    ✓ Tamamlandı")
        except Exception as e:
            print(f"    ✗ Hata: {str(e)[:50]}")
            feature_errors.append(symbol)
    
    # Phase 2: Rally scan
    already_scanned = get_scanned_symbols()
    all_with_features = get_symbols_with_features()
    symbols_to_scan = [s for s in all_with_features if s not in already_scanned]
    
    print(f"\n📊 PHASE 2: Rally Taraması")
    print(f"Features mevcut: {len(all_with_features)}")
    print(f"Zaten taranmış: {len(already_scanned)}")
    print(f"Taranacak: {len(symbols_to_scan)}")
    
    approver = OnyAutoApprover()
    results = []
    scan_errors = []
    
    for i, symbol in enumerate(symbols_to_scan, 1):
        print(f"  [{i}/{len(symbols_to_scan)}] {symbol} taranıyor...")
        try:
            result = run_fast15_scan_for_symbol(symbol)
            results.append({
                'symbol': symbol,
                'events': result.num_events_total
            })
            print(f"    ✓ {result.num_events_total} rally")
            
            # Auto-approve
            try:
                approver.process_symbol(symbol, "15m")
            except:
                pass
                
        except Exception as e:
            print(f"    ✗ Hata: {str(e)[:50]}")
            scan_errors.append(symbol)
    
    # Summary
    duration = datetime.now() - start_time
    print("\n" + "=" * 80)
    print("📊 ÖZET")
    print("=" * 80)
    print(f"Süre: {duration}")
    print(f"Features hesaplanan: {len(symbols_need_features) - len(feature_errors)}")
    print(f"Rally taranan: {len(results)}")
    
    if results:
        total_events = sum(r['events'] for r in results)
        print(f"Toplam yeni rally: {total_events:,}")
    
    if feature_errors:
        print(f"\n⚠️ Feature hataları: {len(feature_errors)}")
    if scan_errors:
        print(f"⚠️ Tarama hataları: {len(scan_errors)}")
    
    print("\n✅ Pipeline tamamlandı!")


if __name__ == "__main__":
    main()
