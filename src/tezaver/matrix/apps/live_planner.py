"""
MX-3001: LivePlanner - Collects APPROVED_FOR_LIVE candidates for live trading.
"""
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from collections import Counter

from tezaver.matrix.adapters.candidate_registry import CandidateRegistry


@dataclass
class LiveCell:
    """A single cell in the LIVE plan - one candidate on one symbol/tf."""
    symbol: str
    tf: str
    candidate_id: str
    bundle_id: str
    bundle_path: str
    config_signature: str = ""
    data_fingerprint: str = ""


@dataclass
class LiveDiagnostics:
    """Diagnostics for live plan generation."""
    candidates_total: int = 0
    candidates_by_status: Dict[str, int] = field(default_factory=dict)
    approved_for_live_count: int = 0
    selected_cells_count: int = 0
    symbols_found: List[str] = field(default_factory=list)
    registry_path: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "candidates_total": self.candidates_total,
            "candidates_by_status": self.candidates_by_status,
            "approved_for_live_count": self.approved_for_live_count,
            "selected_cells_count": self.selected_cells_count,
            "symbols_found": self.symbols_found,
            "registry_path": self.registry_path
        }


@dataclass
class LivePlan:
    """Complete LIVE run plan."""
    plan_id: str
    created_at: str
    cells: List[LiveCell]
    symbols: List[str]
    candidate_ids: List[str]
    config_hash: str
    diagnostics: LiveDiagnostics = field(default_factory=LiveDiagnostics)
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


class LivePlanner:
    """
    MX-3001: LivePlanner
    Collects APPROVED_FOR_LIVE candidates and generates execution plan.
    """
    
    def __init__(self, registry: CandidateRegistry = None):
        self.registry = registry or CandidateRegistry()
        self._last_diagnostics: Optional[LiveDiagnostics] = None
    
    def get_diagnostics(self) -> LiveDiagnostics:
        """Get full diagnostics about candidate registry state."""
        all_candidates = self.registry.list_all()
        
        status_counter = Counter(c.get("status", "UNKNOWN") for c in all_candidates)
        symbols = list(set(c.get("symbol", "?") for c in all_candidates))
        
        diag = LiveDiagnostics(
            candidates_total=len(all_candidates),
            candidates_by_status=dict(status_counter),
            approved_for_live_count=status_counter.get("APPROVED_FOR_LIVE", 0),
            selected_cells_count=0,
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
        Collect candidates with status APPROVED_FOR_LIVE.
        """
        all_candidates = self.registry.list_all()
        
        # Filter by status
        approved = [c for c in all_candidates if c.get("status") == "APPROVED_FOR_LIVE"]
        
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
        max_candidates: int = None
    ) -> LivePlan:
        """Generate LIVE execution plan from approved candidates."""
        diag = self.get_diagnostics()
        
        candidates = self.collect_approved_candidates(symbols, max_candidates)
        
        cells = []
        unique_symbols = set()
        unique_candidate_ids = set()
        
        for cand in candidates:
            cell = LiveCell(
                symbol=cand.get("symbol", "UNKNOWN"),
                tf=cand.get("tf", "15m"),
                candidate_id=cand.get("candidate_id", cand.get("bundle_id")),
                bundle_id=cand.get("bundle_id", ""),
                bundle_path=cand.get("bundle_path", ""),
                config_signature=cand.get("fingerprints", {}).get("config_signature", ""),
                data_fingerprint=cand.get("fingerprints", {}).get("data_fingerprint", "")
            )
            cells.append(cell)
            unique_symbols.add(cell.symbol)
            unique_candidate_ids.add(cell.candidate_id)
        
        diag.selected_cells_count = len(cells)
        
        # Generate plan ID
        plan_content = f"live_{sorted(unique_symbols)}_{len(cells)}"
        plan_id = f"live_{hashlib.sha256(plan_content.encode()).hexdigest()[:12]}"
        
        # Config hash
        config_content = f"{len(cells)}_{sorted(unique_symbols)}"
        config_hash = hashlib.sha256(config_content.encode()).hexdigest()[:16]
        
        is_empty = len(cells) == 0
        
        return LivePlan(
            plan_id=plan_id,
            created_at=datetime.now().isoformat(),
            cells=cells,
            symbols=sorted(unique_symbols),
            candidate_ids=sorted(unique_candidate_ids),
            config_hash=config_hash,
            diagnostics=diag,
            is_empty=is_empty
        )
