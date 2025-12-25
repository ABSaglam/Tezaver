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
    SniperAnnotationRepository,
    SniperStatus,
    SniperLabel,
)
from tezaver.ui.chart_area import render_sniper_studio_chart
from tezaver.core import coin_cell_paths
from tezaver.rally.normalize_engine import normalize_entry, NormalizeResult


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# Tier constants
TIERS = ["DIAMOND", "GOLD", "SILVER", "BRONZE"]

def normalize_tier(value: Any) -> Optional[str]:
    """
    Normalize tier/grade string to standard tier name.
    
    Args:
        value: Tier string (can be 'diamond', 'DIAMOND', 'DIA', etc.) or None
    
    Returns:
        Standardized tier name ("DIAMOND", "GOLD", "SILVER", "BRONZE") or None if unknown
    """
    if pd.isna(value) or value is None:
        return None
    
    s = str(value).strip().upper()
    
    # Diamond variants
    if s in ["DIAMOND", "DIA", "💎"]:
        return "DIAMOND"
    
    # Gold variants
    if s in ["GOLD", "GLD", "🥇"]:
        return "GOLD"
    
    # Silver variants
    if s in ["SILVER", "SLV", "🥈"]:
        return "SILVER"
    
    # Bronze variants
    if s in ["BRONZE", "BRZ", "🥉"]:
        return "BRONZE"
    
    return None


def compute_tier_from_gain(gain_pct: float) -> Optional[str]:
    """
    Compute tier from future_max_gain_pct.
    
    WRAPPER: This function now delegates to the canonical implementation
    in rally_grade_cards.py to prevent threshold drift.
    
    Args:
        gain_pct: Gain percentage as decimal (e.g., 0.30 for 30%)
    
    Returns:
        Tier name or None if gain is too low
    """
    from tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct
    return compute_tier_from_gain_pct(gain_pct)

def _load_events_for_symbol_tf(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Load rally events from Fast15 or Time Labs depending on timeframe.
    
    Dataset paths:
    - 15m: library/fast15_rallies/{symbol}/fast15_rallies.parquet
    - 1h:  library/time_labs/1h/{symbol}/rallies_1h.parquet
    - 4h:  library/time_labs/4h/{symbol}/rallies_4h.parquet
    
    Returns DataFrame with stable event_id generation.
    """
    try:
        if timeframe == "15m":
            path = coin_cell_paths.get_fast15_rallies_path(symbol)
        else:
            path = coin_cell_paths.get_time_labs_rallies_path(symbol, timeframe)
        
        if not path.exists():
            return None
        
        df = pd.read_parquet(path)
        if df.empty:
            return None
        
        # Normalize timestamp column
        for col in ["event_time", "start_ts", "timestamp"]:
            if col in df.columns:
                df["event_time"] = pd.to_datetime(df[col], errors="coerce")
                break
        
        # Compute Tier if missing (needed for ID)
        if 'rally_grade' in df.columns:
            df['temp_tier'] = df['rally_grade'].apply(normalize_tier)
        else:
            df['temp_tier'] = df['future_max_gain_pct'].apply(compute_tier_from_gain)
            
        # Tier Code Mapping
        def get_tier_code(tier_str):
            if not tier_str: return "X"
            t = str(tier_str).upper()
            if "DIAMOND" in t: return "D"
            if "GOLD" in t: return "G"
            if "SILVER" in t: return "S"
            if "BRONZE" in t: return "B"
            return "X"

        # Generate Tier-Coded Event ID: {symbol}_{timeframe}_{tier_code}_{timestamp}
        # We overwrite existing event_id to enforce the new format
        def generate_id(row):
            if pd.isna(row['event_time']): return None
            ts = int(row['event_time'].timestamp())
            code = get_tier_code(row['temp_tier'])
            return f"{symbol}_{timeframe}_{code}_{ts}"

        df["event_id"] = df.apply(generate_id, axis=1)
        
        # Cleanup temp column
        if 'temp_tier' in df.columns:
            df.drop(columns=['temp_tier'], inplace=True)
        
        # Sort by time descending (newest first)
        df = df.sort_values("event_time", ascending=False).reset_index(drop=True)
        
        return df
    except Exception as e:
        st.warning(f"Event yüklenirken hata: {e}")
        return None


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
            repo_check = SniperAnnotationRepository()
            
            for s in target_symbols:
                for t in target_tfs:
                    current_step += 1
                    my_bar.progress(current_step / total_steps, text=f"Scanning {s} {t}...")
                    
                    df_events = _load_events_for_symbol_tf(s, t)
                    if df_events is None or df_events.empty:
                        continue
                        
                    # Compute Tiers
                    if 'rally_grade' in df_events.columns:
                        df_events['tier'] = df_events['rally_grade'].apply(normalize_tier)
                    else:
                        df_events['tier'] = df_events['future_max_gain_pct'].apply(compute_tier_from_gain)
                    
                    # Filter by Tiers
                    filtered = df_events[df_events['tier'].isin(tiers)].copy()
                    
                    if not filtered.empty:
                        # Skip APPROVED
                        existing_anns = repo_check.load_all(s, t)
                        approved_ids = {a.event_id for a in existing_anns if a.status == "APPROVED"}
                        
                        # Apply suppression
                        before_count = len(filtered)
                        filtered = filtered[~filtered['event_id'].isin(approved_ids)]
                        # after_count = len(filtered)
                        
                        if not filtered.empty:
                            # Add metadata
                            filtered['symbol'] = s
                            filtered['timeframe'] = t
                            
                            # Convert to records
                            records = filtered[['event_id', 'tier', 'future_max_gain_pct', 'symbol', 'timeframe']].to_dict('records')
                            all_events.extend(records)
            
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
                repo = SniperAnnotationRepository()
                count = 0
                
                progress_bar = st.progress(0)
                total = len(prev['events'])
                
                for i, evt in enumerate(prev['events']):
                    # Use per-event metadata
                    s = evt['symbol']
                    t = evt['timeframe']
                    eid = str(evt['event_id'])
                    
                    # Check existing
                    existing = repo.get_one(s, t, eid)
                    
                    # Create or Update
                    entry_offset = existing.entry_bar_offset if existing else 0
                    note = existing.note if existing else "Auto-Approved Batch"
                    label = existing.label if existing else "GOOD"
                    
                    repo.append(
                        symbol=s,
                        timeframe=t,
                        event_id=eid,
                        entry_bar_offset=entry_offset,
                        status="APPROVED",
                        label=label,
                        note=note
                    )
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
    
    # Initialize repository
    repo = SniperAnnotationRepository()
    
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
    
    # Load events for filtering
    df_events = _load_events_for_symbol_tf(symbol, timeframe)
    
    # Tier Logic (Hidden calculation for filter)
    if df_events is not None and not df_events.empty:
        if 'rally_grade' in df_events.columns:
            df_events['tier'] = df_events['rally_grade'].apply(normalize_tier)
        else:
            df_events['tier'] = df_events['future_max_gain_pct'].apply(compute_tier_from_gain)
        df_events = df_events[df_events['tier'].notna()].copy()
        
        tier_counts = {tier: len(df_events[df_events['tier'] == tier]) for tier in TIERS}
        tier_options = [f"{tier} ({tier_counts[tier]})" for tier in TIERS]
    else:
        tier_options = TIERS
        tier_counts = {t:0 for t in TIERS}
        
    # AUTO-SWITCH TIER (Jumper Fix)
    if 'ony_prefill_event_id' in st.session_state and df_events is not None:
        target_id = st.session_state['ony_prefill_event_id']
        match = df_events[df_events['event_id'].astype(str) == str(target_id)]
        
        if not match.empty:
             target_tier = match.iloc[0]['tier']
             if target_tier in TIERS and st.session_state.get('ony_selected_tier') != target_tier:
                 st.session_state['ony_selected_tier'] = target_tier

    with c_tier:
        if 'ony_selected_tier' not in st.session_state:
            st.session_state['ony_selected_tier'] = "DIAMOND"
        
        # Horizontal Radio for compact look
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
    if df_events is None or df_events.empty:
        st.warning(f"Event yok: {symbol} {timeframe}")
        return

    filtered_events = df_events[df_events['tier'] == selected_tier].copy()
    
    if filtered_events.empty:
        st.info(f"🔍 {selected_tier} katmanında incelenecek ralli yok.")
        return
    
    # Check for prefill request
    prefill_id = st.session_state.pop('ony_prefill_event_id', None)
    default_idx = 0
    
    # Event Options
    event_options = []
    event_map = {}
    for i, row in filtered_events.head(1000).iterrows(): 
        event_time = row.get("event_time")
        gain_pct = row.get("future_max_gain_pct", 0) * 100 if pd.notna(row.get("future_max_gain_pct")) else 0
        bars_to_peak = int(row.get("bars_to_peak", 0)) if pd.notna(row.get("bars_to_peak")) else 0
        event_id = str(row.get("event_id", i))
        
        # Match Index for Prefill
        if prefill_id:
             # Standard match or RVZ match
             if event_id == prefill_id or (prefill_id.replace("_RVZ_", "_") == event_id) or (event_id.replace("_RVZ_", "_") == prefill_id):
                 default_idx = len(event_options)
        
        # Is reviewed? (Check Raw ID, then Check RVZ variant)
        ann = repo.get_one(symbol, timeframe, event_id)
        if not ann:
            # Try finding RVZ variant
            # Construct tentative RVZ ID: Insert RVZ after tier
            parts = event_id.split('_')
            if len(parts) >= 3 and "RVZ" not in parts:
                parts.insert(3, "RVZ")
                rvz_id = "_".join(parts)
                ann = repo.get_one(symbol, timeframe, rvz_id)
        
        icon = "✅" if ann and ann.status == "APPROVED" else "🆕"
        if ann and "RVZ" in ann.event_id: icon = "🛠️" # Show Wrench for Revised
        
        label = f"{icon} {event_time.strftime('%Y-%m-%d %H:%M') if pd.notna(event_time) else 'N/A'} | +{gain_pct:.1f}% | {bars_to_peak}bar"
        event_options.append(label)
        event_map[label] = row

    if not event_options:
        st.warning("Liste boş.")
        return
        
    # Full width selectbox
    selected_label = st.selectbox("Ralli Seçiniz", event_options, index=default_idx, key="ony_event_select", label_visibility="collapsed")
    selected_event = event_map[selected_label]
    event_id = str(selected_event.get("event_id", 0))
    event_time = selected_event.get("event_time")
    bars_to_peak = int(selected_event.get("bars_to_peak", 20)) if pd.notna(selected_event.get("bars_to_peak")) else 20
    
    # Load Existing
    existing_ann = repo.get_one(symbol, timeframe, event_id)
    
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
    st.markdown("### 📊 Sniper Studio Grafiği")
    
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
                # Handle RVZ Logic (Renaming ID)
                final_id = event_id
                parts = event_id.split('_')
                if "RVZ" not in parts:
                    if len(parts) >= 3:
                        parts.insert(3, "RVZ")
                        final_id = "_".join(parts)
                        # Delete old ID
                        repo.delete(symbol, timeframe, event_id)
                
                repo.append(symbol, timeframe, final_id, nr['entry_offset_out'], exit_offset, note, "APPROVED", "REV")
                del st.session_state["ony_norm_result"]
                st.success(f"✅ Uygulandı! (ID: {final_id})")
                st.rerun()

    # --- SAVE ---
    st.markdown("---")
    if st.button("💾 REVİZYONU KAYDET (Asıl)", type="primary", use_container_width=True):
        # Handle RVZ Logic
        # Expected ID format: SYMBOL_TF_TIER_TS or SYMBOL_TF_TIER_RVZ_TS
        final_id = event_id
        parts = event_id.split('_')
        
        # Check if RVZ is missing
        if "RVZ" not in parts:
            # Insert after TIER (index 2: 0=SYM, 1=TF, 2=TIER) -> Insert at 3
            if len(parts) >= 3:
                parts.insert(3, "RVZ")
                final_id = "_".join(parts)
                
                # Delete old non-RVZ entry to avoid duplicates
                repo.delete(symbol, timeframe, event_id)
        
        repo.append(symbol, timeframe, final_id, entry_offset, exit_offset, note, "APPROVED", "REV")
        st.success(f"✅ Kaydedildi (ID: {final_id})")
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
# REV. STUDIO QUEUE (Simplified)
# =============================================================================

def render_ony_queue():
    """
    Gelişmiş Revizyon Listesi (Matrix UI Style).
    Hamm (Scanner) ve Revize (Repo) verileri arasında geçiş ve filtreleme.
    """
    st.subheader("📋 Revizyon Listesi")
    
    # --- FILTERS ROW 1 ---
    c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
    
    with c1:
        # Source Selection
        source_mode = st.radio("Kaynak", ["REVİZE (Düzenlenenler)", "HAM (Tarama Sonuçları)"], horizontal=True, label_visibility="collapsed")
        is_revize_mode = source_mode.startswith("REVİZE")

    # Coin Pagination Logic
    all_symbols = _get_available_symbols()
    page_size = 50
    total_pages = (len(all_symbols) + page_size - 1) // page_size
    
    with c2:
        # Group Selector
        page_options = ["TÜMÜ"] + [f"{i*page_size+1}-{(i+1)*page_size}" for i in range(total_pages)]
        selected_page = st.selectbox("Grup", page_options, index=0)

    # Filter Symbols based on Page
    target_symbols = all_symbols
    if selected_page != "TÜMÜ":
        # Parse range "1-50"
        try:
            p_start, p_end = map(int, selected_page.split('-'))
            target_symbols = all_symbols[p_start-1 : p_end]
        except: pass
        
    with c3:
        # TF Filter (Single Select)
        timeframes_opts = ["TÜMÜ", "15m", "1h", "4h"]
        sel_tf_val = st.selectbox("Zaman", timeframes_opts, index=1) # Default 15m
        
        if sel_tf_val == "TÜMÜ": sel_tfs = ["15m", "1h", "4h"]
        else: sel_tfs = [sel_tf_val]

    with c4:
        # Tier Filter (Single Select)
        tier_opts = ["TÜMÜ"] + TIERS
        sel_tier_val = st.selectbox("Tier", tier_opts, index=1) # Default DIAMOND
        
        if sel_tier_val == "TÜMÜ": sel_tiers = TIERS
        else: sel_tiers = [sel_tier_val]

    # --- DATA LOADING ---
    rows = []
    repo = SniperAnnotationRepository()
    
    processing_container = st.empty()
    
    if is_revize_mode:
        # REVİZE MODE: Load from Repo
        # Force scan ALL symbols (Revisions are sparse, pagination hides them)
        scan_symbols = all_symbols 
        
        with processing_container:
            prog = st.progress(0, "Revizeler yükleniyor...")
            
        step = 0
        total_steps = len(scan_symbols)
        
        for sym in scan_symbols:
            step += 1
            if step % 20 == 0: prog.progress(min(1.0, step/total_steps))
            
            for tf in sel_tfs:
                anns = repo.load_all(sym, tf)
                for ann in anns:
                    parts = ann.event_id.split('_')
                    tier = "UNKNOWN"
                    for p in parts:
                        if p in TIERS: tier = p; break
                    
                    # STRICT FILTER: Show "Manual Revisions"
                    # Criteria: Has RVZ tag OR Note is custom (not auto-batch)
                    is_rvz_tag = "_RVZ_" in ann.event_id
                    is_custom_note = ann.note and "Auto-Approved Batch" not in ann.note
                    
                    if not (is_rvz_tag or is_custom_note): continue
                    
                    if tier not in sel_tiers: continue
                    
                    # Formatting
                    tier_icon = "❓"
                    if tier == "DIAMOND": tier_icon = "💎"
                    if tier == "GOLD": tier_icon = "🥇"
                    if tier == "SILVER": tier_icon = "🥈"
                    if tier == "BRONZE": tier_icon = "🥉"
                    
                    rows.append({
                        "ID": ann.event_id,
                        "Tier": f"{tier_icon} {tier}" if tier != "UNKNOWN" else "❓ UNKNOWN",
                        "Coin": sym,
                        "Zaman": tf,
                        "Not": ann.note,
                        "Giriş Offset": ann.entry_bar_offset,
                        "Durum": "🛠️ REVİZE" if is_rvz_tag else "📝 DÜZENLENDİ",
                        "_ts": int(parts[-1]) if parts[-1].isdigit() else 0
                    })
        
        # Sort: Newest First
        rows.sort(key=lambda x: x["_ts"], reverse=True)
        
        processing_container.empty()
    else:
        # HAM MODE: Load from Scanner Files
        # Use simple progress bar for feedback
        stats_info = {"scanned": 0, "loaded": 0, "filtered": 0, "skipped_reviewed": 0}
        
        with processing_container:
            prog = st.progress(0, "Veriler taranıyor...")
            
        step = 0
        total_steps = len(target_symbols) * len(sel_tfs)
        if total_steps == 0: total_steps = 1
        
        for sym in target_symbols:
            for tf in sel_tfs:
                step += 1
                if step % 5 == 0: prog.progress(min(1.0, step / total_steps))
                
                df = _load_events_for_symbol_tf(sym, tf)
                stats_info["scanned"] += 1
                
                if df is None or df.empty: continue
                stats_info["loaded"] += len(df)
                
                # Check Repo to exclude already revised items
                existing_anns = repo.load_all(sym, tf)
                reviewed_ids = set()
                for a in existing_anns:
                    # STRICTER FILTER: Only exclude if it is a manual revision (has RVZ tag)
                    if "_RVZ_" in a.event_id:
                         reviewed_ids.add(a.event_id.replace("_RVZ_", "_").replace("__", "_"))
                         reviewed_ids.add(a.event_id)
                
                for _, row in df.iterrows():
                    eid = str(row['event_id'])
                    
                    if eid in reviewed_ids: 
                        stats_info["skipped_reviewed"] += 1
                        continue
                    
                    tier = "UNKNOWN"
                    if 'rally_grade' in row:
                        tier = normalize_tier(row['rally_grade'])
                    else:
                        tier = compute_tier_from_gain(row.get('future_max_gain_pct', 0))
                    
                    if tier not in sel_tiers or not tier: 
                        stats_info["filtered"] += 1
                        continue

                    # Extract fields
                    gain = row.get('future_max_gain_pct', 0) * 100
                    bars = row.get('bars_to_peak', 0)
                    qual = row.get('quality_score', 0)
                    shape = row.get('rally_shape', '-')
                    risk = row.get('risk_level', '-')
                    
                    rows.append({
                        "ID": eid,
                        "Tier": tier,
                        "Coin": sym,
                        "Zaman": tf,
                        "Kazanç (%)": f"{gain:.1f}",
                        "Süre": bars,
                        "Kalite": f"{qual:.0f}",
                        "Şekil": shape,
                        "Risk": risk
                    })
        
        if not rows:
             st.warning(f"Stats: S={stats_info['scanned']}, L={stats_info['loaded']}, F={stats_info['filtered']}, SkipRev={stats_info['skipped_reviewed']}")
        else:
             processing_container.empty()

    # --- DISPLAY ---
    if not rows:
        st.info("Kriterlere uygun kayıt bulunamadı.")
        return

    df_display = pd.DataFrame(rows)
    
    st.markdown(f"**Toplam:** {len(rows)} kayıt")
    
    # Interactive Table
    selection = st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    # Handle Selection -> Navigate to Studio
    if selection and selection.selection.rows:
        idx = selection.selection.rows[0]
        selected_row = df_display.iloc[idx]
        sel_id = selected_row["ID"]
        sel_sym = selected_row["Coin"]
        sel_tf = selected_row["Zaman"]
        
        # Prepare Studio
        st.session_state["ony_prefill_symbol"] = sel_sym
        st.session_state["ony_prefill_tf"] = sel_tf
        # Set target_id to trigger the Deep Link Handler in render_ony_page which updates widgets safely
        st.session_state["ony_target_id"] = sel_id
        
        st.session_state["ony_tab_mode"] = "studio"
        st.rerun()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def render_ony_page():
    """
    Rev. Stüdyo Ana Sayfa - Stüdyo veya Kuyruk seçimi.
    """
    st.title("🎯 Revize")
    
    # --- DEEP LINKING HANDLER (Jumper) ---
    if 'ony_target_id' in st.session_state:
        target_id = st.session_state.pop('ony_target_id')
        target_sym = st.session_state.pop('ony_prefill_symbol', None)
        target_tf = st.session_state.pop('ony_prefill_tf', None)
        
        if target_sym: st.session_state['ony_symbol'] = target_sym
        if target_tf: st.session_state['ony_timeframe'] = target_tf
        st.session_state['ony_prefill_event_id'] = target_id
        st.session_state["ony_tab_mode"] = "studio"
        st.rerun()
    
    # Tab mode
    mode = st.session_state.get("ony_tab_mode", "studio")
    
    tab_studio, tab_queue = st.tabs(["🎨 Revizyon", "📋 Liste"])
    
    with tab_studio:
        render_ony_studio()
    
    with tab_queue:
        render_ony_queue()
