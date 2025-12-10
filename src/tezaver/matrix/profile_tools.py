# Matrix V2 Profile Tools
"""
Tools for enriching Matrix candidate profiles with War Game benchmarks.
"""

from pathlib import Path
import json
from typing import Any, Dict, List

from tezaver.matrix.wargame.runner import SILVER_MULTI_COIN_SUMMARY_PATH


MATRIX_CANDIDATE_PROFILES_PATH = Path(
    "data/coin_profiles/BTCUSDT/matrix_candidate_profiles_v1.json"
)


def load_silver_multi_coin_summary() -> Dict[str, Any]:
    """Load Silver 15m multi-coin summary from JSON."""
    if not SILVER_MULTI_COIN_SUMMARY_PATH.exists():
        raise FileNotFoundError(
            f"Summary not found: {SILVER_MULTI_COIN_SUMMARY_PATH}\n"
            "Run: python -m tezaver.matrix.wargame.runner multi_silver_15m_save"
        )
    
    with SILVER_MULTI_COIN_SUMMARY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_matrix_candidate_profiles() -> List[Dict[str, Any]]:
    """Load Matrix candidate profiles from JSON."""
    if not MATRIX_CANDIDATE_PROFILES_PATH.exists():
        # Return empty list if file doesn't exist
        return []
    
    with MATRIX_CANDIDATE_PROFILES_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Handle both list and dict with "profiles" key
    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and "profiles" in data:
        return data["profiles"]
    return []


def save_matrix_candidate_profiles(profiles: List[Dict[str, Any]]) -> None:
    """Save Matrix candidate profiles to JSON."""
    MATRIX_CANDIDATE_PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with MATRIX_CANDIDATE_PROFILES_PATH.open("w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)


def _find_low_risk_row(
    summary: Dict[str, Any],
    symbol: str,
    risk: float = 0.01,
) -> Dict[str, Any]:
    """Find the summary row for a symbol at given risk level."""
    for row in summary.get("coins", []):
        if row.get("symbol") == symbol and abs(row.get("risk", 0.0) - risk) < 1e-9:
            return row
    return {}


def enrich_silver_15m_profiles_with_benchmark() -> None:
    """
    Enrich Matrix candidate profiles with Silver 15m benchmark data.
    
    Reads silver_15m_multi_coin_wargame_v1.json and adds 
    silver_15m_benchmark_v1 field to matching profiles.
    """
    summary = load_silver_multi_coin_summary()
    profiles = load_matrix_candidate_profiles()
    
    if not profiles:
        print("[SKIP] No Matrix candidate profiles found.")
        return
    
    # Symbol → profile_id mapping
    mapping = {
        "BTCUSDT": "BTC_SILVER_15M_CORE_V1",
        "ETHUSDT": "ETH_SILVER_15M_CORE_V1",
        "SOLUSDT": "SOL_SILVER_15M_CORE_V1",
    }
    
    updated_count = 0
    
    for symbol, profile_id in mapping.items():
        row = _find_low_risk_row(summary, symbol, risk=0.01)
        if not row:
            print(f"[SKIP] No summary row for {symbol} 0.01 risk")
            continue
        
        for profile in profiles:
            if profile.get("profile_id") == profile_id:
                profile["silver_15m_benchmark_v1"] = {
                    "risk": row.get("risk"),
                    "capital_start": row.get("capital_start"),
                    "capital_end": row.get("capital_end"),
                    "pnl_pct": row.get("pnl_pct"),
                    "max_dd_pct": row.get("max_dd_pct"),
                    "trades": row.get("trades"),
                }
                print(f"[OK] Updated profile {profile_id} with silver_15m_benchmark_v1")
                updated_count += 1
                break
    
    if updated_count > 0:
        save_matrix_candidate_profiles(profiles)
        print(f"\n[SAVED] Updated {updated_count} profiles in {MATRIX_CANDIDATE_PROFILES_PATH}")
    else:
        print("\n[INFO] No profiles were updated.")


# =============================================================================
# RISK CONTRACT V1
# =============================================================================

def build_silver_15m_risk_contracts_from_summary(
    summary: Dict[str, Any],
    default_max_risk: float = 0.01,
) -> Dict[str, Dict[str, Any]]:
    """
    Build risk_contract_v1 mapping from Silver 15m multi-coin summary.
    
    All Silver 15m core strategies get:
    - max_risk_per_trade = 0.01 (1%)
    - status = APPROVED
    
    Args:
        summary: Loaded silver_15m_multi_coin_wargame_v1.json content.
        default_max_risk: Default max risk per trade (0.01 = 1%).
        
    Returns:
        Dict mapping symbol to risk_contract_v1 dict.
    """
    result: Dict[str, Dict[str, Any]] = {}
    
    # Supported symbols
    symbols = {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
    
    for symbol in symbols:
        row = _find_low_risk_row(summary, symbol, risk=0.01)
        if not row:
            continue
        
        pnl_pct_ref = float(row.get("pnl_pct", 0.0))
        trades_ref = int(row.get("trades", 0))
        
        result[symbol] = {
            "profile_kind": "silver_15m",
            "status": "APPROVED",
            "max_risk_per_trade": default_max_risk,
            "source": summary.get("version", "silver_15m_multi_coin_v1"),
            "notes": "v1 uniform 1% risk cap; coin-level adjustment TBD",
            "reference": {
                "risk_ref": 0.01,
                "pnl_pct_ref": pnl_pct_ref,
                "trades_ref": trades_ref,
            },
        }
    
    return result


def enrich_silver_15m_profiles_with_risk_contract_v1() -> None:
    """
    Add risk_contract_v1 to Silver 15m core profiles.
    
    Updates matrix_candidate_profiles_v1.json:
    - Finds profiles with type="silver_core" and timeframe="15m"
    - Attaches risk_contract_v1 with max_risk_per_trade=0.01
    """
    if not SILVER_MULTI_COIN_SUMMARY_PATH.exists():
        print(f"[SKIP] Silver 15m summary not found: {SILVER_MULTI_COIN_SUMMARY_PATH}")
        return
    
    summary = load_silver_multi_coin_summary()
    risk_contracts = build_silver_15m_risk_contracts_from_summary(summary)
    
    profiles = load_matrix_candidate_profiles()
    
    if not profiles:
        print("[SKIP] No Matrix candidate profiles found.")
        return
    
    updated = 0
    
    for profile in profiles:
        # Match on type="silver_core" and timeframe="15m"
        profile_type = profile.get("type", "")
        timeframe = profile.get("timeframe", "")
        
        # Accept profiles that are silver_core 15m OR match our known profile IDs
        is_silver_15m = (profile_type == "silver_core" and timeframe == "15m")
        is_known_id = profile.get("profile_id") in {
            "BTC_SILVER_15M_CORE_V1",
            "ETH_SILVER_15M_CORE_V1",
            "SOL_SILVER_15M_CORE_V1",
        }
        
        if not (is_silver_15m or is_known_id):
            continue
        
        symbol = profile.get("symbol")
        if symbol not in risk_contracts:
            print(f"[SKIP] No risk contract for symbol={symbol}")
            continue
        
        profile["risk_contract_v1"] = risk_contracts[symbol]
        updated += 1
        print(f"[OK] Attached risk_contract_v1 to profile_id={profile.get('profile_id')} (symbol={symbol})")
    
    if updated == 0:
        print("[INFO] No matching Silver 15m profiles were updated.")
    else:
        save_matrix_candidate_profiles(profiles)
        print(f"\n[DONE] Updated {updated} Silver 15m profiles with risk_contract_v1.")


if __name__ == "__main__":
    print("=== Matrix Profile Tools ===\n")
    
    # 1. Benchmark enrichment
    print("--- Step 1: Benchmark Enrichment ---")
    try:
        enrich_silver_15m_profiles_with_benchmark()
    except FileNotFoundError as e:
        print(f"[SKIP] Benchmark: {e}")
    
    print()
    
    # 2. Risk Contract v1 enrichment
    print("--- Step 2: Risk Contract v1 ---")
    enrich_silver_15m_profiles_with_risk_contract_v1()

