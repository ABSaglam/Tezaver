"""
Tezaver Cloud / Matrix Control Center (M25)
===========================================

This UI page allows controlling the Unified Engine in 'Matrix Mode'.
It visualizes the simulation progress, trade log, and portfolio performance.
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime

from tezaver.engine.matrix_executor import MatrixExecutor
from tezaver.engine.analyzers.rally_analyzer import RallyAnalyzer
from tezaver.engine.strategists.rally_strategist import RallyStrategist
from tezaver.engine.unified_engine import UnifiedEngine
from tezaver.data.history_loader import load_single_coin_history

def _mini_metric(label, value, delta=None):
    """
    Renders a metric with 80% size font (custom HTML).
    """
    delta_html = ""
    if delta:
        color = "green" if not str(delta).startswith("-") else "red"
        delta_html = f"<span style='color:{color}; font-size:0.8em;'>{delta}</span>"
        
    st.markdown(f"""
    <div style="font-family: sans-serif;">
        <div style="font-size: 0.8em; color: gray;">{label}</div>
        <div style="font-size: 1.2em; font-weight: bold;">{value} {delta_html}</div>
    </div>
    """, unsafe_allow_html=True)

def render_cloud_page():
    # st.title("☁️ Tezaver Bulut & Matrix Lab")
    # st.markdown("---")
    
    st.sidebar.markdown("### Navigasyon")
    if st.sidebar.button("🏠 Ana Sayfa", use_container_width=True):
        # Reset any specific states if needed, or just rerun to clear potential drill-downs
        st.rerun()
    
    # 1. Mode Selection
    mode = st.radio("Simülasyon Modu", ["💊 Matrix (Tekli Sniper)", "🌍 Matrix (Global General)", "☁️ Bulut (Canlı - Pasif)"], horizontal=True)
    
    if mode == "☁️ Bulut (Canlı - Pasif)":
        st.info("Bulut bağlantısı henüz yapılandırılmadı. Lütfen önce sunucu kurulumunu tamamlayın.")
        return

    if mode == "💊 Matrix (Tekli Sniper)":
        render_sniper_mode()
    elif mode == "🌍 Matrix (Global General)":
        render_global_mode()

def render_sniper_mode():
    c1, c2, c3 = st.columns(3)
    with c1:
        sim_coin = st.selectbox("Test Coin", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT"])
    with c2:
        start_balance = st.number_input("Başlangıç Bakiyesi ($)", value=10000, key="sniper_bal")
    with c3:
        sim_speed = st.slider("Simülasyon Hızı", 1, 100, 10, help="Veri işleme hızı", key="sniper_speed")
    
    threshold = st.slider("Rally Tetikleme Eşiği (%)", 1.0, 10.0, 2.0, 0.5, key="sniper_thresh")
        
    if st.button("🚀 Matrix'i Başlat (Sniper)", type="primary"):
        run_simulation(sim_coin, start_balance, sim_speed, threshold / 100.0)

def render_global_mode():
    st.info("💡 General Modu: Seçilen TÜM coinleri aynı anda simüle eder.")
    
    c1, c2 = st.columns(2)
    with c1:
        # Load available coins from file system or config
        # For Demo, specific list
        target_coins = st.multiselect("Coin Sepeti", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "DOGEUSDT", "XRPUSDT"], default=["BTCUSDT", "ETHUSDT"])
    with c2:
        start_balance = st.number_input("Global Kasa ($)", value=50000, key="global_bal")
    
    threshold = st.slider("Global Tetikleme Eşiği (%)", 1.0, 10.0, 2.0, 0.5, key="global_thresh")
        
    if st.button("🌍 Dünya Savaşı'nı Başlat", type="primary"):
        run_global_simulation(target_coins, start_balance, threshold / 100.0)


def run_global_simulation(symbols, initial_balance, threshold):
    from tezaver.engine.matrix_executor import MatrixExecutor
    from tezaver.engine.analyzers.rally_analyzer import RallyAnalyzer
    from tezaver.engine.strategists.rally_strategist import RallyStrategist
    from tezaver.matrix.multi_symbol_engine import MultiSymbolEngine
    from tezaver.matrix.guardrail import GuardrailController
    
    st.divider()
    st.write(f"🌍 {len(symbols)} Coin için Savaş Başlıyor...")
    
    # 1. Load Data
    data_map = {}
    load_bar = st.progress(0, text="Veriler yükleniyor...")
    
    min_len = 999999
    
    for idx, sym in enumerate(symbols):
        df = load_single_coin_history(sym, "1h")
        if df is None or df.empty:
            st.error(f"{sym} verisi yok!")
            return
        
        df = df.tail(500)
        data_map[sym] = df
        if len(df) < min_len: min_len = len(df)
        load_bar.progress((idx+1)/len(symbols), text=f"{sym} yüklendi...")
        
    st.success(f"Tüm veriler hazır! {min_len} ortak bar.")
    time.sleep(1)
    
    # 2. Setup Fleet Command (INTELLIGENCE FUSION)
    # Controller now Auto-Loads profiles from data/
    controller = GuardrailController(
        global_limits={"max_open_positions": 5},
        symbols=symbols
    )
    
    executor = MatrixExecutor(initial_balance_usdt=initial_balance)
    
    multi_engine = MultiSymbolEngine(
        symbols=symbols,
        analyzer_factory=lambda s: RallyAnalyzer(rally_threshold=threshold),
        strategist_factory=lambda s: RallyStrategist(),
        executor=executor,
        guardrails=controller
    )
    
    # 3. Simulation Loop
    dashboard = st.empty()
    log_area = st.empty()
    fleet_table = st.empty()
    logs = []
    
    progress_bar = st.progress(0)
    
    # Pre-calculate time index
    ref_df = list(data_map.values())[0]
    
    for i in range(50, min_len):
        current_time_bar = ref_df.index[i]
        
        # Internal Provider Loop
        def data_provider(sym):
            df = data_map.get(sym)
            if df is None: return None
            return df.iloc[:i+1]
            
        for _ in range(len(symbols)):
            multi_engine.tick(current_time_bar, data_provider)
            
        # 4. Visualize
        account_state = executor.get_balance()
        usdt_val = account_state['equity']
        
        # Dashboard
        with dashboard.container():
            k1, k2, k3 = st.columns(3)
            with k1: _mini_metric("Zaman", str(current_time_bar))
            with k2: _mini_metric("Aktif Coin", f"{len(symbols)}")
            with k3: _mini_metric("Global Kasa", f"${usdt_val:.2f}", delta=f"{usdt_val - initial_balance:.2f}")
           
        # Fleet Status Table (Now with Intelligence)
        status_rows = []
        for slot in multi_engine.slots:
            sig = slot.last_signal
            dec = slot.last_decision
            
            # Intelligence Profile
            profile = controller.get_profile(slot.symbol)
            env_status = profile.env_status if profile else "?"
            promo_status = profile.promotion_status if profile else "?"
            
            # Icons
            env_icon = "🔥" if env_status == "HOT" else "🧊" if env_status == "COLD" else "🌪️" if env_status == "CHAOTIC" else "😐"
            promo_icon = "✅" if promo_status == "APPROVED" else "🚫" if promo_status == "REJECTED" else "⚠️"
            
            sig_str = f"{sig['signal_type']} ({sig['score']:.0f})" if sig else "-"
            # Simplify decision display
            dec_str = dec['action'] if dec else "-"
            
            pos = account_state['positions'].get(slot.symbol)
            pos_str = f"LONG ({pos['qty']:.4f})" if pos else "FLAT"
            
            status_rows.append({
                "Symbol": slot.symbol,
                "Radar": f"{env_icon} {env_status}",
                "Sim": f"{promo_icon} {promo_status}",
                "Position": pos_str,
                "Last Signal": sig_str,
                "Action": dec_str,
            })
            
        fleet_table.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)
        
        # Logs
        hist = executor.trade_history[-10:]
        log_lines = []
        for exe in reversed(hist):
             icon = "🟢" if exe['action'] == "BUY" else "🔴"
             t = exe['timestamp'].strftime("%H:%M")
             msg = f"{t} | {icon} {exe['symbol']} | {exe['status']}"
             log_lines.append(msg)
             
        log_area.code("\n".join(log_lines), language="text")
        
        progress_bar.progress((i - 50) / (min_len - 50))
        
    st.success("🏁 Dünya Savaşı Bitti!")


def run_simulation(symbol, initial_balance, speed, threshold):
    """
    Runs the SNIPER simulation loop.
    """
    st.divider()
    
    # A. Setup Engine
    executor = MatrixExecutor(initial_balance_usdt=initial_balance)
    analyzer = RallyAnalyzer(rally_threshold=threshold)
    strategist = RallyStrategist()
    engine = UnifiedEngine(analyzer, strategist, executor)
    
    # B. Load Data (The Time Machine)
    with st.spinner(f"{symbol} verileri yükleniyor..."):
        # We assume history exists. If not, this might fail (need error handling).
        # We load a chunk of recent history for demo.
        df = load_single_coin_history(symbol, "1h")
        if df is None or df.empty:
            st.error("Veri bulunamadı! Lütfen önce 'History Update' yapın.")
            return
            
        # Take last 500 candles for a quick demo
        data_slice = df.tail(500)
    
    st.success(f"Simülasyon Başladı! {len(data_slice)} mum işlenecek.")
    
    # C. Simulation Loop
    dashboard = st.empty()
    log_area = st.empty()
    logs = []
    
    progress_bar = st.progress(0)
    
    for i in range(50, len(data_slice)):
        # 1. Create Window (Data passed to Analyzer)
        # We simulate "arrival" by growing the window
        window = data_slice.iloc[:i] 
        current_bar = window.iloc[-1]
        
        # 2. Tick The Engine
        result = engine.tick(symbol, "1h", window)
        
        # 3. Visualize
        # Standardized M25 Account State
        account_state = executor.get_balance()
        usdt_val = account_state['equity']
        
        # Update Dashboard
        with dashboard.container():
            k1, k2, k3 = st.columns(3)
            with k1: _mini_metric("Zaman", str(current_bar.name))
            with k2: _mini_metric("Fiyat", f"${current_bar['close']:.2f}")
            with k3: _mini_metric("Portföy Değeri", f"${usdt_val:.2f}", delta=f"{usdt_val - initial_balance:.2f}")
        
        if result.get("execution"):
            execution = result["execution"]
            # Format Timestamp
            ts_str = execution['timestamp'].strftime("%H:%M:%S")
            
            if execution['success']:
                action_icon = "🟢 ALIM" if execution['action'] == "BUY" else "🔴 SATIM"
                total_val = execution['filled_qty'] * execution['filled_price']
                
                # Format: 22:00:00 | 🟢 ALIM | BTCUSDT | $89,000 | 0.005 adet ($450)
                log_msg = f"{ts_str} | {action_icon} | {execution['symbol']} | ${execution['filled_price']:.2f} | {execution['filled_qty']:.4f} adet (${total_val:.2f})"
                logs.append(log_msg)
            else:
                logs.append(f"❌ {ts_str} | {execution['symbol']} | Başarısız: {execution['error_message']}")
        
        # Use code block for logs to avoid Unique Key errors in loop (text_area is an input widget)
        # Use a Monospace font block but maybe custom HTML later for colors if requested.
        log_view = "\n".join(reversed(logs))
        log_area.code(log_view, language="text")
        
        progress_bar.progress(i / len(data_slice))
        time.sleep(0.1 / speed) # Speed control
        
    st.success("🏁 Simülasyon Tamamlandı!")
    
    # Summary Report
    total_pnl = usdt_val - initial_balance
    pnl_pct = (total_pnl / initial_balance) * 100
    trade_count = len([l for l in logs if "✅" in l])
    
    st.markdown("### 📊 Sonuç Karnesi")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam PnL", f"${total_pnl:.2f}", delta=f"{pnl_pct:.2f}%")
    c2.metric("İşlem Sayısı", trade_count)
    c3.metric("Son Bakiye", f"${usdt_val:.2f}")
    c4.metric("Süre", f"{len(data_slice)} Saat")
    
