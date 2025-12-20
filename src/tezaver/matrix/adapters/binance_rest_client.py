import time
import requests
import urllib.parse
from typing import Dict, Any, Optional
from tezaver.matrix.core.binance_sign import sign_request

class BinanceRestClient:
    """
    Minimal Binance Futures REST Client directly implementing signed request logic.
    Handles time synchronization and header management.
    """
    PROD_URL = "https://fapi.binance.com"
    TESTNET_URL = "https://testnet.binancefuture.com" 
    # NOTE: User prompt said https://demo-fapi.binance.com but documented testnet is often testnet.binancefuture.com
    # Let's use user specified or standard? User said: "testnet: https://demo-fapi.binance.com"
    # Actually for futures it is commonly https://testnet.binancefuture.com.
    # But let's respect user hint if possible, but verify standard. 
    # Binance Futures Testnet Base URL: https://testnet.binancefuture.com
    # let's stick to what usually works, or make it configurable. 
    # User prompt: "prod: https://fapi.binance.com", "testnet: https://demo-fapi.binance.com"
    # Wait, demo-fapi might be an alias or user specific knowledge. I will use what user requested as constant but allow override via base_url arg.
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False, base_url: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = "https://demo-fapi.binance.com" if testnet else "https://fapi.binance.com"
            # Correction: Let's use standard testnet URL if the user provided one yields 404, but for now trust user spec.
            # Actually, standard is usually testnet.binancefuture.com. 
            # I will default to user request to comply with "KİLİTLİ KURALLAR" implicit context if strict.
            # But widely known is testnet.binancefuture.com. I'll stick to user prompt value for now: https://demo-fapi.binance.com
            
        self.time_offset_ms = 0
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "TezaverMatrix/4.0"
        })
        self.last_call_meta = {}

    def sync_time(self) -> int:
        """
        Synchronizes local time with server time.
        Updates self.time_offset_ms = server_time - local_time
        Returns the offset.
        """
        local_ts = int(time.time() * 1000)
        try:
            resp = self._request("GET", "/fapi/v1/time", signed=False)
            server_ts = resp.get("serverTime", local_ts)
            self.time_offset_ms = server_ts - local_ts
            return self.time_offset_ms
        except Exception as e:
            # If fail, assume 0
            # print(f"Time sync failed: {e}") 
            self.time_offset_ms = 0
            return 0

    def _request(self, method: str, path: str, params: Dict = None, signed: bool = False) -> Dict:
        if params is None:
            params = {}
            
        # Timestamp logic
        if signed:
            params["timestamp"] = int(time.time() * 1000) + self.time_offset_ms
            
        # Signature Construction
        # To ensure signature matches payload, we must control string construction.
        from tezaver.matrix.core.binance_sign import build_query_string, sign_request
        
        # We build the canonical string
        if signed:
            # Note: sign_request calls build_query_string internally, but we need the string too.
            # Let's optimize: build, then sign.
            query_string = build_query_string(params)
            signature = sign_request(params, self.api_secret) # This re-builds, but safe.
            # Ideally: signature = hmac(query_string...)
            # But sign_request is simpler.
            
            # Now we use the string as params for requests
            final_params = f"{query_string}&signature={signature}"
        else:
            final_params = params # Dict is fine for unsigned
            
        headers = {}
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key
            
        url = f"{self.base_url}{path}"
        
        # Telemetry Metadata
        self.last_call_meta = {
            "method": method,
            "path": path,
            "ts": int(time.time() * 1000),
            "status": "PENDING"
        }
        
        try:
            # Requests supports params as string for existing query params.
            # But for POST, if it's form-encoded body?
            # Binance Futures:
            # GET / DELETE -> Query String
            # POST / PUT -> Query String OR Body
            # "Parameters can be sent in the query string or in the request body."
            # "Content-Type: application/x-www-form-urlencoded" implies body.
            # If I send params=string in requests, it appends to URL (Query String).
            # For POST, usually better in Body?
            # If signed, Binance supports both. Query string is easier to verify.
            # Let's stick to params (Query String) for all for simplicity unless payload too large.
            # "Signature is ... appended to the end of the query string."
            # If we use `params=final_params` (string), requests appends it to URL.
            
            resp = self.session.request(method, url, params=final_params, headers=headers, timeout=5)
            self.last_call_meta["status"] = resp.status_code
            
            # Rate Limit Headers
            # X-MBX-USED-WEIGHT-1M
            self.last_call_meta["weight_1m"] = resp.headers.get("X-MBX-USED-WEIGHT-1M")
            self.last_call_meta["order_count_1m"] = resp.headers.get("X-MBX-ORDER-COUNT-1M")
            
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            self.last_call_meta["error"] = str(e)
            # Pass through for now, or wrap?
            # If 400+, resp.json() might contain code/msg
            try:
                err_json = e.response.json()
                self.last_call_meta["api_code"] = err_json.get("code")
                self.last_call_meta["api_msg"] = err_json.get("msg")
            except: pass
            raise e
        except Exception as e:
            self.last_call_meta["status"] = "EXCEPTION"
            self.last_call_meta["error"] = str(e)
            raise e

    def order_test(self, params: Dict) -> Dict:
        return self._request("POST", "/fapi/v1/order/test", params, signed=True)
        
    def order_place(self, params: Dict) -> Dict:
        return self._request("POST", "/fapi/v1/order", params, signed=True)
        
    def get_account(self) -> Dict:
        return self._request("GET", "/fapi/v2/account", signed=True)
        
    def get_position_risk(self, symbol: Optional[str] = None) -> Dict:
        p = {}
        if symbol: p["symbol"] = symbol
        return self._request("GET", "/fapi/v2/positionRisk", p, signed=True)
