"""
MX-2001 + MX-2000.1: WarPlanner - Collects APPROVED_FOR_WAR candidates and generates cell plan.
W1: Diagnostics support for candidate counts and status breakdown.
"""
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from collections import Counter

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
class PlanDiagnostics:
    """W1: Diagnostics for plan generation."""
    candidates_total: int = 0
    candidates_by_status: Dict[str, int] = field(default_factory=dict)
    approved_for_war_count: int = 0
    selected_cells_count: int = 0
    symbols_found: List[str] = field(default_factory=list)
    registry_path: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "candidates_total": self.candidates_total,
            "candidates_by_status": self.candidates_by_status,
            "approved_for_war_count": self.approved_for_war_count,
            "selected_cells_count": self.selected_cells_count,
            "symbols_found": self.symbols_found,
            "registry_path": self.registry_path
        }


@dataclass
class WarPlan:
    """Complete WAR run plan."""
    plan_id: str
    created_at: str
    cells: List[WarCell]
    symbols: List[str]
    candidate_ids: List[str]
    config_hash: str
    diagnostics: PlanDiagnostics = field(default_factory=PlanDiagnostics)
    is_empty: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "created_at": self.created_at,
            "cell_count": len(self.cells),
            "symbols": self.symbols,
            "candidate_ids": self.candidate_ids,
            "config_hash": self.config_hash,
            "is_empty": self.is_empty,
            "diagnostics": self.diagnostics.to_dict()
        }


class WarPlanner:
    """
    MX-2001 + MX-2000.1: WarPlanner
    Collects APPROVED_FOR_WAR candidates and generates execution plan.
    W1: Diagnostics support for debugging empty plans.
    """
    
    def __init__(self, registry: CandidateRegistry = None):
        self.registry = registry or CandidateRegistry()
        self._last_diagnostics: Optional[PlanDiagnostics] = None
    
    def get_diagnostics(self) -> PlanDiagnostics:
        """W1: Get full diagnostics about candidate registry state."""
        all_candidates = self.registry.list_all()
        
        status_counter = Counter(c.get("status", "UNKNOWN") for c in all_candidates)
        symbols = list(set(c.get("symbol", "?") for c in all_candidates))
        
        diag = PlanDiagnostics(
            candidates_total=len(all_candidates),
            candidates_by_status=dict(status_counter),
            approved_for_war_count=status_counter.get("APPROVED_FOR_WAR", 0),
            selected_cells_count=0,  # Will be updated on generate_plan
            symbols_found=symbols,
            registry_path=str(self.registry.path)
        )
        
        self._last_diagnostics = diag
        return diag
    
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
        W2: Returns empty plan with is_empty=True if no approved candidates.
        """
        # Get diagnostics first
        diag = self.get_diagnostics()
        
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
        
        # Update diagnostics with selected count
        diag.selected_cells_count = len(cells)
        
        # Generate deterministic plan ID
        plan_content = f"{sorted(unique_symbols)}_{sorted(unique_candidate_ids)}_{seed}"
        plan_id = f"war_{hashlib.sha256(plan_content.encode()).hexdigest()[:12]}"
        
        # Config hash for determinism verification
        config_content = f"{seed}_{len(cells)}_{sorted(unique_symbols)}"
        config_hash = hashlib.sha256(config_content.encode()).hexdigest()[:16]
        
        # W2: Mark as empty if no cells
        is_empty = len(cells) == 0
        
        return WarPlan(
            plan_id=plan_id,
            created_at=datetime.now().isoformat(),
            cells=cells,
            symbols=sorted(unique_symbols),
            candidate_ids=sorted(unique_candidate_ids),
            config_hash=config_hash,
            diagnostics=diag,
            is_empty=is_empty
        )
