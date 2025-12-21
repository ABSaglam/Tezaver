"""
MX-2001: WarPlanner - Collects APPROVED_FOR_WAR candidates and generates cell plan.
"""
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

from tezaver.matrix.adapters.candidate_registry import CandidateRegistry


@dataclass
class WarCell:
    """A single cell in the WAR plan - one candidate on one symbol/tf."""
    symbol: str
    tf: str
    candidate_id: str
    bundle_id: str
    bundle_path: str
    data_fingerprint: str = ""
    config_signature: str = ""


@dataclass
class WarPlan:
    """Complete WAR run plan."""
    plan_id: str
    created_at: str
    cells: List[WarCell]
    symbols: List[str]
    candidate_ids: List[str]
    config_hash: str
    
    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "created_at": self.created_at,
            "cell_count": len(self.cells),
            "symbols": self.symbols,
            "candidate_ids": self.candidate_ids,
            "config_hash": self.config_hash
        }


class WarPlanner:
    """
    MX-2001: WarPlanner
    Collects APPROVED_FOR_WAR candidates and generates execution plan.
    """
    
    def __init__(self, registry: CandidateRegistry = None):
        self.registry = registry or CandidateRegistry()
    
    def collect_approved_candidates(
        self, 
        symbols: List[str] = None,
        max_candidates: int = None
    ) -> List[Dict]:
        """
        Collect candidates with status APPROVED_FOR_WAR.
        Optionally filter by symbols and limit count.
        """
        all_candidates = self.registry.list_all()
        
        # Filter by status
        approved = [c for c in all_candidates if c.get("status") == "APPROVED_FOR_WAR"]
        
        # Filter by symbols if specified
        if symbols:
            approved = [c for c in approved if c.get("symbol") in symbols]
        
        # Limit count if specified
        if max_candidates and len(approved) > max_candidates:
            approved = approved[:max_candidates]
        
        return approved
    
    def generate_plan(
        self,
        symbols: List[str] = None,
        max_candidates: int = None,
        seed: int = None
    ) -> WarPlan:
        """
        Generate WAR execution plan from approved candidates.
        """
        candidates = self.collect_approved_candidates(symbols, max_candidates)
        
        cells = []
        unique_symbols = set()
        unique_candidate_ids = set()
        
        for cand in candidates:
            cell = WarCell(
                symbol=cand.get("symbol", "UNKNOWN"),
                tf=cand.get("tf", "15m"),
                candidate_id=cand.get("candidate_id", cand.get("bundle_id")),
                bundle_id=cand.get("bundle_id", ""),
                bundle_path=cand.get("bundle_path", ""),
                data_fingerprint=cand.get("fingerprints", {}).get("data_fingerprint", ""),
                config_signature=cand.get("fingerprints", {}).get("config_signature", "")
            )
            cells.append(cell)
            unique_symbols.add(cell.symbol)
            unique_candidate_ids.add(cell.candidate_id)
        
        # Generate deterministic plan ID
        plan_content = f"{sorted(unique_symbols)}_{sorted(unique_candidate_ids)}_{seed}"
        plan_id = f"war_{hashlib.sha256(plan_content.encode()).hexdigest()[:12]}"
        
        # Config hash for determinism verification
        config_content = f"{seed}_{len(cells)}_{sorted(unique_symbols)}"
        config_hash = hashlib.sha256(config_content.encode()).hexdigest()[:16]
        
        return WarPlan(
            plan_id=plan_id,
            created_at=datetime.now().isoformat(),
            cells=cells,
            symbols=sorted(unique_symbols),
            candidate_ids=sorted(unique_candidate_ids),
            config_hash=config_hash
        )
