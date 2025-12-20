"""
MX-20001 + MX-24001: Bus Adapter Interface and Implementations

Provides abstract BusAdapter, FsBusAdapter, and S3BusAdapter.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import os
import json
import time
import uuid
from pathlib import Path
from datetime import datetime


class BusAdapter(ABC):
    """Abstract interface for Bus (artifact store) operations."""
    
    @property
    def bus_type(self) -> str:
        """Return bus type identifier."""
        return "abstract"
    
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
        """Append JSON object as newline-delimited JSON (legacy)."""
        pass
    
    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete path. Returns True if deleted."""
        pass
        
    @abstractmethod
    def append_event(self, stream: str, obj: dict) -> str:
        """
        Append event to stream (mac/matrix/cloud).
        
        Returns event ID/key.
        """
        pass
        
    @abstractmethod
    def tail_events(self, stream: str, n: int = 50) -> List[dict]:
        """
        Get last N events from stream.
        
        Returns list of event dicts, newest first.
        """
        pass


class FsBusAdapter(BusAdapter):
    """Filesystem implementation of BusAdapter."""
    
    def __init__(self, root_path: str):
        self.root = Path(root_path)
        self.root.mkdir(parents=True, exist_ok=True)
        
    @property
    def bus_type(self) -> str:
        return "fs"
        
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
        
    def append_event(self, stream: str, obj: dict) -> str:
        """Append event to NDJSON file."""
        path = f"events/{stream}.ndjson"
        self.append_ndjson(path, obj)
        return f"{stream}_{int(time.time() * 1000)}"
        
    def tail_events(self, stream: str, n: int = 50) -> List[dict]:
        """Get last N events from NDJSON file."""
        path = f"events/{stream}.ndjson"
        fp = self._full_path(path)
        
        if not fp.exists():
            return []
            
        try:
            with open(fp) as f:
                lines = f.readlines()
            
            events = []
            for line in lines[-n:]:
                try:
                    events.append(json.loads(line.strip()))
                except:
                    pass
                    
            # Return newest first
            return list(reversed(events))
        except:
            return []


class S3BusAdapter(BusAdapter):
    """S3/MinIO implementation of BusAdapter."""
    
    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        endpoint_url: Optional[str] = None,
        region_name: str = "us-east-1",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.endpoint_url = endpoint_url
        self.region_name = region_name
        
        # Initialize S3 client
        import boto3
        
        client_kwargs = {
            "service_name": "s3",
            "region_name": region_name,
        }
        
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
            
        if access_key and secret_key:
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret_key
            
        self.client = boto3.client(**client_kwargs)
        
    @property
    def bus_type(self) -> str:
        return "s3"
        
    def _full_key(self, path: str) -> str:
        if self.prefix:
            return f"{self.prefix}/{path}"
        return path
        
    def put_json(self, path: str, obj: Any) -> None:
        key = self._full_key(path)
        body = json.dumps(obj, indent=2).encode("utf-8")
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType="application/json")
            
    def get_json(self, path: str) -> Optional[Dict]:
        key = self._full_key(path)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"].read().decode("utf-8")
            return json.loads(body)
        except self.client.exceptions.NoSuchKey:
            return None
        except Exception:
            return None
            
    def list(self, prefix: str) -> List[str]:
        full_prefix = self._full_key(prefix)
        if not full_prefix.endswith("/"):
            full_prefix += "/"
            
        results = []
        paginator = self.client.get_paginator("list_objects_v2")
        
        for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Remove prefix to get relative path
                if self.prefix:
                    rel = key[len(self.prefix) + 1:]
                else:
                    rel = key
                results.append(rel)
                
        return results
        
    def exists(self, path: str) -> bool:
        key = self._full_key(path)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except:
            return False
            
    def append_ndjson(self, path: str, obj: Any) -> None:
        """S3 doesn't support append - use append_event instead."""
        # For backwards compat, create individual event objects
        stream = path.replace("events/", "").replace(".ndjson", "")
        self.append_event(stream, obj)
            
    def delete(self, path: str) -> bool:
        key = self._full_key(path)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except:
            return False
            
    def append_event(self, stream: str, obj: dict) -> str:
        """
        Append event as individual S3 object.
        
        Key format: events/{stream}/YYYY/MM/DD/HH/{ts_ms}_{uuid}.json
        """
        now = datetime.utcnow()
        ts_ms = int(time.time() * 1000)
        event_id = uuid.uuid4().hex[:8]
        
        key = f"events/{stream}/{now.strftime('%Y/%m/%d/%H')}/{ts_ms}_{event_id}.json"
        full_key = self._full_key(key)
        
        body = json.dumps(obj).encode("utf-8")
        self.client.put_object(Bucket=self.bucket, Key=full_key, Body=body, ContentType="application/json")
        
        return f"{ts_ms}_{event_id}"
        
    def tail_events(self, stream: str, n: int = 50) -> List[dict]:
        """
        Get last N events from stream.
        
        Lists objects in stream prefix, sorts by key (ts_ms prefix ensures order),
        gets last N objects.
        """
        prefix = f"events/{stream}/"
        full_prefix = self._full_key(prefix)
        
        # Get all keys (for small n, this is acceptable)
        all_keys = []
        paginator = self.client.get_paginator("list_objects_v2")
        
        for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                all_keys.append(obj["Key"])
                
        # Sort by key (lexicographic works because ts_ms is at end of path)
        all_keys.sort()
        
        # Get last N
        last_n_keys = all_keys[-n:] if len(all_keys) > n else all_keys
        
        # Fetch each object
        events = []
        for key in reversed(last_n_keys):  # Newest first
            try:
                response = self.client.get_object(Bucket=self.bucket, Key=key)
                body = response["Body"].read().decode("utf-8")
                events.append(json.loads(body))
            except:
                pass
                
        return events


def create_bus_adapter(spec: str) -> BusAdapter:
    """
    Create appropriate BusAdapter from spec string.
    
    Args:
        spec: Either a local path (e.g., ".tezaver_bus") 
              or S3 URL (e.g., "s3://bucket/prefix")
              
    Returns:
        FsBusAdapter or S3BusAdapter
    """
    if spec.startswith("s3://"):
        # Parse S3 URL
        # Format: s3://bucket/prefix
        parts = spec[5:].split("/", 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""
        
        # Get credentials from environment
        endpoint_url = os.environ.get("TEZAVER_S3_ENDPOINT_URL")
        access_key = os.environ.get("TEZAVER_S3_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("TEZAVER_S3_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
        region = os.environ.get("TEZAVER_S3_REGION", "us-east-1")
        
        return S3BusAdapter(
            bucket=bucket,
            prefix=prefix,
            endpoint_url=endpoint_url,
            access_key=access_key,
            secret_key=secret_key,
            region_name=region,
        )
    else:
        return FsBusAdapter(spec)
