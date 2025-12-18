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
    
    # Fair Scheduler (v1)
    universe_scan_max_per_cycle: int = field(default_factory=lambda: _env_int("UNIVERSE_SCAN_MAX_PER_CYCLE", 400))
    universe_scan_priority_slots: int = field(default_factory=lambda: _env_int("UNIVERSE_SCAN_PRIORITY_SLOTS", 120))
    universe_scan_concurrency: int = field(default_factory=lambda: _env_int("UNIVERSE_SCAN_CONCURRENCY", 30))

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

    # v0.24 Mainnet Launch Gate
    mode: str = field(default_factory=lambda: _env_str("MODE", "REAL_TESTNET"))
    mainnet_allowlist_path: str = "data/bulut_rules/mainnet_allowlist.txt"
    require_allowlist_on_mainnet: bool = True
    mainnet_max_total_notional_usdt: float = 500.0
    mainnet_require_checklist_pass: bool = True
    checklist_max_age_seconds: float = 60.0

    # Migrations (v0.26)
    migrations_enabled: bool = True
    migrations_fail_fast: bool = True
    migrations_dry_run_on_start: bool = False

    # v0.21 USER_DATA Websocket
    user_data_ws_enabled: bool = True
    user_data_keepalive_seconds: int = 1800 # 30 mins
    user_data_reconnect_backoff_ms: int = 500
    user_data_max_backoff_ms: int = 60000 
    user_data_ws_base_url: str = "wss://fstream.binance.com/ws"

    # v0.28 Constitution Lock
    constitution_path: str = "docs/bulut_constitution_v1.md"
    constitution_version: str = "bulut_constitution_v1"
    constitution_checksum_enforce: bool = True
    # v1 Proof Ladder (Evidence-Gated Cap)
    proof_ladder_enabled: bool = field(default_factory=lambda: str(_env_str("PROOF_LADDER_ENABLED", "true")).lower() == "true")
    proof_ladder_auto_evaluate_enabled: bool = field(default_factory=lambda: str(_env_str("PROOF_LADDER_AUTO_EVALUATE_ENABLED", "true")).lower() == "true")
    proof_ladder_auto_evaluate_seconds: int = field(default_factory=lambda: _env_int("PROOF_LADDER_AUTO_EVALUATE_SECONDS", 3600))
    proof_ladder_auto_advance_enabled: bool = field(default_factory=lambda: str(_env_str("PROOF_LADDER_AUTO_ADVANCE_ENABLED", "false")).lower() == "true")
    proof_ladder_require_clean_hours: float = field(default_factory=lambda: _env_float("PROOF_LADDER_REQUIRE_CLEAN_HOURS", 24.0))
    proof_ladder_max_critical_alerts: int = field(default_factory=lambda: _env_int("PROOF_LADDER_MAX_CRITICAL_ALERTS", 0))
    proof_ladder_max_error_alerts: int = field(default_factory=lambda: _env_int("PROOF_LADDER_MAX_ERROR_ALERTS", 0))
    proof_ladder_max_estimated_audits: int = field(default_factory=lambda: _env_int("PROOF_LADDER_MAX_ESTIMATED_AUDITS", 0))
    proof_ladder_max_unconverted_fx_count: int = field(default_factory=lambda: _env_int("PROOF_LADDER_MAX_UNCONVERTED_FX_COUNT", 0))
    proof_ladder_require_time_sync_healthy: bool = field(default_factory=lambda: str(_env_str("PROOF_LADDER_REQUIRE_TIME_SYNC_HEALTHY", "true")).lower() == "true")
    proof_ladder_require_drift_free: bool = field(default_factory=lambda: str(_env_str("PROOF_LADDER_REQUIRE_DRIFT_FREE", "true")).lower() == "true")
    proof_ladder_stages_path: str = field(default_factory=lambda: _env_str("PROOF_LADDER_STAGES_PATH", "data/bulut_rules/proof_ladder_stages.json"))
    proof_ladder_allow_advance_when_armed: bool = field(default_factory=lambda: str(_env_str("PROOF_LADDER_ALLOW_ADVANCE_WHEN_ARMED", "false")).lower() == "true")


    # Ops Auth Gate (v0.32)
    ops_auth_enabled: bool = field(default_factory=lambda: str(_env_str("OPS_AUTH_ENABLED", "true")).lower() == "true")
    ops_auth_token_env: str = field(default_factory=lambda: _env_str("TEZAVER_OPS_TOKEN", ""))
    ops_auth_header: str = field(default_factory=lambda: _env_str("OPS_AUTH_HEADER", "X-TEZAVER-OPS-TOKEN"))
    ops_auth_readonly_allow: bool = field(default_factory=lambda: str(_env_str("OPS_AUTH_READONLY_ALLOW", "true")).lower() == "true")

    # Deploy Hardening (v0.33)
    deploy_env: str = field(default_factory=lambda: _env_str("DEPLOY_ENV", "DEV")) # DEV | PROD
    allowed_hosts: List[str] = field(default_factory=lambda: _env_list("ALLOWED_HOSTS", "localhost,127.0.0.1"))
    cors_allowed_origins: List[str] = field(default_factory=lambda: _env_list("CORS_ALLOWED_ORIGINS", "")) # Empty means CORS off or extremely restricted default? Usually empty means "same origin" in strict. Here we'll toggle middleware.
    trust_proxy_headers: bool = field(default_factory=lambda: str(_env_str("TRUST_PROXY_HEADERS", "true")).lower() == "true")
    secure_headers_enabled: bool = field(default_factory=lambda: str(_env_str("SECURE_HEADERS_ENABLED", "true")).lower() == "true")
    basic_rate_limit_enabled: bool = field(default_factory=lambda: str(_env_str("BASIC_RATE_LIMIT_ENABLED", "true")).lower() == "true")
    basic_rate_limit_rps: int = field(default_factory=lambda: _env_int("BASIC_RATE_LIMIT_RPS", 5))
    basic_rate_limit_burst: int = field(default_factory=lambda: _env_int("BASIC_RATE_LIMIT_BURST", 20))



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
    
    # Policy State Machine (v1)
    policy_min_hold_bars: int = field(default_factory=lambda: _env_int("POLICY_MIN_HOLD_BARS", 2))
    policy_dust_policy: str = field(default_factory=lambda: _env_str("POLICY_DUST_POLICY", "FLATTEN_AFTER"))
    policy_htf_veto_enabled: bool = field(default_factory=lambda: str(_env_str("POLICY_HTF_VETO_ENABLED", "true")).lower() == "true")

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
