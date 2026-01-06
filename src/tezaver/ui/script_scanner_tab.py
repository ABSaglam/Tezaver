"""
Script Scanner Tab
==================

A flexible script-based signal scanner with Win/Loss analysis.
User enters a Python expression, and the system scans all coins for matches.

Usage Example:
    vol > 7 and 50 < rsi < 70 and macd > 0
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field

from tezaver.core.config import DEFAULT_COINS
from tezaver.data.history_service import load_existing_history
from tezaver.simulation.strategy_scanner import calculate_indicators


# Default script template
DEFAULT_SCRIPT = """# Örnek: 7x hacim + RSI 50-70 + MACD pozitif
vol > 7 and 50 < rsi < 70 and macd > 0"""


@dataclass
class SignalResult:
    """A single signal with outcome."""
    symbol: str
    event_time: pd.Timestamp
    event_idx: int
    # Outcome
    max_gain_pct: float  # Max gain in next N bars
    max_loss_pct: float  # Max loss in next N bars
    final_pnl_pct: float  # P&L at exit
    outcome: str  # 'WIN', 'LOSS', 'NEUTRAL'
    # Context
    rsi: float
    macd: float
    volume_ratio: float


@dataclass
class ScanResult:
    """Complete scan result with statistics."""
    total_signals: int = 0
    wins: int = 0
    losses: int = 0
    neutrals: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    signals: List[SignalResult] = field(default_factory=list)


def evaluate_script(
    df: pd.DataFrame, 
    idx: int, 
    script: str
) -> bool:
    """
    Evaluate a custom script condition at the given bar.
    
    Available variables:
        rsi, rsi_ema, macd, macd_signal, macd_hist,
        ema9, ema21, ema50, bb_pos, bb_width, vol, close, open, high, low
    """
    if idx < 1 or idx >= len(df):
        return False
    
    bar = df.iloc[idx - 1]  # Use bar before trigger
    
    # Build evaluation context
    context = {
        'rsi': bar.get('rsi', 50),
        'rsi_ema': bar.get('rsi_ema', 50),
        'macd': bar.get('macd_hist', 0),  # Alias for histogram
        'macd_hist': bar.get('macd_hist', 0),
        'macd_line': bar.get('macd', 0),
        'macd_signal': bar.get('macd_signal', 0),
        'ema9': bar.get('ema9', 0),
        'ema21': bar.get('ema21', 0),
        'ema50': bar.get('ema50', 0),
        'ema200': bar.get('ema200', 0),
        'bb_pos': bar.get('bb_position', 0.5),
        'bb_upper': bar.get('bb_upper', 0),
        'bb_lower': bar.get('bb_lower', 0),
        'vol': bar.get('volume_ratio', 1),
        'volume': bar.get('volume_ratio', 1),
        'close': bar.get('close', 0),
        'open': bar.get('open', 0),
        'high': bar.get('high', 0),
        'low': bar.get('low', 0),
    }
    
    try:
        # Filter out comment lines
        clean_script = '\n'.join(
            line for line in script.split('\n') 
            if not line.strip().startswith('#')
        ).strip()
        
        if not clean_script:
            return False
        
        result = eval(clean_script, {"__builtins__": {}}, context)
        return bool(result)
    except Exception as e:
        return False


def calculate_outcome(
    df: pd.DataFrame,
    entry_idx: int,
    lookahead: int = 12,
    tp_threshold: float = 5.0,
    sl_threshold: float = 5.0
) -> Tuple[float, float, float, str]:
    """
    Calculate trade outcome after entry.
    
    Returns: (max_gain, max_loss, final_pnl, outcome)
    """
    if entry_idx >= len(df) - lookahead:
        lookahead = len(df) - entry_idx - 1
    
    if lookahead <= 0:
        return 0, 0, 0, 'NEUTRAL'
    
    entry_price = df['close'].iloc[entry_idx]
    future_slice = df.iloc[entry_idx + 1: entry_idx + lookahead + 1]
    
    if future_slice.empty:
        return 0, 0, 0, 'NEUTRAL'
    
    max_high = future_slice['high'].max()
    min_low = future_slice['low'].min()
    exit_price = future_slice['close'].iloc[-1]
    
    max_gain = (max_high - entry_price) / entry_price * 100
    max_loss = (min_low - entry_price) / entry_price * 100
    final_pnl = (exit_price - entry_price) / entry_price * 100
    
    # Determine outcome
    if max_gain >= tp_threshold:
        outcome = 'WIN'
    elif max_loss <= -sl_threshold:
        outcome = 'LOSS'
    else:
        outcome = 'NEUTRAL'
    
    return max_gain, max_loss, final_pnl, outcome


def scan_with_script(
    coins: List[str],
    timeframe: str,
    script: str,
    lookahead: int = 12,
    tp_threshold: float = 5.0,
    sl_threshold: float = 5.0,
    progress_callback=None
) -> ScanResult:
    """
    Scan all coins with a custom script condition.
    """
    result = ScanResult()
    all_signals = []
    
    for i, symbol in enumerate(coins):
        if progress_callback:
            progress_callback(i, len(coins))
        
        df = load_existing_history(symbol, timeframe)
        if df is None or len(df) < 100:
            continue
        
        if 'datetime' not in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        
        df = calculate_indicators(df)
        
        # Scan every bar
        for idx in range(50, len(df) - lookahead):
            if evaluate_script(df, idx, script):
                # Signal found, calculate outcome
                max_gain, max_loss, final_pnl, outcome = calculate_outcome(
                    df, idx, lookahead, tp_threshold, sl_threshold
                )
                
                signal = SignalResult(
                    symbol=symbol,
                    event_time=df['datetime'].iloc[idx],
                    event_idx=idx,
                    max_gain_pct=max_gain,
                    max_loss_pct=max_loss,
                    final_pnl_pct=final_pnl,
                    outcome=outcome,
                    rsi=df['rsi'].iloc[idx - 1],
                    macd=df['macd_hist'].iloc[idx - 1],
                    volume_ratio=df['volume_ratio'].iloc[idx]
                )
                all_signals.append(signal)
    
    # Calculate statistics
    result.signals = all_signals
    result.total_signals = len(all_signals)
    result.wins = sum(1 for s in all_signals if s.outcome == 'WIN')
    result.losses = sum(1 for s in all_signals if s.outcome == 'LOSS')
    result.neutrals = sum(1 for s in all_signals if s.outcome == 'NEUTRAL')
    
    if result.total_signals > 0:
        result.win_rate = result.wins / result.total_signals * 100
    
    win_gains = [s.max_gain_pct for s in all_signals if s.outcome == 'WIN']
    loss_losses = [s.max_loss_pct for s in all_signals if s.outcome == 'LOSS']
    
    if win_gains:
        result.avg_win = sum(win_gains) / len(win_gains)
    if loss_losses:
        result.avg_loss = sum(loss_losses) / len(loss_losses)
    
    return result


def render_signal_chart(
    symbol: str,
    timeframe: str,
    event_idx: int,
    lookback: int = 40,
    lookahead: int = 20
):
    """Render chart for a specific signal."""
    df = load_existing_history(symbol, timeframe)
    if df is None or df.empty:
        st.warning(f"{symbol} için veri bulunamadı.")
        return
    
    if 'datetime' not in df.columns:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    
    df = calculate_indicators(df)
    
    start_idx = max(0, event_idx - lookback)
    end_idx = min(len(df), event_idx + lookahead)
    subset = df.iloc[start_idx:end_idx].copy()
    
    if subset.empty:
        return
    
    # Create chart
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=['Fiyat', 'RSI', 'MACD']
    )
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=subset['datetime'],
        open=subset['open'],
        high=subset['high'],
        low=subset['low'],
        close=subset['close'],
        name='Fiyat',
        increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350'
    ), row=1, col=1)
    
    # EMAs
    for ema_col, color in [('ema9', '#ff9800'), ('ema21', '#2196f3'), ('ema50', '#9c27b0')]:
        if ema_col in subset.columns:
            fig.add_trace(go.Scatter(
                x=subset['datetime'], y=subset[ema_col],
                mode='lines', line=dict(color=color, width=1),
                name=ema_col.upper()
            ), row=1, col=1)
    
    # Signal marker
    rel_idx = event_idx - start_idx
    if 0 <= rel_idx < len(subset):
        fig.add_trace(go.Scatter(
            x=[subset['datetime'].iloc[rel_idx]],
            y=[subset['low'].iloc[rel_idx] * 0.99],
            mode='markers',
            marker=dict(symbol='triangle-up', size=15, color='#00ff00'),
            name='Sinyal'
        ), row=1, col=1)
    
    # RSI
    if 'rsi' in subset.columns:
        fig.add_trace(go.Scatter(
            x=subset['datetime'], y=subset['rsi'],
            mode='lines', line=dict(color='#e91e63', width=1.5),
            name='RSI'
        ), row=2, col=1)
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
    
    fig.update_layout(
        height=600,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        margin=dict(l=50, r=50, t=30, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(20,20,30,1)'
    )
    
    fig.update_xaxes(gridcolor='rgba(50,50,60,0.5)')
    fig.update_yaxes(gridcolor='rgba(50,50,60,0.5)')
    
    st.plotly_chart(fig, use_container_width=True)


def render_script_scanner_page():
    """Main render function for Script Scanner tab."""
    
    st.markdown("## 📝 Script Tarama")
    st.caption("Özel koşullarla sinyal tara ve Win/Loss analizi yap")
    
    # Session state
    if 'script_result' not in st.session_state:
        st.session_state['script_result'] = None
    if 'script_text' not in st.session_state:
        st.session_state['script_text'] = DEFAULT_SCRIPT
    
    # --- SCRIPT INPUT ---
    script = st.text_area(
        "Koşul Scripti",
        value=st.session_state['script_text'],
        height=120,
        help="""
Kullanılabilir değişkenler:
- rsi, rsi_ema (RSI göstergeleri)
- macd, macd_hist, macd_signal (MACD)
- ema9, ema21, ema50, ema200 (EMAs)
- bb_pos (Bollinger pozisyonu 0-1)
- vol (Hacim oranı)
- close, open, high, low (Fiyatlar)

Örnek: vol > 10 and 50 < rsi < 70 and macd > 0
        """,
        key="script_input"
    )
    st.session_state['script_text'] = script
    
    # Parameters
    param_cols = st.columns(4)
    with param_cols[0]:
        timeframe = st.selectbox("Timeframe", ["15m", "1h", "4h"], key="script_tf")
    with param_cols[1]:
        coin_limit = st.selectbox("Coin Limiti", [50, 100, 200, 300], key="script_coins")
    with param_cols[2]:
        tp_threshold = st.number_input("TP Eşik (%)", value=5.0, min_value=1.0, max_value=50.0, key="script_tp")
    with param_cols[3]:
        sl_threshold = st.number_input("SL Eşik (%)", value=5.0, min_value=1.0, max_value=50.0, key="script_sl")
    
    # Scan button
    col_btn, col_status = st.columns([1, 3])
    
    with col_btn:
        scan_clicked = st.button("▶ TARA", type="primary", use_container_width=True)
    
    with col_status:
        progress_placeholder = st.empty()
    
    if scan_clicked:
        coins = DEFAULT_COINS[:coin_limit]
        progress_bar = progress_placeholder.progress(0, text="Tarama başlıyor...")
        
        def progress_callback(current, total):
            pct = current / total
            progress_bar.progress(pct, text=f"Taranıyor: {current}/{total} coin...")
        
        result = scan_with_script(
            coins=coins,
            timeframe=timeframe,
            script=script,
            lookahead=12,
            tp_threshold=tp_threshold,
            sl_threshold=sl_threshold,
            progress_callback=progress_callback
        )
        
        st.session_state['script_result'] = result
        progress_placeholder.success(f"✅ {result.total_signals} sinyal bulundu!")
    
    # --- RESULTS ---
    result: ScanResult = st.session_state.get('script_result')
    
    if result and result.total_signals > 0:
        st.markdown("---")
        
        # Stats row
        stat_cols = st.columns(6)
        stat_cols[0].metric("Toplam Sinyal", result.total_signals)
        stat_cols[1].metric("✅ Win", result.wins, delta=f"%{result.win_rate:.1f}")
        stat_cols[2].metric("❌ Loss", result.losses)
        stat_cols[3].metric("➖ Nötr", result.neutrals)
        stat_cols[4].metric("Ort. Kazanç", f"%{result.avg_win:.1f}")
        stat_cols[5].metric("Ort. Kayıp", f"%{result.avg_loss:.1f}")
        
        # Signal list
        st.markdown("### 📋 Sonuç Listesi")
        
        # Convert to DataFrame for display
        signals_df = pd.DataFrame([
            {
                'Coin': s.symbol,
                'Zaman': s.event_time.strftime('%Y-%m-%d %H:%M') if pd.notna(s.event_time) else 'N/A',
                'Sonuç': f"{'✅' if s.outcome == 'WIN' else '❌' if s.outcome == 'LOSS' else '➖'} {s.outcome}",
                'Max Kazanç': f"%{s.max_gain_pct:.1f}",
                'Max Kayıp': f"%{s.max_loss_pct:.1f}",
                'RSI': f"{s.rsi:.1f}",
                'Hacim': f"{s.volume_ratio:.1f}x",
                '_idx': s.event_idx,
                '_symbol': s.symbol
            }
            for s in result.signals
        ])
        
        # Sort by time descending
        signals_df = signals_df.sort_values('Zaman', ascending=False)
        
        with st.expander(f"📊 {len(signals_df)} Sinyal Listesi", expanded=True):
            # Selection
            display_cols = ['Coin', 'Zaman', 'Sonuç', 'Max Kazanç', 'Max Kayıp', 'RSI', 'Hacim']
            
            st.dataframe(
                signals_df[display_cols].head(100),
                use_container_width=True,
                hide_index=True
            )
        
        # Signal selection for chart
        st.markdown("### 📈 Grafik İnceleme")
        
        signal_options = [
            f"{row['Coin']} | {row['Zaman']} | {row['Sonuç']}"
            for _, row in signals_df.head(100).iterrows()
        ]
        
        if signal_options:
            selected_idx = st.selectbox(
                "Sinyal Seç",
                range(len(signal_options)),
                format_func=lambda x: signal_options[x],
                key="script_selected_signal"
            )
            
            if selected_idx is not None:
                selected_row = signals_df.iloc[selected_idx]
                render_signal_chart(
                    symbol=selected_row['_symbol'],
                    timeframe=timeframe,
                    event_idx=int(selected_row['_idx'])
                )
    
    elif result is not None:
        st.info("Bu koşullara uygun sinyal bulunamadı.")
    
    # Help section
    with st.expander("📚 Kullanım Kılavuzu"):
        st.markdown("""
**Değişkenler:**
- `rsi`: RSI (14)
- `macd`: MACD Histogram
- `vol`: Hacim / Ortalama Hacim
- `ema9`, `ema21`, `ema50`: EMA değerleri
- `bb_pos`: Bollinger Band pozisyonu (0=alt, 1=üst)
- `close`, `open`, `high`, `low`: Fiyat değerleri

**Örnek Scriptler:**
```python
# Volume spike + RSI hazır + MACD pozitif
vol > 10 and 50 < rsi < 70 and macd > 0

# EMA bullish alignment
ema9 > ema21 and ema21 > ema50

# Bollinger squeeze breakout
vol > 5 and bb_pos > 0.8

# RSI oversold recovery
rsi < 35 and macd > macd_signal
```

**Win/Loss Mantığı:**
- Sinyalden sonra 12 bar izlenir
- Max kazanç >= TP eşiği → WIN
- Max kayıp <= -SL eşiği → LOSS
- Hiçbiri değilse → NEUTRAL
        """)


# For direct import
render_page = render_script_scanner_page
