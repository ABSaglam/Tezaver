"""
Molder Tab - Kalıpçı (Archetype Labeling)
=========================================

"Ralliyi Adlandırma ve Sınıflandırma Atölyesi"

Flow:
1. Load APPROVED rallies from Ony Repo via RallyAssembler.
2. Filter by Tier (Diamond, Gold, etc.).
3. Select from List (synced with Chart).
4. Label with Archetype (Icons).
"""

import streamlit as st
import pandas as pd
import importlib
from typing import List, Optional, Dict
from datetime import datetime
from pathlib import Path

from tezaver.core.annotations import SniperAnnotation, SniperStatus, SniperLabel
from tezaver.core.molds import Archetype, ARCHETYPE_LABELS, ARCHETYPE_DESCRIPTIONS
from tezaver.ui.chart_area import render_sniper_studio_chart, load_history_data
from tezaver.foundry.archetype_service import ArchetypeService
import tezaver.core.rally_store
importlib.reload(tezaver.core.rally_store)
from tezaver.core.rally_store import RallyStore

import tezaver.foundry.rally_assembler
importlib.reload(tezaver.foundry.rally_assembler)
from tezaver.foundry.rally_assembler import RallyAssembler

# Reuse helpers from Ony Tab to maintain consistency
from tezaver.ui.ony_tab import (
    _get_available_symbols, 
)

from tezaver.core.tier_utils import (
    normalize_tier, 
    compute_tier_from_gain,
    TIERS
)

from tezaver.core.coin_class_utils import (
    get_coin_class_with_override,
    get_coin_class_display,
    get_coin_class_icon,
    get_coin_class_color,
    get_coin_class_color,
    COIN_CLASS_INFO,
)

# @st.cache_data(ttl=60)  # Temporarily disabled for debugging
def load_moldable_history(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Load history and enrich with RSI/VolumeRel for Molder AI.
    Cached to optimize AI Scan loops.
    """
    print(f"DEBUG load_moldable_history: symbol={symbol}, timeframe={timeframe}")
    df_cached = load_history_data(symbol, timeframe)
    print(f"DEBUG load_moldable_history: df_cached is None? {df_cached is None}")
    if df_cached is None or df_cached.empty:
        print(f"DEBUG load_moldable_history: Returning None (cached data is None or empty)")
        return None
        
    df = df_cached.copy()
    
    # Enrich RSI if missing
    if 'rsi' not in df.columns:
        period = 14
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
        loss = -delta.where(delta < 0, 0).ewm(alpha=1/period, adjust=False).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

    # Enrich Volume Rel
    if 'volume_rel' not in df.columns:
        if 'volume' in df.columns: 
            df['volume_rel'] = df['volume'] / df['volume'].rolling(20).mean()
        else: 
            df['volume_rel'] = 0
            
    return df

def render_molder_boutique_view():
    """
    Render the 'Tekli' (Boutique) Molder page.
    Refactored to match Ony Studio's robust loading logic.
    """
    
    # --- PENDING STATE APPLIER (Copy from Ony) ---
    if '_pending_molder_symbol' in st.session_state:
        st.session_state['molder_sym'] = st.session_state.pop('_pending_molder_symbol')
    
    if '_pending_molder_prefill_id' in st.session_state:
        st.session_state['molder_prefill_event_id'] = st.session_state.pop('_pending_molder_prefill_id')

    # Handle return from Revize
    if 'molder_target_id' in st.session_state:
        target_id = st.session_state.pop('molder_target_id')
        if target_id:
            parts = target_id.split('_')
            if len(parts) >= 2:
                st.session_state['molder_sym'] = parts[0]
                st.session_state['molder_tf'] = parts[1]
            st.session_state['molder_prefill_event_id'] = target_id
            st.toast("📐 Revize'den döndünüz! Kalıp seçebilirsiniz.")

    # Initialize repository & Assembler
    store = RallyStore()
    assembler = RallyAssembler()

    # --- COMPACT HEADER (Row 1) ---
    # Col1: Coin, Col2: TF, Col3: Tier Filter
    c_sym, c_tf, c_tier = st.columns([1, 1, 3])
    
    with c_sym:
        raw_symbols = _get_available_symbols()
        symbols = ["TÜMÜ"] + raw_symbols
        # Default Logic: Check Session State first
        sess_sym = st.session_state.get('molder_sym')
        if sess_sym and sess_sym in symbols:
            default_sym_idx = symbols.index(sess_sym)
        else:
            default_sym_idx = 0
            
        sel_sym = st.selectbox("Coin", symbols, index=default_sym_idx, key="molder_sym", label_visibility="collapsed")
        
    with c_tf:
        timeframes = ["15m", "1h", "4h", "1d"]
        sess_tf = st.session_state.get('molder_tf')
        if sess_tf and sess_tf in timeframes:
            default_tf_idx = timeframes.index(sess_tf)
        else:
            default_tf_idx = 0
            
        sel_tf = st.selectbox("Timeframe", timeframes, index=default_tf_idx, key="molder_tf", label_visibility="collapsed")

    # Load Rallies via Assembler (ALL Rallies - Unlocked)
    target_sym = None if sel_sym == "TÜMÜ" else sel_sym
    
    # Fetch data - Show EVERYTHING (Pending + Approved)
    # Increase limit to 100,000 to show full history
    rallies = assembler.get_assembled_rallies(target_sym, sel_tf, status=None, limit=100000)
    
    # Tier Logic & Counts
    if rallies:
        counts = {t: 0 for t in TIERS}
        for r in rallies:
             if r.tier in counts: counts[r.tier] += 1
        tier_options = [f"{t} ({counts.get(t,0)})" for t in TIERS]
    else:
        tier_options = TIERS

    # AUTO-SWITCH TIER (Jumper Fix)
    if 'molder_prefill_event_id' in st.session_state and rallies:
        target_id = str(st.session_state['molder_prefill_event_id'])
        match = next((r for r in rallies if str(r.event_id) == target_id), None)
        if match:
             if match.tier in TIERS and st.session_state.get('molder_selected_tier') != match.tier:
                 st.session_state['molder_selected_tier'] = match.tier
                 st.rerun()

    with c_tier:
        if 'molder_selected_tier' not in st.session_state:
            st.session_state['molder_selected_tier'] = "DIAMOND"
        
        # Horizontal Radio
        selected_tier_label = st.radio(
            "Tier",
            tier_options,
            horizontal=True,
            key="molder_tier_radio",
            label_visibility="collapsed",
            index=TIERS.index(st.session_state['molder_selected_tier']) if st.session_state['molder_selected_tier'] in TIERS else 0
        )
        selected_tier = selected_tier_label.split(" (")[0]
        
        if st.session_state['molder_selected_tier'] != selected_tier:
            st.session_state['molder_selected_tier'] = selected_tier
            # Reset selection if tier changes
            if 'molder_event_select' in st.session_state:
                del st.session_state['molder_event_select']

    # --- LIST SELECTOR (Row 2) ---
    if not rallies:
        st.info(f"Bu coin/zaman için ralli yok.")
        return
        
    # Filter by Tier
    filtered_rallies = [r for r in rallies if r.tier == selected_tier]
    
    # Sort: Unlabeled first, Labeled last
    def is_labeled(r):
        has_arch = (r.archetype is not None and r.archetype != "None")
        return int(has_arch) # 0 = Unlabeled, 1 = Labeled

    filtered_rallies.sort(key=is_labeled)
    
    if not filtered_rallies:
        st.info(f"🔍 {selected_tier} katmanında mold edilecek ralli yok.")
        return

    # Check for prefill request
    prefill_id = st.session_state.pop('molder_prefill_event_id', None)
    default_idx = 0
    
    # Build Options
    event_options = []
    rally_map = {}
    
    for i, rally in enumerate(filtered_rallies):
        # Prefill lookup
        if prefill_id and str(rally.event_id) == str(prefill_id):
            default_idx = i
            
        label = rally.display_label
        event_options.append(label)
        rally_map[label] = rally
        
    if not event_options:
        st.warning("Liste boş.")
        return

    # Dynamic Key Logic for Auto-Advance
    select_counter = st.session_state.get('_molder_select_counter', 0)
    
    # Full width selectbox
    selected_label_str = st.selectbox(
        "Ralli Seçiniz", 
        event_options, 
        index=default_idx, 
        key=f"molder_list_select_{select_counter}", 
        label_visibility="collapsed"
    )
    
    if not selected_label_str:
        return

    current_rally = rally_map[selected_label_str]
    
    # ==========================
    # 1. AI PREDICTION (SYSTEM RECOMMENDATION)
    # ==========================
    
    # Only show AI if specific coin selected (not "TÜMÜ")
    if sel_sym == "TÜMÜ":
        st.info(" AI tavsiyesi için lütfen belirli bir coin seçin")
        df_hist_curr = None
    else:
        df_hist_curr = load_moldable_history(sel_sym, sel_tf)
    
    scores = []  # Initialize to prevent UnboundLocalError
    
    if df_hist_curr is not None:
        print("DEBUG: df_hist_curr loaded successfully")
        curr_ts = current_rally.event_time
        if curr_ts:
            print(f"DEBUG: curr_ts: {curr_ts}")
            # Ensure TZ naive for comparison
            if curr_ts.tzinfo: curr_ts = curr_ts.tz_localize(None)
            
            if df_hist_curr.index.dtype.kind == 'M': t_idx = df_hist_curr.index 
            else: t_idx = pd.DatetimeIndex(pd.to_datetime(df_hist_curr['open_time']))
            if t_idx.tz is not None: t_idx = t_idx.tz_localize(None)
            
            # Enrich Indicators
            if 'rsi' not in df_hist_curr.columns:
                period = 14
                delta = df_hist_curr['close'].diff()
                gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
                loss = -delta.where(delta < 0, 0).ewm(alpha=1/period, adjust=False).mean()
                rs = gain / loss
                df_hist_curr['rsi'] = 100 - (100 / (1 + rs))
            if 'volume_rel' not in df_hist_curr.columns:
                if 'volume' in df_hist_curr.columns: df_hist_curr['volume_rel'] = df_hist_curr['volume'] / df_hist_curr['volume'].rolling(20).mean()
                else: df_hist_curr['volume_rel'] = 0
            
            # Locate and Slice
            pos = t_idx.searchsorted(curr_ts)
            print(f"DEBUG: pos={pos}, len={len(df_hist_curr)}")
            if pos < len(df_hist_curr):
                eff_idx = min(pos + (current_rally.entry_offset or 0), len(df_hist_curr)-1)
                idx_start = max(0, eff_idx - 99)
                window_slice = df_hist_curr.iloc[idx_start:eff_idx+1]
                w_rsi = window_slice['rsi'].tolist()
                w_vol = window_slice['volume_rel'].tolist()
                
                print(f"DEBUG: w_rsi len={len(w_rsi)}, w_vol len={len(w_vol)}")
                
                # PREDICT SCORES
                scores = ArchetypeService.analyze_trend_scores(w_rsi, w_vol)
                print(f"DEBUG: scores={scores}")
                
                if scores:
                    best = scores[0]
                    p_arch = best['arch']
                    p_conf = best['conf']
                    p_reason = best['reason']
                    
                    c1, c2 = st.columns([1, 6])
                    with c1:
                        st.metric("Sistem Önerisi", p_arch, f"%{p_conf}")
                    with c2:
                        try:
                            p_arch_enum = Archetype(p_arch)
                            p_desc = ARCHETYPE_DESCRIPTIONS.get(p_arch_enum, "")
                        except:
                            p_desc = ""
                        st.success(f"**{p_arch}** ({p_desc})\n\n👉 **Gerekçe:** {p_reason}")
                        
                    if len(scores) > 1 and scores[1]['conf'] > 50:
                        sec = scores[1]
                        with st.expander(f"Alternatif: {sec['arch']} (%{sec['conf']})"):
                             try:
                                 s_arch_enum = Archetype(sec['arch'])
                                 s_desc = ARCHETYPE_DESCRIPTIONS.get(s_arch_enum, "")
                             except:
                                 s_desc = ""
                             st.write(f"**Tanım:** {s_desc}")
                             st.write(f"**Gerekçe:** {sec['reason']}")
                else:
                    print("DEBUG: No scores returned!")
                    st.warning("Hiçbir kalıp tespit edilemedi.")
            else:
                print("DEBUG: pos >= len(df_hist_curr)")
        else:
            print("DEBUG: curr_ts is None")
    else:
        print("DEBUG: df_hist_curr is None!")
        st.warning("Grafik verisi yüklenemedi.")



    # ==========================
    # 2. LABELING PANEL + CHART
    # ==========================
    
    # --- BUTTONS (Moved to Top) ---
    # Custom CSS to reduce font size for archetype buttons (~20% smaller)
    st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"] button p {
        font-size: 13px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    cols = st.columns(6)
    mold_list = [
        Archetype.GRIND, Archetype.GUILLOTINE, Archetype.SUPERNOVA, 
        Archetype.PHOENIX, Archetype.SURFER, Archetype.CRASH
    ]
    
    for i, mold in enumerate(mold_list):
        col = cols[i]
        label = ARCHETYPE_LABELS[mold]
        desc = ARCHETYPE_DESCRIPTIONS.get(mold, "")
        is_active = (current_rally.archetype == mold.value)
        
        with col:
            # Always show button (not conditional on is_active)
            if st.button(
                label, 
                key=f"btn_{mold.value}", 
                use_container_width=True, 
                type="primary" if is_active else "secondary",
                help=desc
            ):
                # ALWAYS save and advance, even if same archetype
                store = RallyStore()
                doc = store.get_rally(current_rally.event_id)
                
                if doc:
                    # Update both layers
                    molder_data = doc.get('molder_data', {}) or {}
                    molder_data['archetype'] = mold.value
                    molder_data['updated_at'] = pd.Timestamp.now()
                    
                    rev_data = doc.get('rev_data', {}) or {}
                    rev_data['archetype'] = mold.value
                    rev_data['updated_at'] = pd.Timestamp.now()
                    
                    # AUTO-APPROVE Logic (Unlock Workflow)
                    if rev_data.get('status') != 'APPROVED':
                        rev_data['status'] = 'APPROVED'
                        rev_data['label'] = 'MOLDER_AUTO'
                        st.toast(f"✅ Otomatik Onaylandı: {current_rally.display_label}")
                    
                    store.upsert_rally(current_rally.event_id, molder_data, layer='molder')
                    store.upsert_rally(current_rally.event_id, rev_data, layer='rev')
                    
                    # Find current rally index and move to next
                    available_rallies_labels = list_options
                    current_index = available_rallies_labels.index(selected_label_str)
                    
                    if current_index < len(available_rallies_labels) - 1:
                        # Set flag for next rally
                        st.session_state['_molder_next_rally'] = available_rallies_labels[current_index + 1]
                        st.toast(f"✅ {label} → Sonraki rally")
                    else:
                        # Last rally - try to move to next coin
                        symbols = ["TÜMÜ"] + _get_available_symbols()
                        if sel_sym in symbols and sel_sym != "TÜMÜ":
                            current_sym_idx = symbols.index(sel_sym)
                            if current_sym_idx < len(symbols) - 1:
                                # Move to next coin
                                next_coin = symbols[current_sym_idx + 1]
                                st.session_state['_molder_next_coin'] = next_coin
                                st.toast(f"✅ {label} kaydedildi → {next_coin}'e geçiliyor")
                            else:
                                # Last coin
                                st.toast(f"✅ {label} kaydedildi (Son coin)")
                        else:
                            # TÜMÜ or other case
                            st.toast(f"✅ {label} kaydedildi (Son rally)")
                    
                    st.rerun()

    # --- CHART ---
    event_time = current_rally.event_time
    try:
        render_sniper_studio_chart(
            symbol=current_rally.symbol,  # FIX: Use specific symbol, never wildcard
            timeframe=current_rally.timeframe, # FIX: Use specific TF
            event_time=event_time,
            bars_to_peak=current_rally.bars_to_peak,
            entry_offset=current_rally.entry_offset,
            exit_offset=current_rally.exit_offset,
            raw_gain_pct=current_rally.gain_pct
        )
    except Exception as e:
        st.error(f"Grafik hatası: {e}")

    st.markdown("---")

    # --- INFO ---
    st.markdown("### 🏷️ Kalıp Durumu")
    
    # Header Info + Revise Button
    hb1, hb2 = st.columns([3, 1])
    with hb1:
         st.info(f"ID: `{current_rally.event_id}` | Mevcut: **{current_rally.archetype or 'YOK'}**")
    with hb2:
         if st.button("🛠️ Revize Et", help="Bu ralliyi Revize Stüdyo'da düzenle", type="primary"):
             st.session_state['nav_selection'] = "🎯 Revize"
             st.session_state['ony_target_id'] = current_rally.event_id
             st.session_state['ony_prefill_symbol'] = current_rally.symbol
             st.session_state['ony_prefill_tf'] = current_rally.timeframe
             st.session_state['came_from_molder'] = True
             st.session_state['molder_return_target'] = current_rally.event_id
             st.rerun()
    
    # Selection Check (User vs System)
    st.divider()
    c_chk_1, c_chk_2 = st.columns([1, 6])
    with c_chk_1:
         user_arch = current_rally.archetype
         if user_arch and user_arch != "None":
             st.markdown("**Seçiminiz**")
             match_status = (scores and user_arch == scores[0]['arch'])
             color = "green" if match_status else "orange"
             st.markdown(f":{color}[**{user_arch}**]")
         else:
             st.caption("Seçim Yok")
    
    with c_chk_2:
        if user_arch and user_arch != "None":
             u_desc = ARCHETYPE_DESCRIPTIONS.get(user_arch, "")
             st.info(f"**{user_arch} Özellikleri:** {u_desc}")
             if scores and user_arch == scores[0]['arch']:
                 st.caption("✅ Sistem önerisiyle örtüşüyor.")
             elif scores:
                 st.caption(f"⚠️ Sistem önerisi: **{scores[0]['arch']}**. Farklı bir yorumunuz olabilir.")

    # ==========================
    # 3. MASTERY SCORE & INFO POOL
    # ==========================
    st.markdown("---")
    st.caption("📊 Sistem Karnesi (Son 40 İşlem Başarısı)")
    
    # FIX: Use specific symbol for stats query
    all_rallies = store.list_rallies(symbol=current_rally.symbol, timeframe=current_rally.timeframe)
    reviewed = []
    for r in all_rallies:
        rev = r.get('rev_data', {}) or {}
        if rev.get('archetype'):
            # Convert to simple object to match existing logic if needed, or query directly
            # For mastery score we just need archetype and offset
            reviewed.append(r)
            
    recent = reviewed[-40:] 
    
    if recent and df_hist_curr is not None:
         # Use df_hist_curr (already loaded)
         closes = df_hist_curr['close'].values
         if 'rsi' in df_hist_curr.columns:
             rsi_vals = df_hist_curr['rsi'].values
             vol_vals = df_hist_curr['volume_rel'].values
             times_ai = df_hist_curr.index if df_hist_curr.index.dtype.kind == 'M' else pd.to_datetime(df_hist_curr['open_time'])
             
             # Robust TZ Stripping
             if hasattr(times_ai, 'tz'): # DatetimeIndex
                 if times_ai.tz is not None: times_ai = times_ai.tz_localize(None)
             elif hasattr(times_ai, 'dt'): # Series
                 if hasattr(times_ai.dt, 'tz') and times_ai.dt.tz is not None:
                     times_ai = times_ai.dt.tz_localize(None)
             
             matches = 0
             valid_n = 0
             for r_ann in recent:
                 try:
                     rev_data = r_ann.get('rev_data', {}) or {}
                     eid = r_ann.get('id')
                     
                     parts = eid.split('_')
                     if len(parts) > 1 and parts[1] == sel_tf: # Check TF Match? implied by load_all
                         ts_val = int(parts[-1])
                         event_ts = pd.to_datetime(ts_val, unit='s')
                         
                         idx = times_ai.searchsorted(event_ts)
                         if idx < len(times_ai):
                              e_off = rev_data.get('entry_bar_offset', 0)
                              e_idx = min(idx + (e_off or 0), len(closes)-1)
                              p_arch, _, _ = ArchetypeService.classify_vector(rsi_vals[e_idx], vol_vals[e_idx])
                              
                              # Check match
                              user_arch = rev_data.get('archetype')
                              if p_arch == user_arch: matches += 1
                              valid_n += 1
                 except Exception as e: 
                     # print(f"Mastery calc error: {e}")
                     continue
             
             if valid_n > 0:
                 score = (matches / valid_n) * 100
                 st.progress(score/100, text=f"Başarı: %{score:.0f} (Son {valid_n} işlem)")
             else:
                 st.caption("Veri yetersiz.")
    else:
         st.caption("Veri yükleniyor...")

    # Show Coin Class Info under Mastery Score
    coin_cls = get_coin_class_with_override(sel_sym)
    cls_info = COIN_CLASS_INFO.get(coin_cls, COIN_CLASS_INFO["B"])
    st.info(f"{cls_info.get('icon','')} **Sınıf {coin_cls} - {cls_info.get('name','')}** | {cls_info.get('description','')}")

    # Info Pool (Trade Künyesi)
    st.markdown("---")
    st.markdown("### 📊 Trade Künyesi")
    
    if df_hist_curr is not None:
         # Reuse df_hist_curr
         if not pd.isna(event_time):
             et_naive = event_time
             if et_naive.tzinfo: et_naive = et_naive.tz_localize(None)
             
             times = df_hist_curr.index if df_hist_curr.index.dtype.kind == 'M' else pd.to_datetime(df_hist_curr['open_time'])
             
             # Robust TZ Stripping
             if hasattr(times, 'tz'): # DatetimeIndex
                 if times.tz is not None: times = times.tz_localize(None)
             elif hasattr(times, 'dt'): # Series
                 if hasattr(times.dt, 'tz') and times.dt.tz is not None:
                     times = times.dt.tz_localize(None)
             
             try:
                 valid_diffs = (times - et_naive).abs()
                 event_idx = int(valid_diffs.values.argmin())
                 
                 entry_off = current_rally.entry_offset or 0
                 exit_off = current_rally.exit_offset
                 if exit_off is None: exit_off = current_rally.bars_to_peak
                 
                 entry_idx = min(max(0, event_idx + entry_off), len(df_hist_curr)-1)
                 
                 if entry_idx < len(df_hist_curr):
                      p_entry = df_hist_curr.iloc[entry_idx]['close']
                      t_entry = times[entry_idx]
                      
                      exit_idx = min(max(0, event_idx + exit_off), len(df_hist_curr)-1)
                      p_exit = df_hist_curr.iloc[exit_idx]['close']
                      t_exit = times[exit_idx]
                            
                      net_gain = (p_exit - p_entry) / p_entry if p_entry > 0 else 0
                      duration_bars = exit_off - entry_off
                      duration_time = t_exit - t_entry
                      
                      k1, k2, k3, k4 = st.columns(4)
                      k1.metric("Giriş Fiyatı", f"{p_entry:.4f}")
                      k2.metric("Çıkış Fiyatı", f"{p_exit:.4f}")
                      
                      gain_label = "Net Kazanç"
                      if current_rally.exit_offset is None: gain_label += " (Varsayılan)"
                      k3.metric(gain_label, f"%{net_gain*100:.2f}", delta=f"{net_gain*100:.2f}%")
                      k4.metric("Süre", f"{duration_bars} Bar", help=f"{duration_time}")
                      st.caption(f"📅 **Aralık:** {t_entry} ➡️ {t_exit}")
             except Exception as e_pool:
                 st.warning(f"Künye hesaplanamadı: {e_pool}")

    # Guide (Visual)
    st.markdown("---")
    with st.expander("📚 Kalıp Rehberi (Görsel Anlatım)", expanded=False):
        import os
        
        # Hardcoded paths based on find result
        # library/archetype_images/...
        base_img_path = "library/archetype_images"
        
        # Map arch to filename partial
        img_map = {
            "GRIND": "archetype_grind",
            "GUILLOTINE": "archetype_guillotine",
            "SUPERNOVA": "archetype_supernova",
            "PHOENIX": "archetype_phoenix",
            "SURFER": "archetype_surfer",
            "CRASH": "archetype_crash"
        }
        
        cols = st.columns(3)
        
        # Helper to find ALL exact files
        def get_img_paths(partial_name):
            matches = []
            try:
                if not os.path.exists(base_img_path): return []
                for f in sorted(os.listdir(base_img_path)): # Sorted for consistent order
                    if partial_name in f:
                        matches.append(os.path.join(base_img_path, f))
            except: pass
            return matches

        # Render in Grid
        for i, (arch_key, fname_part) in enumerate(img_map.items()):
            col = cols[i % 3]
            with col:
                img_paths = get_img_paths(fname_part)
                
                st.markdown(f"**{arch_key}**")
                
                if not img_paths:
                    st.caption("Görsel yok")
                elif len(img_paths) == 1:
                    st.image(img_paths[0], use_container_width=True)
                else:
                    # Multiple images - use tabs
                    tabs = st.tabs([f"Görsel {j+1}" for j in range(len(img_paths))])
                    for j, tab in enumerate(tabs):
                        with tab:
                            st.image(img_paths[j], use_container_width=True)
                
                desc = ARCHETYPE_DESCRIPTIONS.get(Archetype(arch_key), "")
                st.caption(desc)

    # --- COIN CLASS LEGEND ---
    st.markdown("---")
    
    with st.expander("🏛️ Sınıf Özellikleri (Coin Character Classes)", expanded=False):
        cls_cols = st.columns(3)
        # Iterate classes (A, B, C, D, N)
        for i, (cls_code, info) in enumerate(COIN_CLASS_INFO.items()):
            
            # Skip unknown if present
            if cls_code not in ["A", "B", "C", "D", "N"]: continue
            
            col = cls_cols[i % 3]
            with col:
                # Header with Icon and Code
                st.markdown(f"#### {info.get('icon', '❓')} {info.get('name', 'Bilinmeyen')} ({cls_code})")
                
                # Badge Color
                color = info.get('color', '#808080')
                st.markdown(f"<span style='color:{color}'>⬤</span> **{cls_code} Sınıfı**", unsafe_allow_html=True)
                
                # Description
                st.info(info.get('description', ''))
                
                # Strategy
                st.caption(f"💡 **Strateji:** {info.get('strategy', '-')}")

# ==========================
# GALLERY MODE & ORCHESTRATOR
# ==========================

def render_molder_gallery_view():
    """
    Render the 'Galeri' (Factory) Molder page for rapid labeling.
    """
    # Initialize Assembler
    assembler = RallyAssembler()
    
    # --- FILTERS ---
    # Set DEFAULTS
    if 'gal_tf' not in st.session_state: st.session_state['gal_tf'] = "15m"
    if 'gal_tier' not in st.session_state: st.session_state['gal_tier'] = "DIAMOND"
    
    # ROW 1: Basic Filters (Coin, TF, Tier with counts)
    c_fil_1, c_fil_2, c_fil_3 = st.columns([1, 1, 3])
    with c_fil_1:
         # Symbol Filter
         symbols = ["TÜMÜ"] + _get_available_symbols()
         sel_sym = st.selectbox("Coin", symbols, key="gal_sym", label_visibility="collapsed")
         target_sym = None if sel_sym == "TÜMÜ" else sel_sym
         
    with c_fil_2:
         # Timeframe Filter
         tfs = ["TÜMÜ", "15m", "1h", "4h", "1d"]
         sel_tf_raw = st.selectbox("Zaman", tfs, key="gal_tf", label_visibility="collapsed")
         target_tf = None if sel_tf_raw == "TÜMÜ" else sel_tf_raw
    
    # Temporary tier selection for data loading - but load ALL to count
    if 'gal_tier_selected' not in st.session_state:
        st.session_state['gal_tier_selected'] = "DIAMOND"
    
    # --- DATA LOADING (to determine available archetypes) ---
    # Load ALL tiers first to get accurate counts (Limit 100k)
    assembled_rows = assembler.get_assembled_rallies(target_sym, target_tf, tier=None, limit=100000)
    
    # Filter 1: APPROVED Filter REMOVED (Unlock Workflow)
    # approved_rallies = [r for r in assembled_rows if r.status == SniperStatus.APPROVED]
    approved_rallies = assembled_rows # Use ALL rallies
    total_approved_cnt = len(approved_rallies)
    
    # Count by tier for display
    from tezaver.core.tier_utils import TIERS
    tier_counts = {"TÜMÜ": len(approved_rallies)}
    for tier in TIERS:
        tier_counts[tier] = len([r for r in approved_rallies if r.tier == tier])
    
    # NOW show tier selector with counts in c_fil_3
    with c_fil_3:
        tier_icons = {
            "DIAMOND": "💎",
            "GOLD": "🏅", 
            "SILVER": "🥈",
            "BRONZE": "🥉"
        }
        
        tier_options = []
        tier_list = ["TÜMÜ"] + list(TIERS)
        for t in tier_list:
            count = tier_counts.get(t, 0)
            if t == "TÜMÜ":
                tier_options.append(f"📦 {count}")
            else:
                icon = tier_icons.get(t, "📦")
                tier_options.append(f"{icon} {count}")
        
        def get_tier_from_label(lbl):
            icon = lbl.split(" ")[0]
            if icon == "📦": return "TÜMÜ"
            for tier_name, tier_icon in tier_icons.items():
                if tier_icon == icon:
                    return tier_name
            return "TÜMÜ"
        
        current_tier_idx = 0
        if st.session_state['gal_tier_selected'] in tier_list:
            current_tier_idx = tier_list.index(st.session_state['gal_tier_selected'])
        
        selected_tier_label = st.radio(
            "Tier",
            tier_options,
            horizontal=True,
            key="gal_tier_radio",
            label_visibility="collapsed",
            index=current_tier_idx
        )
        
        selected_tier = get_tier_from_label(selected_tier_label)
        st.session_state['gal_tier_selected'] = selected_tier
        
        # Re-filter if tier changed
        if selected_tier != "TÜMÜ":
            approved_rallies = [r for r in approved_rallies if r.tier == selected_tier]
    
    # Filter 2: Labeling Status
    if 'gal_label_status' not in st.session_state:
        st.session_state['gal_label_status'] = "KALANLAR"
    
    sel_label_status = st.session_state['gal_label_status']
    
    if sel_label_status == "KALANLAR":
        # Unlabeled only
        all_moldable = [r for r in approved_rallies if (not r.archetype or r.archetype == "None")]
    elif sel_label_status == "OLANLAR":
        # Labeled only
        all_moldable = [r for r in approved_rallies if (r.archetype and r.archetype != "None")]
    else:  # TÜMÜ
        # All approved rallies
        all_moldable = approved_rallies
    
    unlabeled_cnt = len([r for r in approved_rallies if (not r.archetype or r.archetype == "None")])
    labeled_cnt = len([r for r in approved_rallies if (r.archetype and r.archetype != "None")])
    
    # Determine available archetypes based on labeling status
    if sel_label_status == "OLANLAR":
        # Only show archetypes that exist in labeled rallies
        existing_archs = set([r.archetype for r in all_moldable if r.archetype and r.archetype != "None"])
        arch_filter_opts = ["TÜMÜ"] + sorted(list(existing_archs))
    else:
        # Show all archetypes
        arch_filter_opts = ["TÜMÜ"] + [a.value for a in Archetype]
    
    # ROW 2: Advanced Filters (Durum, Kalıp, AI)
    c_fil_4, c_fil_5, c_fil_6 = st.columns([1.5, 1.5, 1.5])
    
    with c_fil_4:
        # Labeling Status Filter
        label_status_opts = ["KALANLAR", "OLANLAR", "TÜMÜ"]
        sel_label_status = st.selectbox("Durum", label_status_opts, key="gal_label_status")
    
    with c_fil_5:
        # Archetype filter
        sel_arch_filter = st.selectbox("Kalıp Filtre", arch_filter_opts, key="gal_arch_filter")
    
    with c_fil_6:
        # AI Filter (Smart Scan)
        ai_opts = ["TÜMÜ"] + [a.value for a in Archetype]
        
        def on_ai_change():
            val = st.session_state.get("gal_ai_filter_sel")
            if val and val != "TÜMÜ":
                st.session_state["gal_target_arch_top"] = val
                
        sel_ai_filter = st.selectbox("🤖 AI Pattern", ai_opts, key="gal_ai_filter_sel", on_change=on_ai_change)
    
    # Filter 3: Archetype Filter (from row 2)
    if sel_arch_filter != "TÜMÜ":
        all_moldable = [r for r in all_moldable if r.archetype == sel_arch_filter]
    
    
    # Filter 4: AI Prediction - handled in action row below
    # Just pass through for now, AI filter applied after UI renders
    
    # Sort by Newest
    all_moldable.sort(key=lambda x: x.event_time, reverse=True)
    
    total_count = len(all_moldable)

    if total_count == 0:
        st.info("Kriterlere uygun bekleyen ralli yok. 🎉")
        return

    # Pagination
    PAGE_SIZE = 20
    if 'gal_page' not in st.session_state: st.session_state['gal_page'] = 0
    
    start_idx = st.session_state['gal_page'] * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    batch_rallies = all_moldable[start_idx:end_idx]
    
    # --- ACTION ROW (2 columns: Selector + Save) ---
    action_c1, action_c2 = st.columns([1, 3])
    
    with action_c1:
        # Target Archetype Selector
        target_arch = st.selectbox("Atanacak Etiket", [a.value for a in Archetype], key="gal_target_arch_top", label_visibility="collapsed")
    
    # Apply AI filter (moved from old action row logic)
    if sel_ai_filter != "TÜMÜ":
        # Reapply AI logic here
        candidates = all_moldable[:50]
        matches = []
        
        for rally in candidates:
            try:
                df = load_moldable_history(rally.symbol, rally.timeframe)
                if df is not None and not df.empty:
                    times = df.index if df.index.dtype.kind == 'M' else pd.to_datetime(df['open_time'])
                    if hasattr(times, 'dt'): times = times.dt.tz_localize(None)
                    et = rally.event_time
                    if et.tzinfo: et = et.tz_localize(None)
                    pos = times.searchsorted(et)
                    eff_idx = min(pos + (rally.entry_offset or 0), len(df)-1)
                    ai_start = max(0, eff_idx - 59)
                    ai_slice = df.iloc[ai_start:eff_idx+1]
                    
                    if 'rsi' in ai_slice.columns:
                        w_rsi = ai_slice['rsi'].tolist()
                        w_vol = ai_slice['volume_rel'].tolist()
                        scores = ArchetypeService.analyze_trend_scores(w_rsi, w_vol)
                        if scores and scores[0]['arch'] == sel_ai_filter:
                            matches.append(rally)
            except:
                pass
        
        all_moldable = matches
    
    with action_c2:
         # SAVE BUTTON (Wide)
         sel_count = len(st.session_state.get('gal_selected', {}))
         label_btn = f"💾 SEÇİLEN {sel_count} RALLİYİ '{target_arch}' OLARAK KAYDET"
         
         if st.button(label_btn, type="primary", disabled=(sel_count==0), use_container_width=True):
             # Process Selections
             store = RallyStore()
             updated_count = 0
             feedback_file = Path("data/brain/feedback_loop.csv")
             if not feedback_file.parent.exists(): feedback_file.parent.mkdir(parents=True, exist_ok=True)
             
             for eid, r_obj in st.session_state['gal_selected'].items():
                 doc = store.get_rally(eid)
                 if not doc: continue
                 
                 rev_data = doc.get('rev_data', {}) or {}
                 molder_data = doc.get('molder_data', {}) or {}
                 coin_cls = get_coin_class_with_override(r_obj.symbol)
                 
                 # AI Feedback Log
                 try:
                      df = load_history_data(r_obj.symbol, r_obj.timeframe)
                      if df is not None:
                           times = df.index if df.index.dtype.kind == 'M' else pd.to_datetime(df['open_time'])
                           if hasattr(times, 'dt'): times = times.dt.tz_localize(None)
                           et = r_obj.event_time
                           if et.tzinfo: et = et.tz_localize(None)
                           pos = times.searchsorted(et)
                           eff_idx = min(pos + (r_obj.entry_offset or 0), len(df)-1)
                           ai_start = max(0, eff_idx - 59)
                           ai_slice = df.iloc[ai_start:eff_idx+1]
                           if 'rsi' in ai_slice.columns:
                                w_rsi = ai_slice['rsi'].tolist()
                                w_vol = ai_slice['volume_rel'].tolist() if 'volume_rel' in ai_slice.columns else []
                                scores = ArchetypeService.analyze_trend_scores(w_rsi, w_vol)
                                sys_pred = scores[0]['arch'] if scores else "NONE"
                                
                                import csv
                                file_exists = feedback_file.exists()
                                with open(feedback_file, 'a', newline='') as f:
                                     writer = csv.writer(f)
                                     if not file_exists: writer.writerow(['timestamp', 'symbol', 'tf', 'rsi_vector', 'vol_vector', 'sys_pred', 'user_label'])
                                     writer.writerow([pd.Timestamp.now(), r_obj.symbol, r_obj.timeframe, str(w_rsi), str(w_vol), sys_pred, target_arch])
                 except: pass # Fail silently on logging
                 
                 rev_data.update({'archetype': target_arch, 'coin_class': coin_cls, 'updated_at': pd.Timestamp.now()})
                 
                 # AUTO-APPROVE (Unlock)
                 if rev_data.get('status') != 'APPROVED':
                     rev_data['status'] = 'APPROVED'
                     rev_data['label'] = 'MOLDER_AUTO'
                     
                 molder_data.update({'archetype': target_arch, 'coin_class': coin_cls, 'labeled_at': pd.Timestamp.now(), 'confidence': 1.0})
                 
                 store.upsert_rally(eid, rev_data, layer='rev')
                 store.upsert_rally(eid, molder_data, layer='molder')
                 updated_count += 1
             
             st.toast(f"✅ {updated_count} Ralli Kaydedildi!", icon="💾")
             st.session_state['gal_selected'] = {}
             st.rerun()

    # ROW 2: NAVIGATION [Select All + Stats (2.5)] [Spacer (0.1)] [Pagination (1.4)]
    r2_c1, r2_c2, r2_c3 = st.columns([2.5, 0.1, 1.4])
    
    with r2_c1:
        # Col: [Button 0.8] [Stats 2]
        c_btn, c_stats = st.columns([0.8, 2])
        with c_btn:
             if st.button("✅ Hepsini Seç", use_container_width=True, help="Ekranda görünen tüm grafikleri işaretler"):
                for r in batch_rallies:
                    st.session_state[f"chk_{r.event_id}"] = True
                    st.session_state['gal_selected'][r.event_id] = r
                st.rerun()
        
        with c_stats:
             # STATS DISPLAY
             st.markdown(
                 f"<div style='margin-top: 5px; font-size: 0.9em;'>"
                 f"🔹 <b>Toplam:</b> {total_approved_cnt} | "
                 f"🔸 <b>Kalıplanacak:</b> {unlabeled_cnt} | "
                 f"✨ <b>Görüntülenen:</b> {total_count}"
                 f"</div>", 
                 unsafe_allow_html=True
             )
            
    with r2_c3:
        # Pagination [Prev] [Text] [Next]
        bp, b_txt, bn = st.columns([1, 2, 1])
        with bp:
            if st.button("⬅️", disabled=(start_idx==0), key="types_prev"): 
                st.session_state['gal_page'] -= 1
                st.rerun()
        with b_txt:
            st.markdown(f"<div style='text-align: center; margin-top: 5px;'><b>{start_idx+1}-{min(end_idx, total_count)}</b> / {total_count}</div>", unsafe_allow_html=True)
        with bn:
            if st.button("➡️", disabled=(end_idx>=total_count), key="types_next"): 
                st.session_state['gal_page'] += 1
                st.rerun()
                
    # --- GRID LAYOUT ---
    # st.markdown("---") # Removed for tighter look

    grid = st.columns(4)
    processed_count = 0
    
    # Selection State Management
    # We use a dictionary in session state to track selected IDs for approval
    if 'gal_selected' not in st.session_state: st.session_state['gal_selected'] = {}

    for i, rally in enumerate(batch_rallies):
        col = grid[i % 4]
        with col:
            # Card Container
            with st.container(border=True):
                # Tier Icon Helper
                t_icon = "🎗️"
                t_raw = rally.tier.upper() if rally.tier else "WEAK"
                if "DIAMOND" in t_raw: t_icon = "💎"
                elif "GOLD" in t_raw: t_icon = "🥇"
                elif "SILVER" in t_raw: t_icon = "🥈"
                elif "BRONZE" in t_raw: t_icon = "🥉"
                
                # AI Analysis (On-the-fly)
                ai_label = ""
                ai_conf = 0.0
                subset = None
                
                try:
                    df = load_moldable_history(rally.symbol, rally.timeframe)
                    if df is not None and not df.empty:
                        # Slice logic (Indicators are already enriched)
                        times = df.index if df.index.dtype.kind == 'M' else pd.to_datetime(df['open_time'])
                        if hasattr(times, 'dt'): times = times.dt.tz_localize(None)
                        elif hasattr(times, 'tz_localize'): times = times.tz_localize(None)
                        
                        et = rally.event_time
                        if et.tzinfo: et = et.tz_localize(None)
                        
                        pos = times.searchsorted(et)
                        if pos < len(df):
                            # Window for Chart
                            s_idx = max(0, pos - 40)
                            e_idx = min(len(df)-1, pos + 20)
                            subset = df.iloc[s_idx:e_idx]
                            
                            # Window for AI (60 bars lookback)
                            eff_idx = min(pos + (rally.entry_offset or 0), len(df)-1)
                            ai_start = max(0, eff_idx - 59)
                            ai_slice = df.iloc[ai_start:eff_idx+1]
                            
                            # Calc AI Inputs
                            if 'rsi' not in ai_slice.columns or 'volume_rel' not in ai_slice.columns:
                                 # Should not happen with load_moldable_history
                                 pass 
                            else:
                                 w_rsi = ai_slice['rsi'].tolist()
                                 w_vol = ai_slice['volume_rel'].tolist()
                                 scores = ArchetypeService.analyze_trend_scores(w_rsi, w_vol)
                                 if scores:
                                     best = scores[0]
                                     ai_label = f"🤖 {best['arch']} %{best['conf']}"
                                     ai_conf = best['conf']
                except:
                    pass

                # Display Header with Tier + AI + Archetype
                arch_icon = ""
                if rally.archetype and rally.archetype != "None":
                    try:
                        arch_label = ARCHETYPE_LABELS.get(Archetype(rally.archetype), rally.archetype)
                        arch_icon = " " + arch_label.split(" ")[-1]  # Get emoji part
                    except:
                        pass
                
                st.markdown(f"**{rally.symbol}** `{rally.timeframe}` {t_icon}{arch_icon}")
                if ai_label:
                    st.caption(f"{rally.event_time.strftime('%d %b %H:%M')} | {ai_label}")
                else:
                    st.caption(f"{rally.event_time.strftime('%d %b %H:%M')}")
                
                # Mini Chart (Plotly)
                if subset is not None and not subset.empty:
                    try:
                        import plotly.graph_objects as go
                        
                        # Primary: Candle
                        fig = go.Figure()
                        
                        fig.add_trace(go.Candlestick(
                            x=subset.index,
                            open=subset['open'], high=subset['high'],
                            low=subset['low'], close=subset['close'],
                            name="Price",
                            increasing_line_color='green', decreasing_line_color='red'
                        ))
                        
                        # Add Moving Averages
                        if len(subset) >= 20:
                            ma20 = subset['close'].rolling(window=20).mean()
                            fig.add_trace(go.Scatter(
                                x=subset.index, y=ma20,
                                mode='lines',
                                line=dict(color='orange', width=1.5),
                                name='MA20'
                            ))
                        
                        if len(subset) >= 50:
                            ma50 = subset['close'].rolling(window=50).mean()
                            fig.add_trace(go.Scatter(
                                x=subset.index, y=ma50,
                                mode='lines',
                                line=dict(color='blue', width=1.5),
                                name='MA50'
                            ))
                        
                        # markers: Start (Green) & End (Red)
                        # Start = event_time + entry_offset
                        # End = event_time + exit_offset (or bars_to_peak)
                        
                        # We need to find the EXACT time index in subset
                        t_subset = subset.index
                        if hasattr(t_subset, 'dt'): t_subset = t_subset.dt.tz_localize(None)
                        
                        # Calculate exact timestamps
                        start_ts = et # approximate event time
                        # refine with offset if needed, but event_time is usually the 'trigger'. 
                        # actually event_time is the start of the rally roughly.
                        
                        # Let's map integer indices relative to 'pos' (event_time index)
                        # subset starts at s_idx (pos - 40)
                        # event is at pos. So relative index is pos - s_idx = 40.
                        
                        rel_event_idx = pos - s_idx
                        
                        # Start Marker
                        if 0 <= rel_event_idx < len(subset):
                            fig.add_trace(go.Scatter(
                                x=[subset.index[rel_event_idx]],
                                y=[subset['low'].iloc[rel_event_idx] * 0.99], # slightly below
                                mode='markers',
                                marker=dict(symbol='triangle-up', size=10, color='blue'),
                                name='Start'
                            ))
                        
                        # Peak Marker
                        peak_bars = int(rally.bars_to_peak) if rally.bars_to_peak else 0
                        peak_idx = rel_event_idx + peak_bars
                        if 0 <= peak_idx < len(subset):
                             fig.add_trace(go.Scatter(
                                x=[subset.index[peak_idx]],
                                y=[subset['high'].iloc[peak_idx] * 1.01], # slightly above
                                mode='markers',
                                marker=dict(symbol='triangle-down', size=10, color='purple'),
                                name='End'
                            ))
                        
                        # Volume (Secondary Axis)
                        if 'volume' in subset.columns:
                            fig.add_trace(go.Bar(
                                x=subset.index, y=subset['volume'],
                                marker_color='rgba(100, 100, 250, 0.3)',
                                yaxis='y2',
                                name="Vol"
                            ))

                        # Layout
                        fig.update_layout(
                            margin=dict(l=0, r=0, t=0, b=0),
                            height=150,
                            xaxis=dict(visible=False, rangeslider=dict(visible=False)),
                            yaxis=dict(visible=False),
                            yaxis2=dict(visible=False, overlaying='y', side='right', range=[0, subset['volume'].max() * 4]), # Scale vol down
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            showlegend=False
                        )
                        
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                    except Exception as e:
                         st.error(f"Chart: {e}")
                else:
                    st.caption("Veri yok")

                # Action Checkbox
                # Key is critical
                chk_key = f"chk_{rally.event_id}"
                
                # Manual "Select"
                is_checked = st.checkbox("✅ Onayla", key=chk_key)
                if is_checked:
                    st.session_state['gal_selected'][rally.event_id] = rally
                elif rally.event_id in st.session_state['gal_selected']:
                     del st.session_state['gal_selected'][rally.event_id]

    # Bottom Action Bar Removed (Moved to Top)
    pass





def render_molder_page():
    """
    Main Orchestrator for Molder Tab.
    Handles view switching between Boutique (Single) and Gallery (Factory) modes.
    """
    # Tabs for Navigation
    t_single, t_gallery = st.tabs(["🔍 Tekli (Butik)", "🏭 Galeri (Seri)"])
    
    with t_single:
        render_molder_boutique_view()
        
    with t_gallery:
        render_molder_gallery_view()

