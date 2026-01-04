"""
SuperNova Module - Focused SUPERNOVA Pattern Detection
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import importlib
import tezaver.core.config
# Force reload config to pick up changes in DEFAULT_COINS
importlib.reload(tezaver.core.config)
from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths
from tezaver.supernova.supernova_detector import SuperNovaDetector

def load_coin_data(symbol, lookback_bars=200):
    """Loads history and runs detector for a specific coin."""
    history_path = coin_cell_paths.get_history_file(symbol, '15m')
    if not history_path.exists():
        return None, None, []
        
    df = pd.read_parquet(history_path)
    if df.empty:
        return None, None, []
        
    # Calculate indicators
    detector = SuperNovaDetector()
    df = detector.calculate_indicators(df)
    
    # Run detection on recent history (for live tab)
    signals = detector.detect(symbol, df, lookback=lookback_bars)
    
    return df, detector, signals

def plot_supernova_chart(df, signals=None, mode_filter=None, highlight_range=None, title="SuperNova Analizi"):
    """
    Draws an interactive Plotly chart with Price, Volume, and Signals.
    :param highlight_range: (start_time, end_time) to highlight in yellow
    """
    # If highlighting, center the chart around the event
    if highlight_range:
        start_t, end_t = highlight_range
        # Find index of start
        mask = df['datetime'] == start_t
        if mask.any():
            idx = df[mask].index[0]
            # Show 50 bars before and 100 bars after
            s_idx = max(0, idx - 50)
            e_idx = min(len(df), idx + 100)
            display_df = df.iloc[s_idx:e_idx].copy()
        else:
            display_df = df.iloc[-96:].copy()
    else:
        display_df = df.iloc[-96:].copy() # Last 24h default
    
    fig = go.Figure()

    # 1. Candlestick
    fig.add_trace(go.Candlestick(
        x=display_df['datetime'],
        open=display_df['open'],
        high=display_df['high'],
        low=display_df['low'],
        close=display_df['close'],
        name='Fiyat'
    ))

    # 2. Add Signals
    if signals:
        for sig in signals:
            if sig.timestamp >= display_df['datetime'].iloc[0] and sig.timestamp <= display_df['datetime'].iloc[-1]:
                if mode_filter and sig.mode != mode_filter:
                    continue
                    
                color = 'red' if sig.mode == 'REVERSAL' else 'green'
                symbol = 'triangle-up' if sig.mode == 'MOMENTUM' else 'triangle-down'
                
                fig.add_trace(go.Scatter(
                    x=[sig.timestamp],
                    y=[sig.price],
                    mode='markers',
                    marker=dict(symbol=symbol, size=12, color=color),
                    name=f'{sig.mode} ({sig.volume_ratio:.1f}x)',
                    hovertext=f"RSI: {sig.rsi:.1f}<br>Vol: {sig.volume_ratio:.1f}x"
                ))
    
    # 3. Highlight Range (Yellow Rectangle)
    if highlight_range:
        start_t, end_t = highlight_range
        fig.add_vrect(
            x0=start_t, x1=end_t,
            fillcolor="yellow", opacity=0.15,
            layer="below", line_width=0,
        )

    # Layout Settings
    fig.update_layout(
        title=title,
        yaxis_title='Fiyat',
        xaxis_title='Zaman',
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

def render_inspector_tab(df, detector):
    """Renders the Backtest Inspector UI."""
    st.caption("Geçmişteki tüm 3x+ hacim patlamalarını ve sonuçlarını (Tier) analiz eder.")
    
    if st.button("🔍 Geçmişi Tara (Backtest)", use_container_width=True):
        with st.spinner("Geçmiş taranıyor..."):
            results = detector.analyze_backtest(df, lookahead=96)
            st.session_state['inspector_results'] = results
            
    if 'inspector_results' in st.session_state:
        results = st.session_state['inspector_results']
        
        # Split by Candle Color (Proxy for Red/Green Mode)
        # RED: Red Candle (Reversal potential)
        # GREEN: Green Candle (Momentum potential)
        
        col_red, col_green = st.columns(2)
        
        # --- RED SECTION ---
        with col_red:
            st.error("🔴 RED İNCELEMESİ (Kırmızı Mumlar)")
            red_events = [r for r in results if r['candle_color'] == 'RED']
            
            # Metrics
            total_red = len(red_events)
            success_red = len([r for r in red_events if r['tier'] != 'FAIL'])
            if total_red > 0:
                st.metric("Toplam / Başarılı", f"{total_red} / {success_red}", f"{success_red/total_red*100:.1f}%")
            
            # Tier Lists
            tiers = ['DIAMOND', 'GOLD', 'SILVER', 'BRONZE']
            selected_red_event = None
            
            for tier in tiers:
                tier_events = [r for r in red_events if r['tier'] == tier]
                label = f"{'💎' if tier=='DIAMOND' else '🥇' if tier=='GOLD' else '🥈' if tier=='SILVER' else '🥉'} {tier} ({len(tier_events)})"
                
                with st.expander(label):
                    for evt in tier_events:
                        evt_label = f"{evt['datetime'].strftime('%d %b %H:%M')} | {evt['vol_ratio']:.1f}x | +{evt['max_gain_pct']:.1f}% ({evt['bars_to_peak']} bar)"
                        if st.button(evt_label, key=f"red_{evt['datetime']}"):
                            st.session_state['selected_event'] = evt

        # --- GREEN SECTION ---
        with col_green:
            st.success("🟢 GREEN İNCELEMESİ (Yeşil Mumlar)")
            green_events = [r for r in results if r['candle_color'] == 'GREEN']
            
            # Metrics
            total_green = len(green_events)
            success_green = len([r for r in green_events if r['tier'] != 'FAIL'])
            if total_green > 0:
                st.metric("Toplam / Başarılı", f"{total_green} / {success_green}", f"{success_green/total_green*100:.1f}%")
                
            # Tier Lists
            selected_green_event = None
            
            for tier in tiers:
                tier_events = [r for r in green_events if r['tier'] == tier]
                label = f"{'💎' if tier=='DIAMOND' else '🥇' if tier=='GOLD' else '🥈' if tier=='SILVER' else '🥉'} {tier} ({len(tier_events)})"
                
                with st.expander(label):
                    for evt in tier_events:
                        evt_label = f"{evt['datetime'].strftime('%d %b %H:%M')} | {evt['vol_ratio']:.1f}x | +{evt['max_gain_pct']:.1f}% ({evt['bars_to_peak']} bar)"
                        if st.button(evt_label, key=f"green_{evt['datetime']}"):
                            st.session_state['selected_event'] = evt

        st.markdown("---")
        
        # --- CHART ---
        if 'selected_event' in st.session_state:
            evt = st.session_state['selected_event']
            st.subheader(f"Seçilen Sinyal: {evt['tier']} ({evt['datetime']})")
            
            # Highlight range: Signal to Peak
            hl_range = (evt['datetime'], evt['peak_time'])
            
            # Custom signal object for plotting
            from tezaver.supernova.supernova_detector import SuperNovaSignal
            fake_sig = SuperNovaSignal(
                "", evt['datetime'], 
                'REVERSAL' if evt['candle_color']=='RED' else 'MOMENTUM', 
                evt['price'], evt['vol_ratio'], 0, evt['candle_color'], 0
            )
            
            fig = plot_supernova_chart(
                df, 
                signals=[fake_sig], 
                highlight_range=hl_range, 
                title=f"Analiz: +{evt['max_gain_pct']:.1f}% Kazanç"
            )
            st.plotly_chart(fig, use_container_width=True)

def render_supernova_page():
    """Main SuperNova UI."""
    st.title("💥 SuperNova Stüdyosu")
    
    # 1. Coin Selection (Top Level)
    col1, col2 = st.columns([3, 1])
    with col1:
        # DEBUG
        # st.caption(f"Yüklü Coin Sayısı: {len(DEFAULT_COINS)}") 
        selected_coin = st.selectbox("Coin Seçin", DEFAULT_COINS, index=DEFAULT_COINS.index('RENDERUSDT') if 'RENDERUSDT' in DEFAULT_COINS else 0)
    with col2:
        lookback = st.selectbox("Pencere", [96, 200, 500], format_func=lambda x: f"Son {x} Bar")

    # Load Data
    df, detector, signals = load_coin_data(selected_coin, lookback_bars=lookback)
    
    if df is None:
        st.error(f"{selected_coin} verisi bulunamadı.")
        return

    # 2. Main Tabs
    main_tab1, main_tab2, main_tab3 = st.tabs(["📡 Dedektör", "🕵️ Denetçi (Backtest)", "🏎️ Rally"])
    
    # --- TAB 1: DETECTOR (LIVE) ---
    with main_tab1:
        reversal_signals = [s for s in signals if s.mode == 'REVERSAL']
        momentum_signals = [s for s in signals if s.mode == 'MOMENTUM']
        
        st.markdown("### Canlı Tarama")
        col_red, col_green = st.columns(2)
        
        with col_red:
            st.error(f"🔴 RED (Reversal): {len(reversal_signals)}")
            if reversal_signals:
                s_data = [{"Zaman": s.timestamp, "Fiyat": s.price, "Vol": f"{s.volume_ratio:.1f}x"} for s in reversal_signals]
                st.dataframe(pd.DataFrame(s_data), hide_index=True, use_container_width=True)
                
        with col_green:
            st.success(f"🟢 GREEN (Momentum): {len(momentum_signals)}")
            if momentum_signals:
                s_data = [{"Zaman": s.timestamp, "Fiyat": s.price, "Vol": f"{s.volume_ratio:.1f}x"} for s in momentum_signals]
                st.dataframe(pd.DataFrame(s_data), hide_index=True, use_container_width=True)
        
        st.markdown("---")
        fig = plot_supernova_chart(df, signals, title=f"Canlı Analiz: {selected_coin}")
        st.plotly_chart(fig, use_container_width=True)

    # --- TAB 2: INSPECTOR (BACKTEST) ---
    with main_tab2:
        render_inspector_tab(df, detector)

    # --- TAB 3: RALLY ---
    with main_tab3:
        st.subheader(f"{selected_coin} Ralli Arşivi")
        rally_path = coin_cell_paths.get_coin_data_dir(selected_coin) / "fast15_rallies_summary.json"
        if rally_path.exists():
            import json
            with open(rally_path, 'r') as f:
                summary = json.load(f)
            st.json(summary)
        else:
            st.warning("Veri yok.")
