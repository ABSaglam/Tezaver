# Tezaver Bulut - Async Scheduler
"""
Async scheduler for managing scan cycles.
Replaces the old thread-based scheduler.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Callable, Awaitable

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import get_context
from tezaver.bulut.engine.market_data_poller import MarketDataPoller
from tezaver.bulut.services.binance_futures_rest import BinanceFuturesRest
# Routes needing scanners are imported inside methods to avoid circular deps if any


class AsyncScheduler:
    """
    Async loop for checking 15m closures and triggering flows.
    """
    
    def __init__(self, config: BulutConfig):
        self._config = config
        self._stop_event = asyncio.Event()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # State
        self._last_processed_close_ts: Optional[datetime] = None
        self._last_check_ts: float = 0
        
        # Services (lazy init or passed in?)
        # We will retrieve from context or init here.
        self._rest_client: Optional[BinanceFuturesRest] = None
        self._poller: Optional[MarketDataPoller] = None
        
    async def start(self):
        """Start the background loop."""
        if self._running:
            return
            
        self._running = True
        self._stop_event.clear()
        
        # Init services
        ctx = get_context()
        self._rest_client = BinanceFuturesRest(self._config)
        self._poller = MarketDataPoller(
            self._config, 
            self._rest_client, 
            ctx.bars_store,
            ctx.telemetry
        )
        
        await self._rest_client.create_session()
        
        print(f"[SCHEDULER] Starting async loop (interval={self._config.poll_interval_seconds}s)")
        
        # Initial Reconciliation
        if ctx.config.execution_enabled:
             print("[SCHEDULER] Running initial reconciliation...")
             try:
                 report = await ctx.reconciliation_service.reconcile()
                 print(f"[SCHEDULER] Reconciliation Report: {report['status']}")
             except Exception as e:
                 print(f"[SCHEDULER] Reconciliation Failed: {e}")

        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        """Stop the background loop."""
        self._running = False
        self._stop_event.set()
        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._rest_client:
            await self._rest_client.close()
            
        print("[SCHEDULER] Stopped")

    def is_running(self) -> bool:
        return self._running

    async def _loop(self):
        """Main check loop."""
        ctx = get_context()
        
        while self._running:
            try:
                # 1. Check for new 15m close via BTCUSDT (Reference)
                ref_bar = await self._rest_client.get_latest_closed_bar("BTCUSDT", interval=self._config.base_tf)
                
                if ref_bar:
                    # Check if this is a new closed bar we haven't processed
                    if (self._last_processed_close_ts is None) or (ref_bar.close_ts > self._last_processed_close_ts):
                        print(f"[SCHEDULER] New 15m close detected: {ref_bar.close_ts}")
                        
                        # UPDATE STATE: Mark this as processed *before* or *after*?
                        # If we mark before, failures might skip. If after, we might retry.
                        # Let's mark after successful ingest start.
                        current_close_ts = ref_bar.close_ts
                        
                        # 2. Run Ingest Cycle (All symbols)
                        universe = ctx.universe_source.load()
                        await self._poller.run_cycle(universe)
                        
                        # 3. Run Scan
                        # Import here to avoid early import issues
                        from tezaver.bulut.engine.scanner import run_scan
                        
                        # Hot reload
                        ctx.pattern_loader.check_reload()
                        ctx.exit_profile_loader.check_reload()
                        
                        ranking = run_scan(
                            config=ctx.config,
                            pattern_loader=ctx.pattern_loader,
                            universe=universe,
                            bars_store=ctx.bars_store,
                            stabilizer=ctx.ranking_stabilizer
                        )
                        
                        # Emit
                        snap = ranking.to_dict()
                        meta = ctx.pattern_loader.get_pack_meta()
                        snap["pattern_pack"] = meta
                        ctx.telemetry.emit_ranking_snapshot(snap)
                        
                        # Update state
                        ctx.state.last_scan_ts = ranking.cycle_ts
                        self._last_processed_close_ts = current_close_ts
                        
                        # --- PLAN GENERATION ---
                        
                        # A. Auto Exits (CLOSE)
                        close_plans = ctx.exit_engine.evaluate_exits(
                            persistence=ctx.persistence,
                            bars_store=ctx.bars_store,
                            profile_loader=ctx.exit_profile_loader,
                            cycle_ts=ranking.cycle_ts
                        )
                        
                        # B. Auto Entries (OPEN)
                        allowlist = ctx.allowlist_source.load()
                        open_plans = ctx.decider.decide(
                            ranking=ranking,
                            open_positions_count=ctx.persistence.get_open_position_count(),
                            total_notional=ctx.persistence.get_total_notional(),
                            pattern_pack_loaded=ctx.state.pattern_pack_loaded,
                            allowlist=allowlist
                        )
                        
                        # --- GATES & MERGE ---
                        
                        # Gate: Filter OPEN if already open
                        current_positions = {p["symbol"] for p in ctx.persistence.get_open_positions()}
                        final_plans = []
                        
                        # Process Close Plans
                        for p in close_plans:
                            if p.symbol not in current_positions:
                                # Orphan close? Block.
                                print(f"[SCHEDULER] Blocked CLOSE for {p.symbol}: NO_POSITION")
                                continue
                            final_plans.append(p)
                            
                        # Process Open Plans
                        for p in open_plans:
                            # Only block if decision is OPEN
                            if p.decision.name == "OPEN":
                                if p.symbol in current_positions:
                                    print(f"[SCHEDULER] Blocked OPEN for {p.symbol}: ALREADY_OPEN")
                                    # Convert to SKIP plan for visibility
                                    p.decision = "SKIP"
                                    p.reasons["skip_reason"] = "ALREADY_OPEN"
                                    final_plans.append(p)
                                else:
                                    final_plans.append(p)
                            else:
                                # BLOCKED/SKIP plans pass
                                final_plans.append(p)
                        
                        # 5. Process Plans
                        # Sort? Close first handled by append order effectively, but let's ensure.
                        # Actually executor executes concurrently or sequentially?
                        # Executor loop is sequential. So Close appended first executes first. Good.
                        
                        for plan in final_plans:
                            # Determine Status
                            status = "PROPOSED" # Default (Blocked ones are SKIP decision)
                            
                            if plan.decision.name == "SKIP":
                                status = "BLOCKED"
                                ctx.telemetry.emit_trade_plan_blocked(
                                    plan.to_dict(), 
                                    plan.reasons.get("skip_reason", "UNKNOWN")
                                )
                            elif ctx.config.auto_trade:
                                if ctx.config.paper_mode:
                                    status = "ACCEPTED" # Auto but Paper -> Accepted but not executed
                                    ctx.telemetry.emit_trade_plan_accepted(plan.to_dict(), mode="PAPER")
                                else:
                                    status = "ACCEPTED" # Real execution TODO
                                    ctx.telemetry.emit_trade_plan_accepted(plan.to_dict(), mode="LIVE")
                                    # Trigger Execution here (Future Step)
                            else:
                                # Manual Mode
                                status = "PROPOSED"
                                ctx.telemetry.emit_trade_plan_proposed(plan.to_dict())
                                
                            # Persist
                            inserted = ctx.persistence.insert_plan(plan, status)
                            if inserted:
                                print(f"[SCHEDULER] Plan {status}: {plan.symbol} {plan.decision.name}")
                        
                        # 6. Execute Plans (Auto Trade & Live)
                        if ctx.config.auto_trade and not ctx.config.paper_mode:
                            # Filter accepted plans for execution
                            # Only execute the ones we JUST created/decided
                            # (executor handles safety checks)
                            accepted_plans = [p for p in final_plans if p.decision.name in ["OPEN", "CLOSE"]]
                            
                            to_execute = []
                            for p in accepted_plans:
                                # Redundant status check but safe
                                # If we had manual plans queue in DB, we'd fetch them here too.
                                # For now just loop-generated plans.
                                to_execute.append(p)
                                        
                            if to_execute:
                                # Run executor
                                await ctx.executor.execute_plans(to_execute)

                    else:
                        # Already processed this bar
                        pass
                        
            except Exception as e:
                print(f"[SCHEDULER] Loop error: {e}")
                # Don't crash loop
            
            # Sleep
            await asyncio.sleep(self._config.poll_interval_seconds)
