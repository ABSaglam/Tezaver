from typing import Protocol, Dict

class StorePort(Protocol):
    def create_run(self, run_id: str, meta: Dict) -> None:
        """Initializes storage for a new run."""
        ...

    def append_event(self, run_id: str, event: Dict) -> None:
        """Appends a new event to the run's event stream."""
        ...

    def write_gates(self, run_id: str, gates: Dict) -> None:
        """Writes gates evaluation details."""
        ...

    def finalize_run(self, run_id: str) -> None:
        """Marks run as complete (e.g. meta update)."""
        ...

    def write_audit(self, run_id: str, audit: Dict) -> None:
        """Writes trade audit (MX-5002)."""
        ...

    def write_scorecard(self, run_id: str, card: Dict) -> None:
        """Writes jury scorecard (MX-7001)."""
        ...
        
    def write_judge_verdict(self, run_id: str, verdict: Dict) -> None:
        """Writes judge verdict (MX-7002)."""
        ...
