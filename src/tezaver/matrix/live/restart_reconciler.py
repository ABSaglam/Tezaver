import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from tezaver.matrix.ports.broker_port import BrokerPort

@dataclass
class ReconciliationReport:
    """Report detailing reconciliation findings and actions."""
    status: str = "PENDING"
    run_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    unknown_orders: List[Dict] = field(default_factory=list)
    orphan_positions: List[Dict] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    ok: bool = True

class RestartReconciler:
    """
    MX-5140: Restart Reconciliation Logic.
    Handles exchange-level state verification and cleanup on engine restart.
    """
    def __init__(self, policy: Dict = None):
        self.policy = policy or {
            "cancel_unknown": True,
            "flatten_orphans": "safe_mode" # or "flatten" or "none"
        }

    def reconcile(self, 
                  broker: BrokerPort, 
                  run_id: str,
                  expected_orders: List[str], 
                  expected_symbols: List[str]) -> ReconciliationReport:
        """
        Tr: Restart anında borsa açık emirlerini ve pozisyonlarını kontrol eder.
        Beklenmeyen durumları (unknown order/orphan position) raporlar ve temizler.
        """
        report = ReconciliationReport(run_id=run_id)
        
        # 1. Open Orders Check
        try:
            exchange_orders = broker.get_open_orders()
            for eo in exchange_orders:
                oid = eo.get("order_id") or eo.get("id")
                if oid not in expected_orders:
                    report.unknown_orders.append(eo)
        except Exception as e:
            logging.error(f"Reconciliation error fetching orders: {e}")
            report.ok = False
            
        # 2. Open Positions Check
        try:
            exchange_positions = broker.get_positions()
            for ep in exchange_positions:
                symbol = ep.get("symbol")
                # If we have a position in a symbol not in our current play, or unexpectedly
                if symbol not in expected_symbols or ep.get("qty", 0) != 0:
                    # In v1, we consider any non-zero position an orphan if not matched in state
                    # (Assuming expected_positions is not yet fully implemented, we check symbol scope)
                    report.orphan_positions.append(ep)
        except Exception as e:
            logging.error(f"Reconciliation error fetching positions: {e}")
            report.ok = False

        # 3. Corrective Actions based on Policy
        if report.unknown_orders and self.policy.get("cancel_unknown"):
            for uo in report.unknown_orders:
                oid = uo.get("order_id") or uo.get("id")
                try:
                    broker.cancel_order(oid)
                    report.actions_taken.append(f"CANCEL_UNKNOWN_ORDER:{oid}")
                except Exception as e:
                    logging.error(f"Failed to cancel unknown order {oid}: {e}")

        # Note: Flattening is high risk, v1 logic mainly reports or triggers safe_mode via engine.
        
        if report.orphan_positions:
            report.actions_taken.append(f"ORPHAN_POSITIONS_DETECTED:{len(report.orphan_positions)}")
            if self.policy.get("flatten_orphans") == "safe_mode":
                report.ok = False # Force inconsistency/safe_mode

        report.status = "SUCCESS" if report.ok else "INCONSISTENT"
        return report
