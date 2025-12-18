# Tezaver Bulut - Exit Profile Loader
"""
Loads and resolves exit profiles.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.paths import get_data_dir, get_project_root
from tezaver.bulut.schemas.exit_profile_v1 import ExitProfileV1, DEFAULT_EXIT_PROFILE


class ExitProfileLoader:
    """
    Manages exit profiles from JSON files (hot-reloadable).
    """
    
    def __init__(self, config: BulutConfig):
        self._config = config
        self._profiles: Dict[str, ExitProfileV1] = {} # profile_id -> obj
        self._last_reload_ts = 0
        self._profiles_dir = get_data_dir() / "bulut_rules" / "exit_profiles"
        self._profiles_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure defaults (soft check on init, no force, no telemetry)
        self.ensure_defaults(force=False)
        
    def ensure_defaults(self, force: bool = False) -> Dict:
        """
        Copy example profiles from resources if dir is empty or force=True.
        Returns statistics dict.
        """
        result = {
            "ok": True,
            "force": force,
            "copied_count": 0,
            "skipped_existing_count": 0,
            "backup_dir": None,
            "errors": []
        }
        
        # Locate resources
        resource_dir = get_project_root() / "src" / "tezaver" / "bulut" / "resources" / "exit_profiles_examples"
        
        if not resource_dir.exists():
            msg = f"Resources dir not found at {resource_dir}"
            print(f"[EXIT_LOADER] {msg}")
            result["errors"].append(msg)
            result["ok"] = False
            return result

        # Check existing
        existing_files = list(self._profiles_dir.glob("*.json"))
        is_empty = len(existing_files) == 0
        
        if not is_empty and not force:
            # Skip mode
            result["skipped_existing_count"] = len(existing_files)
            # Check if any new files in resource dir are missing in target?
            # User requirement: "force=false (default): sadece eksik profilleri kopyala, mevcutları EZME."
            # So we iterate resources and copy ONLY if not exists.
            
            for item in resource_dir.glob("*.json"):
                target = self._profiles_dir / item.name
                if not target.exists():
                    try:
                        if self._validate_and_copy(item, target):
                            result["copied_count"] += 1
                        else:
                            result["errors"].append(f"Validation failed for {item.name}")
                    except Exception as e:
                        result["errors"].append(str(e))
            
            return result
            
        elif force:
            # Backup Logic
            if not is_empty:
                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_root = get_data_dir() / "bulut_rules" / "exit_profiles_backup" / ts_str
                backup_root.mkdir(parents=True, exist_ok=True)
                
                try:
                    for exist_f in existing_files:
                        shutil.copy2(exist_f, backup_root / exist_f.name)
                    result["backup_dir"] = str(backup_root)
                except Exception as e:
                    result["ok"] = False
                    result["errors"].append(f"Backup failed: {e}")
                    return result

            # Overwrite Logic
            for item in resource_dir.glob("*.json"):
                target = self._profiles_dir / item.name
                try:
                    if self._validate_and_copy(item, target):
                        result["copied_count"] += 1
                    else:
                        result["errors"].append(f"Validation failed for {item.name}")
                except Exception as e:
                    result["errors"].append(str(e))
                    
        else:
            # Empty dir, simple copy
             for item in resource_dir.glob("*.json"):
                target = self._profiles_dir / item.name
                try:
                    if self._validate_and_copy(item, target):
                        result["copied_count"] += 1
                    else:
                        result["errors"].append(f"Validation failed for {item.name}")
                except Exception as e:
                    result["errors"].append(str(e))
                    
        return result

    def _validate_and_copy(self, source: Path, target: Path) -> bool:
        """Validate JSON content then copy."""
        try:
            with open(source, "r") as f:
                data = json.load(f)
            
            # Validation
            if data.get("schema") != "exit_profile_v1":
                return False
            
            required = ["profile_id", "version", "priority", "scope", "rules"]
            for r in required:
                if r not in data:
                    return False
            
            if not isinstance(data["rules"], list) or len(data["rules"]) == 0:
                return False
                
            for rule in data["rules"]:
                if rule.get("type") not in ["fixed_pct", "time_stop"]:
                    return False
            
            # Additional logic can go here (e.g. check types)
            
            shutil.copy2(source, target)
            return True
            
        except Exception:
            return False
        
    def check_reload(self):
        """Check for updates and reload if needed."""
        # Check dir mtime
        try:
            mtime = self._profiles_dir.stat().st_mtime
            if mtime > self._last_reload_ts:
                self._load_profiles()
                self._last_reload_ts = mtime
        except Exception as e:
            print(f"[EXIT_LOADER] Check failed: {e}")

    def _load_profiles(self):
        """Load all JSONs."""
        new_profiles = {}
        
        for p_file in self._profiles_dir.glob("*.json"):
            try:
                with open(p_file, "r") as f:
                    data = json.load(f)
                    
                profile = ExitProfileV1.from_dict(data)
                new_profiles[profile.profile_id] = profile
                
            except Exception as e:
                print(f"[EXIT_LOADER] Error loading {p_file}: {e}")
        
        self._profiles = new_profiles
        print(f"[EXIT_LOADER] Loaded {len(self._profiles)} profiles.")

    def resolve(self, symbol: str, pattern_id: Optional[str]) -> ExitProfileV1:
        """
        Resolve best profile.
        Priority:
        1. Symbol + Pattern Match
        2. Pattern Match (Symbol=null)
        3. Symbol Match (Pattern=null)
        4. Global (both null)
        5. Built-in Default
        """
        # Linear search through loaded profiles sort by priority descending
        # Pre-sorting candidates might be faster but N is small.
        
        candidates = list(self._profiles.values())
        candidates.sort(key=lambda p: p.priority, reverse=True)
        
        best = None
        
        for p in candidates:
            scope_sym = p.scope.symbol
            scope_pat = p.scope.pattern_id
            
            # Check Match
            sym_match = (scope_sym == symbol) or (scope_sym is None)
            pat_match = (scope_pat == pattern_id) or (scope_pat is None)
            
            if sym_match and pat_match:
                # Found a matching scope. Since we sorted by priority, first one is best?
                # Need to check specificity?
                # Usually priority handles specificity.
                # If priority equal, prefer more specific?
                # Simple logic for v0.08: Priority wins.
                best = p
                break
                
        return best or DEFAULT_EXIT_PROFILE
