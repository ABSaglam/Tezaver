"""
MX-3021: IncidentBundle - Creates evidence bundles for LIVE incidents.
"""
import json
import traceback
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import hashlib


class IncidentBundle:
    """
    MX-3021: IncidentBundle
    Creates evidence bundles for LIVE trading incidents.
    """
    
    def __init__(self, output_dir: str = "out/matrix_incidents/live"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create(
        self,
        run_id: str,
        incident_type: str,
        telemetry_events: List[Dict],
        config: Dict = None,
        candidate_summary: Dict = None,
        exception: Exception = None,
        extra_data: Dict = None
    ) -> str:
        """
        Create an incident bundle.
        Returns: incident_id
        """
        # Generate incident ID
        incident_content = f"{run_id}_{incident_type}_{datetime.now().isoformat()}"
        incident_id = f"inc_{hashlib.sha256(incident_content.encode()).hexdigest()[:12]}"
        
        incident_dir = self.output_dir / incident_id
        incident_dir.mkdir(parents=True, exist_ok=True)
        
        # Bundle manifest
        manifest = {
            "incident_id": incident_id,
            "run_id": run_id,
            "incident_type": incident_type,
            "created_at": datetime.now().isoformat(),
            "has_stacktrace": exception is not None,
            "telemetry_event_count": len(telemetry_events),
            "has_config": config is not None,
            "has_candidate_summary": candidate_summary is not None
        }
        
        # Save manifest
        with open(incident_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
        
        # Save last N telemetry events
        with open(incident_dir / "telemetry_snapshot.ndjson", "w") as f:
            for event in telemetry_events[-100:]:  # Last 100 events
                f.write(json.dumps(event) + "\n")
        
        # Save config snapshot
        if config:
            with open(incident_dir / "config_snapshot.json", "w") as f:
                json.dump(config, f, indent=2)
        
        # Save candidate summary
        if candidate_summary:
            with open(incident_dir / "candidate_summary.json", "w") as f:
                json.dump(candidate_summary, f, indent=2)
        
        # Save stacktrace
        if exception:
            with open(incident_dir / "stacktrace.txt", "w") as f:
                f.write(f"Exception Type: {type(exception).__name__}\n")
                f.write(f"Message: {str(exception)}\n\n")
                f.write("Full Traceback:\n")
                f.write(traceback.format_exc())
        
        # Save extra data
        if extra_data:
            with open(incident_dir / "extra_data.json", "w") as f:
                json.dump(extra_data, f, indent=2)
        
        return incident_id
    
    def list_incidents(self, run_id: str = None) -> List[Dict]:
        """List all incidents, optionally filtered by run_id."""
        incidents = []
        
        for incident_dir in self.output_dir.iterdir():
            if not incident_dir.is_dir():
                continue
            
            manifest_path = incident_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
                
                if run_id and manifest.get("run_id") != run_id:
                    continue
                
                incidents.append(manifest)
            except:
                continue
        
        return sorted(incidents, key=lambda x: x.get("created_at", ""), reverse=True)
    
    def get_incident(self, incident_id: str) -> Optional[Dict]:
        """Get full incident data."""
        incident_dir = self.output_dir / incident_id
        if not incident_dir.exists():
            return None
        
        manifest_path = incident_dir / "manifest.json"
        if not manifest_path.exists():
            return None
        
        with open(manifest_path) as f:
            data = json.load(f)
        
        data["path"] = str(incident_dir)
        return data
