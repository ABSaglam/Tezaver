"""
Bundle Certification Registry
=============================

Persistent storage for tracking bundle promotion status (War -> Live).
Entities move from 'candidate' to 'certified' based on Matrix simulation performance.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Constants for stages (3-Tier Hierarchy)
STAGE_CANDIDATE = "candidate"        # Phase 1: In Sniper Lab (Target: Benchmark PnL)
STAGE_SNIPER_PASSED = "sniper_passed" # Phase 2: In War Arena (Target: WinRate) -> Suffix -S
STAGE_LIVE_CERTIFIED = "live_certified" # Phase 3: In Live Execution -> Suffix -SW
STAGE_VETERAN = "veteran"            # Phase 4: Proven in Live (Cloud Ready) -> Suffix -SWL
STAGE_DEMOTED = "demoted"

DEFAULT_REGISTRY_PATH = Path("data/matrix/certification_registry.json")

class CertificationRegistry:
    def __init__(self, registry_path: Path = DEFAULT_REGISTRY_PATH):
        self.registry_path = registry_path
        self.data: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self):
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load certification registry: {e}")
                self.data = {}
        else:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            self.data = {}

    def save(self):
        try:
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save certification registry: {e}")

    def get_bundle_stage(self, bundle_id: str) -> str:
        """Returns the current stage of a bundle. Defaults to 'candidate'."""
        entry = self.data.get(bundle_id)
        if not entry:
            return STAGE_CANDIDATE
        return entry.get("stage", STAGE_CANDIDATE)

    def get_qualified_id(self, bundle_id: str) -> str:
        """
        Returns the Bundle ID with dynamic suffixes based on stage.
        - Sniper Passed -> ID-S
        - Live Certified (War Passed) -> ID-SW
        - Veteran (Live Passed) -> ID-SWL
        """
        stage = self.get_bundle_stage(bundle_id)
        
        suffix = ""
        if stage == STAGE_SNIPER_PASSED:
            suffix = "-S"
        elif stage == STAGE_LIVE_CERTIFIED:
            suffix = "-SW"
        elif stage == STAGE_VETERAN:
            suffix = "-SWL"
            
        return f"{bundle_id}{suffix}"

    def certify_sniper_pass(self, bundle_id: str, reason: str = "Benchmark Target Met", metrics: Dict[str, Any] = None):
        """Promotes a bundle to 'sniper_passed' stage (War Ready)."""
        data = {
            "stage": STAGE_SNIPER_PASSED,
            "passed_at": datetime.now().isoformat(),
            "reason": reason
        }
        if metrics:
            data["metrics"] = metrics
            
        self.data[bundle_id] = data
        self.save()
        logger.info(f"Bundle {bundle_id} SNIPER PASSED: {reason} | Metrics: {metrics}")

    def certify_live_ready(self, bundle_id: str, reason: str = "War Simulation Proven", metrics: Dict[str, Any] = None):
        """Promotes a bundle to 'live_certified' stage (Live Ready)."""
        data = {
            "stage": STAGE_LIVE_CERTIFIED,
            "certified_at": datetime.now().isoformat(),
            "reason": reason
        }
        if metrics:
            data["metrics"] = metrics
            
        self.data[bundle_id] = data
        self.save()
        logger.info(f"Bundle {bundle_id} LIVE CERTIFIED: {reason} | Metrics: {metrics}")

    def certify_veteran(self, bundle_id: str, reason: str = "Live Proven", metrics: Dict[str, Any] = None):
        """Promotes a bundle to 'veteran' stage (Cloud Ready)."""
        data = {
            "stage": STAGE_VETERAN,
            "certified_at": datetime.now().isoformat(),
            "reason": reason
        }
        if metrics:
            data["metrics"] = metrics
            
        self.data[bundle_id] = data
        self.save()
        logger.info(f"Bundle {bundle_id} VETERAN: {reason} | Metrics: {metrics}")

    def demote_bundle(self, bundle_id: str, reason: str = "Performance degradation", metrics: Dict[str, Any] = None):
        """Demotes a bundle back to 'candidate' or 'demoted'."""
        data = {
            "stage": STAGE_DEMOTED,
            "demoted_at": datetime.now().isoformat(),
            "reason": reason
        }
        if metrics:
            data["metrics"] = metrics
            
        self.data[bundle_id] = data
        self.save()
        logger.info(f"Bundle {bundle_id} DEMOTED: {reason} | Metrics: {metrics}")

    def reset_bundle(self, bundle_id: str):
        """Resets a bundle to 'candidate' stage."""
        if bundle_id in self.data:
            del self.data[bundle_id]
            self.save()
            logger.info(f"Bundle {bundle_id} RESET to candidate")
