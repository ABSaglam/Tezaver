"""
Strategy Studio Tab
===================

Visual interface for designing, testing, and inspecting trading strategies.

Features:
- Checkbox-based condition selection
- Scan button with progress
- Tier distribution display
- Coin/Event selection dropdowns
- Interactive candlestick chart
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Optional
from pathlib import Path

from tezaver.core.config import DEFAULT_COINS
from tezaver.data.history_service import load_existing_history
from tezaver.simulation.strategy_scanner import (
    AVAILABLE_CONDITIONS,
    scan_with_formula,
    get_unique_symbols,
    get_events_for_symbol,
    calculate_indicators,
    StrategyScanResult
)


def render_strategy_chart(
    symbol: str,
    timeframe: str,
    event_idx: int,
    lookback: int = 50,
    lookahead: int = 20
):
    """
    Render a candlestick chart for the given event.
    Similar to Molder/Kalıpçı style.
    """
    df = load_existing_history(symbol, timeframe)
    if df is None or df.empty:
        st.warning(f"{symbol} için veri bulunamadı.")
        return
    
    if 'datetime' not in df.columns:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    
    df = calculate_indicators(df)
    
    # Define window
    start_idx = max(0, event_idx - lookback)
    end_idx = min(len(df), event_idx + lookahead)
    subset = df.iloc[start_idx:end_idx].copy()
    
    if subset.empty:
        st.warning("Grafik için yeterli veri yok.")
        return
    
    # Create subplots: price, RSI, MACD, Volume
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.15, 0.15, 0.2],
        subplot_titles=['Fiyat', 'RSI', 'MACD', 'Hacim']
    )
    
    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=subset['datetime'],
            open=subset['open'],
            high=subset['high'],
            low=subset['low'],
            close=subset['close'],
            name='Fiyat',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350'
        ),
        row=1, col=1
    )
    
    # EMA lines
    if 'ema9' in subset.columns:
        fig.add_trace(go.Scatter(
            x=subset['datetime'], y=subset['ema9'],
            mode='lines', line=dict(color='#ff9800', width=1),
            name='EMA9'
        ), row=1, col=1)
    
    if 'ema21' in subset.columns:
        fig.add_trace(go.Scatter(
            x=subset['datetime'], y=subset['ema21'],
            mode='lines', line=dict(color='#2196f3', width=1),
            name='EMA21'
        ), row=1, col=1)
    
    if 'ema50' in subset.columns:
        fig.add_trace(go.Scatter(
            x=subset['datetime'], y=subset['ema50'],
            mode='lines', line=dict(color='#9c27b0', width=1.5),
            name='EMA50'
        ), row=1, col=1)
    
    # Bollinger Bands
    if 'bb_upper' in subset.columns:
        fig.add_trace(go.Scatter(
            x=subset['datetime'], y=subset['bb_upper'],
            mode='lines', line=dict(color='rgba(150,150,150,0.5)', width=1, dash='dot'),
            name='BB Upper'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=subset['datetime'], y=subset['bb_lower'],
            mode='lines', line=dict(color='rgba(150,150,150,0.5)', width=1, dash='dot'),
            name='BB Lower',
            fill='tonexty', fillcolor='rgba(150,150,150,0.1)'
        ), row=1, col=1)
    
    # Event marker
    rel_idx = event_idx - start_idx
    if 0 <= rel_idx < len(subset):
        event_time = subset['datetime'].iloc[rel_idx]
        event_price = subset['low'].iloc[rel_idx] * 0.995
        
        fig.add_trace(go.Scatter(
            x=[event_time],
            y=[event_price],
            mode='markers+text',
            marker=dict(symbol='triangle-up', size=15, color='#00ff00'),
            text=['▲ GİRİŞ'],
            textposition='bottom center',
            name='Event'
        ), row=1, col=1)
    
    # RSI
    if 'rsi' in subset.columns:
        fig.add_trace(go.Scatter(
            x=subset['datetime'], y=subset['rsi'],
            mode='lines', line=dict(color='#e91e63', width=1.5),
            name='RSI'
        ), row=2, col=1)
        
        if 'rsi_ema' in subset.columns:
            fig.add_trace(go.Scatter(
                x=subset['datetime'], y=subset['rsi_ema'],
                mode='lines', line=dict(color='#9c27b0', width=1, dash='dash'),
                name='RSI-EMA'
            ), row=2, col=1)
        
        # RSI levels
        fig.add_hline(y=70, line_dash='dot', line_color='red', row=2, col=1)
        fig.add_hline(y=50, line_dash='dot', line_color='gray', row=2, col=1)
        fig.add_hline(y=30, line_dash='dot', line_color='green', row=2, col=1)
    
    # MACD
    if 'macd_hist' in subset.columns:
        colors = ['#26a69a' if v >= 0 else '#ef5350' for v in subset['macd_hist']]
        fig.add_trace(go.Bar(
            x=subset['datetime'], y=subset['macd_hist'],
            marker_color=colors,
            name='MACD Hist'
        ), row=3, col=1)
        
        if 'macd' in subset.columns:
            fig.add_trace(go.Scatter(
                x=subset['datetime'], y=subset['macd'],
                mode='lines', line=dict(color='#2196f3', width=1),
                name='MACD'
            ), row=3, col=1)
        
        if 'macd_signal' in subset.columns:
            fig.add_trace(go.Scatter(
                x=subset['datetime'], y=subset['macd_signal'],
                mode='lines', line=dict(color='#ff9800', width=1),
                name='Signal'
            ), row=3, col=1)
    
    # Volume
    if 'volume' in subset.columns:
        vol_colors = ['#26a69a' if subset['close'].iloc[i] >= subset['open'].iloc[i] else '#ef5350' 
                      for i in range(len(subset))]
        fig.add_trace(go.Bar(
            x=subset['datetime'], y=subset['volume'],
            marker_color=vol_colors,
            name='Volume',
            opacity=0.7
        ), row=4, col=1)
    
    # Layout
    fig.update_layout(
        height=700,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        margin=dict(l=50, r=50, t=30, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(20,20,30,1)'
    )
    
    fig.update_xaxes(gridcolor='rgba(50,50,60,0.5)')
    fig.update_yaxes(gridcolor='rgba(50,50,60,0.5)')
    
    st.plotly_chart(fig, use_container_width=True)


def render_strategy_studio_page():
    """Main render function for Strategy Studio tab."""
    
    st.markdown("## 🎯 Strateji Stüdyosu")
    st.caption("Görsel strateji tasarımı ve test aracı")
    
    # Initialize session state
    if 'strategy_result' not in st.session_state:
        st.session_state['strategy_result'] = None
    if 'strategy_conditions' not in st.session_state:
        st.session_state['strategy_conditions'] = {k: v['default'] for k, v in AVAILABLE_CONDITIONS.items()}
    
    # --- CONDITION SELECTION ---
    st.markdown("### 📋 Koşullar")
    
    cond_cols = st.columns(4)
    conditions = {}
    
    for i, (cond_key, cond_info) in enumerate(AVAILABLE_CONDITIONS.items()):
        col = cond_cols[i % 4]
        with col:
            default_val = st.session_state['strategy_conditions'].get(cond_key, cond_info['default'])
            conditions[cond_key] = st.checkbox(
                cond_info['label'],
                value=default_val,
                help=cond_info['description'],
                key=f"cond_{cond_key}"
            )
    
    st.session_state['strategy_conditions'] = conditions
    
    # --- PARAMETERS ---
    st.markdown("### ⚙️ Parametreler")
    
    param_cols = st.columns(4)
    
    with param_cols[0]:
        timeframe = st.selectbox("Timeframe", ["15m", "1h", "4h"], key="strat_tf")
    
    with param_cols[1]:
        coin_limit = st.selectbox("Coin Limiti", [100, 200, 300, 500], key="strat_coin_limit")
    
    with param_cols[2]:
        min_volume = st.selectbox("Min Hacim", [7, 10, 15, 20], key="strat_min_vol", format_func=lambda x: f"{x}x")
    
    with param_cols[3]:
        min_gain = st.selectbox("Min Kazanç", [5, 10, 15, 20], key="strat_min_gain", format_func=lambda x: f"%{x}")
    
    # --- SCAN BUTTON ---
    col_btn, col_status = st.columns([1, 3])
    
    with col_btn:
        scan_clicked = st.button("▶ TARAMAYI BAŞLAT", type="primary", use_container_width=True)
    
    with col_status:
        progress_placeholder = st.empty()
    
    if scan_clicked:
        coins = DEFAULT_COINS[:coin_limit]
        
        progress_bar = progress_placeholder.progress(0, text="Tarama başlıyor...")
        
        def progress_callback(current, total):
            pct = current / total
            progress_bar.progress(pct, text=f"Taranıyor: {current}/{total} coin...")
        
        result = scan_with_formula(
            coins=coins,
            timeframe=timeframe,
            conditions=conditions,
            min_volume_ratio=float(min_volume),
            min_gain_pct=float(min_gain),
            progress_callback=progress_callback
        )
        
        st.session_state['strategy_result'] = result
        progress_placeholder.success(f"✅ Tarama tamamlandı! {result.total_events} olay bulundu.")
    
    # --- RESULTS ---
    result: StrategyScanResult = st.session_state.get('strategy_result')
    
    if result and result.total_events > 0:
        st.markdown("---")
        st.markdown("### 📊 Sonuçlar")
        
        # Tier cards
        tier_cols = st.columns(5)
        
        with tier_cols[0]:
            st.metric("💎 Diamond", result.diamond_count)
        with tier_cols[1]:
            st.metric("🥇 Gold", result.gold_count)
        with tier_cols[2]:
            st.metric("🥈 Silver", result.silver_count)
        with tier_cols[3]:
            st.metric("🥉 Bronze", result.bronze_count)
        with tier_cols[4]:
            st.metric("📊 Toplam", result.total_events, delta=f"%{result.avg_gain:.1f} ort.")
        
        # --- COIN & EVENT SELECTION ---
        st.markdown("---")
        st.markdown("### 🔍 İnceleme")
        
        sel_cols = st.columns([1, 2])
        
        with sel_cols[0]:
            symbols = get_unique_symbols(result)
            selected_symbol = st.selectbox(
                "Coin Seç",
                symbols,
                key="strat_selected_symbol"
            )
        
        if selected_symbol:
            symbol_events = get_events_for_symbol(result, selected_symbol)
            
            with sel_cols[1]:
                # Format event options
                event_options = []
                for _, row in symbol_events.iterrows():
                    time_str = row['event_time'].strftime('%Y-%m-%d %H:%M') if pd.notna(row['event_time']) else 'N/A'
                    tier_icon = {'DIAMOND': '💎', 'GOLD': '🥇', 'SILVER': '🥈', 'BRONZE': '🥉'}.get(row['tier'], '📦')
                    event_options.append(f"{time_str} | {tier_icon} %{row['gain_pct']:.1f}")
                
                selected_event_idx = st.selectbox(
                    "Event Seç",
                    range(len(event_options)),
                    format_func=lambda x: event_options[x],
                    key="strat_selected_event"
                )
            
            if selected_event_idx is not None and len(symbol_events) > 0:
                event_row = symbol_events.iloc[selected_event_idx]
                
                # Event info bar
                info_cols = st.columns(6)
                info_cols[0].metric("RSI", f"{event_row['rsi']:.1f}")
                info_cols[1].metric("MACD", "+" if event_row['macd_hist'] > 0 else "-")
                info_cols[2].metric("BB Pos", f"{event_row['bb_position']:.2f}")
                info_cols[3].metric("EMA", event_row['ema_aligned'])
                info_cols[4].metric("Hacim", f"{event_row['volume_ratio']:.1f}x")
                info_cols[5].metric("Kazanç", f"%{event_row['gain_pct']:.1f}")
                
                # Chart
                st.markdown("---")
                render_strategy_chart(
                    symbol=selected_symbol,
                    timeframe=timeframe,
                    event_idx=int(event_row['event_idx'])
                )
    
    elif result is not None:
        st.info("Seçilen kriterlere uygun olay bulunamadı. Koşulları gevşetmeyi deneyin.")


# For direct import
render_page = render_strategy_studio_page
