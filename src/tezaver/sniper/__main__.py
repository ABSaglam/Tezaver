"""
Sniper module CLI entry point.

Usage:
    python -m tezaver.sniper BTCUSDT 15m            # From annotations
    python -m tezaver.sniper BTCUSDT 15m --from-patterns  # From rally patterns
    python -m tezaver.sniper all                    # All Silver 15m symbols
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd


def create_sniper_entries_from_patterns(symbol: str, timeframe: str) -> Path:
    """
    Create sniper entries dataset directly from rally patterns.
    No annotations required - uses all Diamond/Gold rallies as entries.
    """
    from tezaver.rally.rally_pattern_loader import load_rally_patterns
    
    symbol = symbol.upper()
    
    # Load rally patterns
    df = load_rally_patterns(symbol, timeframe)
    
    if df.empty:
        raise RuntimeError(f"No rally patterns found for {symbol} {timeframe}")
    
    # Remove duplicate columns
    df = df.loc[:, ~df.columns.duplicated()]
    
    # Filter to Diamond + Gold only (good entries)
    mask = pd.Series([False] * len(df), index=df.index)
    if "label_is_diamond" in df.columns:
        mask |= df["label_is_diamond"] == True
    if "label_is_gold" in df.columns:
        mask |= df["label_is_gold"] == True
    
    if mask.any():
        df_filtered = df[mask].copy()
    else:
        # No grade labels, use top 30% by gain
        gain_col = "label_future_max_gain_pct" if "label_future_max_gain_pct" in df.columns else None
        if gain_col:
            threshold = df[gain_col].quantile(0.70)
            df_filtered = df[df[gain_col] >= threshold].copy()
        else:
            df_filtered = df.copy()
    
    print(f"  Selected {len(df_filtered)} entries from {len(df)} patterns")
    
    # Rename columns to sniper format
    rename_map = {}
    if "label_future_max_gain_pct" in df_filtered.columns:
        rename_map["label_future_max_gain_pct"] = "future_max_gain_pct"
    if "feat_bars_to_peak" in df_filtered.columns:
        rename_map["feat_bars_to_peak"] = "bars_to_peak"
    
    df_filtered = df_filtered.rename(columns=rename_map)
    
    # Add entry_offset column (default to 0 = entry at rally start)
    df_filtered["entry_bar_offset"] = 0
    
    # Save
    output_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/sniper_entries_v1.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_filtered.to_parquet(output_path, index=False)
    
    return output_path


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        print("Sniper Entry Dataset Builder")
        print("=" * 40)
        print()
        print("Usage:")
        print("  python -m tezaver.sniper SYMBOL [TIMEFRAME] [OPTIONS]")
        print("  python -m tezaver.sniper all")
        print()
        print("Options:")
        print("  --from-patterns    Generate from rally patterns (no annotations needed)")
        print()
        print("Examples:")
        print("  python -m tezaver.sniper BTCUSDT 15m")
        print("  python -m tezaver.sniper BTCUSDT 15m --from-patterns")
        print("  python -m tezaver.sniper all")
        return

    from_patterns = "--from-patterns" in argv
    argv = [a for a in argv if a != "--from-patterns"]

    if argv[0].lower() == "all":
        from tezaver.sniper.sniper_story_builder import build_sniper_entry_datasets_for_all_silver_15m_symbols
        print("Building sniper entry datasets for all Silver 15m symbols...")
        print()
        results = build_sniper_entry_datasets_for_all_silver_15m_symbols()
        print()
        print("Summary:")
        for sym, path in results.items():
            print(f"  ✓ {sym}: {path}")
        return

    symbol = argv[0].upper()
    timeframe = argv[1] if len(argv) > 1 else "15m"
    
    print(f"Building sniper entry dataset for {symbol} {timeframe}...")
    
    try:
        if from_patterns:
            print("  Mode: from-patterns (annotation gerekmez)")
            path = create_sniper_entries_from_patterns(symbol, timeframe)
        else:
            from tezaver.sniper.sniper_story_builder import save_sniper_entry_dataset_for_symbol_timeframe
            path = save_sniper_entry_dataset_for_symbol_timeframe(symbol, timeframe)
        print(f"✓ Done: {path}")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
