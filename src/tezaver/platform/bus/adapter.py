"""
MX-20001: Bus Adapter Interface and FS Implementation

Provides abstract BusAdapter and FsBusAdapter for artifact storage.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import os
import json
from pathlib import Path


class BusAdapter(ABC):
    """Abstract interface for Bus (artifact store) operations."""
    
    @abstractmethod
    def put_json(self, path: str, obj: Any) -> None:
        """Write JSON object to path."""
        pass
    
    @abstractmethod
    def get_json(self, path: str) -> Optional[Dict]:
        """Read JSON object from path. Returns None if not exists."""
        pass
    
    @abstractmethod
    def list(self, prefix: str) -> List[str]:
        """List all paths under prefix."""
        pass
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if path exists."""
        pass
    
    @abstractmethod
    def append_ndjson(self, path: str, obj: Any) -> None:
        """Append JSON object as newline-delimited JSON."""
        pass
    
    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete path. Returns True if deleted."""
        pass


class FsBusAdapter(BusAdapter):
    """Filesystem implementation of BusAdapter."""
    
    def __init__(self, root_path: str):
        self.root = Path(root_path)
        self.root.mkdir(parents=True, exist_ok=True)
        
    def _full_path(self, path: str) -> Path:
        return self.root / path
        
    def put_json(self, path: str, obj: Any) -> None:
        fp = self._full_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        with open(fp, "w") as f:
            json.dump(obj, f, indent=2)
            
    def get_json(self, path: str) -> Optional[Dict]:
        fp = self._full_path(path)
        if not fp.exists():
            return None
        try:
            with open(fp) as f:
                return json.load(f)
        except Exception:
            return None
            
    def list(self, prefix: str) -> List[str]:
        base = self._full_path(prefix)
        if not base.exists():
            return []
            
        results = []
        for item in base.iterdir():
            rel = str(item.relative_to(self.root))
            results.append(rel)
        return results
        
    def exists(self, path: str) -> bool:
        return self._full_path(path).exists()
        
    def append_ndjson(self, path: str, obj: Any) -> None:
        fp = self._full_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        with open(fp, "a") as f:
            f.write(json.dumps(obj) + "\n")
            
    def delete(self, path: str) -> bool:
        fp = self._full_path(path)
        if fp.exists():
            fp.unlink()
            return True
        return False


class S3BusAdapter(BusAdapter):
    """S3/MinIO implementation stub (to be implemented later)."""
    
    def __init__(self, bucket: str, prefix: str = "", **kwargs):
        self.bucket = bucket
        self.prefix = prefix
        # S3 client would be initialized here
        
    def put_json(self, path: str, obj: Any) -> None:
        raise NotImplementedError("S3 adapter not yet implemented")
        
    def get_json(self, path: str) -> Optional[Dict]:
        raise NotImplementedError("S3 adapter not yet implemented")
        
    def list(self, prefix: str) -> List[str]:
        raise NotImplementedError("S3 adapter not yet implemented")
        
    def exists(self, path: str) -> bool:
        raise NotImplementedError("S3 adapter not yet implemented")
        
    def append_ndjson(self, path: str, obj: Any) -> None:
        raise NotImplementedError("S3 adapter not yet implemented")
        
    def delete(self, path: str) -> bool:
        raise NotImplementedError("S3 adapter not yet implemented")
