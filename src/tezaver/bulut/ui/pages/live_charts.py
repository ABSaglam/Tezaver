# Tezaver Bulut - Live Charts Pro (vP2-2)
"""
Advanced Charting with Indicators, Patterns, and Trade Lifecycle.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
from datetime import datetime, timezone

from tezaver.bulut.core.context import get_context
from tezaver.bulut.ui.chart_indicators import calculate_rsi, calculate_macd, calculate_atr, calculate_sma, calculate_ema
from tezaver.bulut.ui.contracts.panel_guard import guarded_render
from tezaver.bulut.ui.contracts.backend_guard import backend_status, render_backend_offline_banner

# --- Config ---
API_BASE = "http://127.0.0.1:8000"

def get_ctx():
    return get_context()

def render_page(ctx=None):
    """Entrypoint for Registry."""
    guarded_render("Canlı Grafikler", lambda: _render_content(ctx))

# --- Data Fetching (Cached) ---

@st.cache_data(ttl=10)
def fetch_bars_df(api_base: str, symbol: str, tf: str, limit: int) -> pd.DataFrame:
    try:
        url = f"{api_base}/bars/series?symbol={symbol}&tf={tf}&limit={limit}"
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        if not data: return pd.DataFrame()
        
        df = pd.DataFrame(data)
        # Parse Dates
        # Assuming open_ts is ISO string
        if "open_ts" in df.columns:
            df["time"] = pd.to_datetime(df["open_ts"])
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def fetch_timelines_data(api_base: str, limit: int = 200) -> list:
    try:
        url = f"{api_base}/cycles/timelines?limit={limit}"
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json()
        return []
    except: return []

@st.cache_data(ttl=10)
def fetch_latest_plans(api_base: str, limit: int = 50) -> list:
    try:
        url = f"{api_base}/plans/latest?limit={limit}"
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json()
        return []
    except: return []

def fetch_open_positions(api_base: str) -> dict:
    # No cache, real time status
    try:
        url = f"{api_base}/ui/summary" # fallback source
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("positions_open", {})
    except: pass
    return {}

def _render_content(ctx=None):
    # Backend Guard
    api_base = API_BASE
    if ctx and hasattr(ctx, 'config') and hasattr(ctx.config, 'bulut_api_base_url'):
        api_base = ctx.config.bulut_api_base_url
        
    ok_be, info, err_be = backend_status(api_base)
    if not ok_be:
        render_backend_offline_banner(api_base, err_be)
        return

    # st.set_page_config is only for standalone mode or first load, 
    # but here we are in a sub-component usually. Remove or check mode?
    # Registry runs in main_panel which sets page config.
    
    st.markdown("## 📈 Market Microscope (Pro)")

    # --- Sidebar Controls ---
    with st.sidebar:
        st.header("Graph Controls")
        
        # Symbol
        # Try to get from session state or default
        default_sym = st.session_state.get("selected_symbol", "BTCUSDT")
        symbol = st.text_input("Symbol", value=default_sym).upper()
        if symbol != default_sym:
            st.session_state["selected_symbol"] = symbol
            
        tf = st.selectbox("Timeframe", ["15m", "1h", "4h"], index=0)
        limit = st.slider("Lookback", 100, 500, 200)
        
        st.divider()
        st.subheader("Overlays")
        show_sma = st.checkbox("Show SMA (20/50)", value=True)
        show_ema = st.checkbox("Show EMA (20/50)", value=False)
        show_patterns = st.checkbox("Show Pattern Marks", value=True)
        show_lifecycle = st.checkbox("Show Plans/Orders", value=True)
        
        st.divider()
        st.subheader("Sub-Panels")
        indicator = st.selectbox("Indicator", ["None", "RSI", "MACD", "ATR"], index=1)
        
    # --- Data Loading ---
    df = fetch_bars_df(api_base, symbol, tf, limit)
    
    if df.empty:
        st.warning(f"No data for {symbol}")
        return

    # Check required cols
    req_cols = ["open", "high", "low", "close", "volume"]
    if not all(c in df.columns for c in req_cols):
        st.error(f"Data schema mismatch: {df.columns}")
        return

    # --- Calculations ---
    # Indicators
    if show_sma:
        df["sma20"] = calculate_sma(df["close"], 20)
        df["sma50"] = calculate_sma(df["close"], 50)
    
    if show_ema:
        df["ema20"] = calculate_ema(df["close"], 20)
        df["ema50"] = calculate_ema(df["close"], 50)

    # Sub-indicator
    ind_data = {}
    if indicator == "RSI":
        ind_data["rsi"] = calculate_rsi(df["close"])
    elif indicator == "MACD":
        m, s, h = calculate_macd(df["close"])
        ind_data["macd"] = m
        ind_data["signal"] = s
        ind_data["hist"] = h
    elif indicator == "ATR":
        ind_data["atr"] = calculate_atr(df["high"], df["low"], df["close"])

    # --- Plot Layout ---
    # Rows: 1=Price(0.6), 2=Vol(0.15), 3=Ind(0.25)
    row_heights = [0.6, 0.15, 0.25] if indicator != "None" else [0.7, 0.3]
    specs = [[{"secondary_y": True}], [{}], [{}]] if indicator != "None" else [[{"secondary_y": True}], [{}]]
    
    fig = make_subplots(
        rows=len(row_heights), cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        row_heights=row_heights,
        specs=specs
    )

    # 1. Candlestick
    fig.add_trace(go.Candlestick(
        x=df["time"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        name="Price"
    ), row=1, col=1)

    # Overlays
    if show_sma:
        fig.add_trace(go.Scatter(x=df["time"], y=df["sma20"], line=dict(color='orange', width=1), name="SMA20"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["time"], y=df["sma50"], line=dict(color='blue', width=1), name="SMA50"), row=1, col=1)
    
    if show_ema:
        fig.add_trace(go.Scatter(x=df["time"], y=df["ema20"], line=dict(color='cyan', width=1, dash='dot'), name="EMA20"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["time"], y=df["ema50"], line=dict(color='purple', width=1, dash='dot'), name="EMA50"), row=1, col=1)

    # 2. Volume
    colors = ['green' if r.close >= r.open else 'red' for i, r in df.iterrows()]
    fig.add_trace(go.Bar(x=df["time"], y=df["volume"], marker_color=colors, name="Volume"), row=2, col=1)

    # 3. Indicator
    if indicator != "None":
        r = 3
        if indicator == "RSI":
            rsi = ind_data["rsi"]
            fig.add_trace(go.Scatter(x=df["time"], y=rsi, line=dict(color='purple'), name="RSI"), row=r, col=1)
            # 30/70 lines
            fig.add_hline(y=70, row=r, col=1, line_dash="dot", line_color="gray")
            fig.add_hline(y=30, row=r, col=1, line_dash="dot", line_color="gray")
        elif indicator == "MACD":
            fig.add_trace(go.Scatter(x=df["time"], y=ind_data["macd"], line=dict(color='blue'), name="MACD"), row=r, col=1)
            fig.add_trace(go.Scatter(x=df["time"], y=ind_data["signal"], line=dict(color='orange'), name="Signal"), row=r, col=1)
            fig.add_trace(go.Bar(x=df["time"], y=ind_data["hist"], name="Hist"), row=r, col=1)
        elif indicator == "ATR":
            fig.add_trace(go.Scatter(x=df["time"], y=ind_data["atr"], line=dict(color='brown'), name="ATR"), row=r, col=1)

    # --- Markers (Patterns/Plans) ---
    
    # Pattern Logic
    if show_patterns:
        timelines = fetch_timelines_data(api_base)
        pat_x = []
        pat_y = [] # place above high?
        pat_text = []
        pat_color = []
        
        # Create map of TS to Index/Row for Y placement
        # Or just use fetched DF if TS matches.
        # It's safer to rely on TS matching.
        
        # Iterate backward (latest)
        for tl in timelines:
            # Check symbol involvement in SCAN
            # tl structure: {'stages': [{'name': 'SCAN', 'details': {'candidates': [{'symbol':...}]}}]}
            # Or SCAN.top_k
            
            stages = tl.get("stages", [])
            scan = next((s for s in stages if s["name"] == "SCAN"), None)
            if not scan: continue
            
            dets = scan.get("details", {})
            cands = dets.get("candidates", []) + dets.get("top_k", [])
            
            # Find relevant entry
            match = next((c for c in cands if c.get("symbol") == symbol), None)
            if match:
                # Found pattern for this symbol at this cycle
                ts_str = tl.get("cycle_ts")
                # Parse TS
                try:
                    ts = pd.to_datetime(ts_str)
                    
                    # We add trace with XY points.
                    # We need Y value. We can pass Y=None and use annotation, or find price.
                    row = df[df["time"] == ts]
                    if not row.empty:
                        y_val = row.iloc[0]["high"] * 1.01
                        
                        pattern_id = match.get("pattern_id", "UNK")
                        conf = match.get("conf", 0)
                        
                        pat_x.append(ts)
                        pat_y.append(y_val)
                        pat_text.append(f"{pattern_id}<br>Conf: {conf:.2f}<br>Note: {match.get('evidence',{}).get('note','')}")
                        
                        c = "yellow"
                        if conf > 0.9: c = "green"
                        elif conf < 0.6: c = "gray"
                        pat_color.append(c)
                except: pass

        if pat_x:
            fig.add_trace(go.Scatter(
                x=pat_x, y=pat_y, mode="markers",
                marker=dict(symbol="star", size=10, color=pat_color),
                text=pat_text, hoverinfo="text", name="Pattern"
            ), row=1, col=1)

    # Lifecycle Logic (Plans/Pos)
    if show_lifecycle:
        plans = fetch_latest_plans(api_base)
        pl_x = []
        pl_y = []
        pl_sym = []
        pl_color = []
        
        for p in plans:
            if p.get("symbol") == symbol:
                ts_str = p.get("plan_ts")
                try:
                    ts = pd.to_datetime(ts_str)
                    row = df[df["time"] == ts]
                    y_val = row.iloc[0]["low"] if not row.empty else 0
                    if not row.empty: y_val = row.iloc[0]["low"] * 0.99
                    
                    dec = p.get("decision", "WAIT")
                    if dec in ["ENTRY_LONG", "ENTRY_SHORT"]:
                        pl_x.append(ts)
                        pl_y.append(y_val)
                        pl_sym.append("triangle-up")
                        pl_color.append("blue")
                except: pass
                
        if pl_x:
            fig.add_trace(go.Scatter(
                x=pl_x, y=pl_y, mode="markers",
                marker=dict(symbol=pl_sym, size=12, color=pl_color),
                name="Plan"
            ), row=1, col=1)

        # Active Position Lines
        positions = fetch_open_positions(api_base)
        my_pos = positions.get(symbol)
        if my_pos:
            entry_px = my_pos.get("entry_price")
            if entry_px:
                fig.add_hline(y=entry_px, line_dash="dash", line_color="blue", annotation_text="ENTRY", row=1, col=1)
                
            # Protective
            meta = my_pos
            sl_pct = meta.get("sl_pct", 0)
            tp_pct = meta.get("tp_pct", 0)
            if entry_px and sl_pct:
                sl_px = entry_px * (1 - sl_pct)
                fig.add_hline(y=sl_px, line_color="red", annotation_text="SL", row=1, col=1)
            if entry_px and tp_pct:
                tp_px = entry_px * (1 + tp_pct)
                fig.add_hline(y=tp_px, line_color="green", annotation_text="TP", row=1, col=1)

    # Style
    fig.update_layout(height=800, xaxis_rangeslider_visible=False, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

    # --- Facts Sidebar Update ---
    # Enhanced "Current Facts"
    if st.sidebar.expander("📌 Current Facts (Pro)", expanded=True):
        pos = fetch_open_positions(api_base).get(symbol, {})
        if pos:
            st.success(f"OPEN: {symbol}")
            st.write(f"Entry: {pos.get('entry_price')}")
            st.write(f"Notional: ${pos.get('notional', 0):.1f}")
            st.write(f"Size Profile: {pos.get('sizing_profile_id', '-')}")
            st.write(f"Prot. Status: {pos.get('protective_status', '-')}")
            
        # Last Pattern / Cycle info
        # Reuse logic from markers or just last
        # Fetching timelines again (cached)
        timelines = fetch_timelines_data(api_base, limit=1)
        if timelines:
            last_tl = timelines[0]
            st.write(f"Last Cycle: {last_tl.get('cycle_ts')}")

if __name__ == "__main__":
    render_page()

# Backward-compat alias (deprecated but kept for external calls not via registry yet)
render_live_charts = render_page
