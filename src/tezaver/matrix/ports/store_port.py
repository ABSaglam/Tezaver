from typing import Protocol, Dict

class StorePort(Protocol):
    def create_run(self, run_id: str, meta: Dict) -> None:
        """Initializes storage for a new run."""
        ...

    def append_event(self, run_id: str, event: Dict) -> None:
        """Appends a new event to the run's event stream."""
        ...

    def write_gates(self, run_id: str, gates: Dict) -> None:
        """Writes or updates (overwrites) the gates snapshot."""
        ...

    def finalize_run(self, run_id: str) -> None:
        """Performs any final cleanup or summary generation for the run."""
        ...
