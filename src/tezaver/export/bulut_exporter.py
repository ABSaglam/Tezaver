"""
Bulut Exporter for Tezaver Mac.
Creates unified export artifacts for Tezaver Bulut.

Tezaver Philosophy:
- "Her coin'in bilgeliği bir pakette toplanır, Bulut'a gönderilmek üzere hazır olur."
- "Bu export, sadece bir JSON değil, coin'in ruhunun özet fotoğrafıdır."
"""

import json
from datetime import datetime
from typing import Any, List, Dict, Optional
from pathlib import Path

from tezaver.core import state_store
from tezaver.wisdom.pattern_stats import (
    get_coin_profile_dir,
    get_pattern_stats_file,
    get_trustworthy_patterns_file,
    get_betrayal_patterns_file,
    get_volatility_signature_file,
)


def load_json_if_exists(path: Path) -> Any | None:
    """Loads JSON file if it exists, otherwise returns None."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return None


def load_coin_state_entry(symbol: str) -> dict | None:
    """Loads CoinState entry for a symbol and converts to dict."""
    try:
        coin_states = state_store.load_coin_states()
        state = state_store.find_coin_state(coin_states, symbol)
        
        if not state:
            return None
        
        # Convert to dict
        state_dict = state.__dict__.copy()
        
        # Convert DataState enum to string
        if "data_state" in state_dict:
            state_dict["data_state"] = state_dict["data_state"].value
        
        # Convert datetime to ISO string
        if "last_update" in state_dict and state_dict["last_update"]:
            state_dict["last_update"] = state_dict["last_update"].isoformat()
        
        return state_dict
    except Exception as e:
        print(f"Error loading coin state for {symbol}: {e}")
        return None


def load_levels_for_symbol(symbol: str) -> dict:
    """Loads support/resistance levels for all timeframes."""
    from tezaver.core.config import DEFAULT_SNAPSHOT_BASE_TFS
    
    profile_dir = get_coin_profile_dir(symbol)
    levels_by_tf = {}
    
    for tf in DEFAULT_SNAPSHOT_BASE_TFS:
        levels_file = profile_dir / f"levels_{tf}.json"
        levels_data = load_json_if_exists(levels_file)
        
        # Levels file is a list, not a dict
        if levels_data and isinstance(levels_data, list):
            levels_by_tf[tf] = levels_data
        else:
            levels_by_tf[tf] = []
    
    return levels_by_tf


def load_rally_families_for_symbol(symbol: str) -> List[dict]:
    """Loads rally families for all timeframes."""
    from tezaver.core.config import DEFAULT_SNAPSHOT_BASE_TFS
    
    profile_dir = get_coin_profile_dir(symbol)
    all_families = []
    
    for tf in DEFAULT_SNAPSHOT_BASE_TFS:
        families_file = profile_dir / f"rally_families_{tf}.json"
        families_data = load_json_if_exists(families_file)
        
        if families_data and families_data.get("families"):
            for family in families_data["families"]:
                family["base_timeframe"] = tf
                all_families.append(family)
    
    return all_families


def build_rally_export(families: List[dict]) -> dict:
    """Organizes rally families into preferred/avoid/all categories."""
    preferred = []
    avoid = []
    
    for family in families:
        trust_score = family.get("trust_score", 0.0)
        sample_count = family.get("sample_count", 0)
        
        if trust_score >= 0.6 and sample_count >= 30:
            preferred.append(family)
        elif trust_score <= 0.3 and sample_count >= 30:
            avoid.append(family)
    
    return {
        "preferred": preferred,
        "avoid": avoid,
        "all": families
    }


def build_bulut_export_for_symbol(symbol: str) -> dict:
    """
    Builds complete export artifact for a symbol.
    """
    print(f"Building Bulut export for {symbol}...")
    
    profile_dir = get_coin_profile_dir(symbol)
    
    # Load all data sources
    coin_state_entry = load_coin_state_entry(symbol) or {}
    pattern_stats = load_json_if_exists(get_pattern_stats_file(symbol)) or []
    trustworthy_patterns = load_json_if_exists(get_trustworthy_patterns_file(symbol)) or []
    betrayal_patterns = load_json_if_exists(get_betrayal_patterns_file(symbol)) or []
    volatility_signature = load_json_if_exists(get_volatility_signature_file(symbol)) or {}
    regime_profile = load_json_if_exists(profile_dir / "regime_profile.json") or {}
    shock_profile = load_json_if_exists(profile_dir / "shock_profile.json") or {}
    rally_families = load_rally_families_for_symbol(symbol)
    levels = load_levels_for_symbol(symbol)
    
    # Build rally export
    rally_export = build_rally_export(rally_families)
    
    # Construct export artifact
    from tezaver.core.config import get_turkey_now
    export_dict = {
        "symbol": symbol,
        "generated_at": get_turkey_now().isoformat(),
        "meta": {
            "data_state": coin_state_entry.get("data_state", "unknown"),
            "export_ready": coin_state_entry.get("export_ready", False),
            "last_update": coin_state_entry.get("last_update"),
        },
        "persona": {
            "tags": coin_state_entry.get("persona_summary", []),
            "trend_soul_score": coin_state_entry.get("trend_soul_score", 0),
            "harmony_score": coin_state_entry.get("harmony_score", 0),
            "betrayal_score": coin_state_entry.get("betrayal_score", 0),
            "volume_trust": coin_state_entry.get("volume_trust", 0),
            "risk_level": coin_state_entry.get("risk_level", "medium"),
            "opportunity_score": coin_state_entry.get("opportunity_score", 0),
            "self_trust_score": coin_state_entry.get("self_trust_score", 0),
            "regime": coin_state_entry.get("regime", "unknown"),
            "shock_risk": coin_state_entry.get("shock_risk", 0),
        },
        "volatility": volatility_signature,
        "patterns": {
            "trustworthy": trustworthy_patterns,
            "betrayal": betrayal_patterns,
            "all_stats": pattern_stats,
        },
        "rally_families": rally_export,
        "levels": levels,
        "regime_profile": regime_profile,
        "shock_profile": shock_profile,
    }
    
    # Save to file
    export_path = profile_dir / "export_bulut.json"
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(export_dict, f, indent=2, ensure_ascii=False)
    
    print(f"  Saved Bulut export to {export_path}")
    
    return export_dict


def bulk_build_bulut_exports(symbols: List[str]) -> None:
    """
    Builds Bulut exports for multiple symbols.
    """
    for symbol in symbols:
        try:
            build_bulut_export_for_symbol(symbol)
        except Exception as e:
            print(f"Error building Bulut export for {symbol}: {e}")
            import traceback
            traceback.print_exc()
