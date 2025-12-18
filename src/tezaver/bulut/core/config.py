# Tezaver Bulut - Core Configuration
"""
Centralized configuration for Tezaver Bulut.
All values can be overridden via environment variables.

NO MATRIX IMPORTS - Bulut is standalone.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict


def _env_str(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, str(default)))


def _env_list(key: str, default: str) -> List[str]:
    raw = os.environ.get(key, default)
    return [s.strip() for s in raw.split(",") if s.strip()]


@dataclass(frozen=True)
class BulutConfig:
    """Immutable configuration for Tezaver Bulut."""
    
    # Exchange Settings
    exchange: str = field(default_factory=lambda: _env_str("EXCHANGE", "BINANCE"))
    market: str = field(default_factory=lambda: _env_str("MARKET", "FUTURES"))
    direction: str = field(default_factory=lambda: _env_str("DIRECTION", "LONG_ONLY"))
    
    # Timeframe Settings
    base_tf: str = field(default_factory=lambda: _env_str("BASE_TF", "15m"))
    derived_tfs: List[str] = field(default_factory=lambda: _env_list("DERIVED_TFS", "1h,4h"))
    
    # Data Source Settings
    rest_base_url: str = field(default_factory=lambda: _env_str("REST_BASE_URL", "https://fapi.binance.com"))
    rest_base_url_testnet: str = field(default_factory=lambda: _env_str("REST_BASE_URL_TESTNET", "https://testnet.binancefuture.com"))
    use_testnet: bool = field(default_factory=lambda: str(_env_str("USE_TESTNET", "false")).lower() == "true")
    poll_interval_seconds: int = field(default_factory=lambda: _env_int("POLL_INTERVAL_SECONDS", 2))
    poll_concurrency: int = field(default_factory=lambda: _env_int("POLL_CONCURRENCY", 40))
    kline_limit: int = field(default_factory=lambda: _env_int("KLINE_LIMIT", 2))
    
    # Scanning Rules
    scan_topk: int = field(default_factory=lambda: _env_int("SCAN_TOPK", 20))
    scan_min_score: int = field(default_factory=lambda: _env_int("SCAN_MIN_SCORE", 70))
    universe_path: str = field(default_factory=lambda: _env_str("UNIVERSE_PATH", "data/universe/universe_symbols.txt"))
    universe_fallback_symbols: List[str] = field(default_factory=list)

    # Trading Rules
    auto_trade: bool = field(default_factory=lambda: str(_env_str("AUTO_TRADE", "false")).lower() == "true")
    paper_mode: bool = field(default_factory=lambda: str(_env_str("PAPER_MODE", "true")).lower() == "true")
    allowlist_path: str = field(default_factory=lambda: _env_str("ALLOWLIST_PATH", "data/universe/allowlist.txt"))
    trade_min_score: int = field(default_factory=lambda: _env_int("TRADE_MIN_SCORE", 70))
    trade_topn_from_ranking: int = field(default_factory=lambda: _env_int("TRADE_TOPN_FROM_RANKING", 20))
    
    # Execution Settings
    execution_enabled: bool = field(default_factory=lambda: str(_env_str("EXECUTION_ENABLED", "false")).lower() == "true")
    require_arm: bool = field(default_factory=lambda: str(_env_str("REQUIRE_ARM", "true")).lower() == "true")
    arm_token: Optional[str] = field(default_factory=lambda: os.getenv("TEZAVER_ARM_TOKEN"))
    mode: str = field(default_factory=lambda: _env_str("MODE", "REAL_TESTNET"))
    
    # Protective Orders (v0.09)
    protective_orders_enabled: bool = field(default_factory=lambda: str(_env_str("PROTECTIVE_ORDERS_ENABLED", "true")).lower() == "true")
    protective_working_type: str = field(default_factory=lambda: _env_str("PROTECTIVE_WORKING_TYPE", "MARK_PRICE")) # or CONTRACT_PRICE
    protective_price_protect: bool = field(default_factory=lambda: str(_env_str("PROTECTIVE_PRICE_PROTECT", "true")).lower() == "true")
    protective_cancel_on_close: bool = field(default_factory=lambda: str(_env_str("PROTECTIVE_CANCEL_ON_CLOSE", "true")).lower() == "true")
    protective_client_id_prefix_sl: str = field(default_factory=lambda: _env_str("PROTECTIVE_CLIENT_ID_PREFIX_SL", "tbsl_"))
    protective_client_id_prefix_tp: str = field(default_factory=lambda: _env_str("PROTECTIVE_CLIENT_ID_PREFIX_TP", "tbtp_"))

    # ExchangeInfo Cache (v0.10)
    exchangeinfo_cache_path: str = "data/bulut_state/exchangeinfo_cache.json"
    exchangeinfo_ttl_seconds: int = 3600
    exchangeinfo_refresh_on_start: bool = True
    exchangeinfo_symbols_mode: str = "ALL"
    block_if_filters_missing: bool = True

    # Rate Limit Governor (v0.11/v0.11.1)
    rate_limit_enabled: bool = True
    rate_limit_budget_market_per_min: int = 1800
    rate_limit_budget_trade_per_min: int = 200
    rate_limit_safety_pct: float = 0.85
    backoff_base_ms: int = 250
    backoff_max_ms: int = 8000
    
    # v0.18 Income Sync
    income_sync_enabled: bool = True
    income_sync_types: str = "FUNDING_FEE" # Comma separated
    income_sync_refresh_seconds: int = 900
    income_sync_lookback_hours: int = 48
    income_sync_limit: int = 1000
    include_income_in_daily_loss_guard: bool = True
    
    # v0.19 FX Conversion
    fx_enabled: bool = True
    fx_quote_asset: str = "USDT"
    fx_ttl_seconds: int = 300
    fx_refresh_seconds: int = 300
    fx_refresh_on_start: bool = True
    fx_price_mode: str = "BOOK_MID" # BOOK_MID | LAST_PRICE
    fx_fallback_last_price: bool = True
    fx_max_assets_per_refresh: int = 25

    # v0.20 Startup / Env Doctor
    startup_selftest_enabled: bool = True
    startup_fail_fast: bool = True
    startup_export_incident_on_fail: bool = True
    startup_selftest_timeout_seconds: float = 8.0

    # Endpoint Weights (approximate)
    endpoint_weights: Dict[str, int] = field(default_factory=lambda: {
        "GET:/fapi/v1/order": 1,
        "POST:/fapi/v1/order": 0, # Orders count towards order limit, handled separately
        "DELETE:/fapi/v1/order": 1,
        "GET:/fapi/v1/positionRisk": 5,
        "GET:/fapi/v1/account": 5,
        "GET:/fapi/v2/balance": 5,
        "GET:/fapi/v1/exchangeInfo": 1,
        "GET:/fapi/v1/income": 30, # Heavy endpoint
        "GET:/fapi/v1/ticker/bookTicker": 2, # v0.19
        "GET:/fapi/v1/ticker/price": 1,      # v0.19
    })

    # Portfolio Risk (v0.12)
    cooldown_cycles_after_sl: int = 8
    daily_loss_limit_usdt: float = 200.0
    entry_halted_on_daily_loss: bool = True
    group_caps_path: str = "data/bulut_rules/group_caps.json"
    default_group_cap_max_open: int = 1
    symbol_groups_path: str = "data/bulut_rules/symbol_groups.json"
    
    # v0.13 Time Sync
    time_sync_enabled: bool = True
    time_sync_refresh_seconds: int = 300
    time_sync_max_skew_ms: int = 1000
    recv_window_ms: int = 5000
    block_execution_if_time_sync_fail: bool = True

    # Fill Sync Hardening (v0.17.1)
    fill_sync_max_wait_seconds: int = 6
    fill_sync_retry_interval_ms: int = 400
    fill_sync_window_ms: int = 10 * 60 * 1000
    alert_on_non_usdt_fee: bool = True

    # Income Sync (v0.18)
    income_sync_enabled: bool = True
    income_sync_types: str = "FUNDING_FEE" # Comma separated list
    income_sync_refresh_seconds: int = 900 # 15 min
    income_sync_lookback_hours: int = 48
    income_sync_limit: int = 1000
    include_income_in_daily_loss_guard: bool = True

    # Binance Credentials
    binance_api_key: Optional[str] = field(default_factory=lambda: os.getenv("BINANCE_API_KEY"))
    binance_api_secret: str = field(default_factory=lambda: _env_str("BINANCE_API_SECRET", ""))
    
    order_type: str = field(default_factory=lambda: _env_str("ORDER_TYPE", "MARKET"))
    leverage: int = field(default_factory=lambda: _env_int("LEVERAGE", 1))
    reduce_only_on_close: bool = field(default_factory=lambda: str(_env_str("REDUCE_ONLY_ON_CLOSE", "true")).lower() == "true")
    execution_timeout_sec: int = field(default_factory=lambda: _env_int("TIMEOUT_SECONDS", 8))
    execution_retry_count: int = field(default_factory=lambda: _env_int("RETRY_COUNT", 2))
    
    # Position Limits
    max_open_positions: int = field(default_factory=lambda: _env_int("MAX_OPEN_POSITIONS", 3))
    max_new_entries_per_cycle: int = field(default_factory=lambda: _env_int("MAX_NEW_ENTRIES_PER_CYCLE", 1))
    
    # Risk Limits (USDT)
    max_total_notional_usdt: float = field(default_factory=lambda: _env_float("MAX_TOTAL_NOTIONAL_USDT", 500.0))
    max_cell_notional_usdt: float = field(default_factory=lambda: _env_float("MAX_CELL_NOTIONAL_USDT", 300.0))
    risk_enforce: str = field(default_factory=lambda: _env_str("RISK_ENFORCE", "BLOCK"))
    
    # Paths
    pattern_pack_dir: str = field(default_factory=lambda: _env_str("PATTERN_PACK_DIR", "data/bulut_inbox/pattern_packs"))
    sqlite_path: str = field(default_factory=lambda: _env_str("SQLITE_PATH", "data/bulut_state/tezaver.db"))
    ndjson_path: str = field(default_factory=lambda: _env_str("NDJSON_PATH", "data/bulut_logs/events.ndjson"))
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "exchange": self.exchange,
            "market": self.market,
            "direction": self.direction,
            "base_tf": self.base_tf,
            "derived_tfs": self.derived_tfs,
            "use_testnet": self.use_testnet,
            "poll_interval": self.poll_interval_seconds,
            "scan_topk": self.scan_topk,
            "scan_min_score": self.scan_min_score,
            "universe_path": self.universe_path,
            "auto_trade": self.auto_trade,
            "paper_mode": self.paper_mode,
            "trade_min_score": self.trade_min_score,
            "execution_enabled": self.execution_enabled,
            "mode": self.mode,
            "max_open_positions": self.max_open_positions,
            "max_new_entries_per_cycle": self.max_new_entries_per_cycle,
            "max_total_notional_usdt": self.max_total_notional_usdt,
            "max_cell_notional_usdt": self.max_cell_notional_usdt,
            "risk_enforce": self.risk_enforce,
            "pattern_pack_dir": self.pattern_pack_dir,
            "sqlite_path": self.sqlite_path,
            "ndjson_path": self.ndjson_path,
        }


# Global config instance (lazy-loaded)
_config: BulutConfig | None = None


def get_config() -> BulutConfig:
    """Get or create global config instance."""
    global _config
    if _config is None:
        _config = BulutConfig()
    return _config


def reload_config() -> BulutConfig:
    """Force reload config from environment."""
    global _config
    _config = BulutConfig()
    return _config


# Default symbol universe (placeholder - 400+ symbols)
DEFAULT_SYMBOLS: List[str] = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "LTCUSDT", "ATOMUSDT", "UNIUSDT", "AAVEUSDT",
    "INJUSDT", "ARBUSDT", "OPUSDT", "SUIUSDT", "SEIUSDT",
    # ... placeholder for 400+ symbols - loaded from external source in production
]
