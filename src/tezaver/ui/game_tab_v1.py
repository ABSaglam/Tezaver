import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
from pathlib import Path
from tezaver.matrix.game.game_runner_v1 import GameRunnerV1

def render_game_tab(home: str):
    st.header("🎮 Matrix GAME v1")
    st.caption("Deterministik Replay & Court Trace Analysis")
    
    # Tabs
    tab_list = ["Run Game", "Overview", "Chart", "Court Trace", "Trades"]
    selected_tab = st.radio("Select View", tab_list, horizontal=True)
    
    if selected_tab == "Run Game":
        render_run_params(home)
    elif selected_tab == "Overview":
        render_overview(home)
    elif selected_tab == "Chart":
        render_chart(home)
    elif selected_tab == "Court Trace":
        render_court_trace(home)
    elif selected_tab == "Trades":
        render_trades(home)

from tezaver.matrix.game.game_bundle_discovery_v1 import (
    discover_bundles, 
    load_bundle_from_manual_path, 
    resolve_bus_root,
    BundleRef
)

# ... (Imports remain same, remove load_all_bundles) ...

def render_run_params(home: str):
    st.subheader("⚙️ New Game Run")
    
    # 1. Source Selector
    col1, col2 = st.columns([3, 1])
    with col1:
        source_opts = ["APPROVED", "CANDIDATES", "GOLDEN", "MANUAL"]
        selected_source = st.radio("Bundle Source", source_opts, horizontal=True)
    with col2:
        if st.button("🔄 Refresh"):
            st.rerun()

    # 2. Discovery
    bus_root = resolve_bus_root()
    
    if "discovery_res" not in st.session_state or st.session_state.get("last_source") != selected_source:
        st.session_state["discovery_res"] = discover_bundles(bus_root, selected_source)
        st.session_state["last_source"] = selected_source
        
    res = st.session_state["discovery_res"]
    
    # 3. Bundle Selection / Manual Input
    selected_bundle_ref = None
    
    if selected_source == "MANUAL":
        manual_path = st.text_input("📁 Bundle Folder or Manifest Path", 
                                  help="Enter full path to a bundle directory or manifest.json")
        if st.button("Load Manual Bundle"):
            if manual_path:
                b_ref = load_bundle_from_manual_path(manual_path)
                if b_ref:
                    st.success(f"Loaded: {b_ref.bundle_id}")
                    st.session_state["manual_bundle_ref"] = b_ref
                else:
                    st.error("Invalid path or manifest not found.")
        
        if "manual_bundle_ref" in st.session_state:
            selected_bundle_ref = st.session_state["manual_bundle_ref"]
            st.info(f"Ready: {selected_bundle_ref.label}")
            
    else:
        # Standard Dropdown
        count = len(res.bundles)
        st.caption(f"Found: {count} bundles in {selected_source}")
        
        if count > 0:
            b_options = [b.label for b in res.bundles]
            sel_label = st.selectbox("Select Bundle", b_options)
            if sel_label:
                idx = b_options.index(sel_label)
                selected_bundle_ref = res.bundles[idx]
        else:
            st.warning(f"No bundles found in {selected_source}. Check Debug Panel.")

    # 4. Debug Panel
    with st.expander("🐞 Bundle Discovery Debug"):
        st.write(f"Bus Root: `{bus_root}`")
        st.write("Scanned Paths:")
        for p in res.scanned_paths:
            st.code(p, language="text")
        if res.errors:
            st.error("Errors:")
            for e in res.errors:
                st.write(e)

    st.divider()
    
    # 5. Run Config
    capital = st.number_input("Initial Capital", value=100.0)
    
    btn_disabled = selected_bundle_ref is None
    if st.button("🚀 Start Game", type="primary", disabled=btn_disabled):
        if not selected_bundle_ref:
            st.error("Select a bundle first!")
            return
            
        # Load Data
        symbol = selected_bundle_ref.symbol or "UNKNOWN"
        tf = selected_bundle_ref.timeframe or "UNKNOWN"
        
        # Data path logic (Shared with TimeMachine?)
        # For now, simplistic assumption:
        path = Path(f"coin_cells/{symbol}/data/history_{tf}.parquet")
        
        if not path.exists():
            st.error(f"Data not found at {path}")
            return
            
        df = pd.read_parquet(path)
        
        # Load Manifest Content
        import json
        with open(selected_bundle_ref.manifest_path) as f:
             m_dict = json.load(f)
        
        runner = GameRunnerV1()
        
        with st.spinner("Running Game..."):
            res = runner.run(m_dict, df, initial_capital=capital)
        
        st.success(f"Game Finished! Run ID: {res['run_id']}")
        st.session_state["last_game_run_id"] = res['run_id']
        st.metric("Final Equity", f"{res['equity']:.2f}")

def get_latest_run_dir(home: str) -> Path:
    # return Path(home) / "out/game_runs/..."
    # Logic to find latest or selected run
    base = Path("out/game_runs")
    if not base.exists(): return None
    
    # Sort by time
    runs = sorted([p for p in base.iterdir() if p.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
    if runs:
        return runs[0]
    return None

def render_overview(home: str):
    run_dir = get_latest_run_dir(home)
    if not run_dir:
        st.info("No runs found.")
        return
        
    summary_path = run_dir / "game_summary.json"
    if summary_path.exists():
        with open(summary_path) as f:
            s = json.load(f)
            
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Equity", f"{s.get('final_equity', 0):.2f}")
        c2.metric("Return %", f"{s.get('return_pct', 0):.2f}%")
        c3.metric("Max DD %", f"{s.get('max_drawdown', 0):.2f}%")
        c4.metric("Trades", s.get('trade_count', 0))
        
        st.json(s)
    else:
        st.warning("Summary not found.")

def render_chart(home: str):
    run_dir = get_latest_run_dir(home)
    if not run_dir: return
    
    st.caption(f"Run: {run_dir.name}")
    
    # Load Steps
    steps_path = run_dir / "game_steps.ndjson"
    marks_path = run_dir / "game_chart_marks.json"
    
    if not steps_path.exists(): return
    
    # Parse NDJSON
    data = []
    with open(steps_path) as f:
        for line in f:
            data.append(json.loads(line))
            
    df = pd.DataFrame(data)
    
    fig = go.Figure()
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=pd.to_datetime(df['ts'], unit='ms'),
        open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name='Price'
    ))
    
    # Marks
    if marks_path.exists():
        with open(marks_path) as f:
            marks = json.load(f)
        
        # Plot markers
        # Separate by type
        buys = [m for m in marks if m['type'] == 'BUY']
        sells = [m for m in marks if m['type'] in ('SELL', 'EXIT')]
        blocks = [m for m in marks if m['type'] == 'BLOCK']
        
        if buys:
            fig.add_trace(go.Scatter(
                x=pd.to_datetime([m['ts'] for m in buys], unit='ms'),
                y=[m['price'] for m in buys],
                mode='markers', marker=dict(symbol='triangle-up', size=10, color='green'),
                name='Buy'
            ))
        if sells:
            fig.add_trace(go.Scatter(
                x=pd.to_datetime([m['ts'] for m in sells], unit='ms'),
                y=[m['price'] for m in sells],
                mode='markers', marker=dict(symbol='triangle-down', size=10, color='red'),
                name='Sell'
            ))
        if blocks:
             fig.add_trace(go.Scatter(
                x=pd.to_datetime([m['ts'] for m in blocks], unit='ms'),
                y=[m['price'] for m in blocks],
                mode='markers', marker=dict(symbol='x', size=8, color='gray'),
                name='Block'
            ))

    st.plotly_chart(fig, use_container_width=True)

def render_court_trace(home: str):
    run_dir = get_latest_run_dir(home)
    if not run_dir: return
    
    steps_path = run_dir / "game_steps.ndjson"
    data = []
    with open(steps_path) as f:
        for line in f:
            d = json.loads(line)
            if d.get('verdict') != 'SKIP': # Filter skips to reduce noise
                items = {
                    "ts": pd.to_datetime(d['ts'], unit='ms'),
                    "bar": d['bar_index'],
                    "verdict": d['verdict'],
                    "intent": d['intent_summary'],
                    "reasons": [r['detail'] for r in d['court_trace']['stage_reasons']]
                }
                data.append(items)
                
    st.dataframe(pd.DataFrame(data), use_container_width=True)

def render_trades(home: str):
    run_dir = get_latest_run_dir(home)
    if not run_dir: return
    
    path = run_dir / "game_trades.json"
    if path.exists():
        with open(path) as f:
            t = json.load(f)
        st.dataframe(pd.DataFrame(t), use_container_width=True)
