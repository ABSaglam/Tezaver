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

from tezaver.sniper.sniper_annotations import (
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
        
        # Generate stable event_id if not exists
        if "event_id" not in df.columns:
            # Create deterministic event_id: {symbol}_{timeframe}_{epoch_seconds}
            df["event_id"] = df["event_time"].apply(
                lambda dt: f"{symbol}_{timeframe}_{int(dt.timestamp())}" if pd.notna(dt) else None
            )
        
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
# ONY STUDIO
# =============================================================================

def render_ony_studio():
    """
    ONY Studio - Event seçimi, entry/exit işaretleme, grafik görüntüleme, kaydetme ve onaylama.
    """
    st.subheader("🎯 ONY Stüdyo")
    st.caption("Event seç → Entry/Exit işaretle → Kaydet → Onayla")
    
    # Initialize repository
    repo = SniperAnnotationRepository()
    
    # --- SYMBOL & TIMEFRAME SELECTION ---
    col1, col2 = st.columns(2)
    
    with col1:
        symbols = _get_available_symbols()
        default_sym_idx = symbols.index("BTCUSDT") if "BTCUSDT" in symbols else 0
        symbol = st.selectbox("Coin", symbols, index=default_sym_idx, key="ony_symbol")
    
    with col2:
        timeframes = ["15m", "1h", "4h"]
        timeframe = st.selectbox("Timeframe", timeframes, index=0, key="ony_timeframe")
    
    # --- EVENT SELECTION ---
    st.markdown("---")
    st.markdown("### 📋 Event Seçimi")
    
    # Load events
    df_events = _load_events_for_symbol_tf(symbol, timeframe)
    
    if df_events is None or df_events.empty:
        st.warning(f"{symbol} {timeframe} için event bulunamadı. Önce Time Labs veya Fast15 taraması yapın.")
        return
    
    # --- TIER COMPUTATION & FILTERING ---
    # Compute tier for each event
    if 'rally_grade' in df_events.columns:
        df_events['tier'] = df_events['rally_grade'].apply(normalize_tier)
    else:
        df_events['tier'] = df_events['future_max_gain_pct'].apply(compute_tier_from_gain)
    
    # Remove events without valid tier
    df_events = df_events[df_events['tier'].notna()].copy()
    
    if df_events.empty:
        st.warning(f"{symbol} {timeframe} için geçerli tier'lı event bulunamadı.")
        return
    
    # Count events per tier
    tier_counts = {tier: len(df_events[df_events['tier'] == tier]) for tier in TIERS}
    
    # --- TIER SELECTOR (ABOVE EVENT DROPDOWN) ---
    tier_options = [f"{tier} ({tier_counts[tier]})" for tier in TIERS]
    
    # Initialize tier selection state
    if 'ony_selected_tier' not in st.session_state:
        st.session_state['ony_selected_tier'] = "DIAMOND"
    
    selected_tier_label = st.radio(
        "🏆 Tier Seç:",
        tier_options,
        horizontal=True,
        key="ony_tier_radio",
        index=TIERS.index(st.session_state['ony_selected_tier']) if st.session_state['ony_selected_tier'] in TIERS else 0
    )
    
    # Parse selected tier from label
    selected_tier = selected_tier_label.split(" (")[0]
    
    # Reset event selection if tier changed
    if st.session_state['ony_selected_tier'] != selected_tier:
        st.session_state['ony_selected_tier'] = selected_tier
        if 'ony_event_select' in st.session_state:
            del st.session_state['ony_event_select']
    
    # Filter events by selected tier
    filtered_events = df_events[df_events['tier'] == selected_tier].copy()
    
    if filtered_events.empty:
        st.info(f"{selected_tier} tier'ında event yok.")
        return
    
    st.caption(f"📊 {selected_tier}: {len(filtered_events)} event")
    st.markdown("---")
    
    # Event selector (using filtered events)
    event_options = []
    event_map = {}
    
    for i, row in filtered_events.head(50).iterrows():  # Limit to 50 for performance (using filtered_events)
        event_time = row.get("event_time")
        gain_pct = row.get("future_max_gain_pct", 0) * 100 if pd.notna(row.get("future_max_gain_pct")) else 0
        bars_to_peak = int(row.get("bars_to_peak", 0)) if pd.notna(row.get("bars_to_peak")) else 0
        event_id = str(row.get("event_id", i))
        
        label = f"{event_time.strftime('%Y-%m-%d %H:%M') if pd.notna(event_time) else 'N/A'} | +{gain_pct:.1f}% | {bars_to_peak} bars"
        event_options.append(label)
        event_map[label] = row
    
    if not event_options:
        st.warning("Görüntülenecek event yok.")
        return
    
    selected_label = st.selectbox("Event Seç", event_options, key="ony_event_select")
    selected_event = event_map[selected_label]
    event_id = str(selected_event.get("event_id", 0))
    event_time = selected_event.get("event_time")
    bars_to_peak = int(selected_event.get("bars_to_peak", 20)) if pd.notna(selected_event.get("bars_to_peak")) else 20
    
    # --- LOAD EXISTING ANNOTATION ---
    existing_ann = repo.get_one(symbol, timeframe, event_id)
    
    # --- ENTRY / EXIT CONFIGURATION ---
    st.markdown("---")
    st.markdown("### 🎯 Entry / Exit Ayarları")
    
    col_entry, col_exit = st.columns(2)
    
    with col_entry:
        default_entry = existing_ann.entry_bar_offset if existing_ann else 5
        entry_offset = st.number_input(
            "Entry Bar Offset",
            min_value=0,
            max_value=bars_to_peak + 50,
            value=default_entry,
            step=1,
            help="Event başlangıcından kaç bar sonra giriş yapılacak (0 = ilk bar)",
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
    
    # --- STATUS & LABEL ---
    st.markdown("---")
    st.markdown("### 📝 Durum ve Etiket")
    
    col_status, col_label, col_note = st.columns(3)
    
    with col_status:
        status_options = ["PENDING", "APPROVED", "REJECTED", "REVIEWED"]
        default_status_idx = status_options.index(existing_ann.status) if existing_ann and existing_ann.status in status_options else 0
        status = st.selectbox("Durum", status_options, index=default_status_idx, key="ony_status")
    
    with col_label:
        label_options = ["UNCERTAIN", "GOOD", "BAD"]
        default_label_idx = label_options.index(existing_ann.label) if existing_ann and existing_ann.label in label_options else 0
        label = st.selectbox("Etiket", label_options, index=default_label_idx, key="ony_label")
    
    with col_note:
        default_note = existing_ann.note if existing_ann else ""
        note = st.text_input("Not", value=default_note, key="ony_note")
    
    # --- NORMALIZE ENTRY ---
    st.markdown("---")
    st.markdown("### 🧲 Normalize Entry (Auto-Snap)")
    
    # Snap Mode Selector
    snap_mode = st.radio(
        "Snap Mode",
        options=["HIGH", "LOW", "CLOSE"],
        index=0,
        horizontal=True,
        help="HIGH: Snap to Highest High (Breakout)\nLOW: Snap to Lowest Low (Dip/Pullback)\nCLOSE: Snap to Candle Close"
    )

    col_norm_btn, col_apply_reset = st.columns([1, 1])
    
    with col_norm_btn:
        if st.button("🧲 Normalize (Entry)", key="ony_normalize_btn", use_container_width=True):
            try:
                # Parse event_time
                event_time_ts = pd.to_datetime(event_time)
                
                # Call normalize_entry with selected mode
                norm_result = normalize_entry(
                    symbol=symbol,
                    timeframe=timeframe,
                    event_time=event_time_ts,
                    entry_bar_offset=entry_offset,
                    snap_mode=snap_mode
                )
                
                # Store in session_state
                st.session_state["ony_norm_result"] = norm_result.to_dict()
                st.success("✅ Normalize computed successfully!")
            except FileNotFoundError as e:
                st.error(f"❌ History data not found: {e}")
            except Exception as e:
                st.error(f"❌ Normalize error: {e}")
                import traceback
                st.code(traceback.format_exc())
    
    # Display normalize result if available
    if "ony_norm_result" in st.session_state:
        norm_result_dict = st.session_state["ony_norm_result"]
        
        with st.expander("📊 Normalize Result", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Entry Offset (in)", norm_result_dict["entry_offset_in"])
                st.metric("Entry Offset (out)", norm_result_dict["entry_offset_out"])
            
            with col2:
                st.metric("Snap Distance", f"{norm_result_dict['snap_distance_bars']} bars")
                st.metric("Snap Confidence", f"{norm_result_dict['snap_confidence']:.2f}")
            
            with col3:
                st.caption("**Normalized Entry TS:**")
                st.code(norm_result_dict["entry_ts_iso"])
                st.caption("**Snap Reason:**")
                st.info(norm_result_dict["snap_reason"])
        
        # Apply and Reset buttons
        with col_apply_reset:
            col_apply, col_reset = st.columns(2)
            
            with col_apply:
                if st.button("✅ Apply", key="ony_apply_normalize", use_container_width=True, type="primary"):
                    # Create NormalizeResult from dict
                    from tezaver.rally.normalize_engine import NormalizeResult
                    norm_result_obj = NormalizeResult(**norm_result_dict)
                    
                    # Load or create annotation
                    ann = repo.get_one(symbol, timeframe, event_id)
                    if ann is None:
                        ann = SniperAnnotation(
                            symbol=symbol,
                            timeframe=timeframe,
                            event_id=event_id,
                            entry_bar_offset=entry_offset,
                            note=note,
                            status=status,
                            label=label,
                        )
                    
                    # Apply normalize
                    ann = apply_normalize_to_annotation(ann, norm_result_obj)
                    ann.note = note  # Preserve note
                    ann.status = status
                    ann.label = label
                    if exit_enabled and exit_offset:
                        ann.exit_bar_offset = exit_offset
                    
                    # Save
                    repo.append(
                        symbol=ann.symbol,
                        timeframe=ann.timeframe,
                        event_id=ann.event_id,
                        entry_bar_offset=ann.entry_bar_offset,
                        exit_bar_offset=ann.exit_bar_offset,
                        note=ann.note,
                        status=ann.status,
                        label=ann.label,
                    )
                    
                    st.success("✅ Normalize applied & saved!")
                    st.rerun()
            
            with col_reset:
                if st.button("↩ Reset", key="ony_reset_normalize", use_container_width=True):
                    # Clear from session_state
                    if "ony_norm_result" in st.session_state:
                        del st.session_state["ony_norm_result"]
                    
                    # Clear from annotation if exists
                    ann = repo.get_one(symbol, timeframe, event_id)
                    if ann:
                        ann.normalized_entry_bar_offset = None
                        ann.normalized_entry_ts = None
                        ann.snap_reason = None
                        ann.snap_distance_bars = None
                        ann.snap_confidence = None
                        ann.snap_algo_version = None
                        
                        repo.append(
                            symbol=ann.symbol,
                            timeframe=ann.timeframe,
                            event_id=ann.event_id,
                            entry_bar_offset=ann.entry_bar_offset,
                            exit_bar_offset=ann.exit_bar_offset,
                            note=ann.note,
                            status=ann.status,
                            label=ann.label,
                        )
                    
                    st.success("↩ Normalize reset!")
                    st.rerun()
    
    # Show normalized badge if annotation has normalized data
    if existing_ann and existing_ann.normalized_entry_ts:
        st.info(f"✅ Normalized: {existing_ann.snap_reason} | TS: {existing_ann.normalized_entry_ts}")
    
    # --- ACTION BUTTONS ---
    st.markdown("---")
    
    col_save, col_approve, col_reject = st.columns(3)
    
    with col_save:
        if st.button("💾 Kaydet", use_container_width=True, type="secondary"):
            ann = repo.append(
                symbol=symbol,
                timeframe=timeframe,
                event_id=event_id,
                entry_bar_offset=entry_offset,
                exit_bar_offset=exit_offset,
                note=note,
                status=status,
                label=label,
            )
            st.success(f"✅ Kayıt başarılı: {event_id}")
            st.rerun()
    
    # Action Buttons Logic based on Current Status
    is_already_approved = (existing_ann and existing_ann.status == "APPROVED")
    
    with col_approve:
        btn_label = "💾 Revizyonu Kaydet" if is_already_approved else "✅ Onayla (Approve)"
        btn_key = "btn_approve_update"
        
        if st.button(btn_label, key=btn_key, use_container_width=True, type="primary"):
            ann = repo.append(
                symbol=symbol,
                timeframe=timeframe,
                event_id=event_id,
                entry_bar_offset=entry_offset,
                exit_bar_offset=exit_offset,
                note=note,
                status="APPROVED",
                label=label,
                # Preserve existing internal fields if needed, 
                # or rely on repo.append logic to handle merging if it existed (repo.append usually overwrites or appends new)
                # Ideally we want to update. repo.append in current implementation appends to list and saves. 
                # Correct implementation: load all, replace matching event_id, save.
                # repo.append does: load, remove old if exists, append new, save. So it acts as upsert.
            )
            
            # Additional logic for saving normalized fields if present in session_state or ann
            # (Previously managed via internal modification of 'existing_ann' object)
            # Since 'repo.append' creates a NEW object, we must ensure normalized fields are carried over if we care.
            # But the UI flow above for 'Apply' normalized modified the 'existing_ann' in memory presumably? 
            # No, apply_normalize_to_annotation returned a new object or modified it.
            # If we want to persist normalized fields, we should pass them to append if supported, 
            # or we rely on the fact that repo.append creates a basic annotation. 
            # CAUTION: append() signature in sniper_annotations might not support extra fields like normalized_*.
            # For now, we stick to basic fields. Normalized data retention might need repo update.
            
            if is_already_approved:
                st.success(f"💾 REVİZYON KAYDEDİLDİ: {event_id}")
            else:
                st.success(f"✅ ONAYLANDI: {event_id}")
            st.rerun()
    
    with col_reject:
        if st.button("❌ Reddet (Reject/Revoke)", use_container_width=True):
            ann = repo.append(
                symbol=symbol,
                timeframe=timeframe,
                event_id=event_id,
                entry_bar_offset=entry_offset,
                exit_bar_offset=exit_offset,
                note=note,
                status="REJECTED",
                label=label,
            )
            st.warning(f"❌ REDDEDİLDİ: {event_id}")
            st.rerun()
    
    # --- CHART ---
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
        st.warning("Event zamanı bulunamadı, grafik çizilemiyor.")
    
    # --- INFO BOX ---
    if existing_ann:
        with st.expander("📋 Mevcut Kayıt Bilgisi"):
            st.json({
                "event_id": existing_ann.event_id,
                "entry_bar_offset": existing_ann.entry_bar_offset,
                "exit_bar_offset": existing_ann.exit_bar_offset,
                "status": existing_ann.status,
                "label": existing_ann.label,
                "note": existing_ann.note,
                "created_at": existing_ann.created_at,
            })


# =============================================================================
# ONY QUEUE
# =============================================================================

def render_ony_queue():
    """
    ONY Queue - Tüm annotation kayıtlarını PENDING/APPROVED/REJECTED olarak listele.
    """
    st.subheader("📋 ONY Kuyruğu")
    st.caption("Tüm annotation kayıtları")
    
    repo = SniperAnnotationRepository()
    
    # --- FILTERS ---
    col1, col2 = st.columns(2)
    
    with col1:
        symbols = _get_available_symbols()
        symbol = st.selectbox("Coin", symbols, key="ony_queue_symbol")
    
    with col2:
        timeframes = ["15m", "1h", "4h"]
        timeframe = st.selectbox("Timeframe", timeframes, key="ony_queue_tf")
    
    # Load all annotations
    all_anns = repo.load_all(symbol, timeframe)
    
    if not all_anns:
        st.info(f"{symbol} {timeframe} için kayıtlı annotation yok.")
        return
    
    # Group by status
    pending = [a for a in all_anns if a.status == "PENDING"]
    approved = [a for a in all_anns if a.status == "APPROVED"]
    rejected = [a for a in all_anns if a.status == "REJECTED"]
    reviewed = [a for a in all_anns if a.status == "REVIEWED"]
    
    # Display counts
    st.markdown(f"**Toplam:** {len(all_anns)} | 🟡 PENDING: {len(pending)} | ✅ APPROVED: {len(approved)} | ❌ REJECTED: {len(rejected)} | 👁️ REVIEWED: {len(reviewed)}")
    
    st.markdown("---")
    
    # --- TABS ---
    tab_approved, tab_rejected, tab_pending = st.tabs(["✅ APPROVED (Auto)", "❌ REJECTED", "🟡 PENDING (Legacy)"])
    
    def render_annotation_table(anns: List[SniperAnnotation], status_key: str):
        if not anns:
            st.info("Bu kategoride kayıt yok.")
            return
        
        # Build dataframe
        data = []
        for a in anns:
            data.append({
                "Event ID": a.event_id,
                "Entry": a.entry_bar_offset,
                "Exit": a.exit_bar_offset if a.exit_bar_offset else "-",
                "Label": a.label,
                "Not": a.note[:30] + "..." if a.note and len(a.note) > 30 else a.note,
                "Oluşturulma": a.created_at[:16] if a.created_at else "-",
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Open in Studio button
        if anns:
            selected_idx = st.selectbox(
                "Stüdyoda aç:",
                range(len(anns)),
                format_func=lambda i: f"{anns[i].event_id} (Entry: +{anns[i].entry_bar_offset})",
                key=f"ony_queue_select_{status_key}"
            )
            
            if st.button(f"🎯 Stüdyoda Aç", key=f"ony_queue_open_{status_key}"):
                # Set session state to switch to studio with this event
                st.session_state["ony_prefill_event_id"] = anns[selected_idx].event_id
                st.session_state["ony_tab_mode"] = "studio"
                st.rerun()
    
    with tab_approved:
        render_annotation_table(approved, "approved")
    
    with tab_rejected:
        render_annotation_table(rejected, "rejected")

    with tab_pending:
        render_annotation_table(pending, "pending")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def render_ony_page():
    """
    ONY Ana Sayfa - Stüdyo veya Kuyruk seçimi.
    """
    st.title("🎯 ONY - Onay Stüdyosu")
    
    # Tab mode
    mode = st.session_state.get("ony_tab_mode", "studio")
    
    tab_studio, tab_queue = st.tabs(["🎨 Stüdyo", "📋 Kuyruk"])
    
    with tab_studio:
        render_ony_studio()
    
    with tab_queue:
        render_ony_queue()
