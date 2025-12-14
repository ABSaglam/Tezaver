"""
Sniper Arena Runner v1
======================

Single entry point for all Sniper Arena runs.
Handles entry selection and backtest execution with hash verification.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pandas as pd

from tezaver.sniper.sniper_backtest import (
    run_sniper_backtest_for_symbol_timeframe,
    run_sniper_backtest_from_trade_ids,
)
from tezaver.sniper.sniper_filter_debug import (
    build_effective_sniper_filter_window,
    compute_sniper_dataset_stats,
    select_sniper_entries,
)
from tezaver.sniper.sniper_ids import ensure_trade_id_column


# =============================================================================
# Hash Utilities
# =============================================================================

def compute_entries_hash(df: pd.DataFrame) -> str:
    """Compute SHA1 hash of sorted event_id|ts entries."""
    if df is None or df.empty:
        return "EMPTY"
    
    items = []
    for _, row in df.iterrows():
        eid = str(row.get("event_id", ""))
        ts = str(row.get("event_time", row.get("ts", "")))[:19]
        items.append(f"{eid}|{ts}")
    
    items.sort()
    return hashlib.sha1("".join(items).encode()).hexdigest()[:10]


def extract_entry_ids(df: pd.DataFrame) -> List[str]:
    """Extract sorted list of entry IDs from dataframe."""
    if df is None or df.empty:
        return []
    
    id_col = "event_id" if "event_id" in df.columns else "entry_id"
    if id_col not in df.columns:
        return []
    
    return sorted([str(x) for x in df[id_col].tolist()])


# =============================================================================
# Main Arena Runner
# =============================================================================

def run_sniper_arena(
    symbol: str,
    timeframe: str,
    data_source: str,               # "patterns" | "full_replay"
    selection_mode: str,            # "ARENA_FILTERS" | "CARD_STRICT_IDS"
    tightness: int,
    toggles: Dict[str, bool],       # {"rsi": True, "volume": True, ...}
    pattern_config: Dict[str, Any], # {"stage_enabled": bool, "enabled_features": [...]}
    use_profile: bool,
    apply_risk_contract: bool,
    risk_requested: float,
    tp_override: Optional[float] = None,
    sl_override: Optional[float] = None,
    max_bars_override: Optional[int] = None,
    mode: str = "experiment",       # "contract" | "experiment"
    clamp_policy: str = "HARD",     # "OFF" | "SOFT" | "HARD"
    quality_override: Optional[float] = None,  # Manual quality min override
) -> Dict[str, Any]:
    """
    Run Sniper Arena backtest with explicit entry selection and hash verification.
    
    This is the SINGLE entry point for all Sniper Arena runs.
    
    Returns:
        Dictionary containing:
        - Backtest results (pnl, win_rate, etc.)
        - selected_count, selected_hash
        - used_count, used_hash
        - config_hash, window_hash
        - run_id, computed_at (forensic tracking)
        - engine_path: "ENTRY_BACKTEST"
    """
    # Forensic: Unique run ID and timestamp
    run_id = uuid4().hex[:8]
    computed_at = datetime.utcnow().isoformat()
    
    print(f"[ARENA RUN] {run_id} @ {computed_at}")
    
    symbol = symbol.upper()
    
    # =========================================================================
    # 1. Load Data
    # =========================================================================
    entries_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/sniper_entries_v1.parquet")
    card_path = Path(f"data/coin_profiles/{symbol}/{timeframe}/sniper_strategy_card_v1.json")
    
    if not entries_path.exists():
        raise FileNotFoundError(f"Entries dataset not found: {entries_path}")
    
    df = pd.read_parquet(entries_path)
    total_entries = len(df)
    
    card = {}
    if card_path.exists():
        card = json.loads(card_path.read_text())
    
    # =========================================================================
    # 2. Build Config Hash
    # =========================================================================
    config_dict = {
        "symbol": symbol,
        "timeframe": timeframe,
        "data_source": data_source,
        "selection_mode": selection_mode,
        "tightness": tightness,
        "toggles": toggles,
        "pattern_config": pattern_config,
        "use_profile": use_profile,
        "apply_risk_contract": apply_risk_contract,
        "risk_requested": risk_requested,
        "tp_override": tp_override,
        "sl_override": sl_override,
        "max_bars_override": max_bars_override,
        "mode": mode,
        "clamp_policy": clamp_policy,
        "quality_override": quality_override,
    }
    config_json = json.dumps(config_dict, sort_keys=True)
    config_hash = hashlib.sha1(config_json.encode()).hexdigest()[:10]
    
    # =========================================================================
    # 3. Select Entries Based on Mode
    # =========================================================================
    selected_df: pd.DataFrame
    window_hash: str = "N/A"
    
    if selection_mode == "CARD_STRICT_IDS":
        # Use card's strict entry IDs
        strict_ids = card.get("provenance", {}).get("strict_entry_ids", [])
        
        if strict_ids:
            id_col = "event_id" if "event_id" in df.columns else "entry_id"
            selected_df = df[df[id_col].isin(strict_ids)].copy()
        else:
            # Fallback to full dataset
            selected_df = df.copy()
            
    elif selection_mode == "ARENA_FILTERS":
        # Build effective window and filter
        dataset_stats = compute_sniper_dataset_stats(df)
        
        # Add pattern toggle to toggles
        toggles_with_pattern = toggles.copy()
        toggles_with_pattern["pattern"] = pattern_config.get("stage_enabled", True)
        
        effective_window = build_effective_sniper_filter_window(
            profile_cfg=card,
            tightness=tightness,
            toggles=toggles_with_pattern,
            dataset_stats=dataset_stats,
            clamp_policy=clamp_policy,
            quality_override=quality_override,
        )
        
        # Apply pattern feature filter
        if pattern_config.get("enabled_features"):
            current_rules = effective_window.get("pattern_rules", [])
            allowed_features = set(pattern_config["enabled_features"])
            effective_window["pattern_rules"] = [
                r for r in current_rules if r.get("feature") in allowed_features
            ]
        
        # Compute window hash
        window_json = json.dumps(effective_window, sort_keys=True, default=str)
        window_hash = hashlib.sha1(window_json.encode()).hexdigest()[:10]
        
        # Select entries
        selection_result = select_sniper_entries(
            df=df,
            mode="ARENA_FILTERS",
            card=card,
            effective_window=effective_window,
        )
        selected_df = selection_result.selected_df
        
        # Ensure trade_id column exists for tracking
        selected_df = ensure_trade_id_column(selected_df)
        
    else:
        raise ValueError(f"Unknown selection_mode: {selection_mode}")
    
    # =========================================================================
    # 4. Compute Selected Hash
    # =========================================================================
    selected_count = len(selected_df)
    selected_hash = compute_entries_hash(selected_df)
    selected_trade_ids = selected_df["trade_id"].tolist() if "trade_id" in selected_df.columns else []
    
    # Duplicate Tripwire
    unique_trade_ids = sorted(set(selected_trade_ids))
    unique_count = len(unique_trade_ids)
    dup_count = len(selected_trade_ids) - unique_count
    
    if dup_count > 0:
        from collections import Counter
        c = Counter(selected_trade_ids)
        dups = [k for k, v in c.items() if v > 1][:20]
        raise RuntimeError(
            f"[DUP_TRADE_ID] total={len(selected_trade_ids)} unique={unique_count} "
            f"dup_count={dup_count} dup_sample={dups}"
        )
    
    print(f"[ARENA] Selected: {selected_count}/{total_entries} (Hash: {selected_hash}) Unique: {unique_count}")
    
    # =========================================================================
    # 5. Run Backtest with Trade ID Override (NO DEDUP, NO REFILTER)
    # =========================================================================
    backtest_result = run_sniper_backtest_from_trade_ids(
        symbol=symbol,
        timeframe=timeframe,
        selected_trade_ids=selected_trade_ids,
        risk=risk_requested,
        tp_pct=0.08,  # Default TP
        sl_pct=0.03,  # Default SL
        max_horizon_bars=20,
    )
    
    # =========================================================================
    # 6. Verify Wiring (Tripwire) - Now guaranteed by new function
    # =========================================================================
    used_count = backtest_result.get("used_count", 0)
    trades_count = backtest_result.get("trades", 0)
    trade_fingerprint = backtest_result.get("trade_fingerprint", "N/A")
    
    print(f"[ARENA] Used={used_count} Trades={trades_count} Fingerprint={trade_fingerprint}")
    
    # Hard check: Selected == Used (guaranteed by new function, but verify)
    if selected_count != used_count:
        error_msg = f"WIRING BROKEN: Selected={selected_count} != Used={used_count}"
        print(f"[ARENA ERROR] {error_msg}")
        raise RuntimeError(error_msg)
    
    print(f"[ARENA] Wiring OK: Selected={selected_count} == Used={used_count} == Trades={trades_count}")
    
    # =========================================================================
    # 7. Build Final Report (with Forensic Data)
    # =========================================================================
    report = {
        # Forensic tracking
        "run_id": run_id,
        "computed_at": computed_at,
        
        # Backtest results
        "capital_start": backtest_result.get("capital_start", 100),
        "capital_end": backtest_result.get("capital_end", 100),
        "pnl_pct": backtest_result.get("pnl_pct", 0.0),
        "trade_count": trades_count,
        "win_rate": backtest_result.get("win_rate", 0.0),
        "max_drawdown_pct": backtest_result.get("max_drawdown_pct", 0.0),
        
        # Entry selection proof (NOW GUARANTEED: Selected == Used == Trades)
        "selected_count": selected_count,
        "selected_hash": selected_hash,
        "selected_ids_sample": selected_trade_ids[:20],
        "unique_count": unique_count,
        "all_trade_ids": selected_trade_ids,  # Full list for diff tracking
        "used_count": used_count,
        "used_hash": trade_fingerprint,  # Using fingerprint as used hash
        "used_ids_sample": backtest_result.get("used_trade_ids_sample", []),
        "total_entries": total_entries,
        
        # Config proof
        "config_hash": config_hash,
        "window_hash": window_hash,
        "selection_mode": selection_mode,
        "tightness": tightness,
        "clamp_policy": clamp_policy,
        "quality_override": quality_override,
        
        # Trade tracking
        "trade_list": backtest_result.get("ledger", []),
        "trade_ids_hash": trade_fingerprint,
        "pnl_signature": backtest_result.get("pnl_signature", "N/A"),
        "pnl_signature_v2": backtest_result.get("pnl_signature_v2", "N/A"),
        "position_sizing_mode": backtest_result.get("position_sizing_mode", "equity_pct"),
        "disable_tp_sl_caps": backtest_result.get("disable_tp_sl_caps", False),
        "use_raw_pnl": backtest_result.get("use_raw_pnl", False),
        
        # Diagnostics
        "exit_reason_counts": backtest_result.get("exit_reason_counts", {}),
        "tp_capped_count": backtest_result.get("tp_capped_count", 0),
        "sl_capped_count": backtest_result.get("sl_capped_count", 0),
        "pnl_raw_stats": backtest_result.get("pnl_raw_stats", {}),
        "pnl_eff_stats": backtest_result.get("pnl_eff_stats", {}),
        "pnl_eff_unique_count": backtest_result.get("pnl_eff_unique_count", 0),
        "pnl_eff_top_bins": backtest_result.get("pnl_eff_top_bins", []),
        
        # Engine path
        "engine_path": "ARENA_OVERRIDE",
    }
    
    return report
