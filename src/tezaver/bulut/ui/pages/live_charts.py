import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime

def render_live_charts(api_base: str = "http://localhost:8000"):
    st.header("📈 Live Charts")

    def get_bars(symbol, limit=300):
        try:
            resp = requests.get(f"{api_base}/ui/bars/series", params={"symbol": symbol, "limit": limit})
            if resp.status_code == 200:
                return resp.json()
        except:
            return []
        return []
    
    # Select Symbol
    # Check shared session state
    default_idx = 0
    if "selected_symbol" in st.session_state:
        # If we had a list, we'd match usage. For now just use text input or standard dropdown 
        pass
    
    # Ideally from session_state or default list
    symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"], index=default_idx) 
    
    # Update shared state
    st.session_state["selected_symbol"] = symbol
    
    # Fetch Data
    bars = get_bars(symbol)
    if not bars:
        st.warning(f"No data for {symbol}")
        return
        
    # Convert to DF
    # Assuming bars format: list of {ts, o, h, l, c, v}
    # If API returns lists of lists, adjust.
    # Current implementation in routes_ui calls `bars_store.get_series`.
    # Let's assume list of dicts.
    try:
        df = pd.DataFrame(bars)
        if "time" in df.columns: # unify timestamp col
            df["ts"] = pd.to_datetime(df["time"], unit="ms")
        elif "open_ts" in df.columns:
             df["ts"] = pd.to_datetime(df["open_ts"])
             
        fig = go.Figure(data=[go.Candlestick(
            x=df['ts'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close']
        )])
        
        fig.update_layout(title=f"{symbol} 15m", height=600)
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Chart render error: {e}")

    # Sizing Preview
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔮 Entry Sizing Preview")
    
    # We can't easily call internal ctx from UI process if separated, but here it's monolithic (Streamlit + FastAPI same proc usually in dev, or separate in prod).
    # If separate, we need API.
    # In `main_panel.py`, we import `routes_sizing`.
    # Let's assume we can use `requests` to our own API base.
    
    if st.sidebar.button("Check Sizing"):
        try:
             # Need a resolve endpoint? Or just assume we can't do it easily without one?
             # Let's add a quick resolve endpoint to routes_sizing first?
             # Or just use `ctx` if running locally?
             # MainPanel runs in same process as API usually in this setup? 
             # Wait, `get_context()` works in Streamlit if same process.
             from tezaver.bulut.core.context import get_context
             ctx = get_context()
             res = ctx.entry_sizing_resolver.resolve(symbol)
             
             st.sidebar.info(f"**Profile:** `{res.profile_id}`")
             if res.blocked:
                 st.sidebar.error(f"🚫 Blocked: {res.block_reason}")
             else:
                 st.sidebar.success(f"✅ Notional: {res.notional_usdt:.2f} USDT")
                 st.sidebar.caption(f"Lev: {res.leverage}x | {res.explain}")
                 
        except Exception as e:
             st.sidebar.error(f"Preview Failed: {e}")
