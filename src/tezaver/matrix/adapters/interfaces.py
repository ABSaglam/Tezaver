"""
MX-FINAL-0103: Adapter Interfaces Freeze
Frozen ABC definitions for Matrix adapters.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass


# ============================================================
# DATA PORT INTERFACE
# ============================================================

class DataPort(ABC):
    """
    Abstract base class for data source adapters.
    Contract: Provides historical bar data.
    
    Frozen: v1.0.0
    """
    
    @abstractmethod
    def get_closed_bars(self, symbol: str, timeframe: str) -> List[Any]:
        """
        Get closed bars for symbol/timeframe.
        
        Returns:
            List of Bar objects (ts, open, high, low, close, is_closed)
        """
        pass


class DataFeedPort(ABC):
    """
    Abstract base class for streaming data feeds.
    Contract: Provides bar-by-bar data.
    
    Frozen: v1.0.0
    """
    
    @abstractmethod
    def get_next_bar(self) -> Optional[Dict[str, Any]]:
        """
        Get next closed bar.
        
        Returns:
            Bar dict or None when exhausted
        """
        pass
    
    @abstractmethod
    def reset(self):
        """Reset feed to beginning (for replay)."""
        pass


# ============================================================
# BROKER PORT INTERFACE
# ============================================================

@dataclass
class OrderResult:
    """Broker order result."""
    order_id: str
    status: str  # FILLED, REJECTED, PENDING
    fill_price: Optional[float] = None
    fill_qty: Optional[float] = None
    fee: float = 0.0
    slippage: float = 0.0


class BrokerPort(ABC):
    """
    Abstract base class for broker adapters.
    Contract: Places and manages orders.
    
    Frozen: v1.0.0
    """
    
    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float
    ) -> OrderResult:
        """
        Place an order.
        
        Args:
            symbol: Trading pair
            side: BUY or SELL
            qty: Order quantity
            price: Order price
            
        Returns:
            OrderResult with fill details
        """
        pass
    
    @abstractmethod
    def get_orders(self) -> List[OrderResult]:
        """Get all orders."""
        pass


# ============================================================
# STATE STORE INTERFACE
# ============================================================

class StateStore(ABC):
    """
    Abstract base class for state persistence.
    Contract: Stores and retrieves run state.
    
    Frozen: v1.0.0
    """
    
    @abstractmethod
    def register_run(self, run_id: str, config: Dict) -> Dict:
        """Register a new run."""
        pass
    
    @abstractmethod
    def update_heartbeat(self, run_id: str, bar_count: int, trade_count: int):
        """Update run heartbeat."""
        pass
    
    @abstractmethod
    def update_status(self, run_id: str, status: str):
        """Update run status."""
        pass
    
    @abstractmethod
    def get_run(self, run_id: str) -> Optional[Dict]:
        """Get run by ID."""
        pass
    
    @abstractmethod
    def list_runs(self) -> List[Dict]:
        """List all runs."""
        pass
    
    @abstractmethod
    def save_state(self, run_id: str, positions: List[Dict], orders: List[Dict]):
        """Save reconciliation state."""
        pass
    
    @abstractmethod
    def load_state(self) -> Optional[Dict]:
        """Load reconciliation state."""
        pass
    
    @abstractmethod
    def clear_state(self):
        """Clear reconciliation state."""
        pass


# ============================================================
# TELEMETRY PORT INTERFACE
# ============================================================

class TelemetryPort(ABC):
    """
    Abstract base class for telemetry emission.
    Contract: Emits and stores telemetry events.
    
    Frozen: v1.0.0
    """
    
    @abstractmethod
    def emit(self, kind: str, data: Dict):
        """Emit a telemetry event."""
        pass
    
    @abstractmethod
    def get_events(self) -> List[Dict]:
        """Get all emitted events."""
        pass


# ============================================================
# VERSION INFO
# ============================================================

INTERFACE_VERSION = "1.0.0"
FROZEN_DATE = "2025-12-21"
