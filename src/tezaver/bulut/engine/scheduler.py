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
from tezaver.bulut.services.cycle_forensics import CycleForensicsService
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
        self._forensics: Optional[CycleForensicsService] = CycleForensicsService()
        
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

        # Initial Reconciliation (from original start)
        if ctx.config.execution_enabled:
             print("[SCHEDULER] Running initial reconciliation...")
             try:
                 report = await ctx.reconciliation_service.reconcile()
                 print(f"[SCHEDULER] Reconciliation Report: {report['status']}")
             except Exception as e:
                 print(f"[SCHEDULER] Reconciliation Failed: {e}")

        self._task = asyncio.create_task(self._loop())
        print("[Scheduler] Started.")

    async def run_forever(self, ctx):
        """Run scheduler loop forever (Supervisor mode)."""
        # This overwrites start/stop logic usage.
        self._running = True 
        
        # Init services (from original start, adapted for run_forever)
        # Assuming ctx is passed, we can use it directly
        self._rest_client = BinanceFuturesRest(self._config)
        self._poller = MarketDataPoller(
            self._config, 
            self._rest_client, 
            ctx.bars_store,
            ctx.telemetry
        )
        await self._rest_client.create_session()
        print(f"[SCHEDULER] Starting async loop (interval={self._config.poll_interval_seconds}s) in supervisor mode.")

        # Initial Reconciliation (from original start)
        if ctx.config.execution_enabled:
             print("[SCHEDULER] Running initial reconciliation...")
             try:
                 report = await ctx.reconciliation_service.reconcile()
                 print(f"[SCHEDULER] Reconciliation Report: {report['status']}")
             except Exception as e:
                 print(f"[SCHEDULER] Reconciliation Failed: {e}")

        try:
             await self._loop(ctx)
        finally:
             self._running = False
             if self._rest_client: # Close client if it was opened
                 await self._rest_client.close()
             print("[Scheduler] Stopped (run_forever).")

    async def stop(self):
        """Stop scheduler."""
        self._running = False
        self._stop_event.set() # Keep existing stop_event set
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._rest_client:
            await self._rest_client.close()
            
        print("[SCHEDULER] Stopped")

    def is_running(self) -> bool:
        return self._running

    async def _loop(self, ctx=None):
        """Main loop."""
        # Use provided ctx or rely on self ref (requires refactor if self doesn't have ctx)
        # Existing usage implies Scheduler has ref to components?
        # Let's check init. It gets `scanner`, `executor`...
        # It doesn't seem to hold global `ctx`.
        # But `app_backend` passes ctx to `scheduler.start()`? No, `scheduler.start()` takes no args.
        # It uses injected dependencies.
        # If we use supervisor, we might need access to `task_supervisor` for heartbeats.
        # We can pass `ctx` to `run_forever`.
        
        # If ctx is not provided (e.g., from old start method), get it globally
        if ctx is None:
            ctx = get_context()
        
        while self._running:
            try:
                ref_bar = await self._rest_client.get_latest_closed_bar("BTCUSDT", interval=self._config.base_tf)
                
                if ref_bar:
                    # Strict Timing Check (Dedupe + Drift)
                    should_check = (self._last_processed_close_ts is None) or (ref_bar.close_ts > self._last_processed_close_ts)
                    
                    if should_check:
                        print(f"[SCHEDULER] Detected candidate 15m close: {ref_bar.close_ts}")
                        curr_ts = datetime.now(timezone.utc)
                        
                        # Convert to datetime for service
                        ts_val = ref_bar.close_ts
                        if isinstance(ts_val, (int, float)):
                            ts_dt = datetime.fromtimestamp(ts_val / 1000.0, timezone.utc)
                        else:
                            ts_dt = ts_val
                            
                        # Call Service
                        decision = ctx.strict_timing.on_cycle_attempt(ts_dt, curr_ts)
                        
                        if decision["status"] == "BLOCK":
                            print(f"[SCHEDULER] StrictTiming BLOCKED: {decision['reason']} (Drift: {decision['drift_ms']}ms)")
                            # Assume processed logic if deduped
                            self._last_processed_close_ts = ref_bar.close_ts
                        
                        elif decision["status"] == "ALLOW":
                            print(f"[SCHEDULER] StrictTiming ALLOW (Drift: {decision['drift_ms']}ms)")
                            try:
                                await self._run_cycle_logic(ctx, ref_bar.close_ts)
                                self._last_processed_close_ts = ref_bar.close_ts
                            except Exception as e:
                                print(f"[SCHEDULER] Cycle Run Failed: {e}")
                                # Retry allowed next loop? Or log error and mark processed?
                                # Safer: Don't mark processed so we retry.
                                pass
                        
                    else:
                        # Waiting for next bar
                        pass
                        
            except Exception as e:
                print(f"[SCHEDULER] Loop error: {e}")
                # Don't crash loop
            
            # Sleep
            await asyncio.sleep(self._config.poll_interval_seconds)

    async def _run_cycle_logic(self, ctx, current_close_ts: int):
        """Isolated cycle logic for testing."""
        # 2. Scheduler Logic (Fair Batching)
        universe = ctx.universe_source.load()
        
        # Load state
        s_cursor = int(ctx.persistence.get_system_state("sched_cursor") or 0)
        s_missed_str = ctx.persistence.get_system_state("sched_missed") or ""
        s_missed = [s.strip() for s in s_missed_str.split(",") if s.strip()]
        
        # Deterministic cycle index
        s_cycle = int(ctx.persistence.get_system_state("sched_cycle") or 0)
        s_cycle += 1
        ctx.persistence.set_system_state("sched_cycle", str(s_cycle))

        # Build Priority Lane (Top20 + Missed)
        priority_lane = set(s_missed)
        
        # Fetch Top20 from previous ranking if available
        if ctx.ranking_stabilizer:
            last_rank = ctx.ranking_stabilizer.get_last_ranking()
            if last_rank and last_rank.candidates:
                # Top20 by score
                sorted_cands = sorted(last_rank.candidates, key=lambda c: c.score, reverse=True)
                for c in sorted_cands[:20]:
                        priority_lane.add(c.symbol)
                        
        # Budgeting
        max_cycle = self._config.universe_scan_max_per_cycle
        prio_cap = self._config.universe_scan_priority_slots
        
        priority_list = list(priority_lane)
        if len(priority_list) > prio_cap:
            # Sort: Missed first, then Top20/Others
            priority_list.sort(key=lambda x: 0 if x in s_missed else 1)
            priority_list = priority_list[:prio_cap]
        
        # Available slots for RR
        rr_slots = max_cycle - len(priority_list)
        if rr_slots < 0: rr_slots = 0
        
        # Round Robin Selection
        batch_rr = []
        if rr_slots > 0 and universe:
            total_u = len(universe)
            for _ in range(rr_slots):
                sym = universe[s_cursor % total_u]
                s_cursor += 1
                if sym not in priority_list:
                    batch_rr.append(sym)
        
        # Final Batch
        batch = list(set(priority_list + batch_rr))
        batch.sort() # Ensure deterministic order
        
        # Persist Cursor
        ctx.persistence.set_system_state("sched_cursor", str(s_cursor % len(universe) if universe else 0))
        
        # Telemetry: CYCLE_START
        ctx.telemetry.emit("SCHED_CYCLE_START", {
            "cycle_index": s_cycle,
            "universe_n": len(universe),
            "planned_n": len(batch),
            "priority_n": len(priority_list),
            "rr_n": len(batch_rr)
        })
        print(f"[SCHEDULER] Cycle #{s_cycle}: {len(batch)} symbols (Prio:{len(priority_list)} RR:{len(batch_rr)})")
        
        # Run Poller
        updated_count, failed_symbols = await self._poller.run_cycle(batch)
        
        # Update Missed (Backpressure)
        new_missed = failed_symbols
        ctx.persistence.set_system_state("sched_missed", ",".join(new_missed))
        
        # Telemetry: CYCLE_END
        ctx.telemetry.emit("SCHED_CYCLE_END", {
            "cycle_index": s_cycle,
            "scanned_n": updated_count,
            "missed_n": len(new_missed),
            "partial": len(new_missed) > 0
        })
        
        # 3. Run Scan
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
        current_positions = {p["symbol"] for p in ctx.persistence.get_open_positions()}
        final_plans = []
        
        # Process Close Plans
        for p in close_plans:
            if p.symbol not in current_positions:
                print(f"[SCHEDULER] Blocked CLOSE for {p.symbol}: NO_POSITION")
                continue
            final_plans.append(p)
            
        # Process Open Plans
        for p in open_plans:
            if p.decision.name == "OPEN":
                if p.symbol in current_positions:
                    print(f"[SCHEDULER] Blocked OPEN for {p.symbol}: ALREADY_OPEN")
                    p.decision = "SKIP"
                    p.reasons["skip_reason"] = "ALREADY_OPEN"
                    final_plans.append(p)
                else:
                    final_plans.append(p)
            else:
                final_plans.append(p)
        
        # 5. Process Plans
        for plan in final_plans:
            status = "PROPOSED"
            
            if plan.decision.name == "SKIP":
                status = "BLOCKED"
                ctx.telemetry.emit_trade_plan_blocked(
                    plan.to_dict(), 
                    plan.reasons.get("skip_reason", "UNKNOWN")
                )
            elif ctx.config.auto_trade:
                if ctx.config.paper_mode:
                    status = "ACCEPTED"
                    ctx.telemetry.emit_trade_plan_accepted(plan.to_dict(), mode="PAPER")
                else:
                    status = "ACCEPTED" 
                    ctx.telemetry.emit_trade_plan_accepted(plan.to_dict(), mode="LIVE")
            else:
                status = "PROPOSED"
                ctx.telemetry.emit_trade_plan_proposed(plan.to_dict())
                
            inserted = ctx.persistence.insert_plan(plan, status)
            if inserted:
                print(f"[SCHEDULER] Plan {status}: {plan.symbol} {plan.decision.name}")
        
        # 6. Execute Plans
        if ctx.config.auto_trade and not ctx.config.paper_mode:
            accepted_plans = [p for p in final_plans if p.decision.name in ["OPEN", "CLOSE"]]
            if accepted_plans:
                await ctx.executor.execute_plans(accepted_plans)
                
        # 7. Forensics (Timeline)
        try:
            # Stats gathering
            sched_stats = {
                "universe_n": len(universe),
                "planned_n": len(batch),
                "priority_n": len(priority_list),
                "rr_n": len(batch_rr),
                "scanned_n": updated_count,
                "missed_n": len(new_missed)
            }
            
            scan_stats = {
                "candidates_n": len(ranking.candidates) if ranking else 0,
                "top_score": ranking.candidates[0].score if ranking and ranking.candidates else 0
            }
            
            decider_stats = {
                "close_plans_n": len(close_plans),
                "open_plans_n": len(open_plans),
                "final_plans_n": len(final_plans)
            }
            
            # Count accepted explicitly
            acc_n = 0
            if ctx.config.auto_trade and not ctx.config.paper_mode:
                # We compiled accepted_plans above
                acc_n = len([p for p in final_plans if p.decision.name in ["OPEN", "CLOSE"]])
            
            exec_stats = {
                "executed_n": acc_n
            }
            
            risk_stats = {
                "halted": not ctx.config.execution_enabled,
                "daily_pnl": ctx.persistence.get_today_net_pnl_utc()
            }
            
            # Ensure cycle_ts is datetime
            ts = current_close_ts
            if isinstance(ts, int) or isinstance(ts, float):
                 ts = datetime.fromtimestamp(ts / 1000.0, timezone.utc)
            
            self._forensics.collect_and_save(
                ctx, s_cycle, ts,
                sched_stats, scan_stats, decider_stats, exec_stats, risk_stats
            )
            
            # 8. Strict Timing: Mark Completed
            ctx.strict_timing.record_success(ts, s_cycle)
            
        except Exception as e:
            print(f"[SCHEDULER] Forensics failed: {e}")
