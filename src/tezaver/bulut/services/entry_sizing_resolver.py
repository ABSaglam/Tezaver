# Tezaver Bulut - Entry Sizing Resolver
"""
Resolves the best Entry Sizing Profile for a given context and computes result.
Precedence: Symbol+Pattern > Pattern > Symbol > Global.
"""

from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.schemas.entry_sizing_profile_v1 import EntrySizingProfileV1
from tezaver.bulut.services.entry_sizing_loader import EntrySizingLoader

@dataclass
class SizingResult:
    notional_usdt: float
    leverage: Optional[int]
    profile_id: str
    explain: str
    blocked: bool = False
    block_reason: Optional[str] = None

class EntrySizingResolver:
    def __init__(self, ctx: BulutContext, loader: EntrySizingLoader):
        self._ctx = ctx
        self._loader = loader
        
    def resolve(self, symbol: str, pattern_id: Optional[str] = None) -> SizingResult:
        """
        Find best profile and compute sizing.
        """
        profiles = self._loader.load_all()
        
        # 1. Filter candidates
        # Precedence groups
        candidates_sp = [] # Symbol + Pattern
        candidates_p = []  # Pattern Only
        candidates_s = []  # Symbol Only
        candidates_g = []  # Global
        
        for p in profiles:
            s_match = (p.scope.symbol == symbol)
            p_match = (p.scope.pattern_id == pattern_id) if pattern_id else (p.scope.pattern_id is None)
            s_wild = (p.scope.symbol is None or p.scope.symbol == "*")
            p_wild = (p.scope.pattern_id is None or p.scope.pattern_id == "*")
            
            # Logic Grid:
            # SP: Both Match specific
            if s_match and p_match and not s_wild and not p_wild: candidates_sp.append(p)
            # P: Pattern specific, Symbol wild
            elif p_match and s_wild and not p_wild: candidates_p.append(p)
            # S: Symbol specific, Pattern wild (or None matched if pattern_id is None)
            elif s_match and p_wild and not s_wild: candidates_s.append(p)
            # G: Both wild
            elif s_wild and p_wild: candidates_g.append(p)
            
        # Sort each group by priority DESC
        candidates_sp.sort(key=lambda x: x.priority, reverse=True)
        candidates_p.sort(key=lambda x: x.priority, reverse=True)
        candidates_s.sort(key=lambda x: x.priority, reverse=True)
        candidates_g.sort(key=lambda x: x.priority, reverse=True)
        
        # Pick winner
        best = None
        if candidates_sp: best = candidates_sp[0]
        elif candidates_p: best = candidates_p[0]
        elif candidates_s: best = candidates_s[0]
        elif candidates_g: best = candidates_g[0]
        
        if not best:
             # FALLBACK LEGACY
             limit = self._ctx.config.max_cell_notional_usdt
             return SizingResult(limit, None, "FALLBACK_LEGACY", "No profile found, using global config max", blocked=False)
             
        # 2. Compute
        try:
             notional = self._compute_notional(best)
             leverage = best.rule.leverage
             
             # 3. Safety Clamps
             safe_notional, reason = self._apply_safety(best, notional)
             
             if reason == "BLOCK":
                 return SizingResult(0.0, None, best.profile_id, "Safety Block", blocked=True, block_reason="SAFETY_LIMIT")
                 
             return SizingResult(
                 notional_usdt=safe_notional,
                 leverage=leverage,
                 profile_id=best.profile_id,
                 explain=f"Matched {best.profile_id} (Prior:{best.priority}). Rule:{best.rule.type}. {reason if reason else ''}"
             )
             
        except Exception as e:
            return SizingResult(0.0, None, best.profile_id, str(e), blocked=True, block_reason=f"CALC_ERROR: {e}")

    def _compute_notional(self, p: EntrySizingProfileV1) -> float:
        rule = p.rule
        if rule.type == "fixed_notional":
            return float(rule.fixed_notional_usdt or 0.0)
            
        elif rule.type == "pct_of_cap":
            ref_val = 0.0
            if rule.cap_ref == "MAX_CELL_NOTIONAL":
                ref_val = self._ctx.config.max_cell_notional_usdt
            elif rule.cap_ref == "MAX_TOTAL_NOTIONAL":
                ref_val = self._ctx.config.max_total_notional_usdt
            elif rule.cap_ref == "MAINNET_PILOT_CAP":
                # Check constitution/env for pilot value
                ref_val = getattr(self._ctx.config, "mainnet_pilot_max_total_notional_usdt", 50.0)
            else:
                 # Default fallback?
                 ref_val = self._ctx.config.max_cell_notional_usdt
            
            pct = rule.pct or 0.0
            return (pct / 100.0) * ref_val
            
        return 0.0

    def _apply_safety(self, p: EntrySizingProfileV1, value: float) -> Tuple[float, Optional[str]]:
        """
        Applies profile-specific safety and global sanity checks.
        Returns (clamped_value, reason_or_None). 'BLOCK' in reason implies total block.
        """
        # 1. Negative check
        if value <= 0: return 0.0, "BLOCK"
        
        reason = []
        
        # 2. Profile Min
        if p.safety.min_notional_usdt and value < p.safety.min_notional_usdt:
             # Should we block or clamp up? Ideally BLOCK if too small for strategy, but clamp for safety?
             # Usually min limit is exchange limit.
             # If calculated is less than min, and min is hard requirement -> BLOCK?
             # If profile has min_notional, assume it requires it.
             # Let's BLOCK if below min, assuming "Strategy won't work with less".
             return 0.0, "BLOCK" # Below min profile req
             
        # 3. Profile Max
        if p.safety.max_notional_usdt and value > p.safety.max_notional_usdt:
            value = p.safety.max_notional_usdt
            reason.append("Clamped at Profile Max")

        # 4. Global Hard Cap (Config)
        global_cap = self._ctx.config.max_cell_notional_usdt
        if value > global_cap:
             value = global_cap
             reason.append("Clamped at Global Cell Max")
             
        return value, ", ".join(reason) if reason else None
