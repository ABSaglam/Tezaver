# Matrix V2 Wargame Runner
"""
Main entry point for running wargame simulations.
"""

from datetime import datetime, timezone
from pathlib import Path
import uuid
import json
from typing import Any, Dict, List, Optional, Callable
import pandas as pd

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
from ..core.telemetry import InMemoryEventSink, JsonFileEventSink, MatrixEventType, MatrixEvent
from ..strategies.silver_core import (
    SilverStrategyConfig,
    SilverAnalyzer,
    SilverStrategist,
    load_silver_strategy_config_from_card,
    load_silver_strategy_config_from_profile,
)
from tezaver.rally.rally_detector_v2 import detect_rallies_v2_micro_booster
from tezaver.snapshots.snapshot_engine import load_features


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



class RallyTelemetryAnalyzer(IAnalyzer):
    """Wraps an analyzer to emit RALLY_DETECTED events."""
    
    def __init__(self, inner: IAnalyzer, rallies_by_ts: Dict[datetime, List[Dict]], event_sink: Any, symbol: str):
        self.inner = inner
        self.rallies_by_ts = rallies_by_ts
        self.event_sink = event_sink
        self.symbol = symbol
        self.processed_ts = set()

    def analyze(self, market_snapshot: dict) -> list[MarketSignal]:
        # Check for rally at this timestamp
        # market_snapshot['timestamp'] is typically a python datetime
        ts = market_snapshot.get("timestamp")
        
        # Determine if we should emit
        # Using exact match for now. Datafeed aligns with 15m bars usually.
        if ts and ts in self.rallies_by_ts and ts not in self.processed_ts:
            for rally_data in self.rallies_by_ts[ts]:
                 # Construct robust payload
                 rally_data["bar_close_ts"] = ts.isoformat()
                 rally_data["rally_bucket"] = rally_data.get("rally_bucket", "unknown")
                 
                 evt = MatrixEvent(
                     event_type=MatrixEventType.RALLY_DETECTED,
                     ts=ts,
                     symbol=self.symbol,
                     timeframe="15m",
                     details=rally_data
                 )
                 
                 if hasattr(self.event_sink, "log"):
                     self.event_sink.log(evt)
            
            self.processed_ts.add(ts)

        return self.inner.analyze(market_snapshot)

def _create_silver_components(
    profile_id: str,
    symbol: str,
    timeframe: str,
    strategy_card_path: str | None,
    risk_per_trade_pct: float = 1.0,
    max_risk_per_trade: float | None = None,  # Risk cap from contract (0.01 = 1%)
    event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
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
        event_sink: Optional telemetry sink.
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
    
    # Pass event_sink to Analyzer (M3b)
    analyzer = SilverAnalyzer(silver_cfg, event_sink=event_sink)
    strategist = SilverStrategist(silver_cfg, risk_per_trade_pct=risk_per_trade_pct)
    
    return analyzer, strategist


def run_wargame(
    scenario: WargameScenario,
    coin_page_root: Path | None = None,
    events_path: Path | str | None = None,
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
    events_path: Path | str | None = None,
    force_close_on_exit: bool = False,
) -> WargameReport:
    """
    Internal helper to run wargame with given scenario and feed.
    
    Args:
        scenario: WargameScenario with risk_per_trade_pct.
        feed: ReplayDataFeed to iterate over.
        events_path: Optional path to write NDJSON events.
        force_close_on_exit: If True, emit PROOF_CLOSE_RESULT for open positions at end.
        
    Returns:
        WargameReport with results.
    """
    # Create account store
    store = WargameAccountStore(initial_capital=scenario.initial_capital)
    
    # Create telemetry event sink (Moved up for injection)
    event_sink = InMemoryEventSink()
    ndjson_sink = None
    if events_path:
        ndjson_sink = JsonFileEventSink(events_path)
    
    # Create wrapper sink to log to both (explicitly passed to avoid closure issues)
    class MultiSink:
        def __init__(self, memory_sink: InMemoryEventSink, file_sink: JsonFileEventSink | None):
            self.memory_sink = memory_sink
            self.file_sink = file_sink
            
        def log(self, event: MatrixEvent) -> None:
            self.memory_sink.log(event)
            if self.file_sink is not None:
                self.file_sink.log(event)
    
    multi_sink = MultiSink(event_sink, ndjson_sink)
    
    # Create adapter for SilverAnalyzer (Dict -> MatrixEvent)
    def sink_adapter(event_dict: Dict[str, Any]) -> None:
        etype_str = event_dict.get("event_type", "INFO")
        try:
            etype = MatrixEventType(etype_str)
        except ValueError:
            etype = MatrixEventType.INFO
            
        # Extract core fields if present, else default to scenario/generic
        sym = event_dict.get("symbol", scenario.symbol)
        tf = event_dict.get("timeframe", scenario.timeframe)
        prof = event_dict.get("profile_id", scenario.profile_id)
        
        # Parse TS
        ts_val = event_dict.get("ts")
        if isinstance(ts_val, str):
            try:
                ts = datetime.fromisoformat(ts_val)
            except ValueError:
                ts = datetime.now(timezone.utc)
        elif isinstance(ts_val, datetime):
            ts = ts_val
        else:
            ts = datetime.now(timezone.utc)

        # Create MatrixEvent
        evt = MatrixEvent(
            event_type=etype,
            symbol=sym,
            timeframe=tf,
            profile_id=prof,
            ts=ts,
            details=event_dict
        )
        multi_sink.log(evt)

    # Create Silver components using profile-based config from CoinPage V2
    # risk_per_trade_pct: 0.01 = 1% of capital → convert to percentage
    risk_pct_for_strategist = scenario.risk_per_trade_pct * 100.0
    
    # Get max_risk from scenario (if set by contract mode)
    max_risk_from_contract = scenario.max_risk_per_trade if scenario.mode == "contract" else None
    
    # Load profile and config from CoinPage V2 for parity with Live cluster
    # In experiment mode, use relaxed filters based on tightness setting
    use_relaxed_filters = (scenario.mode == "experiment")
    tightness = getattr(scenario, "tightness", 100.0)
    widen_factor = 100.0 / max(tightness, 1.0)  # tightness 100 → 1.0, tightness 50 → 2.0
    
    try:
        profile, strategy_cfg = _load_silver_profile_and_config(scenario.symbol, scenario.profile_id)
        
        # Override risk settings from scenario
        strategy_cfg.max_risk_per_trade = (
            max_risk_from_contract if max_risk_from_contract is not None 
            else strategy_cfg.max_risk_per_trade
        )
        
        # In experiment mode, relax filters using the helper
        if use_relaxed_filters and widen_factor > 1.0:
            from tezaver.matrix.strategies.silver_core import relax_silver_filters_for_experiment
            strategy_cfg = relax_silver_filters_for_experiment(strategy_cfg, widen_factor)
        
        # Pass sink_adapter to Analyzer
        analyzer = SilverAnalyzer(strategy_cfg, event_sink=sink_adapter)
        strategist = SilverStrategist(strategy_cfg, risk_per_trade_pct=risk_pct_for_strategist)
    except Exception:
        # Fallback to legacy behavior if profile not found
        analyzer, strategist = _create_silver_components(
            scenario.profile_id,
            scenario.symbol,
            scenario.timeframe,
            None,  # No strategy card, use defaults
            risk_per_trade_pct=risk_pct_for_strategist,
            max_risk_per_trade=max_risk_from_contract,
            event_sink=sink_adapter, # Pass sink adapter
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
    
    # Create engine with telemetry
    engine = UnifiedEngine(
        profile_id=scenario.profile_id,
        analyzer=analyzer,
        strategist=strategist,
        executor=executor,
        guardrail=guardrail,
        account_store=store,
        event_sink=multi_sink,
    )
    
    # Emit WARGAME_START
    start_event = MatrixEvent(
        event_type=MatrixEventType.INFO,
        symbol=scenario.symbol,
        timeframe=scenario.timeframe,
        profile_id=scenario.profile_id,
        ts=datetime.now(timezone.utc),
        details={"event_type": "WARGAME_START", "scenario_id": scenario.scenario_id}
    )
    multi_sink.log(start_event)

    # [RALLY TELEMETRY INJECTION]
    # Try to load rally data and wrap analyzer if possible
    # Only for 15m standard setup for now
    if feed and hasattr(feed, 'symbol') and hasattr(feed, 'timeframe') and feed.timeframe == "15m":
        try:
            target_symbol = feed.symbol
            # Use snapshot engine to load features
            df_feat = load_features(target_symbol, "15m")
            
            if not df_feat.empty:
                # Run V2 Booster (Rev 06)
                df_rallies = detect_rallies_v2_micro_booster(df_feat, deduplicate=True)
                
                if not df_rallies.empty:
                    # Index by event_time dictionary
                    rallies_by_ts = {}
                    for _, row in df_rallies.iterrows():
                        evt_ts = pd.to_datetime(row['event_time'])
                        if evt_ts.tzinfo is None:
                             evt_ts = evt_ts.replace(tzinfo=timezone.utc)
                             
                        if evt_ts not in rallies_by_ts:
                            rallies_by_ts[evt_ts] = []
                        
                        r_data = row.to_dict()
                        for k, v in r_data.items():
                            if isinstance(v, (pd.Timestamp, datetime)):
                                r_data[k] = v.isoformat()
                        
                        rallies_by_ts[evt_ts].append(r_data)
                        
                    rally_analyzer = RallyTelemetryAnalyzer(
                        inner=engine.analyzer,
                        rallies_by_ts=rallies_by_ts,
                        event_sink=multi_sink,
                        symbol=target_symbol
                    )
                    engine.analyzer = rally_analyzer
                    multi_sink.log({"event_type": "INFO", "ts": datetime.now(timezone.utc).isoformat(), "msg": f"Rally Telemetry Active: {len(df_rallies)} rallies loaded"})

        except Exception as e:
            import traceback
            multi_sink.log({"event_type": "ERROR", "ts": datetime.now(timezone.utc).isoformat(), "error": f"Rally telemetry init failed: {str(e)}"})
            print(f"Rally telemetry init failed: {e}")
    
    # Run tick loop
    last_snapshot = None
    while feed.has_next():
        snapshot = feed.next()
        if snapshot is None:
            break
        last_snapshot = snapshot
        engine.tick(snapshot)
    
    # Force close logic
    if force_close_on_exit and last_snapshot and ndjson_sink:
        # Check for open positions in store for this profile
        # Note: WargameAccountStore isn't perfectly exposed for iteration, but we can check the ledger
        # or use internal state. SimExecutor tracks positions too.
        # But simpler: check engine.account_store for profile
        acct = store.load_account(scenario.profile_id)
        # However, WargameAccountStore doesn't expose open positions dict easily.
        # Let's check ledger for unclosed trades? No, ledger only strictly has events.
        # Let's check SimExecutor internal state? No.
        # But we know SilverStrategist tracks state too (in live).
        # In SIM, store handles it. WargameAccountStore is simple.
        # Actually, simpler hack: emit a fake forced close event if we suspect open.
        # Or better: check if last trade in ledger is OPEN.
        
        # We can mimic what live loop does: emit PROOF_CLOSE_RESULT with reason FORCED_END
        # We need the last close price.
        close_px = last_snapshot.get("close")
        ts_str = last_snapshot.get("ts", datetime.now().isoformat())
        if isinstance(ts_str, datetime):
            ts_str = ts_str.isoformat()
            
        # Emit a FORCED_END event regardless, or try to succeed only if open?
        # Trade replay parser simply pairs by timestamp. If we emit a newer close, it might pair.
        # But we need "open_qty" to be accurate for PnL in parser.
        # The parser reads from OPEN event. So emitting CLOSE is enough.
        
        # We don't know exact open qty easily here without digging into store.
        # But UI parser uses OPEN event's qty. PROOF_CLOSE_RESULT just needs fill_price.
        
        # Emitting event:
        forced_event = MatrixEvent(
            event_type=MatrixEventType.INFO, # Placeholder, JsonSink writes dicts mostly?
            # Wait, JsonSink expects MatrixEvent. But log parser expects PROOF_CLOSE_RESULT string.
            # MatrixEventType enum doesn't have PROOF_CLOSE_RESULT.
            # We must use a raw dict or extend enum? 
            # Telemetry system is strict? JsonFileEventSink uses event.to_dict().
            # event.event_type is Enum.
            # We can use custom event string if we bypass strict typing or use generic INFO.
            # But "event_type" field in JSON must be "PROOF_CLOSE_RESULT".
            
            # Hack: modify event_type to be custom string in dict
            symbol=scenario.symbol,
            timeframe=scenario.timeframe,
            profile_id=scenario.profile_id,
            ts=datetime.now(timezone.utc),
            details={
                "event_type_override": "PROOF_CLOSE_RESULT",
                "fill_price": close_px,
                "reason": "FORCED_END",
                "bar_close_ts": ts_str,
            }
        )
        # JSON Sink writes result of to_dict().
        # Let's manually write to ndjson_sink._path to be safe and simple.
        
        if events_path:
             with open(events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "event_type": "PROOF_CLOSE_RESULT",
                    "symbol": scenario.symbol,
                    "timeframe": scenario.timeframe,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "fill_price": close_px,
                    "reason": "FORCED_END",
                    "bar_close_ts": ts_str,
                    "forced": True
                }) + "\n")
    
    # Generate report
    ledger = store.get_ledger()
    trade_count = len([e for e in ledger if e.get("event_type") == "TRADE"])
    equity_curve = store.get_equity_history()
    max_dd_pct = compute_max_drawdown_pct(equity_curve)
    
    wins = sum(1 for e in ledger if e.get("event_type") == "TRADE" and e.get("pnl", 0) > 0)
    win_rate = wins / trade_count if trade_count > 0 else 0.0
    
    # Combine ledger events with telemetry events
    telemetry_events = [e.to_dict() for e in event_sink.get_events()]
    
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
        events=telemetry_events,  # Use telemetry events
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
    tightness: float = 100.0,  # 100 = card as-is, lower = wider filters
    events_path: Path | str | None = None,
    force_close_on_exit: bool = False,
) -> WargameReport:
    """
    Generic Silver 15m runner for any symbol.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT", "SOLUSDT").
        risk_per_trade_pct: Risk per trade (0.01 = 1%, 1.0 = 100%).
        mode: "contract" = enforce risk_contract_v1 cap, "experiment" = bypass cap.
        tightness: Filter tightness (100 = card as-is, 50 = 2x wider ranges).
            Only applies in experiment mode.
        events_path: Optional path to write NDJSON events.
        force_close_on_exit: If True, emit PROOF_CLOSE_RESULT for open positions at end.
        
    Returns:
        WargameReport with simulation results.
        
    Raises:
        FileNotFoundError: If pattern dataset doesn't exist for the symbol.
    """
    scenario = build_silver_15m_patterns_scenario(symbol, risk_per_trade_pct)
    scenario.mode = mode
    scenario.tightness = tightness  # Store for reference
    
    # Load risk contract from profile if in contract mode
    max_risk: float | None = None
    if mode == "contract":
        max_risk = _load_risk_contract_max_for_profile(scenario.profile_id)
        scenario.max_risk_per_trade = max_risk
    
    feed = ReplayDataFeed.from_symbol_timeframe_silver_patterns(symbol, "15m")
    return _run_wargame_with_scenario_and_feed(
        scenario, 
        feed,
        events_path=events_path,
        force_close_on_exit=force_close_on_exit,
    )


# =============================================================================
# Full Replay Mode (bar-by-bar 15m data for 2 years)
# =============================================================================

def run_silver_15m_full_replay_for_symbol(
    symbol: str,
    risk: float,
    mode: str = "contract",
    tightness: int = 50,
    start: str | None = None,
    end: str | None = None,
    events_path: Path | str | None = None,
    force_close_on_exit: bool = False,
) -> WargameReport:
    """
    Silver 15m stratejisini full replay (bar bar) modunda çalıştırır.
    
    Bu mod, pattern dataseti yerine 2 yıllık 15m bar datasını bar bar
    oynatarak gerçek sinyalleri tespit eder ve trade simüle eder.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        risk: Risk per trade (0.01 = 1%, 1.0 = 100%).
        mode: "contract" = enforce risk_contract_v1 cap, "experiment" = bypass cap.
        tightness: Filter tightness (0-100). 100 = card as-is, 0 = global min/max.
        start: Optional start date (ISO format, e.g., "2022-01-01").
        end: Optional end date (ISO format, e.g., "2024-01-01").
        events_path: Optional path to write NDJSON events.
        force_close_on_exit: If True, emit PROOF_CLOSE_RESULT for open positions at end.
        
    Returns:
        WargameReport with simulation results.
        
    Raises:
        FileNotFoundError: If full replay dataset doesn't exist.
        
    TODO: UI entegrasyonu - Matrix Operator "Veri Kaynağı" selectbox ekle.
    """
    from datetime import timezone
    
    # Build scenario for full replay
    profile_id = DEFAULT_SILVER_15M_PROFILE_IDS.get(symbol, f"{symbol[:3]}_SILVER_15M_CORE_V1")
    
    # Load full replay feed first (so we fail fast on missing file)
    feed = ReplayDataFeed.from_symbol_timeframe_full_replay(
        symbol=symbol,
        timeframe="15m",
        start=start,
        end=end,
    )
    
    scenario = WargameScenario(
        scenario_id=f"silver_15m_full_replay_{symbol.lower()}_{uuid.uuid4().hex[:8]}",
        profile_id=profile_id,
        symbol=symbol,
        timeframe="15m",
        start_ts=datetime.now(timezone.utc),
        end_ts=datetime.now(timezone.utc),
        initial_capital=100.0,
        risk_per_trade_pct=risk,
        mode=mode,
    )
    scenario.tightness = float(tightness)
    
    # Load risk contract if in contract mode
    if mode == "contract":
        max_risk = _load_risk_contract_max_for_profile(profile_id)
        scenario.max_risk_per_trade = max_risk
    
    return _run_wargame_with_scenario_and_feed(
        scenario, 
        feed,
        events_path=events_path,
        force_close_on_exit=force_close_on_exit,
    )


# =============================================================================
# Sniper Full Replay Mode (bar-by-bar using sniper entries as signals)
# =============================================================================

def run_sniper_full_replay_for_symbol(
    symbol: str,
    timeframe: str = "15m",
    risk: float = 1.0,
    tp_pct: float = 0.08,  # Take profit: 8%
    sl_pct: float = 0.03,  # Stop loss: 3%
    max_bars: int = 50,    # Max bars to hold
) -> WargameReport:
    """
    Sniper entries üzerinden bar-bar full replay simülasyonu.
    
    Bu mod:
    1. sniper_entries_v1.parquet'den entry timestamp'leri alır
    2. 2 yıllık 15m bar datasını yükler
    3. Sadece sniper entry zamanlarında işleme girer
    4. TP/SL veya max bars ile çıkar
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Timeframe (e.g., "15m").
        risk: Risk per trade (1.0 = full equity).
        tp_pct: Take profit percentage (0.08 = 8%).
        sl_pct: Stop loss percentage (0.03 = 3%).
        max_bars: Maximum bars to hold position.
        
    Returns:
        WargameReport with bar-by-bar simulation results.
    """
    import pandas as pd
    import numpy as np
    from pathlib import Path
    
    symbol = symbol.upper()
    
    # 1) Load sniper entries
    entries_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/sniper_entries_v1.parquet")
    if not entries_path.exists():
        raise FileNotFoundError(f"Sniper entries not found: {entries_path}")
    
    entries_df = pd.read_parquet(entries_path)
    entries_df = entries_df.loc[:, ~entries_df.columns.duplicated()]
    
    # Find timestamp column
    ts_col = None
    for c in ["event_time", "ts", "timestamp", "entry_ts"]:
        if c in entries_df.columns:
            ts_col = c
            break
    
    if ts_col is None:
        raise ValueError(f"No timestamp column found in sniper entries: {entries_df.columns.tolist()}")
    
    entries_df["entry_ts"] = pd.to_datetime(entries_df[ts_col])
    entry_timestamps = set(entries_df["entry_ts"].dt.strftime("%Y-%m-%d %H:%M"))
    
    # 2) Load full replay bar data
    bars_path = Path(f"data/replay/{symbol}/{timeframe}/full_replay_bars_v1.parquet")
    if not bars_path.exists():
        raise FileNotFoundError(f"Full replay bars not found: {bars_path}")
    
    bars_df = pd.read_parquet(bars_path)
    bars_df = bars_df.loc[:, ~bars_df.columns.duplicated()]
    
    # Find timestamp column in bars
    bar_ts_col = None
    for c in ["ts", "timestamp", "time", "datetime"]:
        if c in bars_df.columns:
            bar_ts_col = c
            break
    
    if bar_ts_col is None:
        raise ValueError(f"No timestamp column found in bars: {bars_df.columns.tolist()}")
    
    bars_df["bar_ts"] = pd.to_datetime(bars_df[bar_ts_col])
    bars_df = bars_df.sort_values("bar_ts").reset_index(drop=True)
    
    # 3) Simulation loop
    capital = 100.0
    equity = capital
    equity_curve = [equity]
    trades = []
    
    in_position = False
    entry_price = 0.0
    entry_idx = 0
    position_size = 0.0
    
    for i, row in bars_df.iterrows():
        bar_ts_str = row["bar_ts"].strftime("%Y-%m-%d %H:%M")
        
        # Get OHLC
        close = row.get("close", row.get("Close", 0))
        high = row.get("high", row.get("High", close))
        low = row.get("low", row.get("Low", close))
        
        if close == 0:
            continue
        
        if in_position:
            # Check exit conditions
            bars_held = i - entry_idx
            pnl_pct = (close / entry_price - 1.0)
            high_pnl = (high / entry_price - 1.0)
            low_pnl = (low / entry_price - 1.0)
            
            # Check TP (using high)
            if high_pnl >= tp_pct:
                profit = position_size * tp_pct
                equity += profit
                trades.append({
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "pnl_pct": tp_pct,
                    "exit_reason": "TP",
                })
                in_position = False
            # Check SL (using low)
            elif low_pnl <= -sl_pct:
                profit = position_size * (-sl_pct)
                equity += profit
                trades.append({
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "pnl_pct": -sl_pct,
                    "exit_reason": "SL",
                })
                in_position = False
            # Check max bars
            elif bars_held >= max_bars:
                profit = position_size * pnl_pct
                equity += profit
                trades.append({
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "pnl_pct": pnl_pct,
                    "exit_reason": "MAX_BARS",
                })
                in_position = False
        
        else:
            # Check for entry signal
            if bar_ts_str in entry_timestamps:
                in_position = True
                entry_price = close
                entry_idx = i
                position_size = equity * risk
        
        equity_curve.append(equity)
    
    # 4) Calculate metrics
    trade_count = len(trades)
    wins = sum(1 for t in trades if t["pnl_pct"] > 0)
    win_rate = (wins / trade_count * 100.0) if trade_count > 0 else 0.0
    
    pnl_pct = (equity / capital - 1.0) * 100.0
    max_dd_pct = compute_max_drawdown_pct(equity_curve) * 100.0
    
    return WargameReport(
        scenario_id=f"sniper_full_replay_{symbol.lower()}_{uuid.uuid4().hex[:8]}",
        profile_id=f"{symbol}_SNIPER_{timeframe.upper()}_V1",
        capital_start=capital,
        capital_end=round(equity, 2),
        trade_count=trade_count,
        win_rate=round(win_rate / 100.0, 4),  # Store as decimal
        max_drawdown=0.0,
        equity_curve=equity_curve,
        max_drawdown_pct=round(max_dd_pct / 100.0, 4),  # Store as decimal
        events=[],
    )


# =============================================================================
# Hybrid War Game (Pattern + Full Replay)
# =============================================================================

def run_silver_15m_hybrid_for_symbol(
    symbol: str,
    risk: float,
    mode: str = "contract",
    tightness: int = 50,
) -> "HybridWargameResult":
    """
    Pattern dataset + full replay sonuçlarını aynı parametrelerle çalıştırıp
    yan yana döndürür.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        risk: Risk per trade (0.01 = 1%, 1.0 = 100%).
        mode: "contract" or "experiment".
        tightness: Filter tightness (0-100).
        
    Returns:
        HybridWargameResult with both reports.
        
    TODO: Hybrid v2 – pattern dataset'te sinyal olan timestamp set'ini al,
          full replay'de sadece o timestamp'lerde sinyal üret.
    """
    from .reports import HybridWargameResult
    
    pattern_report = run_silver_15m_from_patterns_for_symbol(
        symbol=symbol,
        risk_per_trade_pct=risk,
        mode=mode,
        tightness=float(tightness),
    )
    
    full_report = run_silver_15m_full_replay_for_symbol(
        symbol=symbol,
        risk=risk,
        mode=mode,
        tightness=tightness,
        start=None,
        end=None,
    )
    
    return HybridWargameResult(
        symbol=symbol,
        timeframe="15m",
        profile_id=pattern_report.profile_id,
        risk=risk,
        mode=mode,
        tightness=tightness,
        pattern_report=pattern_report,
        full_replay_report=full_report,
    )


def _print_hybrid_result(result: "HybridWargameResult") -> None:
    """Print hybrid war game result for CLI."""
    print("=== Silver 15m Hybrid War Game ===")
    print(f"Symbol   : {result.symbol}")
    print(f"Profile  : {result.profile_id}")
    print(f"Risk     : {result.risk:.2f} (mode={result.mode}, tightness={result.tightness})")
    print("------------------------------------------------------------")
    pr = result.pattern_report
    fr = result.full_replay_report
    pr_pnl = (pr.capital_end / pr.capital_start - 1.0) * 100.0 if pr.capital_start > 0 else 0.0
    fr_pnl = (fr.capital_end / fr.capital_start - 1.0) * 100.0 if fr.capital_start > 0 else 0.0
    print(f"PATTERN    : Cap {pr.capital_start:.2f}→{pr.capital_end:.2f} ({pr_pnl:+.2f}%) | "
          f"Trades={pr.trade_count} | MaxDD={pr.max_drawdown_pct * 100:.2f}%")
    print(f"FULL_REPLAY: Cap {fr.capital_start:.2f}→{fr.capital_end:.2f} ({fr_pnl:+.2f}%) | "
          f"Trades={fr.trade_count} | MaxDD={fr.max_drawdown_pct * 100:.2f}%")
    print("------------------------------------------------------------")
    print(f"Δ PnL%     : {result.delta_pnl_pct:+.4f}%")
    print(f"Δ Trades   : {result.delta_trades:+d}")
    print(f"Δ MaxDD%   : {result.delta_max_dd_pct * 100:+.4f}%")


# Default profile IDs for Silver 15m (derived from symbol)
DEFAULT_SILVER_15M_PROFILE_IDS = {
    "BTCUSDT": "BTC_SILVER_15M_CORE_V1",
    "ETHUSDT": "ETH_SILVER_15M_CORE_V1",
    "SOLUSDT": "SOL_SILVER_15M_CORE_V1",
}


def _load_silver_profile_and_config(
    symbol: str,
    profile_id: str | None = None,
) -> tuple["MatrixCellProfile", SilverStrategyConfig]:
    """
    Load Silver 15m profile and config from CoinPage V2.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        profile_id: Optional profile ID override.
        
    Returns:
        Tuple of (MatrixCellProfile, SilverStrategyConfig)
        
    Raises:
        ValueError: If profile not found or no strategy config.
    """
    # Default coin_page_root
    coin_page_root = Path("data/coin_profiles")
    repo = MatrixProfileRepository(coin_page_root)
    
    # Determine profile_id
    if profile_id is None:
        profile_id = DEFAULT_SILVER_15M_PROFILE_IDS.get(symbol)
        if not profile_id:
            # Generate from symbol
            base = symbol.replace("USDT", "")
            profile_id = f"{base}_SILVER_15M_CORE_V1"
    
    # Load profiles for symbol first (populates cache)
    repo.load_profiles_for_symbol(symbol)
    
    # Now get profile from cache
    profile = repo.get_profile(profile_id)
    if profile is None:
        raise ValueError(f"Silver profile_id={profile_id} not found in MatrixProfileRepository")
    
    # Load config from profile
    cfg = load_silver_strategy_config_from_profile(profile)
    
    return profile, cfg


def _load_risk_contract_max_for_profile(profile_id: str) -> float | None:
    """
    Load max_risk_per_trade from risk_contract_v1 for a profile.
    
    Now reads from CoinPage V2 via MatrixProfileRepository.
    
    Args:
        profile_id: e.g., "BTC_SILVER_15M_CORE_V1"
        
    Returns:
        max_risk_per_trade from contract, or None if not found.
    """
    try:
        coin_page_root = Path("data/coin_profiles")
        repo = MatrixProfileRepository(coin_page_root)
        profile = repo.get_profile(profile_id)
        
        if profile and profile.risk_contract:
            return profile.risk_contract.max_risk_per_trade
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
    
if __name__ == "__main__":
    import sys
    import argparse

    # Quick and dirty arg parsing (preserving positional args for backward compat)
    # Filter out flags first
    argv_pos = [arg for arg in sys.argv if not arg.startswith("--")]
    
    # Defaults
    events_path = "data/logs/live_events.ndjson"  # Default to live Log
    force_close = True
    
    # Parse flags manually to avoid argparse conflicts with positional args styling
    if "--no-force-close" in sys.argv:
        force_close = False
    
    # Parse --events-path=... or --events-path ...
    for i, arg in enumerate(sys.argv):
        if arg == "--events-path":
            if i + 1 < len(sys.argv):
                events_path = sys.argv[i+1]
        elif arg.startswith("--events_path="):
            events_path = arg.split("=", 1)[1]
        elif arg.startswith("--events-path="):
            events_path = arg.split("=", 1)[1]

    mode = argv_pos[1] if len(argv_pos) > 1 else "single"

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
    
    elif mode == "full_replay_silver_15m":
        # python -m tezaver.matrix.wargame.runner full_replay_silver_15m BTCUSDT 1.0 experiment 50
        symbol = argv_pos[2] if len(argv_pos) > 2 else "BTCUSDT"
        risk = float(argv_pos[3]) if len(argv_pos) > 3 else 1.0
        replay_mode = argv_pos[4] if len(argv_pos) > 4 else "contract"
        tightness = int(argv_pos[5]) if len(argv_pos) > 5 else 50
        
        print(f"=== Silver 15m Full Replay – {symbol} ===")
        print(f"Risk: {risk:.2f}, Mode: {replay_mode}, Tightness: {tightness}")
        print(f"Events: {events_path}, ForceClose: {force_close}")
        print()
        
        try:
            report = run_silver_15m_full_replay_for_symbol(
                symbol=symbol,
                risk=risk,
                mode=replay_mode,
                tightness=tightness,
                events_path=events_path,
                force_close_on_exit=force_close,
            )
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
            print(f"Make sure full_replay_bars_v1.parquet exists in data/replay/{symbol}/15m/")
    
    elif mode == "hybrid_silver_15m":
        # python -m tezaver.matrix.wargame.runner hybrid_silver_15m BTCUSDT 0.01 contract 50
        symbol = argv_pos[2] if len(argv_pos) > 2 else "BTCUSDT"
        risk = float(argv_pos[3]) if len(argv_pos) > 3 else 1.0
        hybrid_mode = argv_pos[4] if len(argv_pos) > 4 else "contract"
        tightness = int(argv_pos[5]) if len(argv_pos) > 5 else 50
        
        try:
            result = run_silver_15m_hybrid_for_symbol(
                symbol=symbol,
                risk=risk,
                mode=hybrid_mode,
                tightness=tightness,
            )
            _print_hybrid_result(result)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print("Make sure both pattern and full_replay datasets exist.")
    
    elif mode == "parity_silver_15m":
        from .parity_tools import run_silver_15m_live_vs_wargame_parity, print_parity_result
        
        symbol = argv_pos[2] if len(argv_pos) > 2 else "BTCUSDT"
        risk = float(argv_pos[3]) if len(argv_pos) > 3 else 1.0
        parity_mode = argv_pos[4] if len(argv_pos) > 4 else "experiment"
        
        try:
            result = run_silver_15m_live_vs_wargame_parity(
                symbol=symbol,
                risk=risk,
                mode=parity_mode,
            )
            print_parity_result(result)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print(f"Make sure rally_patterns_v1.parquet exists for {symbol}")
    
    elif mode == "diary_silver_15m":
        from .diary import print_wargame_diary
        
        symbol = argv_pos[2] if len(argv_pos) > 2 else "BTCUSDT"
        risk = float(argv_pos[3]) if len(argv_pos) > 3 else 1.0
        diary_mode = argv_pos[4] if len(argv_pos) > 4 else "experiment"
        
        try:
            report = run_silver_15m_from_patterns_for_symbol(
                symbol=symbol,
                risk_per_trade_pct=risk,
                mode=diary_mode,
                events_path=events_path,
                force_close_on_exit=force_close,
            )
            print_wargame_diary(report)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print(f"Make sure rally_patterns_v1.parquet exists for {symbol}")
    
    else:
        print("=== BTC Silver 15m – War Game (rally_patterns_v1) ===")
        if len(argv_pos) > 1 and argv_pos[1] == "SIM":
            # Support "SIM" as a mode alias for single run with args potentially
            # Assuming python -m ... runner --mode=SIM --symbol=... via argparse earlier
            # But here we are using manual parsing.
            # The prompt says: python -m ...runner --mode=SIM 
            # If so, sys.argv will have --mode=SIM.
            # My manual parser 'argv_pos' removed it? No, starts with --.
            pass
        
        # Support running via --mode=SIM etc if they used my previous command line
        # Check if --mode is present
        sim_mode = False
        symbol = "BTCUSDT"
        timeframe = "15m"
        
        for arg in sys.argv:
            if arg.startswith("--mode="):
                if arg.split("=")[1] == "SIM":
                    sim_mode = True
            if arg.startswith("--symbol="):
                symbol = arg.split("=")[1]
        
        if sim_mode:
            # Use run_silver_15m_from_patterns_for_symbol
            print(f"Running SIM mode for {symbol}...")
            report = run_silver_15m_from_patterns_for_symbol(
                symbol=symbol,
                events_path=events_path,
                force_close_on_exit=force_close,
            )
        else:
            # Default run
            report = run_btc_silver_15m_from_patterns()
            
        print(f"Scenario : {report.scenario_id}")
        print(f"Profile  : {report.profile_id}")
        print(f"Capital  : {report.capital_start:.2f} → {report.capital_end:.2f}")
        pnl_pct = (report.capital_end / report.capital_start - 1.0) * 100.0
        print(f"PnL      : {pnl_pct:+.2f}%")
        print(f"Trades   : {report.trade_count}")
        print(f"Win Rate : {report.win_rate:.1%}")
        print(f"Max DD   : {report.max_drawdown_pct * 100:.2f}%")




