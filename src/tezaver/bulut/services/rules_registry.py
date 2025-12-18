import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.rules_validator import RulesValidator

class RulesRegistry:
    """
    Manages access to configuration rules (allowlists, groups, profiles).
    Handles reading, writing, backups, and validation.
    """
    
    # Path mappings (relative to project root usually, but we use absolute resolved paths or config based)
    # Assuming run from project root or paths are relative to it.
    # Safe list of editable files.
    
    def __init__(self, config: BulutConfig, base_path: Path):
        self.config = config
        self.base_path = base_path
        self.validator = RulesValidator()
        
        # Define allowed keys and paths
        self.path_map = {
            "allowlist": "data/universe/allowlist.txt",
            "mainnet_allowlist": "data/bulut_rules/mainnet_allowlist.txt",
            "symbol_groups": "data/bulut_rules/symbol_groups.json",
            "group_caps": "data/bulut_rules/group_caps.json",
        }
        self.exit_profile_dir = "data/bulut_rules/exit_profiles"
        
    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve path and ensure it's within bounds."""
        # For simplicity, assuming base_path is project root.
        # Simple security sanity check against .. traversal
        if ".." in relative_path:
            raise ValueError("Invalid path traversal")
        return self.base_path / relative_path

    def list_rules(self) -> List[dict]:
        res = []
        for key, rel_path in self.path_map.items():
            p = self._resolve_path(rel_path)
            res.append({
                "key": key,
                "path": rel_path,
                "exists": p.exists(),
                "type": "json" if rel_path.endswith(".json") else "text"
            })
        return res
        
    def list_exit_profiles(self) -> List[str]:
        p = self._resolve_path(self.exit_profile_dir)
        if not p.exists(): return []
        return [f.name for f in p.glob("*.json")]

    def read_text(self, key: str) -> str:
        if key not in self.path_map: raise ValueError("Unknown key")
        p = self._resolve_path(self.path_map[key])
        if not p.exists(): return ""
        return p.read_text(encoding="utf-8")
        
    def read_json(self, key: str) -> Any:
        # Generic read json or text parsed as json
        content = self.read_text(key)
        if not content: return {}
        return json.loads(content)

    def read_exit_profile(self, filename: str) -> dict:
        # Validate filename
        if not filename.endswith(".json") or ".." in filename or "/" in filename:
            raise ValueError("Invalid filename")
        p = self._resolve_path(f"{self.exit_profile_dir}/{filename}")
        if not p.exists(): return {}
        return json.loads(p.read_text(encoding="utf-8"))

    def _create_backup(self, path: Path):
        if not path.exists(): return
        
        backup_root = self._resolve_path(self.config.rules_backup_dir)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = backup_root / ts
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        shutil.copy2(path, backup_dir / path.name)
        
    def write_text(self, key: str, content: str, user_backup: bool = True):
        if key not in self.path_map: raise ValueError("Unknown key")
        p = self._resolve_path(self.path_map[key])
        
        # Max Size Check
        if len(content.encode("utf-8")) > self.config.rules_max_size_kb * 1024:
             raise ValueError(f"Content exceeds {self.config.rules_max_size_kb}KB limit")
             
        # Validate content based on key
        if key.endswith("allowlist"):
            res = self.validator.validate_allowlist(content)
            if not res["ok"]: raise ValueError(f"Validation failed: {res['errors']}")
            
        # Ensure parent
        p.parent.mkdir(parents=True, exist_ok=True)
        
        if user_backup:
            self._create_backup(p)
            
        p.write_text(content, encoding="utf-8")
        
    def write_json(self, key: str, obj: Any, user_backup: bool = True):
        if key not in self.path_map: raise ValueError("Unknown key")
        
        # Validate
        if key == "symbol_groups":
            res = self.validator.validate_symbol_groups(obj)
        elif key == "group_caps":
            res = self.validator.validate_group_caps(obj)
        else:
            # Check JSON serializable
            res = {"ok": True}
            
        if not res.get("ok", True):
             raise ValueError(f"Validation failed: {res.get('errors')}")
             
        text = json.dumps(obj, indent=2, ensure_ascii=False)
        self.write_text(key, text, user_backup)

    def write_exit_profile(self, filename: str, obj: Any, user_backup: bool = True):
        if not filename.endswith(".json") or ".." in filename or "/" in filename:
            raise ValueError("Invalid filename")
            
        # Validate
        res = self.validator.validate_exit_profile(obj)
        if not res["ok"]:
             raise ValueError(f"Validation failed: {res['errors']}")
             
        text = json.dumps(obj, indent=2, ensure_ascii=False)
        p = self._resolve_path(f"{self.exit_profile_dir}/{filename}")
        
        # Max Size Check
        if len(text.encode("utf-8")) > self.config.rules_max_size_kb * 1024:
             raise ValueError(f"Content exceeds limit")
             
        p.parent.mkdir(parents=True, exist_ok=True)
        
        if user_backup:
            self._create_backup(p)
            
        p.write_text(text, encoding="utf-8")
