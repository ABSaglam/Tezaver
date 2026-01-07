"""
🦅 Kartal Göz - Multi-Timeframe Rally Vision Tab

Ana grafik stili ile 4h, 1h ve 15m rally'leri overlay olarak gösterir.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from typing import Optional

from tezaver.core import coin_cell_paths
from tezaver.ui.chart_area import load_history_data, DEFAULT_INDICATOR_SETTINGS


from tezaver.core.rally_store import RallyStore

def load_all_rallies(symbol: str) -> tuple:
    """Load 4h, 1h, and 15m rally data from RallyStore (SQLite)."""
    store = RallyStore()
    
    def fetch_df(tf):
        rows = store.list_rallies(symbol=symbol, timeframe=tf)
        if not rows:
            return pd.DataFrame()
        
        flat_rows = []
        for r in rows:
            # flatten: base row + raw_data
            item = dict(r)
            raw = item.pop('raw_data', {}) or {}
            if raw:
                item.update(raw)
            flat_rows.append(item)
            
        return pd.DataFrame(flat_rows)

    rallies_4h = fetch_df("4h")
    rallies_1h = fetch_df("1h")
    rallies_15m = fetch_df("15m")
    
    # Ensure datetime
    for df in [rallies_4h, rallies_1h, rallies_15m]:
        if not df.empty:
            # Handle event_time generic
            if 'event_time' in df.columns:
                 # It might be string ISO from SQLite adapter or Timestamp
                 df['event_time'] = pd.to_datetime(df['event_time'])
    
    return rallies_4h, rallies_1h, rallies_15m


def consolidate_overlapping_rallies(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Consolidate overlapping rallies - keep only the best one (highest gain) 
    when multiple rallies cover the same time window.
    
    Args:
        df: Rally DataFrame with event_time, bars_to_peak, future_max_gain_pct
        timeframe: "4h", "1h", or "15m"
    
    Returns:
        Consolidated DataFrame with non-overlapping rallies
    """
    if df.empty:
        return df
    
    # Calculate bar duration
    if timeframe == "4h":
        bar_delta = pd.Timedelta(hours=4)
    elif timeframe == "1h":
        bar_delta = pd.Timedelta(hours=1)
    else:
        bar_delta = pd.Timedelta(minutes=15)
    
    # Calculate end_time for each rally
    df = df.copy()
    df['end_time'] = df['event_time'] + df['bars_to_peak'].astype(int) * bar_delta
    
    # Sort by gain descending (keep best first)
    df = df.sort_values('future_max_gain_pct', ascending=False).reset_index(drop=True)
    
    # Greedy consolidation: keep rally if it doesn't overlap with already kept rallies
    kept_indices = []
    kept_ranges = []  # List of (start, end) tuples
    
    for idx, row in df.iterrows():
        start = row['event_time']
        end = row['end_time']
        
        # Check if this rally overlaps with any already kept rally
        overlaps = False
        for kept_start, kept_end in kept_ranges:
            # Two intervals overlap if: start1 < end2 AND start2 < end1
            if start < kept_end and kept_start < end:
                overlaps = True
                break
        
        if not overlaps:
            kept_indices.append(idx)
            kept_ranges.append((start, end))
    
    # Return only non-overlapping rallies
    result = df.loc[kept_indices].drop(columns=['end_time'], errors='ignore')
    result = result.sort_values('event_time').reset_index(drop=True)
    
    return result


def render_kartal_goz_tab(symbol: str):
    """
    Render Kartal Göz tab with multi-timeframe rally overlay.
    """
    st.markdown("### 🦅 Kartal Göz - Çoklu Zaman Dilimi Rally Görünümü")
    st.caption("4h, 1h ve 15m rally'leri 2 yıllık grafikte farklı renklerle gösterir")
    
    # Load price data (4h for 2-year view)
    df_price = load_history_data(symbol, "4h")
    
    if df_price is None or df_price.empty:
        st.warning(f"{symbol} için 4h fiyat verisi bulunamadı.")
        return
    
    # Ensure timestamp is datetime (convert from milliseconds if needed)
    if 'timestamp' in df_price.columns:
        if not pd.api.types.is_datetime64_any_dtype(df_price['timestamp']):
            # Check if values are large (milliseconds)
            if df_price['timestamp'].iloc[0] > 1e12:
                df_price['timestamp'] = pd.to_datetime(df_price['timestamp'], unit='ms')
            else:
                df_price['timestamp'] = pd.to_datetime(df_price['timestamp'])
    
    # Filter to last 2 years
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=730)
    df_price = df_price[df_price['timestamp'] >= cutoff].copy()
    
    # Load rallies
    rallies_4h, rallies_1h, rallies_15m = load_all_rallies(symbol)
    
    # Consolidate overlapping rallies (keep only best in each time window)
    rallies_4h = consolidate_overlapping_rallies(rallies_4h, "4h")
    rallies_1h = consolidate_overlapping_rallies(rallies_1h, "1h")
    rallies_15m = consolidate_overlapping_rallies(rallies_15m, "15m")
    
    # Show stats after consolidation
    total = len(rallies_4h) + len(rallies_1h) + len(rallies_15m)
    st.info(f"📊 **Toplam {total} rally** (4h:{len(rallies_4h)}, 1h:{len(rallies_1h)}, 15m:{len(rallies_15m)}) - overlap temizlendi")
    
    # === DATA STATUS PANEL ===
    with st.expander("📊 Veri Durumu & Güncelleme", expanded=False):
        st.markdown("#### Rally Veri İstatistikleri")
        
        # Create status table
        status_data = []
        
        for tf_name, df, scan_func in [
            ("15m (Fast15)", rallies_15m, "Fast15 Scanner"),
            ("1h (TimeLabs)", rallies_1h, "TimeLabs 1h"),
            ("4h (TimeLabs)", rallies_4h, "TimeLabs 4h")
        ]:
            if not df.empty:
                first_date = df['event_time'].min()
                last_date = df['event_time'].max()
                count = len(df)
                status_data.append({
                    "Timeframe": tf_name,
                    "Rally Sayısı": count,
                    "İlk Tarih": first_date.strftime('%Y-%m-%d %H:%M'),
                    "Son Tarih": last_date.strftime('%Y-%m-%d %H:%M'),
                    "Kaynak": scan_func
                })
            else:
                status_data.append({
                    "Timeframe": tf_name,
                    "Rally Sayısı": 0,
                    "İlk Tarih": "-",
                    "Son Tarih": "-",
                    "Kaynak": scan_func
                })
        
        status_df = pd.DataFrame(status_data)
        st.dataframe(status_df, use_container_width=True, hide_index=True)
        
        # Update buttons
        st.markdown("#### Verileri Güncelle")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 15m Güncelle", key=f"update_15m_{symbol}"):
                st.info("15m rally taraması başlatılıyor...")
                st.code(f"python src/tezaver/rally/run_fast15_rally_scan.py --symbol {symbol}")
        
        with col2:
            if st.button("🔄 1h Güncelle", key=f"update_1h_{symbol}"):
                st.info("1h rally taraması başlatılıyor...")
                st.code(f"python src/tezaver/rally/run_time_labs_scan.py --symbol {symbol} --timeframe 1h")
        
        with col3:
            if st.button("🔄 4h Güncelle", key=f"update_4h_{symbol}"):
                st.info("4h rally taraması başlatılıyor...")
                st.code(f"python src/tezaver/rally/run_time_labs_scan.py --symbol {symbol} --timeframe 4h")
    
    # Grade assignment (like Fast15)
    def get_grade(pct):
        if pct >= 0.30: return "💎 Diamond"
        if pct >= 0.20: return "🥇 Gold"
        if pct >= 0.10: return "🥈 Silver"
        if pct >= 0.05: return "🥉 Bronze"
        return "🎗️ Weak"
    
    for df in [rallies_4h, rallies_1h, rallies_15m]:
        if not df.empty and 'future_max_gain_pct' in df.columns:
            df['rally_grade'] = df['future_max_gain_pct'].apply(get_grade)
    
    # Grade filter
    st.markdown("#### 🏆 Rally Filtreleri")
    badge_filter = st.radio(
        "Sınıf Seçin",
        options=["♾️ Hepsi", "💎 Diamond", "🥇 Gold", "🥈 Silver", "🥉 Bronze"],
        horizontal=True,
        key=f"kartal_filter_{symbol}",
        label_visibility="collapsed"
    )
    
    # Apply filter to all timeframes
    def apply_filter(df):
        if df.empty:
            return df
        if badge_filter == "♾️ Hepsi":
            return df.copy()
        return df[df['rally_grade'] == badge_filter].copy()
    
    rallies_4h_filt = apply_filter(rallies_4h)
    rallies_1h_filt = apply_filter(rallies_1h)
    rallies_15m_filt = apply_filter(rallies_15m)
    
    # Summary
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("4h Rally", len(rallies_4h_filt))
    col2.metric("1h Rally", len(rallies_1h_filt))
    col3.metric("15m Rally", len(rallies_15m_filt))
    col4.metric("Toplam", len(rallies_4h_filt) + len(rallies_1h_filt) + len(rallies_15m_filt))
    
    st.markdown("---")
    
    # External Chart Link
    st.markdown("### 📊 Grafik Görüntüleyici")
    st.markdown("Detaylı grafik için: [🦅 Kartal Göz Grafiği Aç](file:///Users/alisaglam/TezaverMac/library/kartal_goz_4h_verify.html)")
    st.caption("Terminal'de: `open library/kartal_goz_4h_verify.html`")
    
    st.markdown("---")
    
    # === EVENT LIST (Combined) ===
    st.markdown("### 📋 Tüm Olaylar (Birleşik Liste)")
    
    # Combine all rallies
    combined_events = []
    for tf, df in [("4h", rallies_4h_filt), ("1h", rallies_1h_filt), ("15m", rallies_15m_filt)]:
        if not df.empty:
            df_copy = df.copy()
            df_copy['timeframe'] = tf
            combined_events.append(df_copy)
    
    if combined_events:
        all_events = pd.concat(combined_events, ignore_index=True)
        all_events = all_events.sort_values('event_time', ascending=False)
        
        # Calculate end_time for each rally
        def calc_end_time(row):
            tf = row['timeframe']
            start = pd.to_datetime(row['event_time'])
            bars = int(row['bars_to_peak'])
            if tf == '4h':
                return start + pd.Timedelta(hours=4 * bars)
            elif tf == '1h':
                return start + pd.Timedelta(hours=1 * bars)
            else:
                return start + pd.Timedelta(minutes=15 * bars)
        
        all_events['end_time'] = all_events.apply(calc_end_time, axis=1)
        
        # Convert to Turkey time (UTC+3) for display
        all_events['event_time_tr'] = all_events['event_time'] + pd.Timedelta(hours=3)
        all_events['end_time_tr'] = all_events['end_time'] + pd.Timedelta(hours=3)
        
        # Display table - add parent columns if in GÖZCÜ mode
        display_cols = ['timeframe', 'rally_grade', 'event_time_tr', 'end_time_tr', 'future_max_gain_pct', 'bars_to_peak']
        
        # Add rally_shape if exists
        if 'rally_shape' in all_events.columns:
            display_cols.insert(2, 'rally_shape')
        
        # Add parent columns if they exist (GÖZCÜ mode)
        if 'parent_1h_rally_id' in all_events.columns:
            display_cols.insert(3, 'parent_1h_rally_start')
        if 'parent_4h_rally_id' in all_events.columns:
            display_cols.insert(3, 'parent_4h_rally_start')
        
        display_cols = [c for c in display_cols if c in all_events.columns]
        
        table_disp = all_events[display_cols].copy()
        
        # Rename columns
        rename_map = {
            'timeframe': 'TF',
            'rally_grade': 'Sınıf',
            'rally_shape': 'Şekil',
            'event_time_tr': 'Başlangıç (TR)',
            'end_time_tr': 'Bitiş (TR)',
            'future_max_gain_pct': 'Kazanç',
            'bars_to_peak': 'Süre (Bar)',
            'parent_4h_rally_start': '📍 4h Parent',
            'parent_1h_rally_start': '📍 1h Parent'
        }
        table_disp = table_disp.rename(columns=rename_map)
        
        # Format values
        table_disp['Kazanç'] = table_disp['Kazanç'].apply(lambda x: f"%{x*100:.1f}")
        
        # Format shape as text (not emoji)
        if 'Şekil' in table_disp.columns:
            table_disp['Şekil'] = table_disp['Şekil'].apply(lambda x: str(x).capitalize() if pd.notna(x) else 'Unknown')
        
        st.dataframe(
            table_disp,
            use_container_width=True,
            hide_index=True,
            height=400
        )
    else:
        st.info("Seçilen filtrede hiç rally bulunamadı.")
