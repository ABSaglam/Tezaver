"""
Tezaver Matrix - Safety Protocol Registry Logic
Manages the single-source-of-truth for safety protocols and their statuses.
"""
import yaml
import os
import json
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

    def check_evidence(self, mx_code: str, run_dir: Optional[str] = None) -> Dict[str, List[str]]:
        """
        MX-5260: Validates that the evidence listed in the registry actually exists.
        Tr: Registry'de belirtilen kanıtların (telemetry, artifact, test) gerçekten var olduğunu denetler.
        """
        p = self.get_protocol(mx_code)
        if not p: return {"missing": ["Protocol not found"]}
        
        evidence = p.get("evidence", {})
        missing = {
            "telemetry": [],
            "artifacts": [],
            "tests": []
        }
        
        # 1. Check Tests (Static)
        # We assume tests are in the root of the project.
        # registry.py is at src/tezaver/matrix/protocols/safety_registry.py
        # project_root is 5 levels up: src/tezaver/matrix/protocols -> matrix/protocols -> tezaver/matrix -> tezaver -> src -> root
        project_root = self.path
        for _ in range(5):
            project_root = os.path.dirname(project_root)
            
        for test_rel in evidence.get("tests", []):
            test_path = os.path.join(project_root, test_rel)
            if not os.path.exists(test_path):
                missing["tests"].append(test_rel)
                
        # 2. Check Artifacts & Telemetry (Run-scoped)
        if evidence.get("telemetry") or evidence.get("artifacts"):
            if not run_dir or not os.path.exists(run_dir):
                missing["telemetry"] = evidence.get("telemetry", [])
                missing["artifacts"] = evidence.get("artifacts", [])
            else:
                import json
                # Artifacts
                for art_rel in evidence.get("artifacts", []):
                    art_path = os.path.join(run_dir, art_rel)
                    if not os.path.exists(art_path):
                        missing["artifacts"].append(art_rel)
                
                # Telemetry
                tel_path = os.path.join(run_dir, "telemetry.ndjson")
                if not os.path.exists(tel_path):
                    missing["telemetry"] = evidence.get("telemetry", [])
                else:
                    try:
                        found_types = set()
                        with open(tel_path, 'r') as f:
                            for line in f:
                                if not line.strip(): continue
                                evt = json.loads(line)
                                found_types.add(evt.get("event_type") or evt.get("kind"))
                        for expected in evidence.get("telemetry", []):
                            if expected not in found_types:
                                missing["telemetry"].append(expected)
                    except:
                        missing["telemetry"] = evidence.get("telemetry", [])

                        
        return missing

    def get_ui_rows(self, run_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = []
        for p in self.protocols:
            overall = self.get_overall_for_active(p["mx"])
            
            # MX-5260: Drift Check
            drift = self.check_evidence(p["mx"], run_dir)
            missing_flat = [f"🧪 {t}" for t in drift["tests"]] + \
                           [f"📄 {a}" for a in drift["artifacts"]] + \
                           [f"📡 {tel}" for tel in drift["telemetry"]]
            
            evidence_summary = self._summarize_evidence(p.get("evidence", {}))
            if missing_flat:
                evidence_summary += f" | ❌ Missing: {', '.join(missing_flat[:2])}"
                if len(missing_flat) > 2: evidence_summary += "..."

            row = {
                "MX": p["mx"],
                "Protocol": p["name"],
                "Purpose": p.get("purpose", ""),
                "Active In": ", ".join(p.get("active_in", [])),
                "SNIPER": self.format_badge(p["status"].get("SNIPER", "GRAY")),
                "WAR": self.format_badge(p["status"].get("WAR", "GRAY")),
                "LIVE": self.format_badge(p["status"].get("LIVE", "GRAY")),
                "Overall": self.format_badge(overall.value),
                "Evidence": evidence_summary,
                "evidence_ok": not any(drift.values()),
                "missing_details": drift
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
    def check_pool_evidence_contract(
        self,
        run_dir: str,
        stage: str,
        run_id: str,
        pool_enabled: bool = False
    ) -> Dict[str, Any]:
        """
        MX-Phase0.2: Validates the Pool Evidence Contract.

        Args:
            run_dir: Absolute path to the run directory
            stage: Active stage (SNIPER/WAR/LIVE)
            run_id: Run identifier
            pool_enabled: Signal to enable check. If False, returns SKIPPED.

        Returns:
            Dict containing status, missing_ids, checked_ids, summary
        """
        if not pool_enabled:
            return {
                "status": "SKIPPED",
                "missing_ids": [],
                "checked_ids": [],
                "summary": "Pool not enabled for this run"
            }

        # Locate contract file relative to project root
        # safety_registry.py is in src/tezaver/matrix/protocols
        # contract is in reports/pool_evidence_contract_v1.json (root/reports)
        
        # Path logic: currently self.path is .../protocols/safety_protocol_registry.yaml
        # Root is 4 levels up: src/tezaver/matrix/protocols -> matrix/protocols -> tezaver/matrix -> tezaver -> src -> root
        # Wait, self.path is /Users/alisaglam/TezaverMac/src/tezaver/matrix/protocols/safety_protocol_registry.yaml
        # Root (/Users/alisaglam/TezaverMac) is 5 levels up?
        # Let's count dirs:
        # 1. protocols
        # 2. matrix
        # 3. tezaver
        # 4. src
        # 5. TezaverMac (Root)
        
        project_root = self.path
        for _ in range(5):
            project_root = os.path.dirname(project_root)
            
        contract_path = os.path.join(project_root, "reports", "pool_evidence_contract_v1.json")
        
        if not os.path.exists(contract_path):
             return {
                "status": "MISSING",
                "missing_ids": ["pool_evidence_contract_v1.json"],
                "checked_ids": [],
                "summary": "Contract definition file missing"
            }

        try:
            with open(contract_path, "r", encoding="utf-8") as f:
                contract = json.load(f)
        except Exception as e:
            return {
                "status": "ERROR",
                "missing_ids": [],
                "checked_ids": [],
                "summary": f"Failed to parse contract: {e}"
            }

        missing_ids = []
        checked_ids = []
        
        # Normalize stage for comparison (WAR/LIVE)
        stage_norm = stage.upper()
        stage_path_comp = stage.lower()

        for art in contract.get("artifacts", []):
            art_id = art["artifact_id"]
            if stage_norm not in art.get("stages", []):
                continue
                
            checked_ids.append(art_id)
            
            # Resolve path pattern
            # Pattern: out/matrix_runs/<stage>/<run_id>/reports/...
            # We already have run_dir which should be out/matrix_runs/<stage>/<run_id>
            # But wait, run_dir passed to this function might be valid or might be None/partial.
            # Usually run_dir passed to safety_sweep is the absolute path to the run folder.
            # The pattern in JSON is relative-ish but "out/matrix_runs/..." is from root.
            # We should look inside run_dir because run_dir IS the <run_id> folder.
            
            # The pattern is: out/matrix_runs/<stage>/<run_id>/reports/filename.json
            # run_dir is: .../out/matrix_runs/war/run_123
            # So we just need to look for 'reports/filename.json' inside run_dir?
            # Let's check the pattern end.
            
            pattern = art["path_pattern"]
            # Extract filename part: reports/pool_universe_report_v1.json
            # We can robustly assume artifacts are in run_dir/reports/ usually, 
            # but let's try to follow the pattern concept if we can.
            # Actually, standardizing on run_dir is safer as run_dir might be elsewhere during tests or replay.
            
            # Simple header: "path_pattern": "out/matrix_runs/<stage>/<run_id>/reports/pool_universe_report_v1.json"
            filename = os.path.basename(pattern)
            # We assume it is in reports/ subdir as per convention
            target_path = os.path.join(run_dir, "reports", filename)
            
            if not os.path.exists(target_path):
                missing_ids.append(f"{art_id} (File Missing)")
                continue
                
            # Content Check
            if art.get("required_fields"):
                try:
                    with open(target_path, "r", encoding="utf-8") as tf:
                        data = json.load(tf)
                        for field in art["required_fields"]:
                            if field not in data:
                                missing_ids.append(f"{art_id} (Missing Field: {field})")
                                break # One missing field is enough to fail this artifact
                except Exception as e:
                    missing_ids.append(f"{art_id} (Corrupt JSON: {e})")
                    
        status = "OK" if not missing_ids else "MISSING"
        summary = "All artifacts present" if status == "OK" else f"Missing {len(missing_ids)} artifacts"
        
        return {
            "status": status,
            "missing_ids": missing_ids,
            "checked_ids": checked_ids,
            "summary": summary,
            "contract_version": contract.get("version", "unknown")
        }

