# Matrix V2 Live Cluster
"""
Live trading cluster management.

Orchestrates multiple coin/timeframe/profile cells for LIVE trading.
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Any, List
from pathlib import Path

from tezaver.matrix.core.engine import UnifiedEngine
from tezaver.matrix.core.guardrail import GuardrailController, GuardrailConfig
from tezaver.matrix.core.profile import MatrixProfileRepository, MatrixCellProfile
from tezaver.matrix.live.live_config import MatrixLiveConfig, LiveStrategyCellConfig
from tezaver.matrix.live.live_account_store import LiveAccountStore
from tezaver.matrix.strategies.silver_core import (
    SilverAnalyzer,
    SilverStrategist,
    SilverStrategyConfig,
    load_silver_strategy_config_from_profile,
)
from tezaver.matrix.wargame.sim_executor import SimExecutor


# =============================================================================
# Live Trading Gates
# =============================================================================

def live_can_trade(
    symbol: str,
    timeframe: str,
    profile_id: str,
    profile_status: str,
    selection_mode: str = "ARENA_FILTERS",
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if LIVE trading is allowed for given cell.
    
    Gates:
    1. Profile Status Gate: APPROVED required
    2. Risk Contract Gate: max_risk clamp returned
    3. Strict Quality Contract Gate: Sniper STRICT contract check
    
    Returns:
        (allow: bool, details: dict) - allow=False means no trade execution
    """
    details = {
        "profile_id": profile_id,
        "profile_status": profile_status,
        "selection_mode": selection_mode,
        "contract_gate": "NA",  # PASS/WARN/BLOCK/NA
        "gates": {
            "profile_status": {"passed": False, "reason": None},
            "risk_contract": {"passed": True, "max_risk_pct": 1.0},
            "strict_contract": {"passed": True, "gate": "NA", "reason": None},
        },
        "violations": [],
        "metrics": {},
    }
    
    allow = True
    
    # Gate 1: Profile Status (APPROVED required)
    if profile_status != "APPROVED":
        details["gates"]["profile_status"]["passed"] = False
        details["gates"]["profile_status"]["reason"] = f"status={profile_status}, required=APPROVED"
        details["violations"].append({"code": "PROFILE_NOT_APPROVED", "actual": profile_status, "expected": "APPROVED"})
        allow = False
    else:
        details["gates"]["profile_status"]["passed"] = True
    
    # Gate 2: Risk Contract (clamp max_risk)
    details["gates"]["risk_contract"]["max_risk_pct"] = 1.0
    
    # Gate 3: Strict Quality Contract (only for Sniper + CARD_STRICT_IDS)
    if "SNIPER" in profile_id.upper() and selection_mode == "CARD_STRICT_IDS":
        try:
            from tezaver.sniper.v4.select_v4 import load_card_contract_state
            
            contract_state = load_card_contract_state(symbol, timeframe)
            
            if contract_state.get("available"):
                enforce_mode = contract_state.get("enforce_mode", "WARN")
                contract_ok = contract_state.get("ok", True)
                state_violations = contract_state.get("violations", [])
                
                # Extract metrics
                details["metrics"] = {
                    "p50": contract_state.get("distance_p50"),
                    "p90": contract_state.get("distance_p90"),
                    "strict_count": contract_state.get("strict_count"),
                    "seed_count": contract_state.get("seed_count"),
                    "auto_relax_ratio": contract_state.get("auto_relax_ratio"),
                }
                
                details["gates"]["strict_contract"]["enforce_mode"] = enforce_mode
                details["gates"]["strict_contract"]["contract_ok"] = contract_ok
                
                if contract_ok:
                    # Contract OK - PASS
                    details["contract_gate"] = "PASS"
                    details["gates"]["strict_contract"]["gate"] = "PASS"
                    details["gates"]["strict_contract"]["passed"] = True
                elif enforce_mode == "BLOCK":
                    # Contract violated + BLOCK mode - block trading
                    details["contract_gate"] = "BLOCK"
                    details["gates"]["strict_contract"]["gate"] = "BLOCK"
                    details["gates"]["strict_contract"]["passed"] = False
                    details["gates"]["strict_contract"]["reason"] = f"STRICT_CONTRACT_BLOCK"
                    details["violations"].extend(state_violations)
                    allow = False
                else:
                    # Contract violated + WARN mode - allow but warn
                    details["contract_gate"] = "WARN"
                    details["gates"]["strict_contract"]["gate"] = "WARN"
                    details["gates"]["strict_contract"]["passed"] = True  # allowed through
                    details["gates"]["strict_contract"]["warn"] = True
                    details["violations"].extend(state_violations)
            else:
                details["gates"]["strict_contract"]["error"] = contract_state.get("reason", "unavailable")
        except Exception as e:
            details["gates"]["strict_contract"]["error"] = str(e)
    else:
        details["contract_gate"] = "NA"
        details["gates"]["strict_contract"]["gate"] = "NA"

    
    return allow, details


@dataclass
class LiveCellRuntime:
    """Runtime state for a single live cell."""
    config: LiveStrategyCellConfig
    profile: MatrixCellProfile
    strategy_config: SilverStrategyConfig
    account_store: LiveAccountStore
    engine: UnifiedEngine


class MatrixLiveCluster:
    """
    Matrix Live cluster:
    - Birden fazla coin/timeframe/profile hücresini yönetir
    - Dışarıdan gelen market snapshot'ları tick olarak UnifiedEngine'e verir
    """

    def __init__(
        self,
        live_config: MatrixLiveConfig,
        profile_repo: MatrixProfileRepository,
        guardrail: GuardrailController,
    ) -> None:
        """
        Initialize live cluster.
        
        Args:
            live_config: MatrixLiveConfig with cells and environment.
            profile_repo: Repository for loading profiles.
            guardrail: Controller for risk management.
        """
        self._config = live_config
        self._profile_repo = profile_repo
        self._guardrail = guardrail
        self._cells: Dict[Tuple[str, str, str], LiveCellRuntime] = {}

        self._build_cells()

    def _build_cells(self) -> None:
        """
        Config'teki her hücre için:
        - CoinPage V2'den profile yükle
        - SilverStrategyConfig oluştur
        - LiveAccountStore + UnifiedEngine kur
        """
        for cell_cfg in self._config.cells:
            key = (cell_cfg.symbol, cell_cfg.timeframe, cell_cfg.profile_id)

            # Load profiles for symbol first (populates cache)
            self._profile_repo.load_profiles_for_symbol(cell_cfg.symbol)
            
            # Get profile from cache
            profile = self._profile_repo.get_profile(cell_cfg.profile_id)
            if profile is None:
                # Profile bulunamadıysa hücreyi atla
                continue

            if profile.strategy_config is None:
                # No strategy config, skip
                continue

            strategy_cfg = load_silver_strategy_config_from_profile(profile)

            # In experiment mode, relax ML filters to allow more signals (parity with War Game)
            if cell_cfg.risk_mode == "experiment":
                from tezaver.matrix.strategies.silver_core import relax_silver_filters_for_experiment
                # Use widen_factor=2.0 as default for experiment mode (same as tightness=50)
                strategy_cfg = relax_silver_filters_for_experiment(strategy_cfg, widen_factor=2.0)

            account_store = LiveAccountStore(initial_capital=self._config.initial_capital)

            analyzer = SilverAnalyzer(strategy_cfg)
            
            # SilverStrategist takes risk_per_trade_pct, not mode
            risk_pct = 1.0 if cell_cfg.risk_mode == "experiment" else 1.0
            strategist = SilverStrategist(strategy_cfg, risk_per_trade_pct=risk_pct)

            executor = SimExecutor(account_store=account_store)

            engine = UnifiedEngine(
                profile_id=cell_cfg.profile_id,
                analyzer=analyzer,
                strategist=strategist,
                executor=executor,
                guardrail=self._guardrail,
                account_store=account_store,
                symbol=cell_cfg.symbol,
                timeframe=cell_cfg.timeframe,
                environment=self._config.environment,
                profile_repo=self._profile_repo,
            )

            self._cells[key] = LiveCellRuntime(
                config=cell_cfg,
                profile=profile,
                strategy_config=strategy_cfg,
                account_store=account_store,
                engine=engine,
            )

    def list_cells(self) -> List[LiveStrategyCellConfig]:
        """Return list of cell configs in this cluster."""
        return [rt.config for rt in self._cells.values()]

    def tick(
        self,
        symbol: str,
        timeframe: str,
        market_snapshot: Dict[str, Any],
        runtime_overrides: Dict[str, Any] | None = None,
    ) -> None:
        """
        Dışarıdan gelen tek bir snapshot'ı ilgili hücreye işler.
        
        market_snapshot formatı, SilverAnalyzer'ın beklediği field'ları içermeli
        (rsi_15m, volume_rel_15m, atr_pct_15m, quality_score, vs.).
        
        runtime_overrides: Optional dict with force_dry_run etc.
        """
        key_candidates = [
            (sym, tf, pid)
            for (sym, tf, pid) in self._cells.keys()
            if sym == symbol and tf == timeframe
        ]
        if not key_candidates:
            return

        # Şimdilik aynı symbol+tf için tek profil varsayıyoruz (ilkini al)
        key = key_candidates[0]
        cell = self._cells[key]

        # Inject symbol and timeframe into snapshot
        market_snapshot["symbol"] = symbol
        market_snapshot["timeframe"] = timeframe
        
        # Apply runtime overrides
        if runtime_overrides:
            market_snapshot["_runtime_overrides"] = runtime_overrides
        
        cell.engine.tick(market_snapshot)

    def get_equity(self, symbol: str, timeframe: str, profile_id: str) -> float:
        """Get current equity for a cell."""
        key = (symbol, timeframe, profile_id)
        if key not in self._cells:
            raise KeyError(f"No live cell for {key}")
        return self._cells[key].account_store.get_equity()
    
    def get_all_equities(self) -> Dict[str, float]:
        """Get equities for all cells."""
        return {
            f"{k[0]}_{k[1]}_{k[2]}": cell.account_store.get_equity()
            for k, cell in self._cells.items()
        }


def build_live_cluster_from_profile_board(
    initial_capital: float = 100.0,
    risk_mode: str = "contract",
    root: Path | None = None,
) -> MatrixLiveCluster:
    """
    Build a MatrixLiveCluster from Strategy Board's LIVE eligible profiles.
    
    Args:
        initial_capital: Starting capital for each cell.
        risk_mode: "contract" (use risk_contract limits) or "experiment" (bypass).
        root: Optional coin profiles root override for testing.
    
    Returns:
        MatrixLiveCluster with all LIVE eligible profiles.
    """
    from tezaver.matrix.profile_board import build_profile_board
    from tezaver.matrix.core.guardrail import GuardrailEnvironment
    
    # Determine root path
    if root is None:
        cwd_root = Path.cwd() / "data" / "coin_profiles"
        if cwd_root.exists():
            root = cwd_root
        else:
            base_dir = Path(__file__).resolve().parents[3]
            root = base_dir / "data" / "coin_profiles"
    
    # Build profile board
    board_rows = build_profile_board(root=root)
    
    # Filter LIVE eligible rows
    live_rows = [r for r in board_rows if r.live_eligible]
    
    # Create cell configs
    cells: List[LiveStrategyCellConfig] = []
    for row in live_rows:
        cells.append(
            LiveStrategyCellConfig(
                symbol=row.symbol,
                timeframe=row.timeframe,
                profile_id=row.profile_id,
                risk_mode=risk_mode,
            )
        )
    
    # Create config
    config = MatrixLiveConfig(
        environment=GuardrailEnvironment.LIVE,
        initial_capital=initial_capital,
        cells=cells,
    )
    
    # Create profile repo and guardrail
    repo = MatrixProfileRepository(coin_page_root=root)
    guardrail = GuardrailController(
        GuardrailConfig(
            max_open_positions=5,
            max_daily_loss_pct=10.0,
        )
    )
    
    # Create and return cluster
    return MatrixLiveCluster(
        live_config=config,
        profile_repo=repo,
        guardrail=guardrail,
    )

