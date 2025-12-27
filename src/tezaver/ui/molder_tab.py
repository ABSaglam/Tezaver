"""
Molder Tab - Kalıpçı (Archetype Labeling)
=========================================

"Ralliyi Adlandırma ve Sınıflandırma Atölyesi"

Flow:
1. Load APPROVED rallies from Ony Repo.
2. Display Chart.
3. User selects pattern (GRIND, SUPERNOVA etc).
4. Save label to repo.
"""

import streamlit as st
import pandas as pd
from typing import List, Optional

from tezaver.core.annotations import SniperAnnotationRepository, SniperAnnotation
from tezaver.core.molds import Archetype, ARCHETYPE_LABELS, ARCHETYPE_DESCRIPTIONS
from tezaver.ui.chart_area import render_sniper_studio_chart
from tezaver.ui.ony_tab import _get_available_symbols, _load_events_for_symbol_tf # Reuse helpers

def render_molder_page():
    """Render the Kalıpçı page."""
    st.title("📐 Kalıpçı (Şablon Atölyesi)")
    st.caption("Onaylanmış (Approved) rallilere Arketip (Kalıp) etiketi basar.")
    
    # --- FILTERS ---
    c1, c2, c3 = st.columns(3)
    
    with c1:
        symbols = _get_available_symbols()
        # Session state persistence
        idx = 0
        if "molder_sym" in st.session_state and st.session_state["molder_sym"] in symbols:
            idx = symbols.index(st.session_state["molder_sym"])
        sel_sym = st.selectbox("Coin", symbols, index=idx, key="molder_sym")
        
    with c2:
        timeframes = ["15m", "1h", "4h"]
        idx = 0
        if "molder_tf" in st.session_state and st.session_state["molder_tf"] in timeframes:
            idx = timeframes.index(st.session_state["molder_tf"])
        sel_tf = st.selectbox("Timeframe", timeframes, index=idx, key="molder_tf")
        
    with c3:
        # Filter Mode: Show Unlabeled vs Show All
        view_mode = st.radio("Sıra", ["Etiketlenmemişler", "Tümü"], key="molder_view_mode")
    
    # --- LOADING DATA ---
    repo = SniperAnnotationRepository()
    all_anns = repo.load_all(sel_sym, sel_tf)
    
    # Filter: Must be APPROVED
    approved = [a for a in all_anns if a.status == "APPROVED"]
    
    if not approved:
        st.warning(f"{sel_sym} {sel_tf} için onaylı ralli yok. Önce Revize masasından geçmeli.")
        return
        
    # Queue Logic
    if view_mode == "Etiketlenmemişler":
        queue = [a for a in approved if not getattr(a, 'archetype', None)]
    else:
        queue = approved
        # Sort so unlabeled are first? Or just by time?
        # Let's sort by time desc
        queue.sort(key=lambda x: x.event_id, reverse=True)
        
    st.markdown(f"**Kalan İş:** {len(queue)} adet (Toplam Onaylı: {len(approved)})")
    
    if not queue:
        st.success("🎉 Tebrikler! Tüm ralliler etiketlenmiş.")
        return
        
    # Select Item (Default to first)
    # Using Session State to keep track of current index if we want "Next" functionality
    # But for simplicity, let's pick index 0 from the queue always (Waterfall mode)
    
    current_item = queue[0]
    
    # Render Item Info
    st.divider()
    
    # --- CHART AREA ---
    # Need event_time. ID format: SYM_TF_TIER[_RVZ]_TS
    parts = current_item.event_id.split('_')
    ts = None
    if parts[-1].isdigit():
        ts = int(parts[-1])
        event_time = pd.to_datetime(ts, unit='s')
    else:
        st.error(f"Geçersiz ID formatı: {current_item.event_id}")
        return

    # Chart
    try:
        render_sniper_studio_chart(
            symbol=sel_sym,
            timeframe=sel_tf,
            event_time=event_time,
            bars_to_peak=50, # Default visual range if unknown
            entry_offset=current_item.entry_bar_offset,
            exit_offset=current_item.exit_bar_offset
        )
    except Exception as e:
        st.error(f"Grafik hatası: {e}")
        
    # --- LABELING PANEL ---
    st.markdown("### 🏷️ Kalıp Seçimi")
    st.info(f"Ralli ID: `{current_item.event_id}` | Mevcut Etiket: **{getattr(current_item, 'archetype', None) or 'YOK'}**")
    
    # Buttons for 6+1 Archetypes
    # Layout: 4 cols x 2 rows
    cols = st.columns(4)
    
    mold_list = [
        Archetype.GRIND, Archetype.GUILLOTINE, Archetype.SUPERNOVA, Archetype.PHOENIX,
        Archetype.NINJA, Archetype.SURFER, Archetype.OTHER
    ]
    
    for i, mold in enumerate(mold_list):
        col = cols[i % 4]
        label = ARCHETYPE_LABELS[mold]
        
        # Style active if matches
        type_primary = (getattr(current_item, 'archetype', None) == mold.value)
        
        with col:
            if st.button(label, key=f"btn_{mold.value}", use_container_width=True, type="primary" if type_primary else "secondary"):
                # SAVE ACTION
                repo.append(
                    symbol=sel_sym,
                    timeframe=sel_tf,
                    event_id=current_item.event_id,
                    entry_bar_offset=current_item.entry_bar_offset,
                    # Pass archetype in kwargs
                    archetype=mold.value
                )
                st.toast(f"✅ Etiketlendi: {label}")
                st.rerun()
            
            # Tooltip/Desc
            st.caption(ARCHETYPE_DESCRIPTIONS[mold])

    # Skip/Next logic is implicit: When "Etiketlenmemişler" mode is active, clicking a button removes it from queue (since it becomes labeled), so the next one appears automatically.
