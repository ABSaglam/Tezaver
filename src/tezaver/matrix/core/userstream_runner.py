import time
import json
import logging
from typing import Optional
from tezaver.matrix.ports.websocket_port import WebSocketPort
from tezaver.matrix.core.userstream_manager import UserStreamManager

class UserStreamRunner:
    def __init__(self, ws: WebSocketPort, manager: UserStreamManager, home: str):
        self.ws = ws
        self.manager = manager
        self.home = home
        self.running = False
        self.reconnect_count = 0
        
    def run(self, ticks: Optional[int] = None):
        """
        Main loop.
        ticks: If set, runs loop this many times (for testing).
        """
        self.running = True
        tick_count = 0
        
        while self.running:
            if ticks and tick_count >= ticks:
                break
                
            try:
                # 1. Manage Connection / Keepalive
                status = self.manager.get_status()
                now = int(time.time() * 1000)
                
                # Check Keepalive
                if status.get("keepalive_due_ts", 0) > 0 and now >= status["keepalive_due_ts"]:
                    self._do_keepalive()
                    status = self.manager.get_status() # Refresh
                
                # Check ListenKey validity via status
                if not status.get("listenKey"):
                    # Start new session
                    self._start_session()
                    status = self.manager.get_status()
                    
                # 2. Connect if needed
                if status.get("status") != "CONNECTED_WS":
                    self._connect_ws(status.get("listenKey"))
                    
                # 3. Read
                msg = self.ws.recv(timeout=1.0)
                if msg:
                     try:
                         data = json.loads(msg)
                         self.manager.append_raw_message(data)
                     except Exception as e:
                         print(f"Error parsing msg: {e}")
                         
                tick_count += 1
                
            except Exception as e:
                # Reconnect logic handling
                print(f"Runner Exception: {e}")
                
                # IMPORTANT: We must increment tick_count even on error to prevent infinite testing loops
                # processing failed, but it was a "tick" (an attempt).
                tick_count += 1
                
                self.reconnect_count += 1
                self.manager._update_status(None, "ERROR_WS", str(e))
                # Backoff
                sleep_time = min(10, self.reconnect_count)
                # In tests, we might want to skip sleep or make it short?
                # We can't easily skp unless we inject sleeper.
                # But with tick_count incremented, it will break eventually.
                time.sleep(sleep_time)

    def _start_session(self):
        print("Starting new ListenKey session...")
        key = self.manager.start_stream()
        # Event?
        
    def _do_keepalive(self):
        print("Performing Keepalive...")
        self.manager.keepalive()
        
    def _connect_ws(self, listen_key):
        if not listen_key: return
        url = f"wss://fstream.binance.com/ws/{listen_key}"
        print(f"Connecting to {url[:20]}...")
        self.ws.connect(url)
        self.manager._update_status(listen_key, "CONNECTED_WS")
        self.reconnect_count = 0 # Reset on success
