import os
import json
import time
from typing import Dict, Any, Optional
from tezaver.matrix.adapters.binance_rest_client import BinanceRestClient

class UserStreamManager:
    """
    Manages the lifecycle of the User Data Stream ListenKey and stores raw events.
    Does NOT handle the WebSocket connection itself in this phase (just the key and storage skeleton).
    """
    def __init__(self, client: BinanceRestClient, home: str):
        self.client = client
        self.home = home
        self.stream_dir = os.path.join(home, "cloud_runtime", "userstream")
        os.makedirs(self.stream_dir, exist_ok=True)
        self.status_file = os.path.join(self.stream_dir, "status.json")
        self.raw_file = os.path.join(self.stream_dir, "raw.ndjson")
        
    def start_stream(self) -> str:
        """
        Creates a listenKey or reuses existing if valid?
        Actually Binance REST docs say POST always returns a valid key (new or existing extended).
        """
        # POST /fapi/v1/listenKey
        try:
            resp = self.client._request("POST", "/fapi/v1/listenKey", signed=False, params={}) 
            # Note: listenKey endpoint requires API Key header! 
            # BinanceRestClient._request adds header if api_key is present.
            # But signed=False usually doesn't add keys? 
            # Wait, public requests usually don't need key, but listenKey DOES.
            # We need to make sure API Key is sent even if signed=False.
            # Looking at BinanceRestClient implementation (MX-14004):
            # `if self.api_key: headers["X-MBX-APIKEY"] = self.api_key`
            # It adds it unconditionally if present. So signed=False is correct (no HMAC), but header is sent.
            
            listen_key = resp.get("listenKey")
            if not listen_key:
                raise Exception(f"No listenKey in response: {resp}")
                
            self._update_status(listen_key, "CONNECTED")
            return listen_key
        except Exception as e:
            self._update_status(None, "ERROR", str(e))
            raise e

    def keepalive(self, listen_key: str = None):
        """
        Extends validity of listenKey.
        """
        if not listen_key:
            # Try load from status
            status = self.get_status()
            listen_key = status.get("listenKey")
            
        if not listen_key:
            return # Nothing to keepalive
            
        try:
            # PUT /fapi/v1/listenKey
            # params: {listenKey: ...} ? No, usually just header + no params?
            # Or param? Official doc: "PUT /fapi/v1/listenKey"
            # "Parameters: None" ?
            # Wait, how does it know WHICH key?
            # "No parameters" -> It implies it keeps alive the stream associated with the API Key?
            # "Keepalive a user data stream to prevent a time out. User data streams will close after 60 minutes. It's recommended to send a ping about every 60 minutes."
            # Actually Spot API requires listenKey param sometimes, but Futures API documentation says:
            # PUT /fapi/v1/listenKey
            # Parameters: None.
            # It seems it extends the *current* active stream for this API Key.
            # BUT wait, what if I have multiple?
            # Usually one per API Key.
            
            self.client._request("PUT", "/fapi/v1/listenKey", signed=False, params={})
            # Update status timestamp
            self._update_status(listen_key, "CONNECTED") # Refresh TS
        except Exception as e:
            self._update_status(listen_key, "ERROR_KEEPALIVE", str(e))
            raise e

    def close(self):
        try:
            self.client._request("DELETE", "/fapi/v1/listenKey", signed=False, params={})
            self._update_status(None, "CLOSED")
        except:
            pass

    def append_raw_message(self, msg: Dict[str, Any]):
        """
        Appends a raw WS message to store.
        """
        with open(self.raw_file, "a") as f:
            f.write(json.dumps(msg) + "\n")
            
        # Update last msg ts in status
        status = self.get_status()
        status["last_msg_ts"] = int(time.time() * 1000)
        self._save_status(status)

    def get_status(self) -> Dict[str, Any]:
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file) as f: return json.load(f)
            except: pass
        return {"status": "UNKNOWN", "listenKey": None, "updated_ts": 0}

    def _update_status(self, listen_key: Optional[str], status_code: str, error: str = None):
        s = self.get_status()
        s["status"] = status_code
        if listen_key: s["listenKey"] = listen_key
        s["updated_ts"] = int(time.time() * 1000)
        
        # Keepalive logic
        # Expires in 60 mins. We want to renew every 55 mins.
        # Next Due = Now + 55 mins
        s["keepalive_due_ts"] = s["updated_ts"] + (55 * 60 * 1000)
        
        if error:
            s["last_error"] = error
        elif status_code == "CONNECTED":
            s["last_error"] = None
            
        self._save_status(s)

    def _save_status(self, s: Dict):
        with open(self.status_file, "w") as f:
            json.dump(s, f, indent=2)
