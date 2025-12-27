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
from tezaver.core import coin_cell_paths
from tezaver.ui.chart_area import render_sniper_studio_chart
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
