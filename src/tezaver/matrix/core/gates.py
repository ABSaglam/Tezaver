from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

from tezaver.matrix.core.state import RunState

@dataclass
class GateResult:
    name: str
    allow: bool
    reason: str = ""

@dataclass
class RiskGateConfig:
    max_notional: float = 0.0
    max_positions: int = 1

@dataclass
class GovernanceConfig:
    allowlist: List[str] = field(default_factory=list)
    delist_status: Dict[str, str] = field(default_factory=dict)
    max_age_seconds: int = 86400 * 30 # 30 days default

def eval_risk(symbol: str, price: float, desired_qty: float, state: RunState, cfg: RiskGateConfig) -> GateResult:
    # 1. Check max positions if opening new
    # If we have 0 position and want > 0, check limit.
    # Simplified: assume this symbol is the ONLY one we track in this run engine for now.
    # If multi-symbol, RunState would need list of positions.
    # For now, just check max_notional logic.
    
    notional = price * abs(desired_qty)
    if cfg.max_notional > 0 and notional > cfg.max_notional:
        return GateResult("Risk:MaxNotional", False, f"Notional {notional} > {cfg.max_notional}")
        
    return GateResult("Risk:Check", True)

def eval_allowlist(symbol: str, cfg: GovernanceConfig) -> GateResult:
    if not cfg.allowlist:
        return GateResult("Gov:Allowlist", True, "Empty allowlist")
    
    if symbol in cfg.allowlist:
        return GateResult("Gov:Allowlist", True, f"{symbol} allowed")
        
    return GateResult("Gov:Allowlist", False, f"{symbol} not in allowlist")

def eval_delist(symbol: str, cfg: GovernanceConfig) -> GateResult:
    status = cfg.delist_status.get(symbol)
    if status in ("DELIST_SOON", "DELISTED"):
        return GateResult("Gov:Delist", False, f"Symbol {symbol} status: {status}")
    return GateResult("Gov:Delist", True)

def eval_staleness(candidate_build_ts_iso: str, now_ts_sec: float, cfg: GovernanceConfig) -> GateResult:
    if not candidate_build_ts_iso:
         return GateResult("Gov:Staleness", True, "No build ts")
         
    try:
        # Simple ISO parsing (assumes YYYY-MM-DDTHH:MM:SS format mostly)
        dt = datetime.fromisoformat(candidate_build_ts_iso)
        build_ts = dt.timestamp()
        age = now_ts_sec - build_ts
        if age > cfg.max_age_seconds:
            return GateResult("Gov:Staleness", False, f"Candidate too old: {int(age)}s > {cfg.max_age_seconds}s")
    except ValueError:
        return GateResult("Gov:Staleness", False, f"Invalid build ts format: {candidate_build_ts_iso}")
        
    return GateResult("Gov:Staleness", True)

def eval_all_gates(symbol: str, 
                   price: float, 
                   desired_qty: float, 
                   state: RunState, 
                   risk_cfg: RiskGateConfig, 
                   gov_cfg: GovernanceConfig,
                   candidate_build_ts: str,
                   now_ts: float) -> List[GateResult]:
                   
    results = []
    
    # Governance First
    results.append(eval_allowlist(symbol, gov_cfg))
    results.append(eval_delist(symbol, gov_cfg))
    results.append(eval_staleness(candidate_build_ts, now_ts, gov_cfg))
    
    # Risk Second
    results.append(eval_risk(symbol, price, desired_qty, state, risk_cfg))
    
    return results
