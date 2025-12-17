# Account Page for Matrix UI
"""
Hesap (Account) page showing wallet summary, positions, orders, and reconcile status.
"""

import streamlit as st
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class AccountSnapshot:
    """Account snapshot from exchange."""
    equity: float = 0.0
    available_balance: float = 0.0
    used_margin: float = 0.0
    unrealized_pnl: float = 0.0
    positions: List[Dict[str, Any]] = None
    open_orders: List[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.positions is None:
            self.positions = []
        if self.open_orders is None:
            self.open_orders = []


def get_gateway():
    """Get exchange gateway with graceful fallback."""
    from tezaver.matrix.live.live_gateway import DummyExchangeGateway
    
    try:
        from tezaver.matrix.live.secrets import CompositeVault
        vault = CompositeVault()
        api_key = vault.get("BINANCE_TESTNET_API_KEY")
        api_secret = vault.get("BINANCE_TESTNET_API_SECRET")
        
        if api_key and api_secret:
            from tezaver.matrix.live.live_gateway import BinanceTestnetGateway
            return BinanceTestnetGateway(api_key, api_secret)
    except Exception:
        pass
    
    return DummyExchangeGateway()


def fetch_account_snapshot(symbols: List[str] = None) -> AccountSnapshot:
    """
    Fetch account snapshot from exchange.
    Gracefully degrades if credentials not available.
    """
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    
    snapshot = AccountSnapshot()
    
    try:
        gw = get_gateway()
        
        # Fetch positions for each symbol
        positions = []
        total_unrealized = 0.0
        
        for symbol in symbols:
            pos = gw.get_position_snapshot(symbol)
            if pos and abs(pos.get("position_qty", 0)) > 0.0001:
                positions.append(pos)
                total_unrealized += pos.get("unrealized_pnl", 0)
        
        snapshot.positions = positions
        snapshot.unrealized_pnl = total_unrealized
        
        # Try to get account balance
        try:
            if hasattr(gw, "get_account_balance"):
                balance = gw.get_account_balance()
                snapshot.equity = balance.get("equity", 0)
                snapshot.available_balance = balance.get("available", 0)
                snapshot.used_margin = balance.get("used_margin", 0)
        except Exception:
            pass
        
    except Exception as e:
        snapshot.error = str(e)
    
    return snapshot


def reconcile_account(snapshot: AccountSnapshot, internal_positions: Dict[str, float] = None) -> Dict[str, Any]:
    """
    Compare exchange snapshot with internal state.
    
    Returns:
        {
            "state": "PASS/WARN/BLOCK",
            "reason": "...",
            "details": [...]
        }
    """
    if internal_positions is None:
        internal_positions = {}
    
    result = {
        "state": "PASS",
        "reason": None,
        "details": [],
    }
    
    if snapshot.error:
        result["state"] = "UNKNOWN"
        result["reason"] = f"Bağlantı hatası: {snapshot.error[:50]}"
        return result
    
    # Check for position mismatches
    exchange_positions = {p["symbol"]: p.get("position_qty", 0) for p in snapshot.positions}
    
    for symbol, internal_qty in internal_positions.items():
        exchange_qty = exchange_positions.get(symbol, 0)
        
        # Major mismatch: internal has position, exchange doesn't (or vice versa)
        if abs(internal_qty) > 0.0001 and abs(exchange_qty) < 0.0001:
            result["state"] = "BLOCK"
            result["reason"] = f"{symbol}: Dahili pos={internal_qty:.4f}, Borsa=0"
            result["details"].append(f"BLOCK: {symbol} interno vs exchange mismatch")
        elif abs(exchange_qty) > 0.0001 and abs(internal_qty) < 0.0001:
            result["state"] = "WARN" if result["state"] != "BLOCK" else "BLOCK"
            result["reason"] = f"{symbol}: Borsada açık pos, dahili flat"
            result["details"].append(f"WARN: {symbol} has exchange pos but internal flat")
        # Quantity mismatch
        elif abs(internal_qty - exchange_qty) > 0.001:
            result["state"] = "WARN" if result["state"] != "BLOCK" else "BLOCK"
            result["reason"] = f"{symbol}: Miktar farkı ({internal_qty:.4f} vs {exchange_qty:.4f})"
            result["details"].append(f"WARN: {symbol} qty mismatch")
    
    # Check for unexpected exchange positions
    for symbol, exchange_qty in exchange_positions.items():
        if symbol not in internal_positions and abs(exchange_qty) > 0.0001:
            result["state"] = "WARN" if result["state"] != "BLOCK" else "BLOCK"
            result["reason"] = f"{symbol}: Beklenmeyen borsa pozisyonu"
            result["details"].append(f"WARN: unexpected {symbol} position on exchange")
    
    if result["state"] == "PASS":
        result["reason"] = "Dahili ve borsa durumu uyumlu"
    
    return result


def emit_reconcile_event(reconcile_result: Dict[str, Any]):
    """Emit RECONCILE_CHECK event to NDJSON log."""
    import json
    from datetime import datetime, timezone
    
    event = {
        "event_type": "RECONCILE_CHECK",
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": reconcile_result["state"] == "PASS",
        "state": reconcile_result["state"],
        "reason": reconcile_result.get("reason"),
        "warnings": reconcile_result.get("details", []),
    }
    
    log_path = Path("data/logs/live_events.ndjson")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass


def render_account_page():
    """Render the Hesap (Account) page."""
    import pandas as pd
    
    st.header("👤 Hesap")
    st.caption("Cüzdan durumu, açık pozisyonlar ve reconcile kontrolü.")
    
    # Fetch data
    snapshot = fetch_account_snapshot()
    
    # Connection status
    if snapshot.error:
        st.warning(f"⚠️ Bağlantı yok: {snapshot.error[:60]}")
    
    # === BLOCK 1: Cüzdan Özeti ===
    st.subheader("💰 Cüzdan Özeti")
    wallet_cols = st.columns(4)
    with wallet_cols[0]:
        st.metric("Equity", f"${snapshot.equity:.2f}")
    with wallet_cols[1]:
        st.metric("Kullanılabilir", f"${snapshot.available_balance:.2f}")
    with wallet_cols[2]:
        st.metric("Kullanılan Margin", f"${snapshot.used_margin:.2f}")
    with wallet_cols[3]:
        pnl_delta = f"{snapshot.unrealized_pnl:+.2f}" if snapshot.unrealized_pnl != 0 else None
        st.metric("Unrealized PnL", f"${snapshot.unrealized_pnl:.2f}", delta=pnl_delta)
    
    st.divider()
    
    # === BLOCK 2: Pozisyonlar ===
    st.subheader("📊 Açık Pozisyonlar")
    if snapshot.positions:
        pos_data = [{
            "Sembol": p.get("symbol", ""),
            "Miktar": p.get("position_qty", 0),
            "Giriş": f"${p.get('entry_price', 0):.2f}" if p.get("entry_price") else "-",
            "PnL": f"${p.get('unrealized_pnl', 0):.2f}",
        } for p in snapshot.positions]
        st.dataframe(pd.DataFrame(pos_data), use_container_width=True, hide_index=True)
    else:
        st.info("Açık pozisyon yok.")
    
    st.divider()
    
    # === BLOCK 3: Açık Emirler ===
    st.subheader("📝 Açık Emirler")
    if snapshot.open_orders:
        order_data = [{
            "Sembol": o.get("symbol", ""),
            "Tip": o.get("type", ""),
            "Yön": o.get("side", ""),
            "Miktar": o.get("quantity", 0),
            "Fiyat": o.get("price", 0),
        } for o in snapshot.open_orders]
        st.dataframe(pd.DataFrame(order_data), use_container_width=True, hide_index=True)
    else:
        st.info("Açık emir yok.")
    
    st.divider()
    
    # === BLOCK 4: Risk + Reconcile ===
    st.subheader("🔒 Risk + Reconcile")
    
    # Get internal state (mock for now)
    internal_positions = {}  # Would come from AccountState in production
    
    reconcile_result = reconcile_account(snapshot, internal_positions)
    
    # Display reconcile status
    state = reconcile_result["state"]
    if state == "PASS":
        st.success(f"✅ PASS: {reconcile_result['reason']}")
    elif state == "WARN":
        st.warning(f"⚠️ WARN: {reconcile_result['reason']}")
    elif state == "BLOCK":
        st.error(f"⛔ BLOCK: {reconcile_result['reason']}")
    else:
        st.info(f"❓ UNKNOWN: {reconcile_result['reason']}")
    
    # Details expander
    if reconcile_result["details"]:
        with st.expander("Reconcile Detayları", expanded=False):
            for d in reconcile_result["details"]:
                st.caption(d)
    
    # Emit event button
    if st.button("🔄 Reconcile Kontrolü Yap", key="account_reconcile_btn"):
        emit_reconcile_event(reconcile_result)
        st.toast("Reconcile eventi kaydedildi.", icon="✅")
        st.rerun()


def get_position_summary() -> Dict[str, Any]:
    """
    Get position summary for cockpit card.
    
    Returns:
        {
            "count": int,
            "notional": float,
            "unrealized_pnl": float,
        }
    """
    snapshot = fetch_account_snapshot()
    
    count = len(snapshot.positions)
    notional = 0.0
    unrealized = snapshot.unrealized_pnl
    
    for p in snapshot.positions:
        qty = abs(p.get("position_qty", 0))
        entry = p.get("entry_price") or 0
        notional += qty * entry
    
    return {
        "count": count,
        "notional": notional,
        "unrealized_pnl": unrealized,
    }
