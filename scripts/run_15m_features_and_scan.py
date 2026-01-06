#!/usr/bin/env python3
"""
15m Features + Rally Scan for ALL available 15m history data.
Handles both path styles: coin_cells/SYMBOL/data/ and coin_cells/SYMBOL/

Usage:
    source venv/bin/activate && nohup python scripts/run_15m_features_and_scan.py > logs/15m_scan.log 2>&1 &
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tezaver.features.indicator_engine import build_features_for_history_df
from tezaver.rally.fast15_rally_scanner import run_fast15_scan_for_symbol
from tezaver.ony.auto_approver import OnyAutoApprover
from tezaver.core.logging_utils import get_logger
import pandas as pd

logger = get_logger(__name__)


def get_history_path(symbol: str, tf: str) -> Path:
    """Get history file path, checking both possible locations."""
    coin_cells = Path("coin_cells")
    
    # Try data/ subdirectory first
    path1 = coin_cells / symbol / "data" / f"history_{tf}.parquet"
    if path1.exists():
        return path1
    
    # Try direct path
    path2 = coin_cells / symbol / f"history_{tf}.parquet"
    if path2.exists():
        return path2
    
    return None


def get_features_path(symbol: str, tf: str) -> Path:
    """Get expected features file path."""
    coin_cells = Path("coin_cells")
    
    # Check data/ subdirectory
    data_dir = coin_cells / symbol / "data"
    if data_dir.exists():
        return data_dir / f"features_{tf}.parquet"
    
    # Direct path
    return coin_cells / symbol / f"features_{tf}.parquet"


def build_features_for_symbol(symbol: str, tf: str) -> bool:
    """Build features for a symbol/timeframe."""
    history_path = get_history_path(symbol, tf)
    if not history_path:
        return False
    
    features_path = get_features_path(symbol, tf)
    
    # Load history and build features
    df = pd.read_parquet(history_path)
    df_features = build_features_for_history_df(df)
    
    # Ensure parent directory exists
    features_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save
    df_features.to_parquet(features_path, index=False)
    return True


def get_symbols_with_15m_history():
    """Get all symbols with 15m history."""
    coin_cells = Path("coin_cells")
    symbols = []
    
    for d in coin_cells.iterdir():
        if d.is_dir() and d.name.endswith("USDT"):
            if get_history_path(d.name, "15m"):
                symbols.append(d.name)
    
    return sorted(symbols)


def get_symbols_needing_features():
    """Get symbols with 15m history but no features."""
    coin_cells = Path("coin_cells")
    need_features = []
    
    for d in coin_cells.iterdir():
        if d.is_dir() and d.name.endswith("USDT"):
            if get_history_path(d.name, "15m"):
                features_path = get_features_path(d.name, "15m")
                if not features_path.exists():
                    need_features.append(d.name)
    
    return sorted(need_features)


def get_symbols_needing_scan():
    """Get symbols with features but no rally scan."""
    coin_cells = Path("coin_cells")
    fast15_dir = Path("library/fast15_rallies")
    
    need_scan = []
    for d in coin_cells.iterdir():
        if d.is_dir() and d.name.endswith("USDT"):
            features_path = get_features_path(d.name, "15m")
            if features_path.exists():
                scan_path = fast15_dir / d.name / "fast15_rallies.parquet"
                if not scan_path.exists():
                    need_scan.append(d.name)
    
    return sorted(need_scan)


def main():
    start_time = datetime.now()
    
    print("=" * 80)
    print("🚀 15m FEATURES + RALLY SCAN")
    print("=" * 80)
    print(f"Start: {start_time}")
    
    # Stats
    all_with_15m = get_symbols_with_15m_history()
    print(f"\n📊 15m history mevcut: {len(all_with_15m)} sembol")
    
    # Phase 1: Build features
    need_features = get_symbols_needing_features()
    print(f"\n📊 PHASE 1: Feature Hesaplama")
    print(f"Features eksik: {len(need_features)} sembol")
    
    feature_errors = []
    for i, symbol in enumerate(need_features, 1):
        print(f"  [{i}/{len(need_features)}] {symbol}...", end=" ", flush=True)
        try:
            for tf in ['15m', '1h', '4h', '1d']:
                if get_history_path(symbol, tf):
                    build_features_for_symbol(symbol, tf)
            print("✓")
        except Exception as e:
            print(f"✗ {str(e)[:40]}")
            feature_errors.append(symbol)
    
    # Phase 2: Rally scan
    need_scan = get_symbols_needing_scan()
    print(f"\n🔍 PHASE 2: Rally Scan")
    print(f"Tarama eksik: {len(need_scan)} sembol")
    
    approver = OnyAutoApprover()
    scan_results = []
    scan_errors = []
    
    for i, symbol in enumerate(need_scan, 1):
        print(f"  [{i}/{len(need_scan)}] {symbol}...", end=" ", flush=True)
        try:
            result = run_fast15_scan_for_symbol(symbol)
            scan_results.append({'symbol': symbol, 'events': result.num_events_total})
            print(f"✓ {result.num_events_total} rally")
            try:
                approver.process_symbol(symbol, "15m")
            except:
                pass
        except Exception as e:
            print(f"✗ {str(e)[:40]}")
            scan_errors.append(symbol)
    
    # Summary
    duration = datetime.now() - start_time
    print("\n" + "=" * 80)
    print("📊 ÖZET")
    print("=" * 80)
    print(f"Süre: {duration}")
    print(f"Features hesaplanan: {len(need_features) - len(feature_errors)}/{len(need_features)}")
    print(f"Rally taranan: {len(need_scan) - len(scan_errors)}/{len(need_scan)}")
    
    if scan_results:
        total = sum(r['events'] for r in scan_results)
        print(f"Yeni rally: {total:,}")
    
    # Final count
    fast15_dir = Path("library/fast15_rallies")
    final_count = len([d for d in fast15_dir.iterdir() if d.is_dir() and (d / "fast15_rallies.parquet").exists()])
    print(f"\n✅ Toplam taranmış sembol: {final_count}")
    print("✅ Pipeline tamamlandı!")


if __name__ == "__main__":
    main()
