import os
import json
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

class CandidateRegistry:
    """
    MXI-1020 + PNL-1110: Registry for candidate bundles.
    Primary key: bundle_id (unique per bundle)
    Strategy key: {symbol}_{tf} for grouping
    """
    def __init__(self, registry_path: str = "data/matrix/candidates_registry.jsonl"):
        self.path = Path(registry_path)
        self._ensure_dir()
        self.candidates = self._load_all()

    def _ensure_dir(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def _load_all(self) -> Dict[str, Dict]:
        """Load all candidates keyed by bundle_id."""
        data = {}
        if not self.path.exists():
            return data
        with open(self.path, "r") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    entry = json.loads(line)
                    # PNL-1110: Use bundle_id as primary key
                    key = entry.get('bundle_id') or entry.get('candidate_id')
                    data[key] = entry
                except:
                    continue
        return data

    def _make_strategy_key(self, symbol: str, tf: str, profile_id: str = None) -> str:
        """Generate strategy grouping key."""
        if profile_id:
            return profile_id
        return f"{symbol}_{tf}"

    def register(self, 
                 bundle_id: str, 
                 symbol: str, 
                 tf: str, 
                 bundle_path: str,
                 metrics: Dict,
                 status: str = "NEW",
                 reason: str = None,
                 detected_version: str = None,
                 candidate_id: str = None,  # For backwards compat
                 fingerprints: Dict = None):
        """
        Register a candidate bundle.
        PNL-1110: bundle_id is the primary key.
        """
        strategy_key = self._make_strategy_key(symbol, tf)
        
        entry = {
            "bundle_id": bundle_id,
            "candidate_id": candidate_id or bundle_id,  # Backwards compat
            "strategy_key": strategy_key,
            "symbol": symbol,
            "tf": tf,
            "bundle_path": bundle_path,
            "resolve_rate": metrics.get("trigger_resolve_rate", 0),
            "join_coverage": metrics.get("join_coverage", 0),
            "fingerprints": fingerprints or {},
            "status": status,
            "reason": reason,
            "detected_version": detected_version,
            "imported_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        self.candidates[bundle_id] = entry
        self._save_all()
        return entry

    def update_status(self, bundle_id: str, status: str):
        """Update status by bundle_id."""
        if bundle_id in self.candidates:
            self.candidates[bundle_id]['status'] = status
            self.candidates[bundle_id]['updated_at'] = datetime.now().isoformat()
            self._save_all()

    def upsert(self, bundle_id: str, symbol: str, tf: str, 
               bundle_path: str, metrics: Dict, status: str = None,
               candidate_id: str = None, fingerprints: Dict = None):
        """
        PNL-1110: Upsert by bundle_id - if exists update, else register as NEW.
        """
        if bundle_id in self.candidates:
            # Update existing
            entry = self.candidates[bundle_id]
            entry['bundle_path'] = bundle_path
            entry['resolve_rate'] = metrics.get('trigger_resolve_rate', entry.get('resolve_rate', 0))
            entry['join_coverage'] = metrics.get('join_coverage', entry.get('join_coverage', 0))
            if fingerprints:
                entry['fingerprints'] = fingerprints
            if status:
                entry['status'] = status
            entry['imported_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            self.candidates[bundle_id] = entry
            self._save_all()
            return entry
        else:
            # Register new with NEW status
            return self.register(
                bundle_id=bundle_id,
                symbol=symbol,
                tf=tf,
                bundle_path=bundle_path,
                metrics=metrics,
                status=status or "NEW",
                candidate_id=candidate_id,
                fingerprints=fingerprints
            )

    def _save_all(self):
        with open(self.path, "w") as f:
            for entry in self.candidates.values():
                f.write(json.dumps(entry) + "\n")

    def list_all(self) -> List[Dict]:
        return list(self.candidates.values())

    def list_by_strategy(self) -> Dict[str, List[Dict]]:
        """PNL-1110: Group candidates by strategy_key."""
        grouped = {}
        for entry in self.candidates.values():
            key = entry.get('strategy_key', f"{entry.get('symbol')}_{entry.get('tf')}")
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(entry)
        return grouped

    def get(self, bundle_id: str) -> Optional[Dict]:
        return self.candidates.get(bundle_id)

    def get_by_candidate_id(self, candidate_id: str) -> Optional[Dict]:
        """Backwards compat: lookup by old candidate_id."""
        for entry in self.candidates.values():
            if entry.get('candidate_id') == candidate_id:
                return entry
        return None
