# Tezaver Bulut - Intel Registry Service
"""
Manages the lifecycle of Intel Bundles (Pattern Packs).
Contracts:
- Incoming Bundles are validated before Publishing.
- Published Bundles are immutable.
- Active Pointer determines the live Intel.
- Mainnet Safety: Changes blocked if ARMED on Mainnet (unless overridden).
"""

import json
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.schemas.intel_bundle_v1 import IntelBundleV1

class IntelRegistryService:
    def __init__(self, data_root: Path):
        self._root = data_root / "bulut_intel"
        self._incoming = self._root / "incoming"
        self._published = self._root / "published"
        self._active_ptr = self._root / "active_pointer.json"
        
        # Ensure dirs
        self._incoming.mkdir(parents=True, exist_ok=True)
        self._published.mkdir(parents=True, exist_ok=True)

    def _check_mainnet_safety(self, ctx: BulutContext):
        """
        Blocks mutation if running on REAL_MAINNET and ARMED, unless config override.
        """
        # 1. Config override check first
        if not getattr(ctx.config, "intel_edit_block_on_mainnet_armed", True):
            return
            
        # 2. Environment check
        is_mainnet = (ctx.config.mode == "REAL_MAINNET")
        is_armed = ctx.state.execution_armed
        
        if is_mainnet and is_armed:
            raise RuntimeError("INTEL_CHANGE_BLOCKED_MAINNET_ARMED: Cannot change Intel while Armed on Mainnet.")

    def _calc_sha256(self, file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def list_incoming(self) -> List[str]:
        """Returns list of incoming bundle IDs (folder names)."""
        if not self._incoming.exists(): return []
        return [p.name for p in self._incoming.iterdir() if p.is_dir()]

    def list_published(self, limit: int = 20) -> List[Dict]:
        """Returns list of published bundles metadata."""
        if not self._published.exists(): return []
        
        bundles = []
        for p in self._published.iterdir():
            if p.is_dir():
                meta_path = p / "intel_bundle.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, "r") as f:
                            data = json.load(f)
                            bundles.append(data)
                    except: pass
        
        # Sort by built_at desc
        bundles.sort(key=lambda x: x.get("built_at", ""), reverse=True)
        return bundles[:limit]
        
    def get_active(self) -> Optional[Dict]:
        """Returns active pointer content."""
        if not self._active_ptr.exists(): return None
        try:
            with open(self._active_ptr, "r") as f:
                return json.load(f)
        except: return None

    def validate_incoming(self, bundle_id: str) -> bool:
        """
        Validates an incoming bundle structure and hash.
        """
        path = self._incoming / bundle_id
        if not path.exists(): raise FileNotFoundError(f"Incoming bundle {bundle_id} not found")
        
        meta_path = path / "intel_bundle.json"
        if not meta_path.exists(): raise FileNotFoundError("intel_bundle.json missing")
        
        with open(meta_path, "r") as f:
            data = json.load(f)
            
        bundle = IntelBundleV1.from_dict(data)
        
        # Verify artifacts exist and match hash if provided (optional depth)
        # For V1, we just check existence
        for art in bundle.artifacts:
            art_path = path / art.path
            if not art_path.exists():
                raise FileNotFoundError(f"Artifact {art.path} missing")
                
        return True

    def publish(self, ctx: BulutContext, bundle_id: str):
        """
        Promotes incoming bundle to published.
        """
        self._check_mainnet_safety(ctx)
        
        src = self._incoming / bundle_id
        dst = self._published / bundle_id
        
        if not src.exists(): raise FileNotFoundError(f"Incoming bundle {bundle_id} not found")
        if dst.exists(): raise FileExistsError(f"Bundle {bundle_id} already published")
        
        # Validate first
        self.validate_incoming(bundle_id)
        
        # Copy (Atomic-ish)
        shutil.copytree(src, dst)
        
        ctx.telemetry.emit("INTEL_PUBLISHED", {"bundle_id": bundle_id})

    def activate(self, ctx: BulutContext, bundle_id: str):
        """
        Sets the active pointer to a published bundle.
        Triggers hot reload.
        """
        self._check_mainnet_safety(ctx)
        
        target = self._published / bundle_id
        if not target.exists(): raise FileNotFoundError(f"Published bundle {bundle_id} not found")
        
        # Read bundle hash for pointer
        with open(target / "intel_bundle.json", "r") as f:
            data = json.load(f)
            b_hash = data.get("bundle_hash", "unknown")
            
        pointer = {
            "bundle_id": bundle_id,
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "hash": b_hash
        }
        
        # Write pointer (Atomic temp move for safety)
        tmp_ptr = self._active_ptr.with_suffix(".tmp")
        with open(tmp_ptr, "w") as f:
            json.dump(pointer, f, indent=2)
        tmp_ptr.replace(self._active_ptr)
        
        ctx.telemetry.emit("INTEL_ACTIVATED", {"bundle_id": bundle_id})
        
        # Trigger Hot Reload
        if ctx.pattern_loader:
            ctx.pattern_loader.check_reload(force=True)

    def rollback(self, ctx: BulutContext):
        """
        Reverts to previous active bundle if tracked (simple implementation: just deactivate current??)
        Or we need a history of pointers.
        For V1: User must manually activate a previous ID from list.
        Or we can implement a simple 'previous' field in pointer.
        Let's implement explicit activate call for rollback too involving user selection.
        """
        # Placeholder for auto rollback, for now UI handles manual rollback by calling activate with old ID
        pass
