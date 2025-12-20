import os
import json
import shutil
from typing import List, Dict, Any

class FileNotifier:
    def __init__(self, home: str):
        self.home = home
        self.active_dir = os.path.join(home, "alerts", "active")
        self.history_dir = os.path.join(home, "alerts", "history")
        os.makedirs(self.active_dir, exist_ok=True)
        os.makedirs(self.history_dir, exist_ok=True)

    def emit_alert(self, alert: Dict[str, Any]) -> None:
        aid = alert["alert_id"]
        # Check if already in active or history (deduplication by ID if persisted)
        # But usually ID includes hash, so uniqueness is guaranteed by ID.
        # We just overwrite safe or ignore if exists.
        path = os.path.join(self.active_dir, f"{aid}.json")
        hist_path = os.path.join(self.history_dir, f"{aid}.json")
        
        if os.path.exists(hist_path):
            return # Already handled
            
        if not os.path.exists(path):
            with open(path, "w") as f:
                json.dump(alert, f, indent=2)

    def list_active(self) -> List[Dict[str, Any]]:
        alerts = []
        if not os.path.exists(self.active_dir): return []
        
        for f in os.listdir(self.active_dir):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(self.active_dir, f)) as fp:
                        alerts.append(json.load(fp))
                except: pass
        # Sort by ts desc
        return sorted(alerts, key=lambda x: x.get("ts", 0), reverse=True)

    def ack(self, alert_id: str) -> None:
        src = os.path.join(self.active_dir, f"{alert_id}.json")
        dst = os.path.join(self.history_dir, f"{alert_id}.json")
        
        if os.path.exists(src):
            shutil.move(src, dst)
