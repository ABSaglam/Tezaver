"""
CLOUD-1040: CloudEngine - Cloud-adapted trading engine.
Symmetric with Matrix LiveEngine, uses cloud adapters.
"""
import json
import hashlib
import signal
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from tezaver.cloud.adapters.data_feed_port import DataFeedPort, create_data_feed
from tezaver.cloud.adapters.broker_port_paper import CloudBrokerPaper
from tezaver.cloud.adapters.state_store import CloudStateStore


class CloudEngine:
    """
    CLOUD-1040: Cloud trading engine.
    Symmetric telemetry with Matrix LiveEngine.
    """
    
    def __init__(
        self,
        symbols: List[str],
        tf: str = "15m",
        mode: str = "PAPER",
        data_mode: str = "REPLAY",
        output_dir: str = "out/cloud_runs",
        fee_pct: float = 0.001,
        slippage_pct: float = 0.0005
    ):
        self.symbols = symbols
        self.tf = tf
        self.mode = mode
        self.data_mode = data_mode
        self.output_dir = Path(output_dir)
        
        # Generate run_id
        run_content = f"cloud_{symbols}_{tf}_{datetime.now().isoformat()}"
        self.run_id = f"cloud_{hashlib.sha256(run_content.encode()).hexdigest()[:12]}"
        
        # Adapters
        self.data_feeds: Dict[str, DataFeedPort] = {}
        for sym in symbols:
            self.data_feeds[sym] = create_data_feed(data_mode, sym, tf)
        
        self.broker = CloudBrokerPaper(fee_pct=fee_pct, slippage_pct=slippage_pct)
        self.state_store = CloudStateStore()
        
        # State
        self.running = False
        self.safe_mode = False
        self.bar_count = 0
        self.trade_count = 0
        self.telemetry: List[Dict] = []
        self.open_positions: Dict[str, Dict] = {}
        
        # Output
        self.run_dir = self.output_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        # Signal handlers
        self._setup_signals()
    
    def _setup_signals(self):
        """Setup graceful shutdown handlers."""
        def handle_stop(signum, frame):
            self._emit("SIGNAL_STOP", {"signal": signum})
            self.running = False
        
        signal.signal(signal.SIGTERM, handle_stop)
        signal.signal(signal.SIGINT, handle_stop)
    
    def run(self, max_bars: int = None) -> Dict:
        """
        Run the cloud engine.
        max_bars: for testing, None = infinite
        """
        # Reconciliation check
        recon = self.state_store.check_reconciliation(self.run_id)
        if recon["safe_mode"]:
            self.safe_mode = True
            self._emit("SAFE_MODE_ENABLED", {"issues": recon["issues"]})
        
        self._emit("RECONCILE_RESULT", recon)
        
        # Register run
        self.state_store.register_run(self.run_id, {
            "symbols": self.symbols,
            "tf": self.tf,
            "mode": self.mode,
            "data_mode": self.data_mode
        })
        
        self._emit("CLOUD_START", {
            "run_id": self.run_id,
            "symbols": self.symbols,
            "mode": self.mode,
            "safe_mode": self.safe_mode
        })
        
        self.running = True
        
        try:
            self._run_loop(max_bars)
        except Exception as e:
            self._emit("CLOUD_ERROR", {"error": str(e)})
            self.state_store.update_status(self.run_id, "ERROR")
        finally:
            self._stop()
        
        return {
            "run_id": self.run_id,
            "status": "STOPPED",
            "bar_count": self.bar_count,
            "trade_count": self.trade_count,
            "safe_mode": self.safe_mode,
            "artifacts_dir": str(self.run_dir)
        }
    
    def _run_loop(self, max_bars: int = None):
        """Main closed-bar loop."""
        while self.running:
            # Get next bar from each feed
            bars = {}
            all_exhausted = True
            
            for sym, feed in self.data_feeds.items():
                bar = feed.get_next_bar()
                if bar:
                    bars[sym] = bar
                    all_exhausted = False
            
            if all_exhausted:
                break
            
            # Process closed bars
            self._process_bars(bars)
            
            self.bar_count += 1
            
            # Heartbeat
            self.state_store.update_heartbeat(self.run_id, self.bar_count, self.trade_count)
            
            # Max bars check
            if max_bars and self.bar_count >= max_bars:
                break
    
    def _process_bars(self, bars: Dict[str, Dict]):
        """Process closed bars for all symbols."""
        self._emit("BAR_CLOSED", {"bar_index": self.bar_count, "symbols": list(bars.keys())})
        
        for sym, bar in bars.items():
            self._process_symbol_bar(sym, bar)
    
    def _process_symbol_bar(self, sym: str, bar: Dict):
        """Process bar for single symbol."""
        if self.safe_mode:
            self._emit("SKIP_SAFE_MODE", {"symbol": sym})
            return
        
        close = bar.get("close", 0)
        ts = bar.get("timestamp", self.bar_count)
        
        # Simplified trading logic (same as LiveEngine)
        if sym not in self.open_positions:
            # Entry condition
            if self.bar_count % 10 == 5:
                order = self.broker.place_order(sym, "BUY", 0.1, close)
                
                self.open_positions[sym] = {
                    "entry_price": order.fill_price,
                    "entry_ts": ts,
                    "order_id": order.order_id
                }
                
                self._emit("POSITION_OPEN", {
                    "symbol": sym,
                    "price": order.fill_price,
                    "order_id": order.order_id
                })
        else:
            # Exit condition
            if self.bar_count % 10 == 0:
                pos = self.open_positions[sym]
                order = self.broker.place_order(sym, "SELL", 0.1, close)
                
                pnl = (order.fill_price - pos["entry_price"]) / pos["entry_price"] * 100
                
                self._emit("POSITION_CLOSE", {
                    "symbol": sym,
                    "entry": pos["entry_price"],
                    "exit": order.fill_price,
                    "pnl": pnl,
                    "fee": order.fee
                })
                
                del self.open_positions[sym]
                self.trade_count += 1
        
        # Save state
        self.state_store.save_state(
            self.run_id,
            list(self.open_positions.values()),
            []
        )
    
    def _stop(self):
        """Stop engine and save artifacts."""
        self.running = False
        
        self._emit("CLOUD_STOP", {
            "bar_count": self.bar_count,
            "trade_count": self.trade_count
        })
        
        self.state_store.update_status(self.run_id, "STOPPED")
        
        if not self.open_positions:
            self.state_store.clear_state()
        
        self._save_artifacts()
    
    def _emit(self, kind: str, data: Dict):
        """Emit telemetry event."""
        event = {
            "ts": datetime.now().isoformat(),
            "kind": kind,
            "run_id": self.run_id,
            **data
        }
        self.telemetry.append(event)
        
        # Stream to file and stdout
        line = json.dumps(event)
        print(line)
        
        with open(self.run_dir / "telemetry.ndjson", "a") as f:
            f.write(line + "\n")
    
    def _save_artifacts(self):
        """Save final artifacts."""
        # Report
        report = {
            "run_id": self.run_id,
            "symbols": self.symbols,
            "tf": self.tf,
            "mode": self.mode,
            "bar_count": self.bar_count,
            "trade_count": self.trade_count,
            "safe_mode": self.safe_mode,
            "stopped_at": datetime.now().isoformat()
        }
        with open(self.run_dir / "report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        # Trade audit
        with open(self.run_dir / "trade_audit.jsonl", "w") as f:
            for trade in self.broker.to_trade_audit():
                f.write(json.dumps(trade) + "\n")
