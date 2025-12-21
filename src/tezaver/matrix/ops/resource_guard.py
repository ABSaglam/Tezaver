import os
import shutil
import logging
import resource
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

class ResourceGuard:
    """
    MX-5240: Resource Exhaustion Guardrail.
    Monitors Disk, RAM (RSS), and FDs to trigger safe-mode and prevent crashes.
    """
    def __init__(self, 
                 disk_min_mb: float = 100.0, 
                 rss_max_mb: float = 2048.0, 
                 fd_max: int = 800):
        self.thresholds = {
            "disk_min_mb": disk_min_mb,
            "rss_max_mb": rss_max_mb,
            "fd_max": fd_max
        }
        self.last_check = {}

    def get_rss_mb(self) -> float:
        """Returns current process Resident Set Size in MB."""
        # resource.getrusage returns bytes on macOS, kilobytes on Linux.
        # On macOS (darwin), it is in bytes.
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        import sys
        if sys.platform == 'darwin':
            return usage / (1024 * 1024)
        else:
            return usage / 1024

    def get_fd_count(self) -> Optional[int]:
        """Returns count of open file descriptors."""
        try:
            # /dev/fd or /proc/self/fd
            fd_path = "/dev/fd" if os.path.exists("/dev/fd") else "/proc/self/fd"
            if os.path.exists(fd_path):
                return len(os.listdir(fd_path))
        except:
            pass
        return None

    def check_resources(self, root_path: Path) -> Dict[str, Any]:
        """
        Main check logic.
        Tr: Kaynak kullanımını kontrol eder ve eşik değerleri aşılmışsa raporlar.
        """
        # Disk usage
        disk_usage = shutil.disk_usage(root_path)
        disk_free_mb = disk_usage.free / (1024 * 1024)
        
        # RAM usage
        rss_mb = self.get_rss_mb()
        
        # FD count
        fd_count = self.get_fd_count()
        
        reasons = []
        if disk_free_mb < self.thresholds["disk_min_mb"]:
            reasons.append(f"LOW_DISK: {disk_free_mb:.1f}MB < {self.thresholds['disk_min_mb']}MB")
            
        if rss_mb > self.thresholds["rss_max_mb"]:
            reasons.append(f"HIGH_RSS: {rss_mb:.1f}MB > {self.thresholds['rss_max_mb']}MB")
            
        if fd_count and fd_count > self.thresholds["fd_max"]:
            reasons.append(f"HIGH_FD: {fd_count} > {self.thresholds['fd_max']}")

        result = {
            "ok": len(reasons) == 0,
            "reasons": reasons,
            "metrics": {
                "disk_free_mb": round(disk_free_mb, 2),
                "rss_mb": round(rss_mb, 2),
                "fd_used": fd_count
            },
            "thresholds": self.thresholds,
            "ts": datetime.now().isoformat()
        }
        self.last_check = result
        return result
