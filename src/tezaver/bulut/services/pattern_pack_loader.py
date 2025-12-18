# Tezaver Bulut - Pattern Pack Loader Service
"""
Loads and validates PatternPack files with hot-reload.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict

from tezaver.bulut.schemas.pattern_pack_v1 import PatternPackV1, validate_pattern_pack


class PatternPackLoader:
    """
    Pattern Pack loader for Tezaver Bulut.
    Supports hot-reload by checking file mtime.
    """
    
    def __init__(self, pack_dir: str):
        self._pack_dir = Path(pack_dir)
        self._cached_pack: Optional[PatternPackV1] = None
        self._cached_path: Optional[Path] = None
        self._last_mtime: float = 0.0
    
    def check_reload(self) -> bool:
        """
        Check if reload is needed and perform it.
        Returns True if a NEW pack was loaded.
        """
        latest_path = self.get_latest_path()
        if not latest_path:
            self._clear_cache()
            return False
            
        current_mtime = latest_path.stat().st_mtime
        
        # Check if path changed OR content changed (mtime)
        if latest_path != self._cached_path or current_mtime > self._last_mtime:
            print(f"[PATTERN_LOADER] Detect change. Loading {latest_path.name}...")
            pack = self.load_from_path(latest_path)
            if pack:
                self._cached_pack = pack
                self._cached_path = latest_path
                self._last_mtime = current_mtime
                print(f"[PATTERN_LOADER] Loaded pack {pack.pack_id} ({len(pack.symbols)} symbols)")
                return True
        
        return False

    def list_packs(self) -> list[Path]:
        """List all pattern pack files in inbox."""
        if not self._pack_dir.exists():
            return []
        return sorted(self._pack_dir.glob("*.json"))
    
    def get_latest_path(self) -> Optional[Path]:
        """Get path to most recent pattern pack (by name sort)."""
        packs = self.list_packs()
        return packs[-1] if packs else None
    
    def load_from_path(self, path: Path) -> Optional[PatternPackV1]:
        """Load and validate pattern pack from path."""
        if not path.exists():
            return None
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            valid, error = validate_pattern_pack(data)
            if not valid:
                print(f"[PATTERN_LOADER] Invalid pack {path}: {error}")
                return None
            
            pack = PatternPackV1.from_dict(data)
            return pack
        
        except Exception as e:
            print(f"[PATTERN_LOADER] Error loading {path}: {e}")
            return None
            
    def load_latest_parsed(self) -> Optional[PatternPackV1]:
        """Get cached pack, ensuring reload check first."""
        self.check_reload()
        return self._cached_pack

    def get_pack_meta(self) -> Dict:
        """Get metadata of currently loaded pack."""
        if not self._cached_pack:
            return {"loaded": False}
        return {
            "loaded": True,
            "pack_id": self._cached_pack.pack_id,
            "built_at": self._cached_pack.built_at.isoformat() if hasattr(self._cached_pack.built_at, 'isoformat') else str(self._cached_pack.built_at),
            "hash": self._cached_pack.hash
        }

    def score_symbol(self, symbol: str, tf: str = "15m") -> float:
        """
        Calculate pattern score for a symbol.
        Returns 0..60 score based on patterns present.
        """
    def match_symbol(self, symbol: str, tf: str = "15m", topn: int = 3) -> dict:
        """
        Match patterns for symbol.
        Returns:
            {
                "score": float (0-100),
                "matches": [ {pattern_id, confidence, note, tf, kind} ]
            }
        """
        if not self._cached_pack:
            return {"score": 0.0, "matches": []}
            
        patterns = self._cached_pack.get_patterns_for_symbol(symbol)
        if not patterns:
             return {"score": 0.0, "matches": []}
             
        # Filter by TF if needed? Usually packs are mixed.
        # We process matches.
        
        matches = []
        for p in patterns:
            # v2 support
            conf = p.confidence
            note = p.evidence.get("note", "")
            
            # Legacy v1 fallback: assume score=1.0 if not set but present?
            # Or rely on loader defaulting 0.0.
            # If 0.0, check payload["score"] (v1 internal convention)
            if conf == 0.0:
                 conf = float(p.payload.get("score", 0)) / 100.0 if "score" in p.payload else 0.5 # Default confidence for v1
            
            matches.append({
                "pattern_id": p.pattern_id,
                "confidence": conf,
                "note": note,
                "tf": p.tf,
                "kind": p.kind
            })
            
        # Sort by confidence desc
        matches.sort(key=lambda x: x["confidence"], reverse=True)
        
        # Calculate Deterministic Score
        # Average of top N
        top_matches = matches[:topn]
        if not top_matches:
             return {"score": 0.0, "matches": []}
             
        avg_conf = sum(m["confidence"] for m in top_matches) / len(top_matches)
        
        # Map to 0-100, but clamp to 60 for component weight? 
        # Wait, Scanner expects 0-60 usually for component.
        # But this function returns 0-100 raw score.
        # Scanner will re-scale if needed.
        # Score = avg_conf * 100
        score = min(avg_conf * 100.0, 100.0)

        return {
            "score": score,
            "matches": matches
        }

    def score_symbol(self, symbol: str, tf: str = "15m") -> float:
        """
        Legacy wrapper for score.
        Rescales 0-100 match score to 0-60 component score for backward compat.
        """
        match = self.match_symbol(symbol, tf)
        # Scale 0-100 -> 0-60
        return match["score"] * 0.6

    def _clear_cache(self):
        self._cached_pack = None
        self._cached_path = None
        self._last_mtime = 0.0
