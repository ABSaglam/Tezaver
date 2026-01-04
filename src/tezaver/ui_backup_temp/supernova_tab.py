import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import importlib
import tezaver.core.config
# Force reload config to pick up changes in DEFAULT_COINS
importlib.reload(tezaver.core.config)
from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths
import tezaver.supernova.supernova_detector
importlib.reload(tezaver.supernova.supernova_detector)
from tezaver.supernova.supernova_detector import SuperNovaDetector

def load_coin_data(symbol, timeframe='15m', lookback_bars=200):
    """Loads history and runs detector for a specific coin."""
    history_path = coin_cell_paths.get_history_file(symbol, timeframe)
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

def plot_supernova_chart(df, signals=None, title="SuperNova Analizi"):
    """
    Simplified chart for Live Detector tab (Overview).
    """
    if df is None or df.empty:
        return go.Figure()
        
    display_df = df.iloc[-50:].copy() # Show last 50 bars
    
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

    # Layout Settings
    fig.update_layout(
        title=title,
        yaxis_title='Fiyat',
        xaxis_title='Zaman',
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_rangeslider_visible=False
    )
    
    return fig

def plot_supernova_advanced_chart(df, event_data):
    """
    Draws an advanced 4-panel Sniper Studio chart (Price, Vol, MACD, RSI).
    Replicates 'Kalıpçı' chart style.
    """
    if df is None or df.empty:
        return go.Figure()

    # 1. Prepare Data Window
    # Center around event
    event_time = event_data['datetime']
    
    # Locate index
    # Ensure TZ-naive comparison
    times = df['datetime'].dt.tz_localize(None) if df['datetime'].dt.tz else df['datetime']
    evt_t = event_time.tz_localize(None) if event_time.tzinfo else event_time
    
    try:
        idx = times[times == evt_t].index[0]
    except IndexError:
        # Approximate matching if exact time missing
        idx = (times - evt_t).abs().argmin()
    
    # Window: 100 bars before, 50 bars after (or bars_to_peak + buffer)
    lookahead = event_data.get('bars_to_peak', 30)
    start_idx = max(0, idx - 100)
    end_idx = min(len(df), idx + lookahead + 40)
    
    sub_df = df.iloc[start_idx:end_idx].copy()
    
    # 2. Indicators Calculation (if missing from loaded df)
    # EMA
    if 'ema_20' not in sub_df.columns:
        sub_df['ema_20'] = sub_df['close'].ewm(span=20).mean()
    if 'ema_50' not in sub_df.columns:
        sub_df['ema_50'] = sub_df['close'].ewm(span=50).mean()
        
    # MACD (12, 26, 9) - Manual calc if not present
    if 'macd' not in sub_df.columns:
        exp1 = sub_df['close'].ewm(span=12, adjust=False).mean()
        exp2 = sub_df['close'].ewm(span=26, adjust=False).mean()
        sub_df['macd'] = exp1 - exp2
        sub_df['macd_signal'] = sub_df['macd'].ewm(span=9, adjust=False).mean()
        sub_df['macd_hist'] = sub_df['macd'] - sub_df['macd_signal']

    # RSI (14) - Detector already calcs 'rsi', but ensure 'rsi_ema'
    if 'rsi_ema' not in sub_df.columns:
        sub_df['rsi_ema'] = sub_df['rsi'].ewm(span=14).mean()
        
    # 3. Create Figure
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.15, 0.15, 0.2],
        specs=[[{}], [{}], [{}], [{}]],
        subplot_titles=("", "Hacim", "MACD", "RSI")
    )
    
    # --- Row 1: Price ---
    # Colors
    c_inc = '#089981'
    c_dec = '#F23645'
    
    fig.add_trace(go.Candlestick(
        x=sub_df['datetime'],
        open=sub_df['open'], high=sub_df['high'],
        low=sub_df['low'], close=sub_df['close'],
        name='OHLC',
        increasing_line_color=c_inc, decreasing_line_color=c_dec,
        showlegend=False
    ), row=1, col=1)
    
    # EMAs
    fig.add_trace(go.Scatter(x=sub_df['datetime'], y=sub_df['ema_20'], line=dict(color='orange', width=1), name='EMA 20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=sub_df['datetime'], y=sub_df['ema_50'], line=dict(color='blue', width=1), name='EMA 50'), row=1, col=1)
    
    # --- Row 2: Volume ---
    colors_vol = [c_inc if c >= o else c_dec for c, o in zip(sub_df['close'], sub_df['open'])]
    fig.add_trace(go.Bar(
        x=sub_df['datetime'], y=sub_df['volume'],
        marker_color=colors_vol, opacity=0.5, name='Volume'
    ), row=2, col=1)
    
    # --- Row 3: MACD ---
    # Histogram colors
    hist_colors = []
    prev_hist = sub_df['macd_hist'].shift(1).fillna(0)
    for i, val in enumerate(sub_df['macd_hist']):
        prev = prev_hist.iloc[i]
        if val >= 0:
            hist_colors.append('#00E676' if val > prev else '#B9F6CA') # Green strong vs weak
        else:
            hist_colors.append('#FF1744' if val < prev else '#FF8A80') # Red strong vs weak

    fig.add_trace(go.Bar(x=sub_df['datetime'], y=sub_df['macd_hist'], marker_color=hist_colors, name='Hist'), row=3, col=1)
    fig.add_trace(go.Scatter(x=sub_df['datetime'], y=sub_df['macd'], line=dict(color='#2962FF', width=1), name='MACD'), row=3, col=1)
    fig.add_trace(go.Scatter(x=sub_df['datetime'], y=sub_df['macd_signal'], line=dict(color='#FF9800', width=1), name='Signal'), row=3, col=1)
    
    # --- Row 4: RSI ---
    fig.add_trace(go.Scatter(x=sub_df['datetime'], y=sub_df['rsi'], line=dict(color='#7E57C2', width=1.5), name='RSI'), row=4, col=1)
    fig.add_trace(go.Scatter(x=sub_df['datetime'], y=sub_df['rsi_ema'], line=dict(color='yellow', width=1), name='RSI EMA'), row=4, col=1)
    
    # RSI Refs
    fig.add_hline(y=70, line_dash="dot", line_color="gray", row=4, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="gray", row=4, col=1)
    
    # --- 4. Event Overlays ---
    # Highlight Range: Entry -> Peak (or Bottom)
    
    # Calculate bar duration estimate to adjust start time for visual centering
    # (Assuming regular intervals, take median diff)
    if len(sub_df) > 1:
        diffs = sub_df['datetime'].diff().dropna()
        bar_duration = diffs.median()
    else:
        bar_duration = pd.Timedelta(minutes=15) # Fallback

    # Determine end time based on Outcome Type
    if event_data.get('outcome_type') == 'NEGATIVE' and 'min_price' in event_data:
        range_end = event_data['peak_time']
    else:
        range_end = event_data['peak_time']
    
    # Adjust Start to include the signal candle (approx half bar width left shift)
    # Using 0.6 to be safe and ensure coverage
    range_start = event_time - (bar_duration * 0.6)

    fig.add_vrect(
        x0=range_start, x1=range_end,
        fillcolor="rgba(255, 215, 0, 0.15)",
        layer="below", line_width=0,
        row=1, col=1
    )
    
    # Entry Line
    fig.add_vline(x=event_time, line_width=1, line_dash="dash", line_color="blue", row=1, col=1)
    fig.add_annotation(x=event_time, y=event_data['price'], text="GİRİŞ", showarrow=True, arrowhead=1, ax=20, ay=0, row=1, col=1)
    
    # Exit Line (at end of range)
    fig.add_vline(x=range_end, line_width=1, line_dash="dash", line_color="purple", row=1, col=1)
    
    # Layout Update
    title_str = f"Analiz: {event_data.get('tier', 'N/A')} | "
    if event_data.get('outcome_type') == 'POSITIVE':
        title_str += f"Kazanç: +{event_data['max_gain_pct']:.2f}%"
    else:
        title_str += f"Drawdown: {event_data.get('max_loss_pct', 0):.2f}%"
        
    fig.update_layout(
        title=title_str,
        height=800,
        dragmode='pan',
        hovermode='x unified',
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_rangeslider_visible=False
    )
    
    return fig


def render_inspector_tab(df, detector):
    """Renders the Backtest Inspector UI."""
    sub_tabs = st.tabs(["Hacim"])
    
    with sub_tabs[0]:
        st.caption("Geçmişteki tüm 3x+ hacim patlamalarını ve sonuçlarını (Tier) analiz eder.")
        
        col_dur, col_look, col_btn = st.columns([2, 1.5, 3])
        with col_dur:
            scan_duration = st.selectbox("Tarama Süresi", ['2 Yıl', '1 Yıl', '6 Ay', '3 Ay', '1 Ay', '1 Hafta'], label_visibility="collapsed")
        with col_look:
            lookahead = st.number_input("Bar Aralığı", min_value=10, max_value=200, value=30, step=10, label_visibility="collapsed", help="Analiz penceresi (bar)")
        
        with col_btn:
            if st.button("🔍 Geçmişi Tara (Backtest)", use_container_width=True):
                with st.spinner("Geçmiş taranıyor..."):
                    df_filtered = df.copy()
                    
                    try:
                        max_date = df['datetime'].max()
                        delta = None
                        if scan_duration == '1 Hafta': delta = pd.Timedelta(weeks=1)
                        elif scan_duration == '1 Ay': delta = pd.Timedelta(days=30)
                        elif scan_duration == '3 Ay': delta = pd.Timedelta(days=90)
                        elif scan_duration == '6 Ay': delta = pd.Timedelta(days=180)
                        elif scan_duration == '1 Yıl': delta = pd.Timedelta(days=365)
                        elif scan_duration == '2 Yıl': delta = pd.Timedelta(days=730)
                        
                        if delta:
                            cutoff = max_date - delta
                            df_filtered = df[df['datetime'] >= cutoff].copy()
                    except:
                        pass # Fallback to full

                    results = detector.analyze_backtest(df_filtered, lookahead=lookahead)
                    st.session_state['inspector_results'] = results
                
        st.markdown("""
            <style>
            /* Tier Button Styling - Flat Look */
            div[data-testid="column"] button {
                border: none !important;
                background: transparent !important;
                box-shadow: none !important;
                color: inherit !important;
            }
            div[data-testid="column"] button:hover {
                background: rgba(128, 128, 128, 0.1) !important;
                color: #FF4B4B !important; /* Streamlit Red accent */
            }
            div[data-testid="column"] button:active {
                transform: scale(0.98);
            }
            /* Highlight Selected Button */
            div[data-testid="column"] button:focus {
                border: 1px solid #FF4B4B !important;
            }
            </style>
        """, unsafe_allow_html=True)

        if 'inspector_results' in st.session_state:
            results = st.session_state['inspector_results']
            
            # Helper Callback for Selectboxes
            def update_selection(k):
                st.session_state['selected_event'] = st.session_state[k]

            # Initial Default Selection
            if 'selected_event' not in st.session_state:
                def_evts = [r for r in results if r['candle_color'] == 'GREEN' and r.get('outcome_type') == 'POSITIVE']
                if def_evts:
                    st.session_state['selected_event'] = def_evts[0]
            
            # Helper for icons
            def get_tier_icon(t):
                if t == 'DIAMOND': return '💎'
                elif t == 'GOLD': return '🏅'
                elif t == 'SILVER': return '🥈'
                elif t == 'BRONZE': return '🥉'
                else: return '⚙️'
            
            tiers = ['DIAMOND', 'GOLD', 'SILVER', 'BRONZE', 'IRON']

            # --- GREEN SECTION (MAIN) ---
            st.success("🟢 Hacim Analizi (Yeşil Mumlar)")
            # Filter for POSITIVE Outcome
            green_events = [r for r in results if r['candle_color'] == 'GREEN' and r.get('outcome_type') == 'POSITIVE']
            
            total_green = len(green_events)
            success_green = len([r for r in green_events if r['tier'] != 'FAIL'])
            if total_green > 0:
                st.metric("Toplam (Pozitif)", f"{total_green}", f"Başarılı: {success_green}")
                
            tier_cols_g = st.columns(len(tiers))
            if 'sel_tier_green' not in st.session_state: st.session_state['sel_tier_green'] = 'DIAMOND'

            for i, tier in enumerate(tiers):
                count = len([r for r in green_events if r['tier'] == tier])
                icon = get_tier_icon(tier)
                label = f"{icon} {count}"
                if tier_cols_g[i].button(label, key=f"btn_green_{tier}", help=f"{tier} Seviyesi", use_container_width=True):
                    st.session_state['sel_tier_green'] = tier
                    # Explicitly update selected event to match new tier
                    new_tier_evts = [r for r in green_events if r['tier'] == tier]
                    if new_tier_evts:
                        st.session_state['selected_event'] = new_tier_evts[0]
                    else:
                        st.session_state['selected_event'] = None

            curr_tier_g = st.session_state['sel_tier_green']
            st.markdown(f"**Seçili: {get_tier_icon(curr_tier_g)} {curr_tier_g}**")

            tier_events_g = [r for r in green_events if r['tier'] == curr_tier_g]
            selected_evt_g = None
            if not tier_events_g:
                st.caption("Bu seviyede olay yok.")
            else:
                def fmt_func_g(evt):
                        return f"{evt['datetime'].strftime('%d %b %H:%M')} | {evt['vol_ratio']:.1f}x | +{evt['max_gain_pct']:.1f}%"
                
                selected_evt_g = st.selectbox(
                    "Olay Seçin", 
                    tier_events_g, 
                    format_func=fmt_func_g,
                    key=f"selbox_green_{curr_tier_g}",
                    on_change=update_selection,
                    args=(f"selbox_green_{curr_tier_g}",)
                )
            
            # --- NEGATIVE SECTION (GREEN) ---
            st.markdown("---")
            st.caption("📉 Negatif Senaryolar (Drawdown)")
            
            # Filter for NEGATIVE Outcome
            neg_green_events = [r for r in results if r['candle_color'] == 'GREEN' and r.get('outcome_type') == 'NEGATIVE']
            
            if neg_green_events:
                    st.metric("Toplam (Negatif)", f"{len(neg_green_events)}")
            
            cols_neg_g = st.columns(len(tiers))
            if 'sel_neg_tier_green' not in st.session_state: st.session_state['sel_neg_tier_green'] = 'IRON'
            
            for i, tier in enumerate(tiers):
                count = len([r for r in neg_green_events if r['neg_tier'] == tier])
                icon = get_tier_icon(tier)
                label = f"{icon} {count}"
                if cols_neg_g[i].button(label, key=f"btn_neg_green_{tier}", help=f"Drawdown {tier}", use_container_width=True):
                    st.session_state['sel_neg_tier_green'] = tier
                    # Explicitly update selected event to match new tier
                    new_neg_tier_evts = [r for r in neg_green_events if r['neg_tier'] == tier]
                    if new_neg_tier_evts:
                        st.session_state['selected_event'] = new_neg_tier_evts[0]
                    else:
                        st.session_state['selected_event'] = None
                    
            curr_neg_tier_g = st.session_state['sel_neg_tier_green']
            st.markdown(f"**Seçili: {get_tier_icon(curr_neg_tier_g)} {curr_neg_tier_g} (Neg)**")
            
            tier_neg_events_g = [r for r in neg_green_events if r['neg_tier'] == curr_neg_tier_g]
            if not tier_neg_events_g:
                st.caption("Bu seviyede olay yok.")
            else:
                def fmt_func_neg_g(evt):
                    return f"{evt['datetime'].strftime('%d %b %H:%M')} | Drawdown: {evt['max_loss_pct']:.1f}%"
                
                sel_neg_evt_g = st.selectbox(
                    "Kayba Göre Olay Seç", 
                    tier_neg_events_g, 
                    format_func=fmt_func_neg_g, 
                    key=f"selbox_neg_green_{curr_neg_tier_g}",
                    on_change=update_selection,
                    args=(f"selbox_neg_green_{curr_neg_tier_g}",)
                )


            # --- CHART AREA ---
            st.markdown("---")
            if 'selected_event' in st.session_state:
                evt = st.session_state['selected_event']
                
                # Use Advanced Chart
                fig = plot_supernova_advanced_chart(df, evt)
                st.plotly_chart(fig, use_container_width=True, theme="streamlit")
                
                # Metadata Display
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Tarih", evt['datetime'].strftime('%d %b %H:%M'))
                m2.metric("Giriş Fiyatı", f"{evt['price']:.4f}")
                
                if evt.get('outcome_type') == 'POSITIVE':
                    m3.metric("Tepe Fiyatı", f"{evt['peak_price']:.4f}")
                    m4.metric("Maks Kazanç", f"%{evt['max_gain_pct']:.2f}")
                else:
                    # Show drawdown info
                    # Assuming min_price/max_loss is available in evt
                    loss_val = evt.get('max_loss_pct', 0)
                    m3.metric("Dip Fiyatı", f"{evt.get('min_price', 0):.4f}")
                    m4.metric("Maks Kayıp", f"{loss_val:.2f}%", delta=f"{loss_val:.2f}%", delta_color="inverse")
            else:
                st.info("👆 Analiz etmek için listeden bir olay seçin.")


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
        timeframe = st.selectbox("Zaman Dilimi", ["15m", "1h", "4h"], index=0)

    # Load Data
    df, detector, signals = load_coin_data(selected_coin, timeframe=timeframe, lookback_bars=30)
    
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
