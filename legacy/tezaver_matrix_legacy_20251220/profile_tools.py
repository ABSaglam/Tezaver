# Matrix V2 Profile Tools
"""
Tools for enriching Matrix candidate profiles with War Game benchmarks.
Also builds CoinStrategyPageV2 JSON files.
"""

from pathlib import Path
import json
import sys
from typing import Any, Dict, List, Optional

from tezaver.matrix.wargame.runner import SILVER_MULTI_COIN_SUMMARY_PATH
from tezaver.matrix.coin_page.schema import (
    CoinStrategyPageV2,
    TimeframeStrategiesV2,
    MatrixStrategyProfileV2,
    StrategyConfigV1,
    StrategyBenchmarkV1,
    StrategyRiskContractV1,
    StrategyRuntimeMode,
)


MATRIX_CANDIDATE_PROFILES_PATH = Path(
    "data/coin_profiles/BTCUSDT/matrix_candidate_profiles_v1.json"
)

BTCUSDT_COIN_PAGE_V2_PATH = Path(
    "data/coin_profiles/BTCUSDT/matrix_coin_page_v2.json"
)

BTCUSDT_SILVER_STRATEGY_CARD_PATH = Path(
    "data/coin_profiles/BTCUSDT/15m/silver_strategy_card_v1.json"
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


# =============================================================================
# COIN PAGE V2 BUILDER
# =============================================================================

def _load_strategy_card(path: Path) -> Dict[str, Any]:
    """Load strategy card JSON."""
    if not path.exists():
        raise FileNotFoundError(f"Strategy card not found: {path}")
    
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_btc_silver_15m_coin_page_v2() -> CoinStrategyPageV2:
    """
    Build BTCUSDT CoinStrategyPageV2 from existing data sources:
    
    - Strategy card: data/coin_profiles/BTCUSDT/15m/silver_strategy_card_v1.json
    - Benchmark: data/ai_insights/global/silver_15m_multi_coin_wargame_v1.json
    - Risk contract: from matrix_candidate_profiles_v1.json or built fresh
    
    Returns:
        CoinStrategyPageV2 object for BTCUSDT.
    """
    symbol = "BTCUSDT"
    profile_id = "BTC_SILVER_15M_CORE_V1"
    
    # 1. Load strategy card (v2_ml)
    strategy_card = _load_strategy_card(BTCUSDT_SILVER_STRATEGY_CARD_PATH)
    
    # Build StrategyConfigV1 from card
    strategy_config = StrategyConfigV1(
        version=strategy_card.get("version", "v2_ml"),
        entry_filters=strategy_card.get("filters", {}),
        ml_filters=strategy_card.get("ml_filters", {}),
        exit={
            "tp_pct": strategy_card.get("risk", {}).get("tp_pct", 0.09),
            "sl_pct": strategy_card.get("risk", {}).get("sl_pct", 0.002),
            "max_horizon_bars": strategy_card.get("risk", {}).get("max_horizon_bars", 48),
        },
    )
    
    # 2. Load benchmark from War Game summary
    benchmark_v1 = None
    try:
        summary = load_silver_multi_coin_summary()
        row = _find_low_risk_row(summary, symbol, risk=0.01)
        if row:
            benchmark_v1 = StrategyBenchmarkV1(
                capital_start=row.get("capital_start", 100.0),
                capital_end=row.get("capital_end", 100.0),
                pnl_pct=row.get("pnl_pct", 0.0),
                trades=row.get("trades", 0),
            )
    except FileNotFoundError:
        print("[WARN] War Game summary not found, skipping benchmark")
    
    # 3. Load or build risk contract
    risk_contract_v1 = None
    try:
        summary = load_silver_multi_coin_summary()
        contracts = build_silver_15m_risk_contracts_from_summary(summary)
        if symbol in contracts:
            c = contracts[symbol]
            risk_contract_v1 = StrategyRiskContractV1(
                profile_kind=c["profile_kind"],
                status=c["status"],
                max_risk_per_trade=c["max_risk_per_trade"],
                source=c["source"],
                notes=c["notes"],
                reference=c["reference"],
            )
    except FileNotFoundError:
        print("[WARN] War Game summary not found, using default risk contract")
        risk_contract_v1 = StrategyRiskContractV1(
            profile_kind="silver_15m",
            status="APPROVED",
            max_risk_per_trade=0.01,
            source="default",
            notes="Default 1% risk cap",
            reference={},
        )
    
    # 4. Build profile
    profile = MatrixStrategyProfileV2(
        profile_id=profile_id,
        kind="silver_15m_core",
        status="APPROVED",
        strategy=strategy_config,
        benchmark_v1=benchmark_v1,
        risk_contract_v1=risk_contract_v1,
        runtime_mode=StrategyRuntimeMode(enabled=True),
    )
    
    # 5. Build page
    page = CoinStrategyPageV2(
        version="matrix_coin_page_v2",
        symbol=symbol,
        timeframes={
            "15m": TimeframeStrategiesV2(
                tf="15m",
                profiles={
                    profile_id: profile,
                },
            ),
        },
    )
    
    return page


def _profile_to_dict(profile: MatrixStrategyProfileV2) -> Dict[str, Any]:
    """Convert MatrixStrategyProfileV2 to JSON-serializable dict."""
    result: Dict[str, Any] = {
        "profile_id": profile.profile_id,
        "kind": profile.kind,
        "status": profile.status,
        "strategy": {
            "version": profile.strategy.version,
            "entry_filters": profile.strategy.entry_filters,
            "ml_filters": profile.strategy.ml_filters,
            "exit": profile.strategy.exit,
        },
        "runtime_mode": {
            "enabled": profile.runtime_mode.enabled,
        },
    }
    
    if profile.benchmark_v1:
        result["benchmark_v1"] = {
            "capital_start": profile.benchmark_v1.capital_start,
            "capital_end": profile.benchmark_v1.capital_end,
            "pnl_pct": profile.benchmark_v1.pnl_pct,
            "trades": profile.benchmark_v1.trades,
        }
    
    if profile.risk_contract_v1:
        result["risk_contract_v1"] = {
            "profile_kind": profile.risk_contract_v1.profile_kind,
            "status": profile.risk_contract_v1.status,
            "max_risk_per_trade": profile.risk_contract_v1.max_risk_per_trade,
            "source": profile.risk_contract_v1.source,
            "notes": profile.risk_contract_v1.notes,
            "reference": profile.risk_contract_v1.reference,
        }
    
    return result


def _page_to_dict(page: CoinStrategyPageV2) -> Dict[str, Any]:
    """Convert CoinStrategyPageV2 to JSON-serializable dict."""
    timeframes: Dict[str, Any] = {}
    
    for tf_key, tf_strategies in page.timeframes.items():
        profiles: Dict[str, Any] = {}
        for profile_id, profile in tf_strategies.profiles.items():
            profiles[profile_id] = _profile_to_dict(profile)
        
        timeframes[tf_key] = {
            "tf": tf_strategies.tf,
            "profiles": profiles,
        }
    
    return {
        "version": page.version,
        "symbol": page.symbol,
        "timeframes": timeframes,
    }


def save_btc_silver_15m_coin_page_v2() -> None:
    """
    Build and save BTCUSDT matrix_coin_page_v2.json.
    
    Consolidates strategy config, benchmark, and risk contract
    into a single v2 coin page file.
    """
    print("=== Building BTCUSDT CoinPage V2 ===\n")
    
    page = build_btc_silver_15m_coin_page_v2()
    page_dict = _page_to_dict(page)
    
    # Save to file
    BTCUSDT_COIN_PAGE_V2_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with BTCUSDT_COIN_PAGE_V2_PATH.open("w", encoding="utf-8") as f:
        json.dump(page_dict, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] Created: {BTCUSDT_COIN_PAGE_V2_PATH}")
    print(f"[OK] Symbol: {page.symbol}")
    print(f"[OK] Timeframes: {list(page.timeframes.keys())}")
    
    for tf_key, tf_strategies in page.timeframes.items():
        for profile_id, profile in tf_strategies.profiles.items():
            print(f"[OK] Profile: {profile_id} (status={profile.status})")
            if profile.benchmark_v1:
                print(f"     Benchmark: PnL={profile.benchmark_v1.pnl_pct}%, trades={profile.benchmark_v1.trades}")
            if profile.risk_contract_v1:
                print(f"     Risk: max_risk={profile.risk_contract_v1.max_risk_per_trade}")


# =============================================================================
# GENERIC COIN PAGE V2 BUILDER
# =============================================================================

# Symbol to profile_id mapping
SILVER_15M_PROFILE_IDS = {
    "BTCUSDT": "BTC_SILVER_15M_CORE_V1",
    "ETHUSDT": "ETH_SILVER_15M_CORE_V1",
    "SOLUSDT": "SOL_SILVER_15M_CORE_V1",
}

# Symbol status overrides (SOL marked experimental due to extreme PnL)
SILVER_15M_STATUS_OVERRIDES = {
    "SOLUSDT": "EXPERIMENTAL",
}


def _get_strategy_card_path(symbol: str) -> Path:
    """Get strategy card path for a symbol."""
    return Path(f"data/coin_profiles/{symbol}/15m/silver_strategy_card_v1.json")


def _get_coin_page_v2_path(symbol: str) -> Path:
    """Get coin page v2 output path for a symbol."""
    return Path(f"data/coin_profiles/{symbol}/matrix_coin_page_v2.json")


def build_silver_15m_coin_page_v2_for_symbol(
    symbol: str,
    profile_id: Optional[str] = None,
    kind: str = "silver_15m_core",
    status: Optional[str] = None,
) -> CoinStrategyPageV2:
    """
    Build CoinStrategyPageV2 for a given symbol's Silver 15m strategy.
    
    Reads:
    - silver_strategy_card_v1.json (v2_ml config)
    - silver_15m_multi_coin_wargame_v1.json (benchmark)
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT", "SOLUSDT")
        profile_id: Override profile ID (default: derived from symbol)
        kind: Profile kind (default: "silver_15m_core")
        status: Override status (default: APPROVED, SOL -> EXPERIMENTAL)
    
    Returns:
        CoinStrategyPageV2 object for the symbol.
    """
    # 1. Determine profile_id
    if profile_id is None:
        profile_id = SILVER_15M_PROFILE_IDS.get(symbol)
        if not profile_id:
            # Generate from symbol: XYZUSDT -> XYZ_SILVER_15M_CORE_V1
            base = symbol.replace("USDT", "")
            profile_id = f"{base}_SILVER_15M_CORE_V1"
    
    # 2. Determine status
    if status is None:
        status = SILVER_15M_STATUS_OVERRIDES.get(symbol, "APPROVED")
    
    # 3. Load strategy card (v2_ml)
    strategy_card_path = _get_strategy_card_path(symbol)
    strategy_card = _load_strategy_card(strategy_card_path)
    
    # Build StrategyConfigV1 from card
    strategy_config = StrategyConfigV1(
        version=strategy_card.get("version", "v2_ml"),
        entry_filters=strategy_card.get("filters", {}),
        ml_filters=strategy_card.get("ml_filters", {}),
        exit={
            "tp_pct": strategy_card.get("risk", {}).get("tp_pct", 0.09),
            "sl_pct": strategy_card.get("risk", {}).get("sl_pct", 0.002),
            "max_horizon_bars": strategy_card.get("risk", {}).get("max_horizon_bars", 48),
        },
    )
    
    # 4. Load benchmark from War Game summary
    benchmark_v1 = None
    try:
        summary = load_silver_multi_coin_summary()
        row = _find_low_risk_row(summary, symbol, risk=0.01)
        if row:
            benchmark_v1 = StrategyBenchmarkV1(
                capital_start=row.get("capital_start", 100.0),
                capital_end=row.get("capital_end", 100.0),
                pnl_pct=row.get("pnl_pct", 0.0),
                trades=row.get("trades", 0),
            )
    except FileNotFoundError:
        print(f"[WARN] War Game summary not found for {symbol}, skipping benchmark")
    
    # 5. Build risk contract
    risk_contract_v1 = None
    try:
        summary = load_silver_multi_coin_summary()
        row = _find_low_risk_row(summary, symbol, risk=0.01)
        pnl_pct_ref = float(row.get("pnl_pct", 0.0)) if row else 0.0
        trades_ref = int(row.get("trades", 0)) if row else 0
        
        # Use status for risk contract (same as profile status)
        risk_status = status
        
        risk_contract_v1 = StrategyRiskContractV1(
            profile_kind="silver_15m",
            status=risk_status,
            max_risk_per_trade=0.01,
            source="silver_15m_multi_coin_v1",
            notes="v1 uniform 1% risk cap; SOL marked experimental due to extreme PnL; coin-level tuning TBD",
            reference={
                "risk_ref": 0.01,
                "pnl_pct_ref": pnl_pct_ref,
                "trades_ref": trades_ref,
            },
        )
    except FileNotFoundError:
        print(f"[WARN] War Game summary not found for {symbol}, using default risk contract")
        risk_contract_v1 = StrategyRiskContractV1(
            profile_kind="silver_15m",
            status=status,
            max_risk_per_trade=0.01,
            source="default",
            notes="Default 1% risk cap",
            reference={},
        )
    
    # 6. Build profile
    profile = MatrixStrategyProfileV2(
        profile_id=profile_id,
        kind=kind,
        status=status,
        strategy=strategy_config,
        benchmark_v1=benchmark_v1,
        risk_contract_v1=risk_contract_v1,
        runtime_mode=StrategyRuntimeMode(enabled=True),
    )
    
    # 7. Build page
    page = CoinStrategyPageV2(
        version="matrix_coin_page_v2",
        symbol=symbol,
        timeframes={
            "15m": TimeframeStrategiesV2(
                tf="15m",
                profiles={
                    profile_id: profile,
                },
            ),
        },
    )
    
    return page


def save_silver_15m_coin_page_v2_for_symbol(symbol: str) -> None:
    """
    Build and save matrix_coin_page_v2.json for a symbol's Silver 15m strategy.
    """
    print(f"\n=== Building {symbol} CoinPage V2 ===")
    
    page = build_silver_15m_coin_page_v2_for_symbol(symbol)
    page_dict = _page_to_dict(page)
    
    # Save to file
    output_path = _get_coin_page_v2_path(symbol)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(page_dict, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] Created: {output_path}")
    print(f"[OK] Symbol: {page.symbol}")
    
    for tf_key, tf_strategies in page.timeframes.items():
        for pid, profile in tf_strategies.profiles.items():
            print(f"[OK] Profile: {pid} (status={profile.status})")
            if profile.benchmark_v1:
                print(f"     Benchmark: PnL={profile.benchmark_v1.pnl_pct}%, trades={profile.benchmark_v1.trades}")
            if profile.risk_contract_v1:
                print(f"     Risk: max_risk={profile.risk_contract_v1.max_risk_per_trade}")


def build_silver_15m_coin_pages_v2_for_all() -> None:
    """
    Build matrix_coin_page_v2.json for all Silver 15m symbols:
    - BTCUSDT (APPROVED)
    - ETHUSDT (APPROVED)
    - SOLUSDT (EXPERIMENTAL)
    """
    print("=" * 60)
    print("Building Silver 15m CoinPage V2 for all symbols")
    print("=" * 60)
    
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    
    for symbol in symbols:
        try:
            save_silver_15m_coin_page_v2_for_symbol(symbol)
        except FileNotFoundError as e:
            print(f"[ERROR] {symbol}: {e}")
    
    print("\n" + "=" * 60)
    print(f"Done! Created {len(symbols)} CoinPage V2 files.")
    print("=" * 60)


# =============================================================================
# SNIPER 15M PROFILE BUILDER
# =============================================================================

SNIPER_15M_PROFILE_IDS = {
    "BTCUSDT": "BTC_SNIPER_15M_CORE_V1",
    "ETHUSDT": "ETH_SNIPER_15M_CORE_V1",
    "SOLUSDT": "SOL_SNIPER_15M_CORE_V1",
}


def _get_sniper_strategy_card_path(symbol: str, timeframe: str = "15m") -> Path:
    """Get sniper strategy card path for a symbol."""
    return Path(f"data/coin_profiles/{symbol}/{timeframe}/sniper_strategy_card_v1.json")


def build_sniper_15m_profile_v2_for_symbol(
    symbol: str,
    timeframe: str = "15m",
) -> MatrixStrategyProfileV2:
    """
    Build MatrixStrategyProfileV2 for Sniper 15m strategy.
    
    Reads:
    - Sniper strategy card: data/coin_profiles/{symbol}/{tf}/sniper_strategy_card_v1.json
    - Sniper backtest: run_sniper_backtest_for_symbol_timeframe()
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        timeframe: Timeframe (default: "15m")
        
    Returns:
        MatrixStrategyProfileV2 for Sniper strategy.
    """
    symbol = symbol.upper()
    
    # 1. Profile ID
    profile_id = SNIPER_15M_PROFILE_IDS.get(
        symbol, 
        f"{symbol.replace('USDT', '')}_SNIPER_{timeframe.upper()}_CORE_V1"
    )
    
    # 2. Load sniper strategy card
    card_path = _get_sniper_strategy_card_path(symbol, timeframe)
    if not card_path.exists():
        raise FileNotFoundError(f"Sniper strategy card not found: {card_path}")
    
    with card_path.open("r", encoding="utf-8") as f:
        sniper_card = json.load(f)
    
    # 3. Build StrategyConfigV1 from sniper card
    strategy_config = StrategyConfigV1(
        version=sniper_card.get("version", "sniper_v1"),
        entry_filters=sniper_card.get("entry_filters", sniper_card.get("filters", {})),
        ml_filters=sniper_card.get("ml_filters", {}),
        exit={
            "tp_pct": sniper_card.get("exit", {}).get("tp_pct", 0.08),
            "sl_pct": sniper_card.get("exit", {}).get("sl_pct", 0.03),
            "max_horizon_bars": sniper_card.get("exit", {}).get("max_horizon_bars", 50),
        },
    )
    
    # 4. Run sniper backtest for benchmark
    benchmark_v1 = None
    try:
        from tezaver.sniper.sniper_backtest import run_sniper_backtest_for_symbol_timeframe
        
        result = run_sniper_backtest_for_symbol_timeframe(
            symbol=symbol,
            timeframe=timeframe,
            risk_per_trade=1.0,  # Full equity for benchmark
        )
        
        benchmark_v1 = StrategyBenchmarkV1(
            capital_start=result["capital_start"],
            capital_end=result["capital_end"],
            pnl_pct=result["pnl_pct"],
            trades=result["trade_count"],
        )
    except FileNotFoundError:
        print(f"[WARN] Sniper entries not found for {symbol} {timeframe}, skipping benchmark")
    except Exception as e:
        print(f"[WARN] Sniper backtest failed for {symbol}: {e}")
    
    # 5. Build risk contract (EXPERIMENTAL, 0.01 max risk)
    risk_contract_v1 = StrategyRiskContractV1(
        profile_kind="sniper_15m",
        status="EXPERIMENTAL",
        max_risk_per_trade=0.01,
        source="sniper_risk_contract_v1",
        notes="Initial sniper risk contract v1; EXPERIMENTAL status until calibration.",
        reference={},
    )
    
    # 6. Build profile
    profile = MatrixStrategyProfileV2(
        profile_id=profile_id,
        kind="sniper_15m_core",
        status="EXPERIMENTAL",
        strategy=strategy_config,
        benchmark_v1=benchmark_v1,
        risk_contract_v1=risk_contract_v1,
        runtime_mode=StrategyRuntimeMode(enabled=True),  # Enable for WarGame
    )
    
    return profile


def add_sniper_15m_profile_to_coin_page_v2(symbol: str, timeframe: str = "15m") -> None:
    """
    Add Sniper 15m profile to existing matrix_coin_page_v2.json.
    
    If page exists, merges sniper profile into 15m timeframe.
    If page doesn't exist, creates new page with sniper profile.
    """
    symbol = symbol.upper()
    page_path = _get_coin_page_v2_path(symbol)
    
    print(f"\n=== Adding Sniper 15m profile to {symbol} CoinPage V2 ===")
    
    # 1. Build sniper profile
    sniper_profile = build_sniper_15m_profile_v2_for_symbol(symbol, timeframe)
    print(f"[OK] Built sniper profile: {sniper_profile.profile_id}")
    
    # 2. Load or create page
    if page_path.exists():
        with page_path.open("r", encoding="utf-8") as f:
            page_dict = json.load(f)
        print(f"[OK] Loaded existing CoinPage V2: {page_path}")
    else:
        # Create new page
        page_dict = {
            "version": "matrix_coin_page_v2",
            "symbol": symbol,
            "timeframes": {},
        }
        print(f"[INFO] Creating new CoinPage V2 for {symbol}")
    
    # 3. Ensure timeframe exists
    if timeframe not in page_dict.get("timeframes", {}):
        page_dict["timeframes"][timeframe] = {
            "tf": timeframe,
            "profiles": {},
        }
    
    # 4. Add sniper profile (convert to dict)
    sniper_profile_dict = _profile_to_dict(sniper_profile)
    page_dict["timeframes"][timeframe]["profiles"][sniper_profile.profile_id] = sniper_profile_dict
    
    # 5. Save
    page_path.parent.mkdir(parents=True, exist_ok=True)
    with page_path.open("w", encoding="utf-8") as f:
        json.dump(page_dict, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] Saved: {page_path}")
    print(f"[OK] Added profile: {sniper_profile.profile_id} (status={sniper_profile.status})")
    if sniper_profile.benchmark_v1:
        print(f"     Benchmark: PnL={sniper_profile.benchmark_v1.pnl_pct:.2f}%, trades={sniper_profile.benchmark_v1.trades}")
    if sniper_profile.risk_contract_v1:
        print(f"     Risk: max_risk={sniper_profile.risk_contract_v1.max_risk_per_trade}")


def build_sniper_15m_coin_pages_v2_for_all() -> None:
    """
    Add Sniper 15m profiles to CoinPage V2 for BTC/ETH/SOL.
    """
    print("=" * 60)
    print("Adding Sniper 15m profiles to CoinPage V2")
    print("=" * 60)
    
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    
    for symbol in symbols:
        try:
            add_sniper_15m_profile_to_coin_page_v2(symbol, "15m")
        except FileNotFoundError as e:
            print(f"[ERROR] {symbol}: {e}")
        except Exception as e:
            print(f"[ERROR] {symbol}: {e}")
    
    print("\n" + "=" * 60)
    print(f"Done! Added Sniper profiles to {len(symbols)} CoinPage V2 files.")
    print("=" * 60)


# =============================================================================
# CLI
# =============================================================================


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "build_btc_coin_page_v2":
            save_btc_silver_15m_coin_page_v2()
            sys.exit(0)
        
        elif cmd == "build_silver_15m_coin_pages_v2":
            build_silver_15m_coin_pages_v2_for_all()
            sys.exit(0)
        
        elif cmd == "build_coin_page_v2":
            # Build for specific symbol
            if len(sys.argv) < 3:
                print("Usage: build_coin_page_v2 <SYMBOL>")
                print("Example: build_coin_page_v2 ETHUSDT")
                sys.exit(1)
            symbol = sys.argv[2].upper()
            save_silver_15m_coin_page_v2_for_symbol(symbol)
            sys.exit(0)
        
        elif cmd == "build_sniper_15m_coin_pages_v2":
            build_sniper_15m_coin_pages_v2_for_all()
            sys.exit(0)
        
        elif cmd == "add_sniper_profile":
            # Add sniper to specific symbol
            if len(sys.argv) < 3:
                print("Usage: add_sniper_profile <SYMBOL>")
                print("Example: add_sniper_profile BTCUSDT")
                sys.exit(1)
            symbol = sys.argv[2].upper()
            add_sniper_15m_profile_to_coin_page_v2(symbol)
            sys.exit(0)
        
        else:
            print(f"Unknown command: {cmd}")
            print("Available commands:")
            print("  build_btc_coin_page_v2             - Build BTCUSDT matrix_coin_page_v2.json")
            print("  build_silver_15m_coin_pages_v2     - Build all 3 coins (BTC, ETH, SOL) Silver")
            print("  build_coin_page_v2 <SYMBOL>        - Build Silver for specific symbol")
            print("  build_sniper_15m_coin_pages_v2     - Add Sniper profiles to all 3 coins")
            print("  add_sniper_profile <SYMBOL>        - Add Sniper to specific symbol")
            sys.exit(1)
    
    # Default: run legacy enrichment
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
