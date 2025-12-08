"""
Tezaver Matrix Guardrail Controller (M25.4)
===========================================

This module implements the "Soft Power" laws of the Matrix.
It acts as the Intelligence Bridge between Offline Lab (Radar/Sim files) and the Live Matrix.

It answers the question: "Does the Offline Lab approve this trade?"
"""

import os
import json
from typing import Dict, Optional, TypedDict, List, Tuple, Any, Callable
from dataclasses import dataclass
from datetime import datetime
from tezaver.engine.interfaces import AccountState, IStrategist, MarketSignal, TradeDecision

@dataclass
class GuardrailProfile:
    """Intelligence snapshot for a symbol."""
    symbol: str
    env_status: str           # HOT / NEUTRAL / COLD / CHAOTIC / UNKNOWN
    promotion_status: str     # APPROVED / CANDIDATE / REJECTED / UNKNOWN
    affinity_score: float     # 0-100
    last_updated_at: datetime

def load_guardrail_profile(symbol: str, data_root: str = "data") -> GuardrailProfile:
    """
    Loads intelligence from Offline Lab JSON files.
    Paths:
      - data/coin_profiles/{symbol}/rally_radar.json
      - data/coin_profiles/{symbol}/sim_promotion.json
    """
    profile_dir = os.path.join(data_root, "coin_profiles", symbol)
    
    # Defaults
    env_status = "UNKNOWN"
    promotion_status = "UNKNOWN"
    affinity_score = 0.0
    
    # A. Load Radar
    radar_path = os.path.join(profile_dir, "rally_radar.json")
    if os.path.exists(radar_path):
        try:
            with open(radar_path, "r") as f:
                radar_data = json.load(f)
                env_status = radar_data.get("environment_status", "UNKNOWN")
        except:
            pass
            
    # B. Load Promotion / Affinity
    promo_path = os.path.join(profile_dir, "sim_promotion.json")
    if os.path.exists(promo_path):
        try:
            with open(promo_path, "r") as f:
                promo_data = json.load(f)
                promotion_status = promo_data.get("promotion_status", "UNKNOWN")
                # Try to get score from somewhere, or default 50
                affinity_score = promo_data.get("score", 50.0)
        except:
            pass
            
    return GuardrailProfile(
        symbol=symbol,
        env_status=env_status,
        promotion_status=promotion_status,
        affinity_score=affinity_score,
        last_updated_at=datetime.now()
    )

@dataclass
class GuardrailDecision:
    """Outcome of a Guardrail evaluation."""
    allow: bool
    reason_code: str         # ALLOW / BLOCK_RADAR_COLD / BLOCK_STRATEGY_REJECTED ...
    details: Dict[str, Any]  # Extra context for logging

class GuardrailStrategistProxy(IStrategist):
    """
    Wraps a real Strategist to enforce Guardrail policies.
    """
    def __init__(self, real_strategist: IStrategist, controller: "GuardrailController", on_decision_callback: Optional[Callable[[str, "GuardrailDecision"], None]] = None):
        self.real = real_strategist
        self.controller = controller
        self.on_decision_callback = on_decision_callback
        
    def evaluate(self, signal: MarketSignal, account_state: AccountState) -> Optional[TradeDecision]:
        # 1. Get raw decision
        decision = self.real.evaluate(signal, account_state)
        
        if not decision: 
            return None
            
        # 2. Check Guardrails
        # Only check signal-based entries (OPEN_LONG/BUY). 
        if decision['action'] == "BUY":
            symbol = decision['symbol']
            
            # Use detailed check
            g_decision = self.controller.check_open_new_long(symbol, account_state)
            
            # Create a detailed log via callback if wired
            if self.on_decision_callback:
                self.on_decision_callback(symbol, g_decision)
            
            if not g_decision.allow:
                # Log rejection (Future: could inject into a structured log)
                # For now, we return None (Silent Block)
                # Ideally, we should report this block somewhere.
                return None
                
        return decision

class GuardrailController:
    def __init__(self, global_limits: Dict[str, int], symbols: List[str]):
        """
        Args:
            global_limits: e.g. {"max_open_positions": 5}
            symbols: List of symbols to manage (triggers auto-load).
        """
        self.global_limits = global_limits
        self.profiles: Dict[str, GuardrailProfile] = {}
        
        # Initial Load
        for sym in symbols:
            self.profiles[sym] = load_guardrail_profile(sym)

    def reload(self):
        """Refreshes intelligence from disk."""
        for sym in list(self.profiles.keys()):
            self.profiles[sym] = load_guardrail_profile(sym)

    def check_open_new_long(self, symbol: str, account_state: AccountState) -> GuardrailDecision:
        """
        Detailed check for OPEN_LONG permission.
        Returns GuardrailDecision.
        """
        # 1. Check Global Limits
        current_positions = account_state.get('positions', {})
        max_pos = self.global_limits.get('max_open_positions', 999)
        
        if len(current_positions) >= max_pos and symbol not in current_positions:
            return GuardrailDecision(False, "BLOCK_GLOBAL_LIMIT", {"current": len(current_positions), "max": max_pos})

        # 2. Check Symbol Constraints
        profile = self.profiles.get(symbol)
        if not profile:
            return GuardrailDecision(False, "BLOCK_NO_PROFILE", {})
            
        details = {
            "env_status": profile.env_status,
            "promotion_status": profile.promotion_status,
            "affinity_score": profile.affinity_score
        }

        # A. Promotion Check
        if profile.promotion_status == "REJECTED":
            return GuardrailDecision(False, "BLOCK_STRATEGY_REJECTED", details)
            
        # B. Radar Check
        # Don't buy in COLD (Downtrend) or CHAOTIC (High Volatility/Crash) markets
        if profile.env_status in ["COLD", "CHAOTIC"]:
            return GuardrailDecision(False, f"BLOCK_RADAR_{profile.env_status}", details)
            
        # C. Score Check (Strict Mode for War Game v2)
        # Assuming minimal score of 60 for APPROVED strategies
        if profile.affinity_score < 60:
             return GuardrailDecision(False, "BLOCK_STRATEGY_LOW_SCORE", details)
            
        return GuardrailDecision(True, "ALLOW", details)

    def can_open_new_long(self, symbol: str, account_state: AccountState) -> bool:
        """
        Legacy/Simple Check.
        """
        decision = self.check_open_new_long(symbol, account_state)
        return decision.allow

    def get_profile(self, symbol: str) -> Optional[GuardrailProfile]:
        return self.profiles.get(symbol)
