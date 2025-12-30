"""
ONY Tab - ONY Onay Stüdyosu ve Kuyruk Yönetimi

Phase 1 ONY v1:
- render_ony_studio(): Event seç, entry/exit offset ayarla, grafik gör, kaydet, onayla
- render_ony_queue(): PENDING/APPROVED/REJECTED listesi
- render_ony_page(): Ana giriş noktası
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Any

from tezaver.core.annotations import (
    SniperAnnotation,
    SniperStatus,
    SniperLabel
)
from tezaver.core import coin_cell_paths
from tezaver.ui.chart_area import render_sniper_studio_chart, load_history_data
from tezaver.rally.normalize_engine import normalize_entry, NormalizeResult
from tezaver.foundry.rally_assembler import RallyAssembler
from tezaver.core.tier_utils import TIERS, normalize_tier, compute_tier_from_gain
from tezaver.core.rally_store import RallyStore


# =============================================================================
# HELPER FUNCTIONS - MOVED TO CORE/TIER_UTILS.PY
# =============================================================================

# Helper removed: _load_events_for_symbol_tf (Replaced by RallyStore/Assembler)


def _get_available_symbols() -> List[str]:
    """Get list of available symbols from coin_cells."""
    try:
        coin_cells_dir = Path("coin_cells")
        if not coin_cells_dir.exists():
            return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        
        symbols = [d.name for d in coin_cells_dir.iterdir() if d.is_dir() and d.name.endswith("USDT")]
        return sorted(symbols) if symbols else ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    except:
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def apply_normalize_to_annotation(annotation: SniperAnnotation, norm_result: NormalizeResult) -> SniperAnnotation:
    """
    Apply normalize result to annotation.
    
    Args:
        annotation: SniperAnnotation instance
        norm_result: NormalizeResult from normalize_entry()
    
    Returns:
        Updated annotation
    """
    annotation.entry_bar_offset = norm_result.entry_offset_out
    annotation.normalized_entry_bar_offset = norm_result.entry_offset_out
    annotation.normalized_entry_ts = norm_result.entry_ts_iso
    annotation.snap_reason = norm_result.snap_reason
    annotation.snap_distance_bars = norm_result.snap_distance_bars
    annotation.snap_confidence = norm_result.snap_confidence
    annotation.snap_algo_version = norm_result.snap_algo_version
    
    return annotation


# =============================================================================
# BATCH OPERATIONS (AUTO-APPROVE)
# =============================================================================

def render_batch_operations():
    """
    MX-5360: ONY - Auto-Approve Batch Tool.
    Allows automated approval of rallies based on Tiers (Diamond, Gold, etc.)
    without manual review.
    """
    with st.expander("⚡ Batch Auto-Approve Tool (Toplu Onay)", expanded=False):
        st.warning("⚠️ Bu araç seçili kriterlere uyan TÜM olayları otomatik onaylar (APPROVED). Dikkatli kullanın.")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            raw_symbols = _get_available_symbols()
            symbols = ["TÜMÜ"] + raw_symbols
            symbol = st.selectbox("Coin", symbols, key="batch_sym")
        with c2:
            timeframes = ["TÜMÜ", "15m", "1h", "4h"]
            tf = st.selectbox("Timeframe", timeframes, key="batch_tf")
        with c3:
            # Default to all tiers
            tiers = st.multiselect("Hedef Tierlar", TIERS, default=TIERS, key="batch_tiers")
            
        if st.button("🔍 Önizle (Scan)", use_container_width=True):
            # Target logic
            target_symbols = raw_symbols if symbol == "TÜMÜ" else [symbol]
            target_tfs = ["15m", "1h", "4h"] if tf == "TÜMÜ" else [tf]
            
            all_events = []
            
            progress_text = "Taranıyor..."
            my_bar = st.progress(0, text=progress_text)
            total_steps = len(target_symbols) * len(target_tfs)
            current_step = 0
            
            # Load Repo for checking existing
            store = RallyStore()
            
            for s in target_symbols:
                for t in target_tfs:
                    current_step += 1
                    my_bar.progress(current_step / total_steps, text=f"Scanning {s} {t}...")
                    
                    # FETCH FROM STORE
                    rallies = assembler.get_ony_review_rallies(s, t)
                    
                    # Filter by Tiers
                    filtered = [r for r in rallies if r.tier in tiers]
                    
                    if filtered:
                        # Skip APPROVED using property
                        pending = [r for r in filtered if r.status != "APPROVED"]
                        
                        if pending:
                            for r in pending:
                                all_events.append({
                                    'event_id': r.event_id,
                                    'tier': r.tier,
                                    'future_max_gain_pct': r.gain_pct,
                                    'symbol': r.symbol,
                                    'timeframe': r.timeframe
                                })
            
            my_bar.empty()
            
            if not all_events:
                 st.error("Kriterlere uyan ralli bulunamadı.")
                 return
            
            st.session_state['batch_preview'] = {
                "count": len(all_events),
                "events": all_events,
                "symbol_selection": symbol,
                "tf_selection": tf
            }
            
        # Execute Block
        if 'batch_preview' in st.session_state:
            prev = st.session_state['batch_preview']
            st.info(f"🎯 Hedef: {prev['count']} adet olay (Seçim: {prev['symbol_selection']} / {prev['tf_selection']})")
            
            # Summary stats
            df_prev = pd.DataFrame(prev['events'])
            if not df_prev.empty:
                st.write(df_prev['tier'].value_counts())
            
            if st.button(f"🚀 ONAYLA ({prev['count']} Adet)", type="primary", use_container_width=True):
                store = RallyStore()
                count = 0
                
                progress_bar = st.progress(0)
                total = len(prev['events'])
                
                for i, evt in enumerate(prev['events']):
                    # Use per-event metadata
                    s = evt['symbol']
                    t = evt['timeframe']
                    eid = str(evt['event_id'])
                    
                    # Get Existing Unified Doc
                    doc = store.get_rally(eid)
                    rev = doc.get('rev_data', {}) or {}
                    
                    # Update
                    rev.update({
                        'status': 'APPROVED',
                        'label': rev.get('label', 'GOOD'),
                        'note': rev.get('note', 'Auto-Approved Batch'),
                        'updated_at': pd.Timestamp.now()
                    })
                    
                    store.upsert_rally(eid, rev, layer='rev')
                    
                    count += 1
                    progress_bar.progress((i + 1) / total)
                
                st.success(f"✅ {count} olay başarıyla ONAYLANDI!")
                del st.session_state['batch_preview']
                st.rerun()



# =============================================================================
# REV. STUDIO
# =============================================================================

def render_ony_studio():
    """
    Rev. Stüdyo - Sadece problemli rallileri revize etme ekranı.
    "Durum" ve "Etiket" kavramları UI'dan gizlenmiştir.
    """
    st.subheader("🛠️ Rev. Stüdyo")
    st.caption("Problemli ralliyi seç → Ayarları düzelt → Kaydet (Otorite)")
    
    # Return to Molder Button (if came from Molder)
    if st.session_state.get('came_from_molder'):
        col_back, col_spacer = st.columns([1, 5])
        with col_back:
            if st.button("🔙 Kalıpçı'ya Dön", type="secondary"):
                # Navigate back to Molder with target ID
                st.session_state['nav_selection'] = "📐 Kalıpçı"
                st.session_state['molder_target_id'] = st.session_state.get('molder_return_target')
                # Clean up
                st.session_state.pop('came_from_molder', None)
                st.session_state.pop('molder_return_target', None)
                st.rerun()
    
    # Initialize repository
    # Initialize store
    store = RallyStore()
    
    # --- COMPACT HEADER (Row 1) ---
    # Col1: Coin, Col2: TF, Col3: Tier Filter
    c_sym, c_tf, c_tier = st.columns([1, 1, 3])
    
    with c_sym:
        symbols = _get_available_symbols()
        # Default Logic: Check Session State first
        sess_sym = st.session_state.get('ony_symbol')
        if sess_sym and sess_sym in symbols:
            default_sym_idx = symbols.index(sess_sym)
        else:
            default_sym_idx = symbols.index("BTCUSDT") if "BTCUSDT" in symbols else 0
            
        symbol = st.selectbox("Coin", symbols, index=default_sym_idx, key="ony_symbol", label_visibility="collapsed")
        
    with c_tf:
        timeframes = ["15m", "1h", "4h"]
        sess_tf = st.session_state.get('ony_timeframe')
        if sess_tf and sess_tf in timeframes:
            default_tf_idx = timeframes.index(sess_tf)
        else:
            default_tf_idx = 0
            
        timeframe = st.selectbox("Timeframe", timeframes, index=default_tf_idx, key="ony_timeframe", label_visibility="collapsed")
    
    # Load Rallies via Steel Core Assembler
    assembler = RallyAssembler()
    rallies = assembler.get_ony_review_rallies(symbol, timeframe)
    
    # Tier Logic
    if rallies:
        # Group count
        counts = {t: 0 for t in TIERS}
        for r in rallies:
             if r.tier in counts: counts[r.tier] += 1
        tier_options = [f"{t} ({counts[t]})" for t in TIERS]
    else:
        tier_options = TIERS
        
    # AUTO-SWITCH TIER (Jumper Fix)
    if 'ony_prefill_event_id' in st.session_state and rallies:
        target_id = str(st.session_state['ony_prefill_event_id'])
        # Find rally
        match = next((r for r in rallies if str(r.event_id) == target_id), None)
        if match:
             if match.tier in TIERS and st.session_state.get('ony_selected_tier') != match.tier:
                 st.session_state['ony_selected_tier'] = match.tier
                 st.rerun()

    with c_tier:
        if 'ony_selected_tier' not in st.session_state:
            st.session_state['ony_selected_tier'] = "DIAMOND"
        
        # Horizontal Radio
        selected_tier_label = st.radio(
            "Tier",
            tier_options,
            horizontal=True,
            key="ony_tier_radio",
            label_visibility="collapsed",
            index=TIERS.index(st.session_state['ony_selected_tier']) if st.session_state['ony_selected_tier'] in TIERS else 0
        )
        selected_tier = selected_tier_label.split(" (")[0]
        
        if st.session_state['ony_selected_tier'] != selected_tier:
            st.session_state['ony_selected_tier'] = selected_tier
            if 'ony_event_select' in st.session_state:
                del st.session_state['ony_event_select']

    # --- EVENT SELECTOR (Row 2) ---
    if not rallies:
        st.warning(f"Event yok: {symbol} {timeframe}")
        return

    # Filter by Tier
    filtered_rallies = [r for r in rallies if r.tier == selected_tier]
    
    if not filtered_rallies:
        st.info(f"🔍 {selected_tier} katmanında incelenecek ralli yok.")
        return
    
    # Check for prefill request
    prefill_id = st.session_state.pop('ony_prefill_event_id', None)
    default_idx = 0
    
    # Build Options
    event_options = []
    rally_map = {}
    
    for i, rally in enumerate(filtered_rallies):
        # Prefill logic
        if prefill_id and str(rally.event_id) == str(prefill_id):
            default_idx = i
            
        label = rally.display_label
        event_options.append(label)
        rally_map[label] = rally

    if not event_options:
        st.warning("Liste boş.")
        return
        
    # Full width selectbox
    selected_label = st.selectbox("Ralli Seçiniz", event_options, index=default_idx, key="ony_event_select", label_visibility="collapsed")
    current_rally = rally_map[selected_label]
    
    # Extract Data from Assembler Object (Unified Source)
    event_id = current_rally.event_id
    event_time = current_rally.event_time
    bars_to_peak = current_rally.bars_to_peak
    
    # Since we use Repository inside Assembler, current_rally ALREADY reflects the DB state.
    # But for the Edit Form, we can use the assembler object's properties as defaults.
    # To be absolutely safe regarding latest DB state (concurrency), we can reload via repo if we want,
    # but Assembler just loaded it. Let's rely on Assembler object.
    
    existing_ann = None
    doc = store.get_rally(event_id)
    if doc:
        rev_data = doc.get('rev_data', {}) or {}
        if rev_data.get('status'): # If status exists, it's effectively an annotation
            existing_ann = SniperAnnotation(
                 symbol=symbol,
                 timeframe=timeframe,
                 event_id=event_id,
                 entry_bar_offset=rev_data.get('entry_bar_offset', 0),
                 exit_bar_offset=rev_data.get('exit_bar_offset'),
                 status=rev_data.get('status', 'PENDING'),
                 label=rev_data.get('label', ''),
                 note=rev_data.get('note', ''),
                 created_at=rev_data.get('updated_at', pd.Timestamp.now())
            )
            # Inject rev_gain if needed
            if 'rev_gain' in rev_data:
                existing_ann.rev_gain = rev_data['rev_gain']

    
    # --- ENTRY / EXIT CONFIGURATION (Top) ---
    st.markdown("---")
    st.markdown("### 🎯 Entry / Exit Ayarları")
    
    col_entry, col_exit = st.columns(2)
    
    with col_entry:
        default_entry = existing_ann.entry_bar_offset if existing_ann else 0
        entry_offset = st.number_input(
            "Entry Bar Offset",
            min_value=0,
            max_value=bars_to_peak + 50,
            value=default_entry,
            step=1,
            help="Event başlangıcından kaç bar sonra giriş yapılacak",
            key="ony_entry_offset"
        )
    
    with col_exit:
        default_exit_enabled = existing_ann is not None and existing_ann.exit_bar_offset is not None
        exit_enabled = st.checkbox("Exit Belirle", value=default_exit_enabled, key="ony_exit_enabled")
        
        if exit_enabled:
            default_exit = existing_ann.exit_bar_offset if existing_ann and existing_ann.exit_bar_offset else bars_to_peak
            exit_offset = st.number_input(
                "Exit Bar Offset",
                min_value=entry_offset + 1,
                max_value=bars_to_peak + 100,
                value=default_exit,
                step=1,
                help="Event başlangıcından kaç bar sonra çıkış yapılacak",
                key="ony_exit_offset"
            )
        else:
            exit_offset = None
            
    # --- CHART (Middle) ---
    st.markdown("---")
    # Header removed (Chart has internal title now)
    
    if pd.notna(event_time):
        try:
            render_sniper_studio_chart(
                symbol=symbol,
                timeframe=timeframe,
                event_time=event_time,
                bars_to_peak=bars_to_peak,
                entry_offset=entry_offset,
                exit_offset=exit_offset,
            )
        except Exception as e:
            st.error(f"Grafik hatası: {e}")
    else:
        st.warning("Event zamanı bulunamadı.")
        
    # --- NOTE ---
    st.markdown("---")
    st.markdown("### 📝 Revizyon Notu")
    
    col_note, col_dummy = st.columns([2, 1])
    with col_note:
        default_note = existing_ann.note if existing_ann else ""
        note = st.text_input("Not / Açıklama", value=default_note, placeholder="Ne değişti?", key="ony_note")

    # --- NORMALIZE ---
    st.markdown("---")
    st.markdown("### 🧲 Normalize Entry (Auto-Snap)")
    snap_mode = st.radio("Snap Mode", ["HIGH", "LOW", "CLOSE"], horizontal=True)
    
    if st.button("🧲 Normalize Hesapla", key="ony_normalize_btn"):
        try:
            ts = pd.to_datetime(event_time)
            res = normalize_entry(symbol, timeframe, ts, entry_offset, snap_mode)
            st.session_state["ony_norm_result"] = res.to_dict()
            st.success("✅ Normalize computed!")
        except Exception as e:
            st.error(f"Hata: {e}")

    if "ony_norm_result" in st.session_state:
        nr = st.session_state["ony_norm_result"]
        with st.expander("📊 Sonuç", expanded=True):
            st.code(f"Offset: {nr['entry_offset_in']} -> {nr['entry_offset_out']}")
            if st.button("✅ Uygula (Apply)"):

                # Immutable ID Architecture: No renaming to _RVZ_
                # We just update the existing ID with new offsets and REV label
                
                # Calculate Rev Gain
                rev_gain = None
                try:
                    df = load_history_data(symbol, timeframe)
                    if df is not None:
                        if 'open_time' in df.columns: df = df.set_index('open_time')
                        if df.index.tz is not None: df.index = df.index.tz_localize(None)
                        
                        ts = pd.to_datetime(event_time).tz_localize(None)
                        if ts in df.index:
                            start_pos = df.index.get_loc(ts)
                            # Handle slice if get_loc returns slice (duplicates) - take first
                            if isinstance(start_pos, slice): start_pos = start_pos.start
                            
                            p_entry = df.iloc[min(start_pos + nr['entry_offset_out'], len(df)-1)]['open']
                            exit_pos = min(start_pos + (exit_offset if exit_offset else 0), len(df)-1)
                            p_exit = df.iloc[exit_pos]['high'] # Use High for rally potential
                            if p_entry > 0:
                                rev_gain = (p_exit - p_entry) / p_entry
                except Exception as e:
                    print(f"Gain calc error: {e}")

                # Save to Store
                rev_data = {
                     'symbol': symbol,
                     'timeframe': timeframe,
                     'event_id': event_id,
                     'entry_bar_offset': nr['entry_offset_out'],
                     'exit_bar_offset': exit_offset,
                     'note': note,
                     'status': "APPROVED",
                     'label': "REV",
                     'rev_gain': rev_gain,
                     'updated_at': pd.Timestamp.now()
                }
                
                # Check for existing logic to preserve other fields? Store.upsert handles merge if we read first, 
                # but upsert replaces the layer blob. 
                # Ideally we should read existing 'rev_data' first.
                curr_doc = store.get_rally(event_id)
                curr_rev = curr_doc.get('rev_data', {}) or {}
                
                # Merge
                curr_rev.update(rev_data)
                
                store.upsert_rally(event_id, curr_rev, layer='rev')
                
                del st.session_state["ony_norm_result"]
                st.success(f"✅ Uygulandı! (ID: {event_id})")
                st.rerun()

    # --- SAVE ---
    st.markdown("---")
    cols_save = st.columns([3, 1])
    
    with cols_save[0]:
        if st.button("💾 KAYDET (GÜNCELLE)", type="primary", use_container_width=True):
            # Immutable ID Architecture: 
            # ID never changes. We overwrite the annotation with "REV" label.
            
            # Calculate Rev Gain
            rev_gain = None
            try:
                df = load_history_data(symbol, timeframe)
                if df is not None:
                    if 'open_time' in df.columns: df = df.set_index('open_time')
                    if df.index.tz is not None: df.index = df.index.tz_localize(None)
                    
                    ts = pd.to_datetime(event_time).tz_localize(None)
                    if ts in df.index:
                        start_pos = df.index.get_loc(ts)
                        if isinstance(start_pos, slice): start_pos = start_pos.start
                        
                        p_entry = df.iloc[min(start_pos + entry_offset, len(df)-1)]['open']
                        exit_pos = min(start_pos + (exit_offset if exit_offset else 0), len(df)-1)
                        p_exit = df.iloc[exit_pos]['high']
                        if p_entry > 0:
                            rev_gain = (p_exit - p_entry) / p_entry
            except Exception as e:
                print(f"Gain calc error: {e}")
    
            # Save to Store
            rev_data = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'event_id': event_id,
                    'entry_bar_offset': entry_offset,
                    'exit_bar_offset': exit_offset,
                    'note': note,
                    'status': "APPROVED",
                    'label': "REV",
                    'rev_gain': rev_gain,
                    'updated_at': pd.Timestamp.now()
            }
            
            curr_doc = store.get_rally(event_id)
            curr_rev = curr_doc.get('rev_data', {}) or {}
            curr_rev.update(rev_data)
            
            store.upsert_rally(event_id, curr_rev, layer='rev')
            
            if st.session_state.get('came_from_molder'):
                    st.session_state['molder_return_target'] = event_id
                    
            st.success(f"✅ Kaydedildi (ID: {event_id})")
            st.rerun()

    with cols_save[1]:
        if st.button("↩️ ORJİNALE DÖN", type="secondary", use_container_width=True, help="Tüm revizyonları siler ve ralliyi ilk haline döndürür."):
             # Reset Logic
             curr_doc = store.get_rally(event_id)
             curr_rev = curr_doc.get('rev_data', {}) or {}
             
             # Reset Critical Fields to Defaults
             reset_data = {
                 'entry_bar_offset': 0,
                 'exit_bar_offset': None,
                 'rev_gain': None,
                 'note': "",
                 'label': "", # Remove REV label
                 'status': "APPROVED", # Keep Approved
                 'updated_at': pd.Timestamp.now()
             }
             curr_rev.update(reset_data)
             
             store.upsert_rally(event_id, curr_rev, layer='rev')
             st.success("✅ Orjinale dönüldü.")
             st.rerun()
    # --- INFO BOX ---
    if existing_ann:
        with st.expander("📋 Mevcut Kayıt Bilgisi"):
            st.json({
                "entry": existing_ann.entry_bar_offset,
                "note": existing_ann.note,
                "created": existing_ann.created_at
            })


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def render_ony_page():
    """
    Rev. Stüdyo Ana Sayfa.
    Tek Görünüm: Editör.
    """
    # Title removed per user request
    
    if 'ony_target_id' in st.session_state:
        target_id = st.session_state.pop('ony_target_id')
        target_sym = st.session_state.pop('ony_prefill_symbol', None)
        target_tf = st.session_state.pop('ony_prefill_tf', None)
        
        # Determine Symbol/TF if not provided
        if not target_sym or not target_tf:
             start_parts = target_id.split('_') 
             if len(start_parts) >= 2:
                 target_sym = start_parts[0]
                 target_tf = start_parts[1]

        if target_sym: st.session_state['ony_symbol'] = target_sym
        if target_tf: st.session_state['ony_timeframe'] = target_tf
        
        st.session_state['ony_prefill_event_id'] = target_id
    
    # --- TABS ---
    # Directly render studio, no tabs
    render_ony_studio()
