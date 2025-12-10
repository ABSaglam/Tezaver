# Matrix V2 Wargame Runner
"""
Main entry point for running wargame simulations.
"""

from datetime import datetime
from pathlib import Path
import uuid
import json
from typing import Any, Dict

from .scenarios import (
    WargameScenario,
    build_btc_silver_15m_patterns_scenario,
    build_silver_15m_patterns_scenario,
)
from .reports import WargameReport, compute_max_drawdown_pct
from .replay_datafeed import ReplayDataFeed
from .wargame_account_store import WargameAccountStore
from .sim_executor import SimExecutor
from ..core.engine import UnifiedEngine, IAnalyzer, IStrategist, IExecutor
from ..core.types import MarketSignal, TradeDecision, ExecutionReport
from ..core.account import AccountState
from ..core.guardrail import GuardrailController, GuardrailConfig
from ..core.profile import MatrixProfileRepository
from ..strategies.silver_core import (
    SilverStrategyConfig,
    SilverAnalyzer,
    SilverStrategist,
    load_silver_strategy_config_from_card,
)


# Dummy components for non-Silver profiles
class DummyAnalyzer:
    """Dummy analyzer that generates no-op signals."""
    
    def analyze(self, market_snapshot: dict) -> list[MarketSignal]:
        """Return a single NOOP signal for testing."""
        return [
            MarketSignal(
                signal_id=str(uuid.uuid4()),
                symbol=market_snapshot.get("symbol", "UNKNOWN"),
                timeframe=market_snapshot.get("timeframe", "15m"),
                signal_type="NOOP",
                direction="neutral",
                confidence=0.0,
                timestamp=datetime.now(),
                metadata={"source": "DummyAnalyzer"},
            )
        ]


class DummyStrategist:
    """Dummy strategist that never trades."""
    
    def evaluate(self, signal: MarketSignal, account: AccountState) -> TradeDecision | None:
        """Always return None (no trade)."""
        return None


class DummyExecutor:
    """Dummy executor that simulates successful execution (no PnL)."""
    
    def execute(
        self,
        decision: TradeDecision,
        account: AccountState,
        market_snapshot: dict | None = None,
    ) -> ExecutionReport:
        """Return a successful execution report."""
        return ExecutionReport(
            execution_id=str(uuid.uuid4()),
            decision_id=decision.decision_id,
            symbol=decision.symbol,
            status="filled",
            executed_price=decision.entry_price,
            executed_quantity=decision.position_size,
            commission=0.0,
            timestamp=datetime.now(),
            error_message=None,
            metadata={"source": "DummyExecutor"},
        )


def _create_silver_components(
    profile_id: str,
    symbol: str,
    timeframe: str,
    strategy_card_path: str | None,
    risk_per_trade_pct: float = 1.0,
    max_risk_per_trade: float | None = None,  # Risk cap from contract (0.01 = 1%)
) -> tuple[IAnalyzer, IStrategist]:
    """
    Create SilverAnalyzer and SilverStrategist for a Silver profile.
    
    If strategy card doesn't exist, creates a default config.
    
    Args:
        profile_id: Profile ID.
        symbol: Trading symbol.
        timeframe: Timeframe.
        strategy_card_path: Path to strategy card JSON.
        risk_per_trade_pct: Risk percentage per trade (1.0 = 1%, 100.0 = 100%).
        max_risk_per_trade: Risk cap from risk_contract_v1 (0.01 = 1%), None = no cap.
    """
    if strategy_card_path and Path(strategy_card_path).exists():
        silver_cfg = load_silver_strategy_config_from_card(
            Path(strategy_card_path),
            symbol,
            timeframe,
        )
        # Apply risk contract cap
        silver_cfg.max_risk_per_trade = max_risk_per_trade
    else:
        # Default config for testing
        silver_cfg = SilverStrategyConfig(
            symbol=symbol,
            timeframe=timeframe,
            rsi_range=(15.0, 35.0),
            volume_rel_range=(1.5, 3.0),
            atr_pct_range=(0.5, 2.0),
            min_quality_score=50.0,
            tp_pct=0.09,
            sl_pct=0.02,
            max_horizon_bars=48,
            max_risk_per_trade=max_risk_per_trade,
            metadata={"source": "default"},
        )
    
    analyzer = SilverAnalyzer(silver_cfg)
    strategist = SilverStrategist(silver_cfg, risk_per_trade_pct=risk_per_trade_pct)
    
    return analyzer, strategist


def run_wargame(
    scenario: WargameScenario,
    coin_page_root: Path | None = None,
) -> WargameReport:
    """
    Run a wargame simulation for the given scenario.
    
    Args:
        scenario: WargameScenario defining simulation parameters.
        coin_page_root: Optional root path for coin pages (for profile loading).
        
    Returns:
        WargameReport with simulation results.
    """
    # Step 1: Create replay datafeed
    feed = ReplayDataFeed.from_dummy_data(scenario.symbol, scenario.timeframe)
    
    # Step 2: Create account store with initial capital
    store = WargameAccountStore(initial_capital=scenario.initial_capital)
    
    # Step 3: Determine analyzer and strategist based on profile
    analyzer: IAnalyzer
    strategist: IStrategist
    
    is_silver_profile = "SILVER" in scenario.profile_id.upper()
    
    if is_silver_profile:
        strategy_card_path = None
        if coin_page_root:
            try:
                repo = MatrixProfileRepository(coin_page_root)
                profile = repo.get_profile(scenario.profile_id)
                if profile:
                    strategy_card_path = profile.strategy_card_path
            except Exception:
                pass
        
        analyzer, strategist = _create_silver_components(
            scenario.profile_id,
            scenario.symbol,
            scenario.timeframe,
            strategy_card_path,
        )
    else:
        analyzer = DummyAnalyzer()
        strategist = DummyStrategist()
    
    # Step 4: Create executor (dummy for basic run)
    executor = DummyExecutor()
    
    # Step 5: Create guardrail
    guardrail = GuardrailController(
        GuardrailConfig(
            max_open_positions=5,
            max_daily_loss_pct=10.0,
            min_affinity_score=None,
        )
    )
    
    # Step 6: Create UnifiedEngine
    engine = UnifiedEngine(
        profile_id=scenario.profile_id,
        analyzer=analyzer,
        strategist=strategist,
        executor=executor,
        guardrail=guardrail,
        account_store=store,
    )
    
    # Step 7: Run tick loop
    tick_count = 0
    all_events = []
    
    while True:
        bar = feed.get_next_bar(scenario.symbol, scenario.timeframe)
        if bar is None:
            break
        
        bar["symbol"] = scenario.symbol
        bar["timeframe"] = scenario.timeframe
        
        events = engine.tick(bar)
        all_events.extend(events)
        tick_count += 1
    
    # Step 8: Generate report with equity curve and drawdown
    final_state = store.load_account(scenario.profile_id)
    equity_curve = store.get_equity_history()
    max_dd_pct = compute_max_drawdown_pct(equity_curve)
    
    return WargameReport(
        scenario_id=scenario.scenario_id,
        profile_id=scenario.profile_id,
        capital_start=scenario.initial_capital,
        capital_end=final_state.capital,
        trade_count=final_state.trade_count,
        win_rate=0.0,
        max_drawdown=0.0,
        equity_curve=equity_curve,
        max_drawdown_pct=max_dd_pct,
    )


def run_btc_silver_15m_from_patterns(
    parquet_path: Path | None = None,
) -> WargameReport:
    """
    BTCUSDT Silver 15m core profili için:
    - rally_patterns_v1.parquet üzerinden snapshot replay yapar
    - SilverAnalyzer ve SilverStrategist kullanır
    - SimExecutor ile gerçek PnL hesaplar (future_max_gain_pct ile)
    - WargameReport döner (100 → X formatı)
    
    Args:
        parquet_path: Optional path to parquet file.
        
    Returns:
        WargameReport with simulation results.
    """
    # Create scenario
    scenario = build_btc_silver_15m_patterns_scenario()
    
    # Load real pattern data
    feed = ReplayDataFeed.from_btc_15m_silver_patterns(parquet_path)
    
    # Create account store
    store = WargameAccountStore(initial_capital=scenario.initial_capital)
    
    # Create Silver components with default config
    # risk_per_trade_pct: 0.01 = 1% of capital
    risk_pct_for_strategist = scenario.risk_per_trade_pct * 100.0  # Convert to % format
    analyzer, strategist = _create_silver_components(
        scenario.profile_id,
        scenario.symbol,
        scenario.timeframe,
        None,  # No strategy card, use defaults
        risk_per_trade_pct=risk_pct_for_strategist,
    )
    
    # Create SimExecutor for real PnL calculation
    executor = SimExecutor(account_store=store)
    
    # Create guardrail
    guardrail = GuardrailController(
        GuardrailConfig(
            max_open_positions=5,
            max_daily_loss_pct=10.0,
            min_affinity_score=None,
        )
    )
    
    # Create engine
    engine = UnifiedEngine(
        profile_id=scenario.profile_id,
        analyzer=analyzer,
        strategist=strategist,
        executor=executor,
        guardrail=guardrail,
        account_store=store,
    )
    
    # Run tick loop
    signal_count = 0
    decision_count = 0
    
    while feed.has_next():
        snapshot = feed.next()
        if snapshot is None:
            break
        
        events = engine.tick(snapshot)
        
        # Count events
        for e in events:
            if e.event_type == "SIGNAL" and "SILVER" in str(e.payload.get("signal_type", "")):
                signal_count += 1
            if e.event_type == "DECISION":
                decision_count += 1
    
    # Generate report with equity curve and drawdown
    ledger = store.get_ledger()
    trade_count = len([e for e in ledger if e.get("event_type") == "TRADE"])
    equity_curve = store.get_equity_history()
    max_dd_pct = compute_max_drawdown_pct(equity_curve)
    
    # Calculate win rate
    wins = sum(1 for e in ledger if e.get("event_type") == "TRADE" and e.get("pnl", 0) > 0)
    win_rate = wins / trade_count if trade_count > 0 else 0.0
    
    report = WargameReport(
        scenario_id=scenario.scenario_id,
        profile_id=scenario.profile_id,
        capital_start=scenario.initial_capital,
        capital_end=store.get_equity(),
        trade_count=trade_count,
        win_rate=win_rate,
        max_drawdown=abs(max_dd_pct),  # Keep old field for compat
        equity_curve=equity_curve,
        max_drawdown_pct=max_dd_pct,
        events=ledger,
    )
    
    return report


def _run_wargame_with_scenario_and_feed(
    scenario: WargameScenario,
    feed: ReplayDataFeed,
) -> WargameReport:
    """
    Internal helper to run wargame with given scenario and feed.
    
    Args:
        scenario: WargameScenario with risk_per_trade_pct.
        feed: ReplayDataFeed to iterate over.
        
    Returns:
        WargameReport with results.
    """
    # Create account store
    store = WargameAccountStore(initial_capital=scenario.initial_capital)
    
    # Create Silver components
    # risk_per_trade_pct: 0.01 = 1% of capital → convert to percentage
    risk_pct_for_strategist = scenario.risk_per_trade_pct * 100.0
    
    # Get max_risk from scenario (if set by contract mode)
    max_risk_from_contract = scenario.max_risk_per_trade if scenario.mode == "contract" else None
    
    analyzer, strategist = _create_silver_components(
        scenario.profile_id,
        scenario.symbol,
        scenario.timeframe,
        None,  # No strategy card, use defaults
        risk_per_trade_pct=risk_pct_for_strategist,
        max_risk_per_trade=max_risk_from_contract,
    )
    
    # Create SimExecutor for real PnL calculation
    executor = SimExecutor(account_store=store)
    
    # Create guardrail
    guardrail = GuardrailController(
        GuardrailConfig(
            max_open_positions=5,
            max_daily_loss_pct=10.0,
            min_affinity_score=None,
        )
    )
    
    # Create engine
    engine = UnifiedEngine(
        profile_id=scenario.profile_id,
        analyzer=analyzer,
        strategist=strategist,
        executor=executor,
        guardrail=guardrail,
        account_store=store,
    )
    
    # Run tick loop
    while feed.has_next():
        snapshot = feed.next()
        if snapshot is None:
            break
        engine.tick(snapshot)
    
    # Generate report
    ledger = store.get_ledger()
    trade_count = len([e for e in ledger if e.get("event_type") == "TRADE"])
    equity_curve = store.get_equity_history()
    max_dd_pct = compute_max_drawdown_pct(equity_curve)
    
    wins = sum(1 for e in ledger if e.get("event_type") == "TRADE" and e.get("pnl", 0) > 0)
    win_rate = wins / trade_count if trade_count > 0 else 0.0
    
    return WargameReport(
        scenario_id=scenario.scenario_id,
        profile_id=scenario.profile_id,
        capital_start=scenario.initial_capital,
        capital_end=store.get_equity(),
        trade_count=trade_count,
        win_rate=win_rate,
        max_drawdown=abs(max_dd_pct),
        equity_curve=equity_curve,
        max_drawdown_pct=max_dd_pct,
        events=ledger,
    )


def run_btc_silver_15m_risk_sweep() -> list[dict]:
    """
    BTC Silver 15m stratejisi için farklı risk seviyelerinde
    War Game sonuçlarını karşılaştırır.

    Risk profilleri:
    - 0.01 (%1)
    - 0.05 (%5)
    - 0.10 (%10)
    - 1.0  (%100 - full risk)
    
    Returns:
        List of result dicts with risk, capital, pnl, max_dd, trades.
    """
    results: list[dict] = []
    risk_profiles = [0.01, 0.05, 0.10, 1.0]

    for rp in risk_profiles:
        scenario = build_btc_silver_15m_patterns_scenario(
            risk_per_trade_pct=rp
        )
        feed = ReplayDataFeed.from_btc_15m_silver_patterns()
        report = _run_wargame_with_scenario_and_feed(scenario, feed)

        pnl_pct = (report.capital_end / report.capital_start - 1.0) * 100.0

        results.append(
            {
                "risk_per_trade_pct": rp,
                "capital_start": report.capital_start,
                "capital_end": report.capital_end,
                "pnl_pct": pnl_pct,
                "trade_count": report.trade_count,
                "max_dd_pct": report.max_drawdown_pct * 100.0,
            }
        )

    # Console output
    print("=== BTC Silver 15m – Risk Sweep ===")
    print()
    print("Risk\tCapital(100→X)\tPnL%\tMaxDD%\tTrades")
    for item in results:
        rp = item["risk_per_trade_pct"]
        cs = item["capital_start"]
        ce = item["capital_end"]
        pnl = item["pnl_pct"]
        dd = item["max_dd_pct"]
        tc = item["trade_count"]
        print(f"{rp:.2f}\t{cs:.2f}→{ce:.2f}\t{pnl:+6.2f}%\t{dd:6.2f}%\t{tc}")

    return results


def run_silver_15m_from_patterns_for_symbol(
    symbol: str,
    risk_per_trade_pct: float = 0.01,
    mode: str = "contract",  # "contract" = enforce cap, "experiment" = bypass cap
) -> WargameReport:
    """
    Generic Silver 15m runner for any symbol.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT", "SOLUSDT").
        risk_per_trade_pct: Risk per trade (0.01 = 1%, 1.0 = 100%).
        mode: "contract" = enforce risk_contract_v1 cap, "experiment" = bypass cap.
        
    Returns:
        WargameReport with simulation results.
        
    Raises:
        FileNotFoundError: If pattern dataset doesn't exist for the symbol.
    """
    scenario = build_silver_15m_patterns_scenario(symbol, risk_per_trade_pct)
    scenario.mode = mode
    
    # Load risk contract from profile if in contract mode
    max_risk: float | None = None
    if mode == "contract":
        max_risk = _load_risk_contract_max_for_profile(scenario.profile_id)
        scenario.max_risk_per_trade = max_risk
    
    feed = ReplayDataFeed.from_symbol_timeframe_silver_patterns(symbol, "15m")
    return _run_wargame_with_scenario_and_feed(scenario, feed)


def _load_risk_contract_max_for_profile(profile_id: str) -> float | None:
    """
    Load max_risk_per_trade from risk_contract_v1 for a profile.
    
    Args:
        profile_id: e.g., "BTC_SILVER_15M_CORE_V1"
        
    Returns:
        max_risk_per_trade from contract, or None if not found.
    """
    # Load from candidate profiles JSON
    profiles_path = Path("data/coin_profiles/BTCUSDT/matrix_candidate_profiles_v1.json")
    if not profiles_path.exists():
        return None
    
    try:
        with profiles_path.open("r", encoding="utf-8") as f:
            profiles = json.load(f)
        
        if isinstance(profiles, list):
            for profile in profiles:
                if profile.get("profile_id") == profile_id:
                    rc = profile.get("risk_contract_v1")
                    if isinstance(rc, dict):
                        return rc.get("max_risk_per_trade")
    except Exception:
        pass
    
    return None


def run_silver_15m_multi_coin_risk_sweep() -> list[dict]:
    """
    Multi-coin Silver 15m risk sweep across BTC, ETH, SOL.
    
    For each symbol and risk level, runs War Game and reports results.
    Skips symbols that don't have pattern datasets.
    
    Returns:
        List of result dicts with symbol, risk, capital, pnl, max_dd, trades.
    """
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    risk_profiles = [0.01, 0.05, 0.10, 1.0]
    results: list[dict] = []

    print("=== Silver 15m – Multi-Coin Risk Sweep (100 → X) ===")
    print()
    print(f"{'Coin':<10} {'Risk':>6} {'Cap(100→X)':>14} {'PnL%':>8} {'MaxDD%':>8} {'Trades':>8}")

    for symbol in symbols:
        for risk in risk_profiles:
            try:
                # Use experiment mode to bypass risk contract cap for sweep
                report = run_silver_15m_from_patterns_for_symbol(symbol, risk, mode="experiment")
                
                pnl_pct = (report.capital_end / report.capital_start - 1.0) * 100.0
                max_dd_pct = report.max_drawdown_pct * 100.0
                
                result = {
                    "symbol": symbol,
                    "risk_per_trade_pct": risk,
                    "capital_start": report.capital_start,
                    "capital_end": report.capital_end,
                    "pnl_pct": pnl_pct,
                    "trade_count": report.trade_count,
                    "max_dd_pct": max_dd_pct,
                }
                results.append(result)
                
                print(
                    f"{symbol:<10} {risk:>6.2f} "
                    f"{report.capital_start:>6.2f}→{report.capital_end:>6.2f} "
                    f"{pnl_pct:>+7.2f}% {max_dd_pct:>7.2f}% {report.trade_count:>8d}"
                )
            except FileNotFoundError:
                # Skip symbols without pattern datasets
                if risk == risk_profiles[0]:  # Only print once per symbol
                    print(f"{symbol:<10} [SKIP] No pattern dataset found")
                continue

    return results


# =============================================================================
# SILVER 15M MULTI-COIN SUMMARY JSON
# =============================================================================

SILVER_MULTI_COIN_SUMMARY_PATH = Path(
    "data/ai_insights/global/silver_15m_multi_coin_wargame_v1.json"
)


def build_silver_15m_multi_coin_risk_summary() -> Dict[str, Any]:
    """
    Pure computation of Silver 15m multi-coin risk sweep.
    Returns JSON-friendly dict without any I/O or printing.
    
    Risk levels: 0.01 (1%) and 1.0 (100%) for summary.
    Coins: BTCUSDT, ETHUSDT, SOLUSDT.
    
    Returns:
        Dict with version and coins array.
    """
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    risk_profiles = [0.01, 1.0]  # Summary uses only low and full risk
    coins: list[Dict[str, Any]] = []
    
    for symbol in symbols:
        for risk in risk_profiles:
            try:
                report = run_silver_15m_from_patterns_for_symbol(symbol, risk)
                
                pnl_pct = (report.capital_end / report.capital_start - 1.0) * 100.0
                max_dd_pct = report.max_drawdown_pct * 100.0
                
                coins.append({
                    "symbol": symbol,
                    "risk": risk,
                    "capital_start": round(report.capital_start, 2),
                    "capital_end": round(report.capital_end, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "max_dd_pct": round(max_dd_pct, 2),
                    "trades": report.trade_count,
                })
            except FileNotFoundError:
                # Skip symbols without pattern datasets
                pass
    
    return {
        "version": "silver_15m_multi_coin_v1",
        "coins": coins,
    }


def save_silver_15m_multi_coin_risk_summary_to_json(
    summary: Dict[str, Any] | None = None,
) -> Path:
    """
    Save Silver 15m multi-coin summary to JSON file.
    
    Args:
        summary: Pre-computed summary dict. If None, computes it.
        
    Returns:
        Path to saved JSON file.
    """
    if summary is None:
        summary = build_silver_15m_multi_coin_risk_summary()
    
    SILVER_MULTI_COIN_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with SILVER_MULTI_COIN_SUMMARY_PATH.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    return SILVER_MULTI_COIN_SUMMARY_PATH


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "single"

    if mode == "risk_sweep":
        try:
            run_btc_silver_15m_risk_sweep()
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print("Make sure rally_patterns_v1.parquet exists in data/ai_datasets/BTCUSDT/15m/")
    
    elif mode == "multi_silver_15m":
        run_silver_15m_multi_coin_risk_sweep()
    
    elif mode == "multi_silver_15m_save":
        print("Building Silver 15m multi-coin risk summary...")
        summary = build_silver_15m_multi_coin_risk_summary()
        path = save_silver_15m_multi_coin_risk_summary_to_json(summary)
        print(f"[OK] Silver 15m multi-coin summary saved to: {path}")
        print()
        print("Summary:")
        for coin in summary.get("coins", []):
            print(
                f"  {coin['symbol']:<10} risk={coin['risk']:.2f}  "
                f"100→{coin['capital_end']:.2f}  "
                f"PnL={coin['pnl_pct']:+.2f}%  "
                f"Trades={coin['trades']}"
            )
    
    else:
        print("=== BTC Silver 15m – War Game (rally_patterns_v1) ===")
        print()
        
        try:
            report = run_btc_silver_15m_from_patterns()
            print(f"Scenario : {report.scenario_id}")
            print(f"Profile  : {report.profile_id}")
            print(f"Capital  : {report.capital_start:.2f} → {report.capital_end:.2f}")
            pnl_pct = (report.capital_end / report.capital_start - 1.0) * 100.0
            print(f"PnL      : {pnl_pct:+.2f}%")
            print(f"Trades   : {report.trade_count}")
            print(f"Win Rate : {report.win_rate:.1%}")
            print(f"Max DD   : {report.max_drawdown_pct * 100:.2f}%")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print("Make sure rally_patterns_v1.parquet exists in data/ai_datasets/BTCUSDT/15m/")



