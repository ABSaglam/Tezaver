# Tezaver Bulut - Exit Engine
"""
Evaluates exit rules for open positions.
"""

from typing import List
from datetime import datetime, timezone
import math

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.schemas.trade_plan_v1 import TradePlanV1, TradeDecision, TradeSide
from tezaver.bulut.services.exit_profile_loader import ExitProfileLoader
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.bars_15m_store import Bars15mStore
from tezaver.bulut.services.idempotency import IdempotencyService # For key gen maybe?


class ExitEngine:
    """
    Evaluates AUTO EXIT rules.
    """
    
    def __init__(self, config: BulutConfig):
        self._config = config
    
    def evaluate_exits(
        self,
        persistence: SqlitePersistence,
        bars_store: Bars15mStore,
        profile_loader: ExitProfileLoader,
        cycle_ts: datetime
    ) -> List[TradePlanV1]:
        """
        Check all OPEN positions against their exit rules.
        Returns list of CLOSE plans.
        """
        close_plans = []
        positions = persistence.get_open_positions()
        
        for pos in positions:
            symbol = pos["symbol"]
            
            # 1. Get Market Data
            bar = bars_store.get_last_closed(symbol)
            if not bar:
                continue
                
            current_close = bar.c
            entry_price = float(pos["entry_price"])
            entry_ts_str = pos["entry_ts"]
            
            try:
                entry_ts = datetime.fromisoformat(entry_ts_str)
            except:
                entry_ts = cycle_ts # Fallback
            
            # 2. Resolve Profile
            pattern_id = pos.get("pattern_id")
            # Preference: Use stored profile ID if we want stickiness?
            # Or re-resolve to allow rule updates?
            # Re-resolve allows hot-patching exit rules for active trades!
            profile = profile_loader.resolve(symbol, pattern_id)
            
            # 3. Evaluate Rules
            exit_reason = None
            exit_rule_type = None
            
            for rule in profile.rules:
                if rule.type == "fixed_pct":
                    sl_limit = entry_price * (1.0 - (rule.sl_pct / 100.0))
                    tp_limit = entry_price * (1.0 + (rule.tp_pct / 100.0))
                    
                    if current_close <= sl_limit:
                        exit_reason = f"SL_HIT_{rule.sl_pct}%"
                        exit_rule_type = "fixed_pct"
                        break
                    elif current_close >= tp_limit:
                        exit_reason = f"TP_HIT_{rule.tp_pct}%"
                        exit_rule_type = "fixed_pct"
                        break
                        
                elif rule.type == "time_stop":
                    # Calc bars elapsed
                    # Simplistic time calc: (now - entry) / 15m
                    delta = cycle_ts - entry_ts
                    minutes = delta.total_seconds() / 60.0
                    bars_elapsed = minutes / 15.0
                    
                    if bars_elapsed >= rule.max_bars:
                        exit_reason = f"TIME_STOP_{rule.max_bars}BARS"
                        exit_rule_type = "time_stop"
                        break
            
            # 4. Create Plan if Triggered
            if exit_reason:
                # idempotency: cycle + symbol + reason
                # ensures we don't spam same close plan in same cycle (though cycle is unique)
                key = f"{cycle_ts.isoformat()}:{symbol}:CLOSE_LONG:{exit_reason}"
                
                plan = TradePlanV1(
                    plan_ts=cycle_ts,
                    symbol=symbol,
                    side=TradeSide.LONG, # Closing Long
                    decision=TradeDecision.CLOSE,
                    notional_usdt=0, # Full Close
                    idempotency_key=key,
                    reasons={
                        "exit_trigger": True,
                        "reason": exit_reason,
                        "rule_type": exit_rule_type,
                        "entry_price": entry_price,
                        "close_trigger_price": current_close,
                        "profile_id": profile.profile_id
                    }
                )
                close_plans.append(plan)
                
        return close_plans
