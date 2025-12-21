"""
Tezaver Matrix - Safety Protocol Registry Logic
Manages the single-source-of-truth for safety protocols and their statuses.
"""
import yaml
import os
from enum import Enum
from typing import List, Dict, Any, Optional

class SafetyStatus(Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    GRAY = "GRAY"
    LOCKED = "LOCKED"

STATUS_METADATA = {
    SafetyStatus.GREEN: {"emoji": "🟩", "label": "GREEN", "weight": 1},
    SafetyStatus.YELLOW: {"emoji": "🟨", "label": "YELLOW", "weight": 2},
    SafetyStatus.RED: {"emoji": "🟥", "label": "RED", "weight": 3},
    SafetyStatus.GRAY: {"emoji": "⬜", "label": "GRAY", "weight": 0},
    SafetyStatus.LOCKED: {"emoji": "🔒", "label": "LOCKED", "weight": 4},
}

class SafetyProtocolRegistry:
    def __init__(self, path: Optional[str] = None):
        if path is None:
            # Resolve default path relative to this file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base_dir, "safety_protocol_registry.yaml")
        
        self.path = path
        self.data = self._load_yaml()
        self.protocols = self.data.get("protocols", [])
        self.version = self.data.get("version", "unknown")
        self.cloud_locked = self.data.get("cloud_locked", False)

    def _load_yaml(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Safety registry not found at: {self.path}")
        
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except ImportError:
            raise ImportError("PyYAML is required to load the safety registry. Please run 'pip install PyYAML'.")
        except Exception as e:
            raise RuntimeError(f"Failed to load safety registry: {e}")

    def get_protocol(self, mx_code: str) -> Optional[Dict[str, Any]]:
        for p in self.protocols:
            if p.get("mx") == mx_code:
                return p
        return None

    def compute_overall_status(self, protocol_mx: str, stage: str = "LIVE") -> SafetyStatus:
        """
        Compute worst-of-active status for a specific stage or 'all active'.
        Weight: RED (3) > YELLOW (2) > GREEN (1) > GRAY (0). LOCKED (4) is terminal.
        """
        p = self.get_protocol(protocol_mx)
        if not p:
            return SafetyStatus.GRAY
        
        active_in = p.get("active_in", [])
        statuses = p.get("status", {})
        
        # If cloud_locked and this is a cloud protocol, it might be LOCKED.
        # For now we use the status in the YAML.
        
        current_status_str = statuses.get(stage, "GRAY")
        return SafetyStatus(current_status_str)

    def get_overall_for_active(self, protocol_mx: str) -> SafetyStatus:
        """Worst-of status across all active_in stages."""
        p = self.get_protocol(protocol_mx)
        if not p:
            return SafetyStatus.GRAY
        
        active_in = p.get("active_in", [])
        statuses = p.get("status", {})
        
        worst_weight = -1
        worst_status = SafetyStatus.GRAY
        
        for stage in active_in:
            s_str = statuses.get(stage, "GRAY")
            try:
                s_enum = SafetyStatus(s_str)
                weight = STATUS_METADATA[s_enum]["weight"]
                if weight > worst_weight:
                    worst_weight = weight
                    worst_status = s_enum
            except:
                continue
                
        return worst_status

    def get_ui_rows(self) -> List[Dict[str, Any]]:
        rows = []
        for p in self.protocols:
            overall = self.get_overall_for_active(p["mx"])
            row = {
                "MX": p["mx"],
                "Protocol": p["name"],
                "Purpose": p.get("purpose", ""),
                "Active In": ", ".join(p.get("active_in", [])),
                "SNIPER": self.format_badge(p["status"].get("SNIPER", "GRAY")),
                "WAR": self.format_badge(p["status"].get("WAR", "GRAY")),
                "LIVE": self.format_badge(p["status"].get("LIVE", "GRAY")),
                "Overall": self.format_badge(overall.value),
                "Evidence": self._summarize_evidence(p.get("evidence", {}))
            }
            rows.append(row)
        return rows

    def format_badge(self, status_str: str) -> str:
        try:
            s_enum = SafetyStatus(status_str)
            meta = STATUS_METADATA[s_enum]
            return f"{meta['emoji']} {meta['label']}"
        except:
            return f"❓ {status_str}"

    def _summarize_evidence(self, evidence: Dict[str, List[Any]]) -> str:
        parts = []
        if evidence.get("telemetry"): parts.append(f"📡 {len(evidence['telemetry'])}")
        if evidence.get("tests"): parts.append(f"🧪 {len(evidence['tests'])}")
        if evidence.get("artifacts"): parts.append(f"📄 {len(evidence['artifacts'])}")
        if evidence.get("ui"): parts.append(f"🖥️ {len(evidence['ui'])}")
        return " ".join(parts) if parts else "No evidence"
