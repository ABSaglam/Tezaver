# Tezaver Bulut - Risk Rules Bootstrap
"""
Service to bootstrap default risk rules from resources.
Copies JSON files to data/bulut_rules if missing.
"""

import shutil
from pathlib import Path
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.paths import get_project_root
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

class RiskRulesBootstrap:
    def __init__(self, config: BulutConfig, telemetry: NdjsonTelemetry):
        self._config = config
        self._telemetry = telemetry
        
    def ensure_risk_rules(self):
        """
        Ensure risk rule files exist in data dir.
        Copy from resources if missing.
        """
        # Resolve Data Dir
        # Usually repo_root/data/bulut_rules
        # Using config paths
        
        # Resolve Resource Dir: src/tezaver/bulut/resources/risk_examples
        # Relative to this file: ../resources/risk_examples
        resource_dir = Path(__file__).parent.parent / "resources/risk_examples"

        # Resolve Target Paths from Config
        # Config paths like "data/bulut_rules/..."
        # We assume they are relative to REPO_ROOT.
        # And get_project_root() returns `src/tezaver/bulut` ?
        # Let's derive repo_root safely.
        repo_root = Path(__file__).parent.parent.parent.parent.parent
        
        # If running installed package, this might differ, but for mac dev env:
        # tezaver/bulut/services/risk_rules_bootstrap.py
        # parent = services
        # parent.parent = bulut
        # ... = tezaver
        # ... = src
        # ... = TezaverMac (Repo Root)
        
        copied = []
        skipped = []
        
        # Ensure rules dir
        target_groups = repo_root / self._config.symbol_groups_path
        target_caps = repo_root / self._config.group_caps_path
        
        target_groups.parent.mkdir(parents=True, exist_ok=True)
        
        # List of (Source Name, Target Path)
        items = [
            ("symbol_groups.json", target_groups),
            ("group_caps.json", target_caps)
        ]
        
        for fname, target_path in items:
            source_path = resource_dir / fname
            
            if not target_path.exists():
                if source_path.exists():
                    try:
                        shutil.copy(source_path, target_path)
                        print(f"[RISK_BOOTSTRAP] Copied {fname} to {target_path}")
                        copied.append(fname)
                    except Exception as e:
                        print(f"[RISK_BOOTSTRAP] Failed to copy {fname}: {e}")
                else:
                    print(f"[RISK_BOOTSTRAP] Source not found: {source_path}")
            else:
                skipped.append(fname)
                
        # Telemetry
        self._telemetry.emit_custom("RISK_RULES_BOOTSTRAP", {
            "copied": copied,
            "skipped": skipped
        })
