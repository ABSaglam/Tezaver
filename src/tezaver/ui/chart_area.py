"""
Tezaver Mac - Chart Area Module (M23_NEW_CHART)

Bu modül, Coin Detay ekranı için ana grafik alanını oluşturur.
TradingView tarzı fiyat + hacim grafiği ile event odaklı görselleştirme.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import streamlit as st
from datetime import timedelta

from tezaver.core import coin_cell_paths


@dataclass
class ChartFocus:
    """
    Grafik odak noktasını temsil eden dataclass.
    
    Attributes:
        symbol: Coin sembolü (örn. "BTCUSDT")
        timeframe: Zaman dilimi (örn. "1h", "4h", "1d")
        event_time: Opsiyonel event timestamp'i (pd.Timestamp)
        event_meta: Event'ten gelen ek bilgiler (dict)
    """
    symbol: str
    timeframe: str
    event_time: Optional[pd.Timestamp] = None
    event_meta: Optional[Dict[str, Any]] = None


# Default configuration
# Default indicator settings
DEFAULT_INDICATOR_SETTINGS = {
    'ema_fast': {
        'enabled': True,
        'period': 20,
        'color': '#2962FF'
    },
    'ema_slow': {
        'enabled': True,
        'period': 50,
        'color': '#FF9800'
    },
    'atr': {
        'enabled': True,
        'period': 14,
        'color': '#00BCD4',
        'multiplier': 1.0
    },
    'rsi': {
        'enabled': True,
        'period': 11,   # Updated to 11
        'color': '#7E57C2'
    },
    'rsi_ema': {
        'enabled': True,
        'period': 11,   # Updated to 11
        'color': '#FFC107'
    },
    'macd': {
        'enabled': True,
        'fast': 12,
        'slow': 26,
        'signal': 9,
        'macd_color': '#2962FF',
        'signal_color': '#FF9800',
        'hist_pos_inc_color': '#00E676',  # 1. Green
        'hist_pos_dec_color': '#D500F9',  # 2. Purple
        'hist_neg_inc_color': '#FF1744',  # 3. Red
        'hist_neg_dec_color': '#FFEA00'   # 4. Yellow
    },
    'volume': {
        'enabled': True,
        'up_color': '#089981',
        'down_color': '#F23645'
    },
    'candles': {
        'sync_with_volume': True
    }
}



@st.cache_data(ttl=60)
def load_history_data(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    coin_cells/{SYMBOL}/data/history_{TF}.parquet dosyasını yükler.
    
    Args:
        symbol: Coin sembolü
        timeframe: Zaman dilimi
    
    Returns:
        DataFrame with OHLCV data or None if not found
    """
    history_file = coin_cell_paths.get_history_file(symbol, timeframe)
    
    if not history_file.exists():
        return None
    
    try:
        df = pd.read_parquet(history_file)
        
        # Ensure open_time is datetime
        if 'open_time' in df.columns:
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        elif 'datetime' in df.columns:
            df['open_time'] = pd.to_datetime(df['datetime'])
        elif 'timestamp' in df.columns:
            df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        return df
    except Exception as e:
        print(f"Error loading history for {symbol} {timeframe}: {e}")
        return None


@st.cache_data(ttl=60)
def load_features_data(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """Load features parquet for RSI/MACD indicators."""
    from tezaver.snapshots.snapshot_engine import load_features
    try:
        df = load_features(symbol, timeframe)
        if 'timestamp' in df.columns:
            df['open_time'] = pd.to_datetime(df['timestamp'])
        elif 'open_time' not in df.columns:
            df['open_time'] = pd.to_datetime(df.index)
        return df
    except:
        return None


def build_coin_chart_figure(
    focus: ChartFocus,
    window_before: int,
    window_after: int,
    indicator_settings: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[go.Figure], Optional[pd.Series], Optional[Dict]]:
    """
    Verilen focus için TradingView tarzı 4 panelli grafik oluşturur.
    Panel 1: Fiyat + EMA'lar
    Panel 2: Hacim
    Panel 3: MACD
    Panel 4: RSI
    
    Args:
        focus: ChartFocus objesi
        window_before: Event öncesi bar sayısı
        window_after: Event sonrası bar sayısı
        indicator_settings: İndikatör ayarları (None ise default kullanılır)
    
    Returns:
        Tuple of (Plotly Figure, center_bar Series, data_info Dict)
    """
    # Use default settings if none provided
    if indicator_settings is None:
        indicator_settings = DEFAULT_INDICATOR_SETTINGS
    # Load history data
    df = load_history_data(focus.symbol, focus.timeframe)
    
    if df is None or df.empty:
        return None, None, None
    
    
    # Convert timestamps to Turkey Time using standard function
    from tezaver.core.config import to_turkey_time
    if 'open_time' in df.columns:
        df['open_time'] = df['open_time'].apply(lambda x: to_turkey_time(x) if pd.notna(x) else x)
    if isinstance(df.index, pd.DatetimeIndex):
        df.index = df.index.map(to_turkey_time)
    
    
    # Calculate EMAs if not present (though usually present in features)
    if 'ema_fast' not in df.columns:
        df['ema_fast'] = df['close'].ewm(span=20, adjust=False).mean()
    if 'ema_slow' not in df.columns:
        df['ema_slow'] = df['close'].ewm(span=50, adjust=False).mean()
        
    # Calculate MACD/RSI if missing (fallback)
    if 'macd_line' not in df.columns:
        exp12 = df['close'].ewm(span=12, adjust=False).mean()
        exp26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd_line'] = exp12 - exp26
        df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd_line'] - df['macd_signal']
        
    if 'rsi' not in df.columns:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
    
    # Calculate RSI EMA if missing
    if 'rsi_ema' not in df.columns and 'rsi' in df.columns:
        rsi_ema_period = indicator_settings.get('rsi_ema', {}).get('period', 14)
        df['rsi_ema'] = df['rsi'].ewm(span=rsi_ema_period, adjust=False).mean()
    
    # Calculate ATR if missing
    if 'atr' not in df.columns:
        df['tr'] = df[['high', 'low', 'close']].apply(
            lambda row: max(row['high'] - row['low'],
                          abs(row['high'] - df['close'].shift(1).loc[row.name]) if pd.notna(df['close'].shift(1).loc[row.name]) else 0,
                          abs(row['low'] - df['close'].shift(1).loc[row.name]) if pd.notna(df['close'].shift(1).loc[row.name]) else 0),
            axis=1
        )
        atr_period = indicator_settings.get('atr', {}).get('period', 14)
        df['atr'] = df['tr'].rolling(window=atr_period).mean()

    
    # Determine window
    # Determine window and initial range
    initial_range_start = None
    initial_range_end = None
    
    if focus.event_time is not None:
        # Event mode: Focus on specific window around event
        # Find closest index to event_time
        if 'open_time' in df.columns:
            df_sorted = df.sort_values('open_time').reset_index(drop=True)
            time_series = pd.to_datetime(df_sorted['open_time'])
        else:
            df_sorted = df.sort_index()
            time_series = pd.to_datetime(pd.Series(df_sorted.index))
        
        event_dt = pd.to_datetime(focus.event_time)
        time_diff = (time_series - event_dt).abs()
        center_idx = time_diff.idxmin()
        
        start_idx = max(0, center_idx - window_before)
        end_idx = min(len(df_sorted), center_idx + window_after + 1)
        
        df_window = df_sorted.iloc[start_idx:end_idx].copy()
        center_bar = df_sorted.iloc[center_idx]
    else:
        # Default mode: Load FULL history but zoom to last N bars
        df_window = df.copy() # Use full data
        center_bar = df.iloc[-1]
        
        # Calculate initial zoom range (last 120 bars)
        zoom_bars = 120
        if len(df) > zoom_bars:
            initial_range_start = df['open_time'].iloc[-zoom_bars]
            initial_range_end = df['open_time'].iloc[-1]
            # Add a small buffer to end
            initial_range_end = initial_range_end + (initial_range_end - df['open_time'].iloc[-2]) * 2

    if df_window.empty:
        return None, None, None
    
    # Data Info for display
    data_info = {
        "start_date": df_window['open_time'].min(),
        "end_date": df_window['open_time'].max(),
        "total_bars": len(df_window)
    }
    
    # Get time column
    time_col = 'open_time' if 'open_time' in df_window.columns else df_window.index
    x_axis = df_window[time_col] if isinstance(time_col, str) else time_col
    
    # Create 4-panel subplot (Price, Volume, MACD, RSI)
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.5, 0.15, 0.175, 0.175],
        specs=[[{}], [{}], [{}], [{}]],
        subplot_titles=(f"{focus.symbol} {focus.timeframe}", "", "", "")
    )
    
    # --- Panel 1: Price + EMAs ---
    
    # Candlestick (sync colors with volume if enabled, and theme-aware)
    # Candlestick Colors
    candles_cfg = indicator_settings.get('candles', {})
    inc_color = candles_cfg.get('up_color', '#089981')
    dec_color = candles_cfg.get('down_color', '#F23645')
    
    fig.add_trace(
        go.Candlestick(
            x=x_axis,
            open=df_window['open'],
            high=df_window['high'],
            low=df_window['low'],
            close=df_window['close'],
            name='Fiyat',
            increasing_line_color=inc_color,
            decreasing_line_color=dec_color,
            increasing_fillcolor=inc_color,  # Filled body same as line
            decreasing_fillcolor=dec_color,  # Filled body same as line
            showlegend=False
        ),
        row=1, col=1
    )
    
    # EMAs (if enabled)
    if indicator_settings.get('ema_fast', {}).get('enabled', True):
        ema_fast_color = indicator_settings.get('ema_fast', {}).get('color', '#2962FF')
        ema_fast_period = indicator_settings.get('ema_fast', {}).get('period', 20)
        fig.add_trace(
            go.Scatter(x=x_axis, y=df_window['ema_fast'], name=f'EMA {ema_fast_period}',
                      line=dict(color=ema_fast_color, width=1.5)),
            row=1, col=1
        )
    
    if indicator_settings.get('ema_slow', {}).get('enabled', True):
        ema_slow_color = indicator_settings.get('ema_slow', {}).get('color', '#FF9800')
        ema_slow_period = indicator_settings.get('ema_slow', {}).get('period', 50)
        fig.add_trace(
            go.Scatter(x=x_axis, y=df_window['ema_slow'], name=f'EMA {ema_slow_period}',
                      line=dict(color=ema_slow_color, width=1.5)),
            row=1, col=1
        )
    
    # ATR (if enabled, as overlay on price)
    if indicator_settings.get('atr', {}).get('enabled', True) and 'atr' in df_window.columns:
        atr_color = indicator_settings.get('atr', {}).get('color', '#00BCD4')
        atr_multiplier = indicator_settings.get('atr', {}).get('multiplier', 1.0)
        # ATR bands around price
        atr_upper = df_window['close'] + (df_window['atr'] * atr_multiplier)
        atr_lower = df_window['close'] - (df_window['atr'] * atr_multiplier)
        
        fig.add_trace(
            go.Scatter(
                x=x_axis, 
                y=atr_upper, 
                name=f'ATR Upper',
                line=dict(color=atr_color, width=1, dash='dot'),
                showlegend=False
            ),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=x_axis, 
                y=atr_lower, 
                name=f'ATR Lower',
                line=dict(color=atr_color, width=1, dash='dot'),
                fill='tonexty',
                fillcolor=f'rgba(0, 188, 212, 0.1)',
                showlegend=False
            ),
            row=1, col=1
        )

    
    # Event Marker
    if focus.event_time is not None:
        event_price = center_bar['close']
        marker_time = center_bar[time_col] if isinstance(time_col, str) else center_bar.name
        
        fig.add_trace(
            go.Scatter(
                x=[marker_time],
                y=[event_price],
                mode='markers',
                name='Event',
                marker=dict(
                    color='yellow',
                    size=12,
                    symbol='star',
                    line=dict(color='white', width=1)
                ),
                showlegend=False
            ),
            row=1, col=1
        )

    # --- Panel 2: Volume ---
    
    if indicator_settings.get('volume', {}).get('enabled', True):
        # Volume bars with color based on candle direction
        vol_up_color = indicator_settings.get('volume', {}).get('up_color', '#089981')
        vol_down_color = indicator_settings.get('volume', {}).get('down_color', '#F23645')
        colors = [vol_up_color if c >= o else vol_down_color 
                  for c, o in zip(df_window['close'], df_window['open'])]
        
        fig.add_trace(
            go.Bar(
                x=x_axis,
                y=df_window['volume'],
                name='Hacim',
                marker_color=colors,
                showlegend=False
            ),
            row=2, col=1
        )

    # --- Panel 3: MACD ---
    
    if indicator_settings.get('macd', {}).get('enabled', True):
        # 4-color Histogram
        macd_hist_prev = df_window['macd_hist'].shift(1)
        hist_colors = []
        for i, h in enumerate(df_window['macd_hist']):
            if pd.isna(h):
                hist_colors.append('#089981')
            elif h >= 0:
                if i > 0 and not pd.isna(macd_hist_prev.iloc[i]) and h > macd_hist_prev.iloc[i]:
                    # Positive and increasing
                    hist_colors.append(indicator_settings.get('macd', {}).get('hist_pos_inc_color', '#26A69A'))
                else:
                    # Positive and decreasing
                    hist_colors.append(indicator_settings.get('macd', {}).get('hist_pos_dec_color', '#4DB6AC'))
            else:
                if i > 0 and not pd.isna(macd_hist_prev.iloc[i]) and h < macd_hist_prev.iloc[i]:
                    # Negative and decreasing
                    hist_colors.append(indicator_settings.get('macd', {}).get('hist_neg_dec_color', '#EF5350'))
                else:
                    # Negative and increasing
                    hist_colors.append(indicator_settings.get('macd', {}).get('hist_neg_inc_color', '#FFCDD2'))
        
        macd_color = indicator_settings.get('macd', {}).get('macd_color', '#2962FF')
        signal_color = indicator_settings.get('macd', {}).get('signal_color', '#FF9800')
        
        fig.add_trace(
            go.Bar(x=x_axis, y=df_window['macd_hist'], name='MACD Hist',
                  marker_color=hist_colors),
            row=3, col=1
        )
        fig.add_trace(
            go.Scatter(x=x_axis, y=df_window['macd_line'], name='MACD',
                      line=dict(color=macd_color, width=1)),
            row=3, col=1
        )
        fig.add_trace(
            go.Scatter(x=x_axis, y=df_window['macd_signal'], name='Signal',
                      line=dict(color=signal_color, width=1)),
            row=3, col=1
        )
    
    # --- Panel 4: RSI ---
    
    if indicator_settings.get('rsi', {}).get('enabled', True):
        rsi_color = indicator_settings.get('rsi', {}).get('color', '#7E57C2')
        fig.add_trace(
            go.Scatter(x=x_axis, y=df_window['rsi'], name='RSI',
                      line=dict(color=rsi_color, width=1.5)),
            row=4, col=1
        )
    
    # RSI EMA (if enabled)
    if indicator_settings.get('rsi_ema', {}).get('enabled', True) and 'rsi_ema' in df_window.columns:
        rsi_ema_color = indicator_settings.get('rsi_ema', {}).get('color', '#FFC107')
        rsi_ema_period = indicator_settings.get('rsi_ema', {}).get('period', 14)
        fig.add_trace(
            go.Scatter(x=x_axis, y=df_window['rsi_ema'], name=f'RSI EMA {rsi_ema_period}',
                      line=dict(color=rsi_ema_color, width=1.5)), # Removed dash='dash' for solid line
            row=4, col=1
        )
    
    
    
    # RSI Levels & Backgrounds
    # 30-50 Background (Light Red)
    fig.add_hrect(
        y0=30, y1=50, 
        fillcolor="red", opacity=0.10, 
        layer="below", line_width=0, 
        row=4, col=1
    )
    # 50-70 Background (Light Green)
    fig.add_hrect(
        y0=50, y1=70, 
        fillcolor="green", opacity=0.20, 
        layer="below", line_width=0, 
        row=4, col=1
    )

    # 30 Line (Red, Thin, Solid)
    fig.add_hline(y=30, line_dash="solid", line_color="red", line_width=1, row=4, col=1)
    
    # 70 Line (Green, Thin, Solid)
    fig.add_hline(y=70, line_dash="solid", line_color="green", line_width=1, row=4, col=1)

    # 50 Line (Neutral Gray for both themes)
    fig.add_hline(y=50, line_dash="solid", line_color="gray", line_width=1, opacity=0.5, row=4, col=1)
    
    # --- Layout Updates ---
    # We let Streamlit handle the theme (template, background, grid) via theme="streamlit"
    
    fig.update_layout(
        height=800,
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode='x unified',
        showlegend=False,
        dragmode='pan', # Pan by default, mouse wheel for zoom
    )
    
    # Hide rangeslider
    fig.update_xaxes(rangeslider_visible=False)
    
    # Ensure grid is shown (Streamlit theme will style it)
    # Ensure grid is shown (Streamlit theme will style it)
    # Enable spikes for crosshair effect
    fig.update_xaxes(
        showgrid=True, 
        type='date',
        showspikes=True,
        spikemode='across',
        spikesnap='cursor',
        showline=True,
        spikecolor="grey",
        spikethickness=1,
        spikedash='dash'
    ) 
    
    # Y-axis settings: Move to right, enable spikes
    fig.update_yaxes(
        showgrid=True, 
        side='right',
        showspikes=True,
        spikemode='across',
        spikesnap='cursor',
        spikecolor="grey",
        spikethickness=1,
        spikedash='dash'
    )
    
    # Set initial range if calculated
    if initial_range_start and initial_range_end:
        fig.update_xaxes(range=[initial_range_start, initial_range_end], row=4, col=1) # Apply to bottom axis (shared)
        
    return fig, center_bar, data_info


def render_rally_event_chart(
    symbol: str,
    timeframe: str,
    event_time: pd.Timestamp,
    bars_to_peak: int,
    window_before: int = 30,
    window_after: int = 20,
) -> None:
    """
    Renders candlestick chart around a rally event with event highlight and bars_to_peak shaded region.
    Generic version supporting any timeframe.
    
    Args:
        symbol: Coin symbol
        timeframe: Timeframe string (e.g. "15m", "1h", "4h")
        event_time: Event timestamp
        bars_to_peak: Number of bars to peak (for shading)
        window_before: Bars before event
        window_after: Bars after event
    """
    try:
        # Load data for specific timeframe
        df_history = load_history_data(symbol, timeframe)
        df_features = load_features_data(symbol, timeframe)
        
        if df_history is None or df_history.empty:
            st.warning(f"{symbol} için {timeframe} tarihsel veri bulunamadı.")
            return
        
        # Merge features if available
        if df_features is not None and not df_features.empty:
            # Robust timezone normalization
            try:
                # Ensure datetime and remove timezone for history
                df_history['open_time'] = pd.to_datetime(df_history['open_time'], errors='coerce')
                if df_history['open_time'].dt.tz is not None:
                    df_history['open_time'] = df_history['open_time'].dt.tz_localize(None)
                
                # Ensure datetime and remove timezone for features
                df_features['open_time'] = pd.to_datetime(df_features['open_time'], errors='coerce')
                if df_features['open_time'].dt.tz is not None:
                    df_features['open_time'] = df_features['open_time'].dt.tz_localize(None)
                    
                df = pd.merge(
                    df_history,
                    df_features[['open_time', 'rsi', 'rsi_ema']],
                    on='open_time',
                    how='left'
                )
            except Exception as e:
                st.warning(f"Feature merge failed (gösterim devam ediyor): {e}")
                df = df_history
        else:
            df = df_history
        
        # --- TIMEZONE: Convert to Turkey Time (UTC+3) ---
        from tezaver.core.config import to_turkey_time
        if 'open_time' in df.columns:
            df['open_time'] = df['open_time'].apply(lambda x: to_turkey_time(x) if pd.notna(x) else x)
        # Convert event_time to Turkey Time
        event_time = to_turkey_time(pd.to_datetime(event_time))
        # ------------------------------------------------
            
        # Calculate RSI if missing or empty
        # Note: Using Wilder's Smoothing (alpha=1/period) to match indicator_engine
        if 'rsi' not in df.columns or df['rsi'].isnull().all():
            period = DEFAULT_INDICATOR_SETTINGS['rsi']['period']
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
            
            rs = avg_gain / avg_loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
        # Calculate RSI EMA if missing
        if 'rsi_ema' not in df.columns or df['rsi_ema'].isnull().all():
             period_ema = DEFAULT_INDICATOR_SETTINGS['rsi_ema']['period']
             df['rsi_ema'] = df['rsi'].ewm(span=period_ema, adjust=False).mean()
        
        # Calculate MACD if missing or empty
        if 'macd' not in df.columns or df['macd'].isnull().all():
            fast = DEFAULT_INDICATOR_SETTINGS['macd']['fast']
            slow = DEFAULT_INDICATOR_SETTINGS['macd']['slow']
            signal = DEFAULT_INDICATOR_SETTINGS['macd']['signal']
            
            exp12 = df['close'].ewm(span=fast, adjust=False).mean()
            exp26 = df['close'].ewm(span=slow, adjust=False).mean()
            df['macd'] = exp12 - exp26
            df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # Sort and find event index
        df = df.sort_values('open_time').reset_index(drop=True)
        
        # Normalize event_time to ensure compatibility
        event_time_normalized = pd.to_datetime(event_time)
        
        # CRITICAL: Make both timezone-naive for comparison
        # to_turkey_time() returns tz-aware, but we need naive for time_diff calculation
        if 'open_time' in df.columns:
            df['open_time_naive'] = df['open_time'].dt.tz_localize(None) if hasattr(df['open_time'].dtype, 'tz') else df['open_time']
        else:
            df['open_time_naive'] = df['open_time']
            
        if event_time_normalized.tzinfo is not None:
            event_time_normalized = event_time_normalized.tz_localize(None)
        
        # Find closest timestamp using numpy argmin (returns integer position)
        if df.empty:
             st.warning("Veri işleme sonrası boş tablo.")
             return

        time_diff = (df['open_time_naive'] - event_time_normalized).abs()
        event_idx = int(time_diff.to_numpy().argmin())
        
        # Slice window
        # WIDE Window for panning (+/- 500 bars)
        wide_start_idx = max(0, event_idx - 500)
        wide_end_idx = min(len(df), event_idx + 500)
        df_window = df.iloc[wide_start_idx:wide_end_idx].copy()
        
        # ZOOM Window (Initial View)
        zoom_start = max(0, event_idx - window_before)
        zoom_end = min(len(df), event_idx + window_after + 1)
        
        if zoom_start < len(df) and zoom_end <= len(df):
             zoom_start_ts = df.iloc[zoom_start]['open_time']
             zoom_end_ts = df.iloc[min(zoom_end, len(df)-1)]['open_time']
        else:
             zoom_start_ts = None
             zoom_end_ts = None

        if df_window.empty:
            st.warning("Grafik için yeterli veri bulunamadı.")
            return
        
        # Create figure with 4 subplots (Price, Volume, MACD, RSI)
        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=[0.5, 0.15, 0.15, 0.2],
            specs=[[{}], [{}], [{}], [{}]],
            subplot_titles=(f"{symbol} {timeframe} - Rally Event", "Hacim", "MACD", "RSI")
        )
        
        # Candlestick (Row 1)
        fig.add_trace(
            go.Candlestick(
                x=df_window['open_time'],
                open=df_window['open'],
                high=df_window['high'],
                low=df_window['low'],
                close=df_window['close'],
                name='Fiyat',
                increasing_line_color=DEFAULT_INDICATOR_SETTINGS['candles']['sync_with_volume'] and DEFAULT_INDICATOR_SETTINGS['volume']['up_color'] or '#089981',
                decreasing_line_color=DEFAULT_INDICATOR_SETTINGS['candles']['sync_with_volume'] and DEFAULT_INDICATOR_SETTINGS['volume']['down_color'] or '#F23645',
                showlegend=False
            ),
            row=1, col=1
        )
        
        # Volume bars (Row 2)
        colors = [DEFAULT_INDICATOR_SETTINGS['volume']['up_color'] if close >= open else DEFAULT_INDICATOR_SETTINGS['volume']['down_color'] 
                  for close, open in zip(df_window['close'], df_window['open'])]
        
        fig.add_trace(
            go.Bar(
                x=df_window['open_time'],
                y=df_window['volume'],
                name="Volume",
                marker_color=colors,
                opacity=0.5
            ),
            row=2, col=1
        )
        
        # Event vertical line - use explicit integer for indexing
        event_window_idx = int(event_idx - wide_start_idx)
        # Check bounds just in case
        if 0 <= event_window_idx < len(df_window):
            event_row = df_window.iloc[event_window_idx]
            fig.add_vline(
                x=event_row['open_time'],
                line_dash="solid",
                line_color="gold",
                line_width=2,
                row=1, col=1
            )
            
            # Add annotation manually
            fig.add_annotation(
                x=event_row['open_time'],
                y=1,
                yref="y domain",
                text="Event",
                showarrow=False,
                yshift=10,
                row=1, col=1
            )
            
            # Rally Highlighting Logic
            if bars_to_peak > 0:
                try:
                    peak_idx = min(int(event_idx + bars_to_peak), len(df) - 1)
                    highlight_end = df.iloc[peak_idx]['open_time']
                    label_text = f"Rally ({bars_to_peak} bars)"
                    
                    fig.add_vrect(
                        x0=event_time,
                        x1=highlight_end,
                        fillcolor="yellow",
                        opacity=0.2,
                        line_width=0,
                        row=1
                    )
                    
                    # Add vertical line at the END of the rally
                    fig.add_vline(
                        x=highlight_end,
                        line_dash="solid",
                        line_color="gold",
                        line_width=2,
                        row=1, col=1
                    )
                    
                    # Add annotation manually for label
                    fig.add_annotation(
                        x=event_time,
                        y=1,
                        yref="y domain",
                        text=label_text,
                        showarrow=False,
                        xanchor="left",
                        yshift=10,
                        row=1, col=1
                    )
                except Exception as e:
                    st.error(f"YELLOW BOX ERROR: {e}")
                    # Print full traceback to console
                    import traceback
                    print(traceback.format_exc())

        
        # MACD subplot (Row 3)
        if 'macd' in df_window.columns:
            # --- Load User Settings for MACD ---
            from tezaver.core.settings_manager import settings_manager
            user_settings = settings_manager.load_settings()
            macd_cfg = user_settings.get('indicators', {}).get('macd', {})
            
            # Use user settings or fallback to explicit defaults if missing
            line_color = macd_cfg.get('macd_color', '#2962FF')
            sig_color = macd_cfg.get('signal_color', '#FF9800')
            
            # MACD Line
            fig.add_trace(
                go.Scatter(
                    x=df_window['open_time'],
                    y=df_window['macd'],
                    name='MACD',
                    line=dict(color=line_color, width=1.5)
                ),
                row=3, col=1
            )
            # Signal Line
            fig.add_trace(
                go.Scatter(
                    x=df_window['open_time'],
                    y=df_window['macd_signal'],
                    name='Signal',
                    line=dict(color=sig_color, width=1.5)
                ),
                row=3, col=1
            )
            
            # Histogram Coloring with Tolerance Logic
            cols = {
                'pos_inc': macd_cfg.get('hist_pos_inc_color', '#00E676'),
                'pos_dec': macd_cfg.get('hist_pos_dec_color', '#D500F9'),
                'neg_inc': macd_cfg.get('hist_neg_inc_color', '#FF1744'),
                'neg_dec': macd_cfg.get('hist_neg_dec_color', '#FFEA00')
            }
            
            tolerance_pct = float(macd_cfg.get('color_tolerance', 0.0)) / 100.0
            
            # Prepare data
            hist_vals = df_window['macd_hist'].fillna(0).values
            prev_vals = df_window['macd_hist'].shift(1).fillna(0).values
            
            colors_macd = []
            previous_color = cols['pos_inc'] # Initial dummy state
            
            for i, h in enumerate(hist_vals):
                prev = prev_vals[i]
                
                # Determine "Target" Color based on strict physics (Rise/Fall)
                if h >= 0:
                    if h > prev: target_color = cols['pos_inc']
                    else: target_color = cols['pos_dec']
                else:
                    if h < prev: target_color = cols['neg_inc'] # Deepening (Red)
                    else: target_color = cols['neg_dec'] # Recovering (Yellow)
                
                # Apply Tolerance Logic
                # If tolerance > 0, we check if the change is significant enough to switch color
                if tolerance_pct > 0 and i > 0:
                     # Calculate change pct relative to previous bar amplitude
                     # Avoid div/0
                     denom = abs(prev) if abs(prev) > 1e-9 else 1.0 
                     change_ratio = abs(h - prev) / denom
                     
                     # Check if we are staying in the same visual group (Positive or Negative)
                     # Tolerance mainly makes sense for Dec/Inc switches within same polarity (e.g. Green->Purple)
                     # Or Negative Deep->Recover (Red->Yellow)
                     # Switching from Positive to Negative (Green->Red) implies crossing zero, which is structural change.
                     # We usually enforce strict zero crossing. Color tolerance applies to momentum shifts.
                     
                     same_polarity = (h >= 0 and prev >= 0) or (h < 0 and prev < 0)
                     
                     if same_polarity and change_ratio < tolerance_pct:
                         # Change is too small, keep previous color (hysteresis)
                         final_color = previous_color
                     else:
                         final_color = target_color
                else:
                    final_color = target_color
                
                colors_macd.append(final_color)
                previous_color = final_color

            fig.add_trace(
                go.Bar(
                    x=df_window['open_time'],
                    y=df_window['macd_hist'],
                    name='Hist',
                    marker_color=colors_macd
                ),
                row=3, col=1
            )

        # RSI subplot (Row 4)
        if 'rsi' in df_window.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_window['open_time'],
                    y=df_window['rsi'],
                    name='RSI',
                    line=dict(color=DEFAULT_INDICATOR_SETTINGS['rsi']['color'], width=1.5)
                ),
                row=4, col=1
            )
        
        if 'rsi_ema' in df_window.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_window['open_time'],
                    y=df_window['rsi_ema'],
                    name='RSI EMA',
                    line=dict(color=DEFAULT_INDICATOR_SETTINGS['rsi_ema']['color'], width=1.5)
                ),
                row=4, col=1
            )
        
        # RSI levels
        fig.add_hline(y=30, line_dash="solid", line_color="red", line_width=1, opacity=0.5, row=4, col=1)
        fig.add_hline(y=70, line_dash="solid", line_color="green", line_width=1, opacity=0.5, row=4, col=1)
        fig.add_hline(y=50, line_dash="solid", line_color="gray", line_width=1, opacity=0.3, row=4, col=1)
        
        # ====================================================================
        # RALLY HIGHLIGHT: Yellow shaded area from event_time to peak
        # ====================================================================
        # CRITICAL: This must happen BEFORE timezone shift and AFTER finding event_idx
        # because bars_to_peak is relative to the ORIGINAL (pre-shifted) dataframe
        try:
            # We already found event_idx earlier (line 640) using event_time_normalized
            # event_idx is the position in the FULL df (before windowing)
            # bars_to_peak tells us how many bars FORWARD from event_idx to the peak
            
            rally_start_idx = event_idx  # This is already correct
            rally_peak_idx = event_idx + bars_to_peak
            
            # Safety check
            if rally_peak_idx >= len(df):
                st.caption(f"⚠️ Peak is outside data range (peak_idx={rally_peak_idx}, len={len(df)})")
            else:
                # Get the ORIGINAL timestamps (before timezone shift was applied on line 590)
                # But we need the SHIFTED versions for plotting
                rally_start_time = df.iloc[rally_start_idx]['open_time']  # Already shifted +3
                rally_peak_time = df.iloc[rally_peak_idx]['open_time']  # Already shifted +3
                
                # Add yellow vertical rectangle
                fig.add_vrect(
                    x0=rally_start_time,
                    x1=rally_peak_time,
                    fillcolor="rgba(255, 215, 0, 0.3)",  # Gold/yellow with 30% opacity
                    layer="below",
                    line_width=0,
                    annotation_text="",  # Remove annotation for cleaner look
                )
                
        except Exception as e:
            st.error(f"🔴 Rally highlight başarısız: {e}")
            import traceback
            with st.expander("Debug Traceback"):
                st.code(traceback.format_exc())
        # ====================================================================
        
        # Layout
        fig.add_hline(y=50, line_dash="solid", line_color="gray", line_width=1, opacity=0.3, row=4, col=1)
        
        # Layout
        fig.update_layout(
            height=800,  # Increased height for 4 panels
            margin=dict(l=10, r=10, t=40, b=10),
            hovermode='x unified',
            showlegend=False,
            dragmode='pan',
            # Apply initial zoom range to the bottom axis (shared)
            xaxis4=dict(range=[zoom_start_ts, zoom_end_ts]) if zoom_start_ts else None
        )
         # Note: with shared_xaxes=True in subplots, usually the last axis (xaxis4) controls the range, or we set matches='x'. 
         # Plotly makes all x-axes match x4 or x1 depending on config. Safest is to set it on the layout.xaxis or specifically.
         # Actually, update_layout(xaxis=...) usually affects the bottom one if shared. Let's try general update.
        if zoom_start_ts:
             fig.update_xaxes(range=[zoom_start_ts, zoom_end_ts], row=4, col=1)


        
        fig.update_xaxes(rangeslider_visible=False, showgrid=True)
        fig.update_yaxes(showgrid=True, side='right')
        
        st.plotly_chart(fig, use_container_width=True, theme="streamlit")
        
    except Exception as e:
        import traceback
        st.error(f"Grafik hatası: {e}")
        with st.expander("Teknik Detaylar (Traceback)"):
            st.code(traceback.format_exc())


def render_fast15_event_chart(
    symbol: str,
    event_time: pd.Timestamp,
    bars_to_peak: int,
    window_before: int = 30,
    window_after: int = 20,
) -> None:
    """Wrapper for backward compatibility calling generic renderer with 15m."""
    render_rally_event_chart(
        symbol=symbol,
        timeframe="15m",
        event_time=event_time,
        bars_to_peak=bars_to_peak,
        window_before=window_before,
        window_after=window_after
    )


def explain_center_bar(focus: ChartFocus, center_bar: pd.Series) -> List[str]:
    """
    Merkez bar için Türkçe açıklama satırları üretir.
    
    Args:
        focus: ChartFocus objesi
        center_bar: Açıklanacak bar (pd.Series)
    
    Returns:
        List of Turkish explanation strings
    """
    if center_bar is None or center_bar.empty:
        return []
    
    explanations = []
    
    # 1. Mum bilgisi
    open_price = center_bar.get('open', 0)
    close_price = center_bar.get('close', 0)
    high_price = center_bar.get('high', 0)
    low_price = center_bar.get('low', 0)
    
    if close_price >= open_price:
        direction = "**yukarı**"
        body_color = "yeşil"
    else:
        direction = "**aşağı**"
        body_color = "kırmızı"
    
    explanations.append(
        f"Bu mumda fiyat **{open_price:.2f} → {close_price:.2f}** aralığında hareket etmiş, "
        f"gövde yönü {direction} ({body_color} mum)."
    )
    
    # 2. Fiyat aralığı
    price_range = high_price - low_price
    body_size = abs(close_price - open_price)
    
    if body_size > 0:
        body_ratio = body_size / price_range if price_range > 0 else 0
        if body_ratio > 0.7:
            explanations.append(
                f"Gövde, toplam aralığın **%{body_ratio*100:.0f}**'ını kaplıyor "
                f"(güçlü {direction} hareket)."
            )
        elif body_ratio < 0.3:
            explanations.append(
                f"Gövde küçük (%{body_ratio*100:.0f}), fitil uzun "
                f"(kararsızlık veya red sinyali)."
            )
    
    # 3. Hacim analizi
    volume = center_bar.get('volume', 0)
    if volume > 0:
        explanations.append(
            f"Bu barda **{volume:,.0f}** birim işlem hacmi kaydedilmiş."
        )
    
    # 4. Event meta bilgileri
    if focus.event_meta:
        # Future gain/loss
        future_gain = focus.event_meta.get('future_max_gain_pct')
        if future_gain is not None:
            explanations.append(
                f"📊 Bu olaydan sonraki dönemde **maksimum +%{future_gain:.1f}** yükseliş görülmüş."
            )
        
        future_loss = focus.event_meta.get('future_max_loss_pct')
        if future_loss is not None and future_loss < 0:
            explanations.append(
                f"📉 Aynı dönemde **maksimum %{future_loss:.1f}** düşüş yaşanmış."
            )
        
        # Rule name
        rule_name = focus.event_meta.get('rule_name')
        if rule_name:
            explanations.append(
                f"⚠️ Bu bar, **{rule_name}** risk kuralının tetiklendiği nokta."
            )
        
        # Rally label
        rally_label = focus.event_meta.get('rally_label')
        if rally_label and rally_label != 'none':
            rally_display = rally_label.replace('rally_', '').replace('p', '%')
            explanations.append(
                f"🚀 Bu nokta bir rally başlangıcı olarak etiketlenmiş (**{rally_display}** rally)."
            )
        
        # Family ID
        family_id = focus.event_meta.get('family_id')
        if family_id is not None:
            explanations.append(
                f"📋 Rally ailesi: **Family #{family_id}**"
            )
    
    return explanations


# ===== Pattern/Rally Example Charts =====

def render_pattern_example_chart(
    symbol: str,
    example,  # ExampleEvent from pattern_story_view
    timeframe: str,
    window_bars: int = 100
) -> None:
    """
    Render candlestick chart for pattern example.
    
    Shows event time with highlight and rally zone (bars_to_peak).
    
    Args:
        symbol: Coin symbol
        example: ExampleEvent object with event_time, bars_to_peak, etc.
        timeframe: Chart timeframe
        window_bars: Total bars to show (before + after event)
    """
    try:
        # Load history data
        history_path = coin_cell_paths.get_history_file(symbol, timeframe)
        
        if not history_path.exists():
            st.info(f"Bu patern için {timeframe} grafiği bulunamadı.")
            return
        
        df = pd.read_parquet(history_path)
        
        # Ensure timestamp is datetime
        # Robust timestamp column detection
        time_col = None
        for col in ['timestamp', 'open_time', 'datetime', 'Date']:
            if col in df.columns:
                time_col = col
                break
        
        if not time_col:
            st.error(f"Timestamp kolonu bulunamadı. Mevcut kolonlar: {list(df.columns)}")
            return
            
        # Convert to datetime (handle int/float/str)
        try:
            if pd.api.types.is_numeric_dtype(df[time_col]):
                df['timestamp'] = pd.to_datetime(df[time_col], unit='ms', errors='coerce')
            else:
                df['timestamp'] = pd.to_datetime(df[time_col], errors='coerce')
            
            # Verify conversion succeeded
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                st.error(f"Timestamp dönüşümü başarısız. Tip: {df['timestamp'].dtype}")
                return
        except Exception as e:
            st.error(f"Timestamp dönüşüm hatası: {e}")
            return

        # --- TIMEZONE FIX: SHIFT +3 HOURS ---
        # Convert timestamp to Turkey Time
        from tezaver.core.config import to_turkey_time
        if 'timestamp' in df.columns:
            df['timestamp'] = df['timestamp'].apply(lambda x: to_turkey_time(x) if pd.notna(x) else x)
        # ------------------------------------
        
        # Normalize timezone to naive
        if df['timestamp'].dt.tz is not None:
            df['timestamp'] = df['timestamp'].dt.tz_localize(None)
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Find event index
        try:
            event_time = pd.to_datetime(example.event_time)
            
            # Normalize event_time to naive
            if event_time.tzinfo is not None:
                event_time = event_time.tz_localize(None)
                
            # Find closest timestamp using numpy argmin (returns integer position)
            time_diffs = (df['timestamp'] - event_time).abs()
            event_idx = int(time_diffs.to_numpy().argmin())
        except Exception as e:
            st.error(f"Event index bulma hatası: {e}")
            return
        
        # Calculate RSI if missing or empty
        if 'rsi' not in df.columns or df['rsi'].isnull().all():
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            df['rsi_ema'] = df['rsi'].ewm(span=14, adjust=False).mean()
            
        # Calculate MACD if missing or empty
        if 'macd' not in df.columns or df['macd'].isnull().all():
            exp12 = df['close'].ewm(span=12, adjust=False).mean()
            exp26 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = exp12 - exp26
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # Window Strategy:
        # Load a WIDE window (e.g. +/- 500 bars) so user can pan/scroll.
        # But set initial ZOOM to the specific event window (e.g. -40 / +40).
        
        # 1. Wide Data Window (for panning)
        # Load +/- 500 bars as requested by user
        wide_start_idx = max(0, event_idx - 500)
        wide_end_idx = min(len(df), event_idx + 500)
        df_window = df.iloc[wide_start_idx:wide_end_idx].copy()
        
        # 2. Initial Zoom Logic
        # User Requirement: 100 bars visible on screen.
        # Strategy: 70 bars BEFORE event, 30 bars AFTER event.
        # This keeps the event in context (result visible) but focus on formation.
        zoom_start_idx = max(0, event_idx - 70)
        # We want exactly 100 bars total. So end is start + 100? 
        # Or relative to event: event + 30.
        zoom_end_idx = min(len(df), event_idx + 30)
        
        # If we hit an edge (beginning of data), ensure we still try to show 100 bars if possible
        if zoom_start_idx == 0:
            zoom_end_idx = min(len(df), 100)
        
        # Get timestamps for range slider
        if zoom_start_idx < len(df) and zoom_end_idx <= len(df):
            initial_zoom_start = df.iloc[zoom_start_idx]['timestamp']
            initial_zoom_end = df.iloc[min(zoom_end_idx, len(df)-1)]['timestamp']
        else:
            initial_zoom_start = None
            initial_zoom_end = None

        if df_window.empty:
            st.info("Grafik için yeterli veri yok.")
            return
        
        # Create subplots (Price, Volume, MACD, RSI)
        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=[0.5, 0.15, 0.15, 0.2],
            specs=[[{}], [{}], [{}], [{}]],
            subplot_titles=("Fiyat", "Hacim", "MACD", "RSI")
        )
        
        # Candlestick (Row 1)
        fig.add_trace(
            go.Candlestick(
                x=df_window['timestamp'],
                open=df_window['open'],
                high=df_window['high'],
                low=df_window['low'],
                close=df_window['close'],
                name="OHLC",
                increasing_line_color=DEFAULT_INDICATOR_SETTINGS['candles']['sync_with_volume'] and DEFAULT_INDICATOR_SETTINGS['volume']['up_color'] or '#089981',
                decreasing_line_color=DEFAULT_INDICATOR_SETTINGS['candles']['sync_with_volume'] and DEFAULT_INDICATOR_SETTINGS['volume']['down_color'] or '#F23645'
            ),
            row=1, col=1
        )
        
        # Volume bars (Row 2)
        colors = [DEFAULT_INDICATOR_SETTINGS['volume']['up_color'] if close >= open else DEFAULT_INDICATOR_SETTINGS['volume']['down_color'] 
                  for close, open in zip(df_window['close'], df_window['open'])]
        
        fig.add_trace(
            go.Bar(
                x=df_window['timestamp'],
                y=df_window['volume'],
                name="Volume",
                marker_color=colors,
                opacity=0.5
            ),
            row=2, col=1
        )
        
        # MACD subplot (Row 3)
        if 'macd' in df_window.columns:
            # MACD Line
            fig.add_trace(
                go.Scatter(
                    x=df_window['timestamp'],
                    y=df_window['macd'],
                    name='MACD',
                    line=dict(color=DEFAULT_INDICATOR_SETTINGS['macd']['macd_color'], width=1.5)
                ),
                row=3, col=1
            )
            # Signal Line
            fig.add_trace(
                go.Scatter(
                    x=df_window['timestamp'],
                    y=df_window['macd_signal'],
                    name='Signal',
                    line=dict(color=DEFAULT_INDICATOR_SETTINGS['macd']['signal_color'], width=1.5)
                ),
                row=3, col=1
            )
            # Histogram (4-color TradingView style)
            macd_hist_prev = df_window['macd_hist'].shift(1)
            colors_macd = []
            for i, h in enumerate(df_window['macd_hist']):
                if pd.isna(h):
                    colors_macd.append(DEFAULT_INDICATOR_SETTINGS['macd']['hist_pos_inc_color'])
                elif h >= 0:
                    if i > 0 and not pd.isna(macd_hist_prev.iloc[i]) and h > macd_hist_prev.iloc[i]:
                        colors_macd.append(DEFAULT_INDICATOR_SETTINGS['macd']['hist_pos_inc_color'])
                    else:
                        colors_macd.append(DEFAULT_INDICATOR_SETTINGS['macd']['hist_pos_dec_color'])
                else:
                    if i > 0 and not pd.isna(macd_hist_prev.iloc[i]) and h < macd_hist_prev.iloc[i]:
                        colors_macd.append(DEFAULT_INDICATOR_SETTINGS['macd']['hist_neg_dec_color'])
                    else:
                        colors_macd.append(DEFAULT_INDICATOR_SETTINGS['macd']['hist_neg_inc_color'])

            fig.add_trace(
                go.Bar(
                    x=df_window['timestamp'],
                    y=df_window['macd_hist'],
                    name='Hist',
                    marker_color=colors_macd
                ),
                row=3, col=1
            )
            
        # RSI subplot (Row 4)
        if 'rsi' in df_window.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_window['timestamp'],
                    y=df_window['rsi'],
                    name='RSI',
                    line=dict(color=DEFAULT_INDICATOR_SETTINGS['rsi']['color'], width=1.5)
                ),
                row=4, col=1
            )
        
        if 'rsi_ema' in df_window.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_window['timestamp'],
                    y=df_window['rsi_ema'],
                    name='RSI EMA',
                    line=dict(color=DEFAULT_INDICATOR_SETTINGS['rsi_ema']['color'], width=1.5)
                ),
                row=4, col=1
            )
            
        # RSI levels
        fig.add_hline(y=30, line_dash="solid", line_color="red", line_width=1, opacity=0.5, row=4, col=1)
        fig.add_hline(y=70, line_dash="solid", line_color="green", line_width=1, opacity=0.5, row=4, col=1)
        fig.add_hline(y=50, line_dash="solid", line_color="gray", line_width=1, opacity=0.3, row=4, col=1)
        
        # Event highlight - Gold vertical line
        fig.add_vline(
            x=event_time,
            line_dash="dash",
            line_color="gold",
            line_width=2,
            row="all"
        )
        
        # Add annotation manually to avoid Plotly Timestamp/int arithmetic error
        fig.add_annotation(
            x=event_time,
            y=1,
            yref="y domain",
            text="📍 Event",
            showarrow=False,
            yshift=10,
            row=1, col=1
        )
        
        # Rally Highlighting Logic
        highlight_start = event_time
        highlight_end = event_time
        label_text = "Event"
        
        # Check if we have explicit start/end
        if hasattr(example, 'rally_start_time') and example.rally_start_time:
            try:
                st_time = pd.to_datetime(example.rally_start_time)
                if st_time.tzinfo: st_time = st_time.tz_localize(None)
                highlight_start = st_time
                highlight_end = event_time # Event is Peak (now)
                label_text = f"Rally (+{example.future_max_gain_pct*100:.1f}%)"
            except:
                pass
        elif hasattr(example, 'bars_to_peak') and example.bars_to_peak > 0:
             # Old logic fallback (if data not updated)
             try:
                 peak_idx = min(int(event_idx + example.bars_to_peak), len(df) - 1)
                 highlight_end = df.iloc[peak_idx]['timestamp']
                 label_text = f"Rally ({example.bars_to_peak} bars)"
             except: pass

        if highlight_start != highlight_end:
            fig.add_vrect(
                x0=highlight_start,
                x1=highlight_end,
                fillcolor="yellow",
                opacity=0.2,
                line_width=0,
                row=1
            )
            
        # Add Star at Peak (Event Time)
        fig.add_annotation(
            x=event_time,
            y=df_window['high'].max(),
            text="⭐",
            showarrow=True,
            arrowhead=1,
            row=1, col=1
        )
        
        # Add annotation manually for label
        fig.add_annotation(
            x=highlight_start,
            y=1,
            yref="y domain",
            text=label_text,
            showarrow=False,
            xanchor="left",
            yshift=10,
            row=1, col=1
        )
        
        # Layout
        fig.update_layout(
            title=f"{symbol} - {example.event_time.strftime('%d.%m.%Y')} (+%{example.future_max_gain_pct*100:.1f})",
            xaxis_rangeslider_visible=False,
            height=800,  # Increased height for 4 panels
            template="plotly_dark",
            showlegend=False,
            margin=dict(l=10, r=10, t=40, b=10),
            hovermode='x unified',
            dragmode='pan',
            # Set initial zoom
            xaxis=dict(range=[initial_zoom_start, initial_zoom_end]) if initial_zoom_start else None
        )
        
        fig.update_xaxes(title_text="Tarih", row=2, col=1)
        fig.update_yaxes(title_text="Fiyat", row=1, col=1)
        fig.update_yaxes(title_text="Hacim", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.error(f"Grafik oluşturulurken hata: {e}")
        with st.expander("Detaylı Hata Bilgisi"):
            st.code(error_details)


def render_rally_family_example_chart(
    symbol: str,
    example,  # ExampleEvent from pattern_story_view
    base_timeframe: str,
    window_bars: int = 80
) -> None:
    """
    Render candlestick chart for rally family example.
    
    Same as render_pattern_example_chart (could be merged).
    
    Args:
        symbol: Coin symbol
        example: ExampleEvent object
        base_timeframe: Chart timeframe
        window_bars: Total bars to show
    """
    # Reuse pattern chart logic
    render_pattern_example_chart(symbol, example, base_timeframe, window_bars)

def render_universal_chart(
    symbol: str,
    timeframe: str,
    event_time: Optional[pd.Timestamp] = None,
    bars_to_peak: int = 0,
    window_before: int = 30,
    window_after: int = 20,
) -> None:
    """
    Universal Chart Renderer based on the render_rally_event_chart engine.
    Supports both Event View (with highlight) and General View (latest data).
    
    Args:
        symbol: Coin symbol
        timeframe: Timeframe (e.g. "1h")
        event_time: Optional event time. If None, shows latest data.
        bars_to_peak: For rally highlighting.
    """
    try:
        # Load data
        df_history = load_history_data(symbol, timeframe)
        df_features = load_features_data(symbol, timeframe)
        
        if df_history is None or df_history.empty:
            st.warning(f"{symbol} için {timeframe} veri yok.")
            return
            
        # Merge features if available
        if df_features is not None and not df_features.empty:
            try:
                # Timezone normalization
                df_history['open_time'] = pd.to_datetime(df_history['open_time'], errors='coerce')
                if df_history['open_time'].dt.tz is not None:
                    df_history['open_time'] = df_history['open_time'].dt.tz_localize(None)
                
                df_features['open_time'] = pd.to_datetime(df_features['open_time'], errors='coerce')
                if df_features['open_time'].dt.tz is not None:
                    df_features['open_time'] = df_features['open_time'].dt.tz_localize(None)
                    
                df = pd.merge(
                    df_history,
                    df_features[['open_time', 'rsi', 'rsi_ema']],
                    on='open_time',
                    how='left'
                )
            except:
                df = df_history
        else:
            df = df_history
            
        # Convert to Turkey Time
        from tezaver.core.config import to_turkey_time
        if 'open_time' in df.columns:
            df['open_time'] = df['open_time'].apply(lambda x: to_turkey_time(x) if pd.notna(x) else x)
        if event_time:
            event_time = to_turkey_time(pd.to_datetime(event_time))
             
        # Indicators (RSI, MACD) - Fast calculation if missing
        if 'rsi' not in df.columns or df['rsi'].isnull().all():
            period = DEFAULT_INDICATOR_SETTINGS['rsi']['period']
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
            loss = -delta.where(delta < 0, 0).ewm(alpha=1/period, adjust=False).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
        if 'rsi_ema' not in df.columns or df['rsi_ema'].isnull().all():
             period_ema = DEFAULT_INDICATOR_SETTINGS['rsi_ema']['period']
             df['rsi_ema'] = df['rsi'].ewm(span=period_ema, adjust=False).mean()
             
        if 'macd' not in df.columns or df['macd'].isnull().all():
            fast = DEFAULT_INDICATOR_SETTINGS['macd']['fast']
            slow = DEFAULT_INDICATOR_SETTINGS['macd']['slow']
            signal = DEFAULT_INDICATOR_SETTINGS['macd']['signal']
            
            exp12 = df['close'].ewm(span=fast, adjust=False).mean()
            exp26 = df['close'].ewm(span=slow, adjust=False).mean()
            df['macd'] = exp12 - exp26
            df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
            
        # Determine Window
        df = df.sort_values('open_time').reset_index(drop=True)
        
        if event_time is None:
            # Universal Mode: Latest Data
            df_window = df.iloc[-1000:].copy() if len(df) > 1000 else df.copy()
            
            # Initial Zoom: Last 150 bars
            initial_start = df_window['open_time'].iloc[-150] if len(df_window) > 150 else df_window['open_time'].iloc[0]
            initial_end = df_window['open_time'].iloc[-1]
            # Buffer
            initial_end = initial_end + (initial_end - df_window['open_time'].iloc[-2]) * 5
            
            title = f"{symbol} {timeframe}"
        else:
            # Event Mode
            e_norm = pd.to_datetime(event_time)
            if e_norm.tzinfo: e_norm = e_norm.tz_localize(None)
            
            # Create naive version for comparison
            df_open_naive = df['open_time'].dt.tz_localize(None) if hasattr(df['open_time'].dtype, 'tz') else df['open_time']
            e_norm_naive = e_norm.tz_localize(None) if e_norm.tzinfo else e_norm
            time_diff = (df_open_naive - e_norm_naive).abs()
            event_idx = int(time_diff.to_numpy().argmin())
            
            start_i = max(0, event_idx - 500)
            end_i = min(len(df), event_idx + 500)
            df_window = df.iloc[start_i:end_i].copy()
            
            # Zoom
            initial_start = df['open_time'].iloc[max(0, event_idx - window_before)]
            initial_end = df['open_time'].iloc[min(len(df)-1, event_idx + window_after + 10)]
            
            title = f"{symbol} {timeframe} - Rally"

        if df_window.empty:
            st.warning("Veri yok.")
            return

        # Build Chart
        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=[0.5, 0.15, 0.15, 0.2],
            specs=[[{}], [{}], [{}], [{}]],
            subplot_titles=(title, "Hacim", "MACD", "RSI")
        )

        # 1. Price
        fig.add_trace(go.Candlestick(
            x=df_window['open_time'],
            open=df_window['open'], high=df_window['high'],
            low=df_window['low'], close=df_window['close'],
            name='Fiyat',
            increasing_line_color='#089981', decreasing_line_color='#F23645',
            showlegend=False
        ), row=1, col=1)

        # 2. Volume
        colors = ['#089981' if c >= o else '#F23645' for c, o in zip(df_window['close'], df_window['open'])]
        fig.add_trace(go.Bar(
            x=df_window['open_time'], y=df_window['volume'],
            name="Volume", marker_color=colors, opacity=0.5
        ), row=2, col=1)

        # 3. MACD
        if 'macd' in df_window.columns:
            fig.add_trace(go.Bar(x=df_window['open_time'], y=df_window['macd_hist'], name='Hist', marker_color='gray'), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_window['open_time'], y=df_window['macd'], name='MACD', line=dict(color='#2962FF', width=1)), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_window['open_time'], y=df_window['macd_signal'], name='Signal', line=dict(color='#FF9800', width=1)), row=3, col=1)

        # 4. RSI
        if 'rsi' in df_window.columns:
            fig.add_trace(go.Scatter(x=df_window['open_time'], y=df_window['rsi'], name='RSI', line=dict(color='#7E57C2', width=1.5)), row=4, col=1)
            if 'rsi_ema' in df_window.columns:
                fig.add_trace(go.Scatter(x=df_window['open_time'], y=df_window['rsi_ema'], name='EMA', line=dict(color='#FFC107', width=1.5)), row=4, col=1)
            
            fig.add_hline(y=70, line_dash="dot", line_color="red", row=4, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="green", row=4, col=1)

        # Event Highlight (Only if event_time)
        if event_time is not None:
             fig.add_vline(x=event_time, line_color="gold", line_width=2, row=1, col=1)
             if bars_to_peak > 0:
                 try:
                     # Re-find index in window
                     # Simplified: just use time calculation
                     # We assume event_time is exact match in df (it usually is if sourced from it)
                     # But we need to highlight Area.
                     
                     # Find end time
                     # We can iterate or use simple offset if bars known?
                     # Let's use logic: find event index in GLOBAL df, calculate peak index, get time.
                     # Create naive for comparison
                     df_open_naive = df['open_time'].dt.tz_localize(None) if hasattr(df['open_time'].dtype, 'tz') else df['open_time']
                     event_time_naive = event_time.tz_localize(None) if event_time.tzinfo else event_time
                     time_diff = (df_open_naive - event_time_naive).abs()
                     e_idx = int(time_diff.to_numpy().argmin())
                     p_idx = min(len(df)-1, e_idx + bars_to_peak)
                     end_time = df.iloc[p_idx]['open_time']
                     
                     fig.add_vrect(x0=event_time, x1=end_time, fillcolor="yellow", opacity=0.2, line_width=0, row=1)
                     fig.add_vline(x=end_time, line_color="gold", line_width=2, row=1, col=1)
                 except: pass

        # Layout
        fig.update_layout(
             height=800, margin=dict(l=10, r=10, t=30, b=10),
             hovermode='x unified', showlegend=False, dragmode='pan',
             xaxis_rangeslider_visible=False
        )
        
        # Initial Zoom
        if initial_start and initial_end:
             fig.update_xaxes(range=[initial_start, initial_end], row=4, col=1)

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Grafik hatası: {e}")
