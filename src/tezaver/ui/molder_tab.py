"""
Molder Tab - Kalıpçı (Archetype Labeling)
=========================================

"Ralliyi Adlandırma ve Sınıflandırma Atölyesi"

Flow:
1. Load APPROVED rallies from Ony Repo.
2. Filter by Tier (Diamond, Gold, etc.).
3. Select from List (synced with Chart).
4. Label with Archetype (Icons).
"""

import streamlit as st
import pandas as pd
from typing import List, Optional, Dict

from tezaver.core.annotations import SniperAnnotationRepository, SniperAnnotation, SniperStatus
from tezaver.core.molds import Archetype, ARCHETYPE_LABELS, ARCHETYPE_DESCRIPTIONS
from tezaver.ui.chart_area import render_sniper_studio_chart
# Reuse helpers from Ony Tab to maintain consistency
from tezaver.ui.ony_tab import (
    _get_available_symbols, 
    _load_events_for_symbol_tf, 
    normalize_tier, 
    compute_tier_from_gain,
    TIERS
)

def render_molder_page():
    """Render the Kalıpçı page."""
    # st.title("📐 Kalıpçı (Şablon Atölyesi)") # Title removed per style guide preference in Ony
    st.caption("Onaylanmış (Approved) rallilere Arketip (Kalıp) etiketi basar.")
    
    # Initialize repository
    repo = SniperAnnotationRepository()

    # --- TOP FILTERS (Coin, TF, Tier) ---
    c_sym, c_tf, c_tier = st.columns([1, 1, 3])
    
    with c_sym:
        symbols = _get_available_symbols()
        # Session state persistence
        idx = 0
        if "molder_sym" in st.session_state and st.session_state["molder_sym"] in symbols:
            idx = symbols.index(st.session_state["molder_sym"])
        sel_sym = st.selectbox("Coin", symbols, index=idx, key="molder_sym", label_visibility="collapsed")
        
    with c_tf:
        timeframes = ["15m", "1h", "4h"]
        idx = 0
        if "molder_tf" in st.session_state and st.session_state["molder_tf"] in timeframes:
            idx = timeframes.index(st.session_state["molder_tf"])
        sel_tf = st.selectbox("Timeframe", timeframes, index=idx, key="molder_tf", label_visibility="collapsed")
    
    # --- DATA LOADING ---
    # 1. Load Repo (Source of Truth for "Approved")
    all_anns = repo.load_all(sel_sym, sel_tf)
    approved_anns = [a for a in all_anns if a.status == SniperStatus.APPROVED]
    
    # 2. Load Parquet (Source of Metadata: Gain, Tier, Bars)
    df_events = _load_events_for_symbol_tf(sel_sym, sel_tf)
    
    # Create Metadata Map from Parquet
    meta_map = {}
    if df_events is not None and not df_events.empty:
        # Index by event_id for fast lookup
        # Note: df_events might have raw IDs. Annotations might have _RVZ_ IDs.
        # We'll handle matching below.
        df_events['str_id'] = df_events['event_id'].astype(str)
        
        # Ensure Tier is present
        if 'rally_grade' in df_events.columns:
            df_events['tier'] = df_events['rally_grade'].apply(normalize_tier)
        else:
            df_events['tier'] = df_events['future_max_gain_pct'].apply(compute_tier_from_gain)
            
        meta_map = df_events.set_index('str_id')[['tier', 'future_max_gain_pct', 'bars_to_peak', 'event_time']].to_dict('index')

    # 3. Merge Repo + Metadata
    # We want to group Approved Anns by Tier
    tier_groups = {t: [] for t in TIERS}
    tier_groups["OTHER"] = [] # Fallback
    
    display_items = []
    
    for ann in approved_anns:
        eid = str(ann.event_id)
        # Lookup metadata
        # Logic: Try direct ID match. If fail, try removing '_RVZ_' infix.
        meta = meta_map.get(eid)
        if not meta and "_RVZ_" in eid:
            raw_id = eid.replace("_RVZ_", "_")
            meta = meta_map.get(raw_id)
            
        if meta:
            tier = meta.get('tier')
            gain = meta.get('future_max_gain_pct', 0) * 100
            bars = int(meta.get('bars_to_peak', 0))
            ts = meta.get('event_time')
        else:
            # Metadata missing? Fallback or calculate from annotation if possible?
            # We assume metadata usually exists. If not, tier is unknown.
            tier = "OTHER"
            gain = 0
            bars = 0
            ts = pd.NaT

        # Store for list logic
        item = {
            "ann": ann,
            "tier": tier if tier in TIERS else "OTHER",
            "gain": gain,
            "bars": bars,
            "ts": ts
        }
        
        target_tier = item["tier"]
        if target_tier not in tier_groups: target_tier = "OTHER"
        tier_groups[target_tier].append(item)

    # --- TIER SELECTOR ---
    # Calc counts
    tier_options = []
    for t in TIERS:
        count = len(tier_groups[t])
        tier_options.append(f"{t} ({count})")
    
    with c_tier:
        if 'molder_selected_tier' not in st.session_state:
            st.session_state['molder_selected_tier'] = "DIAMOND"
            
        # Helper to strip count
        def get_clean_tier(opt): return opt.split(" (")[0]
        
        # Find index
        current_sel_idx = 0
        if st.session_state['molder_selected_tier'] in TIERS:
            current_sel_idx = TIERS.index(st.session_state['molder_selected_tier'])
            
        selected_tier_label = st.radio(
            "Tier", 
            tier_options, 
            horizontal=True, 
            key="molder_tier_radio",
            label_visibility="collapsed",
            index=current_sel_idx
        )
        selected_tier = get_clean_tier(selected_tier_label)
        st.session_state['molder_selected_tier'] = selected_tier

    # --- LIST SELECTOR ---
    current_list_items = tier_groups.get(selected_tier, [])
    # Sort by Time Descending
    current_list_items.sort(key=lambda x: x["ann"].event_id, reverse=True) 
    
    if not current_list_items:
        st.info(f"🔍 {selected_tier} katmanında etiketlenecek ralli yok. (Önce Revize Stüdyo'dan onaylanmalı)")
        return

    # Helper for Icons
    def get_arch_icon(arch_code):
        if not arch_code: return "❓"
        try:
            lbl = ARCHETYPE_LABELS.get(Archetype(arch_code), "")
            return lbl.split(" ")[-1] if " " in lbl else "🏷️"
        except:
            return "🏷️"

    # Revised Check
    def is_revised(ann):
        return "_RVZ_" in str(ann.event_id) or str(ann.label) == "REV"

    # --- PRELOAD HISTORY FOR GAIN CALC ---
    from tezaver.ui.chart_area import load_history_data
    df_hist_cache = None
    
    list_options = []
    list_map = {}
    
    for item in current_list_items:
        ann = item["ann"]
        arch = ann.archetype
        
        # Icons
        arch_icon = get_arch_icon(arch)
        revised = is_revised(ann)
        rev_icon = "🛠️" if revised else ""
        
        # Dynamic Vars
        display_gain = item['gain']
        eff_entry = ann.entry_bar_offset or 0
        eff_exit = ann.exit_bar_offset if ann.exit_bar_offset is not None else item['bars']
        
        # Duration
        display_bars = max(1, eff_exit - eff_entry)
        
        # Attempt Dynamic Gain Calculation (Greedy but Cached)
        # Only try if revised (to match user expectation)
        if revised:
            try:
                # We fetch history individually. Streamlit cache makes this fast-ish.
                # Use a lightweight fetch if possible? load_history_data is full load.
                dh = load_history_data(ann.symbol, ann.timeframe)
                if dh is not None:
                     # Calculate
                     # Need event index
                     # Using naive approach for speed
                     target_ts = None
                     if pd.notna(item.get("ts")): target_ts = item["ts"]
                     if target_ts:
                         pass
            except:
                pass
        
        # Let's try the direct calculation approach just for the currently selected symbol?
        # If the outer scope `sel_sym` matches `ann.symbol`.
        # (We need to check if `sel_sym` is available in scope. It is usually top-level)
        
        # Actually, let's look at `molder_tab.py` top scope again...
        # It has `sel_sym` from sidebar.
        is_active_symbol = (ann.symbol == sel_sym) and (ann.timeframe == sel_tf)
        
        if is_active_symbol and revised:
             # Load history (should be cached hot)
             dh = load_history_data(sel_sym, sel_tf)
             if dh is not None and not dh.empty:
                 try:
                     # Find index 
                     if dh.index.dtype.kind == 'M': times = dh.index
                     else: times = pd.to_datetime(dh['open_time'])
                     
                     if times.dt.tz is not None: times = times.dt.tz_localize(None)
                     
                     ets = item["ts"]
                     if ets.tzinfo: ets = ets.tz_localize(None)
                     
                     # Binary search or min abs
                     # Fast approx
                     idx = dh.index.get_loc(ets) if ets in dh.index else None
                     
                     if idx is None:
                         # Fallback search
                         diffs = (times - ets).abs()
                         idx = int(diffs.values.argmin())
                     
                     if idx is not None:
                         # Calc
                         i_start = min(max(0, idx + eff_entry), len(dh)-1)
                         i_end = min(max(0, idx + eff_exit), len(dh)-1)
                         
                         p0 = dh.iloc[i_start]['close']
                         p1 = dh.iloc[i_end]['close']
                         
                         new_g = (p1 - p0) / p0
                         display_gain = new_g * 100
                 except:
                     pass

        final_icon = f"{rev_icon} {arch_icon}".strip()
        ts_str = item["ts"].strftime('%Y-%m-%d %H:%M') if pd.notna(item["ts"]) else "N/A"
        label_str = f"{final_icon} {ts_str} | +{display_gain:.1f}% | {display_bars}bar"
        
        if label_str in list_map:
             label_str = f"{label_str} ({ann.event_id[-4:]})"
        
        list_options.append(label_str)
        list_map[label_str] = item

    selected_label_str = st.selectbox("Ralli Seçiniz", list_options, key="molder_list_select", label_visibility="collapsed")
    
    if not selected_label_str:
        return
        
    selected_item = list_map[selected_label_str]
    current_ann = selected_item["ann"]
    
    # --- MAIN CONTENT ---
    # st.divider() # Removed, merging panel directly

    # --- LABELING PANEL (Now Top) ---
    st.markdown("### 🏷️ Kalıp Seçimi (Archetype)")
    
    # Header Info + Revise Button
    hb1, hb2 = st.columns([3, 1])
    with hb1:
         st.info(f"ID: `{current_ann.event_id}` | Mevcut: **{current_ann.archetype or 'YOK'}**")
    with hb2:
         if st.button("🛠️ Revize Et", help="Bu ralliyi Revize Stüdyo'da düzenle", type="primary"):
             st.session_state['nav_selection'] = "🎯 Revize"
             st.session_state['ony_target_id'] = current_ann.event_id
             st.session_state['ony_prefill_symbol'] = sel_sym
             st.session_state['ony_prefill_tf'] = sel_tf
             st.rerun()

             st.rerun()

    # Layout: 7 Columns (Single Row)
    cols = st.columns(7)
    mold_list = [
        Archetype.GRIND, Archetype.GUILLOTINE, Archetype.SUPERNOVA, Archetype.PHOENIX,
        Archetype.NINJA, Archetype.SURFER, Archetype.OTHER
    ]
    
    for i, mold in enumerate(mold_list):
        col = cols[i] # 1 to 1 mapping
        label = ARCHETYPE_LABELS[mold]
        desc = ARCHETYPE_DESCRIPTIONS.get(mold, "")
        is_active = (current_ann.archetype == mold.value)
        
        with col:
            if st.button(
                label, 
                key=f"btn_{mold.value}", 
                use_container_width=True, 
                type="primary" if is_active else "secondary",
                help=desc # Tooltip for description
            ):
                # SAVE
                repo.append(
                    symbol=sel_sym,
                    timeframe=sel_tf,
                    event_id=current_ann.event_id,
                    entry_bar_offset=current_ann.entry_bar_offset,
                    status=current_ann.status, # Keep APPROVED
                    label=current_ann.label,
                    note=current_ann.note,
                    archetype=mold.value # UPDATE ARCHETYPE
                )
                st.toast(f"✅ Etiketlendi: {label}")
                st.rerun()
             # No separate caption/description below button

    # --- CHART AREA (Positioned below Labeling) ---
    st.markdown("---")
    
    # Need event_time. Parse from metadata or ID
    event_time = selected_item["ts"]
    if pd.isna(event_time):
        # Fallback to ID parse
        parts = current_ann.event_id.split('_')
        if parts[-1].isdigit():
            event_time = pd.to_datetime(int(parts[-1]), unit='s')
            
    # Auto-Zoom Calculation
    # If revised exit exists, use it. Else fall back to metadata bars.
    if current_ann.exit_bar_offset and current_ann.exit_bar_offset > 0:
        display_bars = current_ann.exit_bar_offset + 30 # +Buffer
    else:
        display_bars = selected_item["bars"] if selected_item["bars"] > 0 else 50
        
    # Cap display bars to reasonable max if needed, but usually zoom in is better
    display_bars = max(30, display_bars) # At least 30 bars

    try:
        render_sniper_studio_chart(
            symbol=sel_sym,
            timeframe=sel_tf,
            event_time=event_time,
            bars_to_peak=display_bars,
            entry_offset=current_ann.entry_bar_offset,
            exit_offset=current_ann.exit_bar_offset
            # Note: We don't need 'entry_offset' to be mutable here usually, but if we wanted to tweak it?
            # Molder is usually just "Labeling". Revize is for tweaking offsets.
            # So static view is fine.
        )
    except Exception as e:
        st.error(f"Grafik hatası: {e}")

    # --- MOLDER AI ASSISTANT (Vertical Layout) ---
    st.markdown("---")
    st.markdown("### 🤖 Sistem Analizi ve Öneriler")
    
    from tezaver.foundry.archetype_service import ArchetypeService
    from tezaver.core.molds import ARCHETYPE_DESCRIPTIONS
    
    # --- 1. PREDICTIONS (Top) ---
    from tezaver.ui.chart_area import load_history_data
    df_hist_curr = load_history_data(sel_sym, sel_tf)
    
    scores = []
    
    if df_hist_curr is not None:
         curr_ts = item.get("ts")
         if pd.isna(curr_ts):
             try:
                 parts = current_ann.event_id.split('_')
                 curr_ts = pd.to_datetime(int(parts[-1]), unit='s')
             except: pass

         if curr_ts:
             if curr_ts.tzinfo: curr_ts = curr_ts.tz_localize(None)
             if df_hist_curr.index.dtype.kind == 'M': t_idx = df_hist_curr.index 
             else: t_idx = pd.DatetimeIndex(pd.to_datetime(df_hist_curr['open_time']))
             if t_idx.tz is not None: t_idx = t_idx.tz_localize(None)
             
             # Ensure Indicators
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
             
             pos = t_idx.searchsorted(curr_ts)
             if pos < len(df_hist_curr):
                 eff_idx = min(pos + (current_ann.entry_bar_offset or 0), len(df_hist_curr)-1)
                 idx_start = max(0, eff_idx - 59)
                 window_slice = df_hist_curr.iloc[idx_start:eff_idx+1]
                 w_rsi = window_slice['rsi'].tolist()
                 w_vol = window_slice['volume_rel'].tolist()
                 
                 # PREDICT SCORES (All)
                 scores = ArchetypeService.analyze_trend_scores(w_rsi, w_vol)
                 
                 if scores:
                      best = scores[0]
                      p_arch = best['arch']
                      p_conf = best['conf']
                      p_reason = best['reason']
                      
                      # Highlighted Suggestion
                      c1, c2 = st.columns([1, 6])
                      with c1:
                          st.metric("Sistem Önerisi", p_arch, f"%{p_conf}")
                      with c2:
                          p_desc = ARCHETYPE_DESCRIPTIONS.get(p_arch, "")
                          st.success(f"**{p_arch}** ({p_desc})\n\n👉 **Gerekçe:** {p_reason}")
                          
                      # Secondary
                      if len(scores) > 1 and scores[1]['conf'] > 50:
                          sec = scores[1]
                          with st.expander(f"Alternatif: {sec['arch']} (%{sec['conf']})"):
                               s_desc = ARCHETYPE_DESCRIPTIONS.get(sec['arch'], "")
                               st.write(f"**Tanım:** {s_desc}")
                               st.write(f"**Gerekçe:** {sec['reason']}")
                 else:
                      st.warning("Hiçbir kalıp tespit edilemedi.")

    st.markdown("---")

    # --- 2. SELECTION CHECK (Middle) ---
    c_chk_1, c_chk_2 = st.columns([1, 6])
    with c_chk_1:
         user_arch = current_ann.archetype
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

    st.markdown("---")

    # --- 3. MASTERY SCORE (Bottom) ---
    st.caption("📊 Sistem Karnesi (Son 40 İşlem Başarısı)")
    
    hist_anns = repo.load_all(sel_sym, sel_tf)
    reviewed = [a for a in hist_anns if a.archetype and a.archetype != "None"]
    recent = reviewed[-40:] 
    
    if recent:
        df_hist_ai = load_history_data(sel_sym, sel_tf)
        if df_hist_ai is not None and not df_hist_ai.empty:
            if df_hist_ai.index.dtype.kind == 'M': times_ai = df_hist_ai.index 
            else: times_ai = pd.DatetimeIndex(pd.to_datetime(df_hist_ai['open_time']))
            if times_ai.tz is not None: times_ai = times_ai.tz_localize(None)
            
            # Ensure Indicators
            if 'rsi' not in df_hist_ai.columns:
                period = 14
                delta = df_hist_ai['close'].diff()
                gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
                loss = -delta.where(delta < 0, 0).ewm(alpha=1/period, adjust=False).mean()
                rs = gain / loss
                df_hist_ai['rsi'] = 100 - (100 / (1 + rs))
            if 'volume_rel' not in df_hist_ai.columns:
                if 'volume' in df_hist_ai.columns: df_hist_ai['volume_rel'] = df_hist_ai['volume'] / df_hist_ai['volume'].rolling(20).mean()
                else: df_hist_ai['volume_rel'] = 0

            closes = df_hist_ai['close'].values
            rsi_vals = df_hist_ai['rsi'].values
            vol_vals = df_hist_ai['volume_rel'].values
            
            matches = 0
            valid_n = 0
            for r_ann in recent:
                try:
                    if r_ann.symbol != sel_sym: continue
                    parts = r_ann.event_id.split('_')
                    ts_val = int(parts[-1])
                    event_ts = pd.to_datetime(ts_val, unit='s')
                    idx = times_ai.searchsorted(event_ts)
                    if idx < len(times_ai):
                         e_idx = min(idx + (r_ann.entry_bar_offset or 0), len(closes)-1)
                         curr_rsi = rsi_vals[e_idx]
                         curr_vol = vol_vals[e_idx]
                         p_arch, _, _ = ArchetypeService.classify_vector(curr_rsi, curr_vol)
                         if p_arch == r_ann.archetype: matches += 1
                         valid_n += 1
                except: continue
            
            if valid_n > 0:
                score = (matches / valid_n) * 100
                st.progress(score/100, text=f"Başarı: %{score:.0f} (Son {valid_n} işlem)")
            else:
                st.caption("Veri yetersiz.")
        else:
            st.caption("Veri yükleniyor...")
    else:
        st.caption("Henüz yeterli işlem yok.")

    # --- INFO POOL (Bilgi Havuzu - Moved Below AI) ---
    st.markdown("---")
    st.markdown("### 📊 Trade Künyesi")
    
    with st.spinner("Künye Hazırlanıyor..."):
        try:
            from tezaver.ui.chart_area import load_history_data
            df_hist = load_history_data(sel_sym, sel_tf)
            
            if df_hist is not None and not df_hist.empty:
                # Find index
                # Ensure timezone compatibility (naive)
                if df_hist.index.dtype.kind == 'M': # DatetimeIndex
                        times = df_hist.index
                else:
                        times = pd.to_datetime(df_hist['open_time'])
                
                if times.dt.tz is not None:
                    times = times.dt.tz_localize(None)
                
                if not pd.isna(event_time):
                    et_naive = event_time
                    if et_naive.tzinfo: et_naive = et_naive.tz_localize(None)
                    
                    try:
                        valid_diffs = (times - et_naive).abs()
                        event_idx = int(valid_diffs.values.argmin())
                        
                        # Calculate Entry/Exit Indices
                        entry_off = current_ann.entry_bar_offset or 0
                        # Handle Partial Revision: If exit missing, use default metadata bars
                        exit_off = current_ann.exit_bar_offset
                        if exit_off is None:
                             exit_off = selected_item.get("bars", 0) # Fallback to metadata
                        
                        entry_idx = min(max(0, event_idx + entry_off), len(df_hist)-1)
                        
                        # Get Entry Data
                        p_entry = df_hist.iloc[entry_idx]['close']
                        t_entry = times[entry_idx]
                        
                        # Get Exit Data & Calculation
                        if entry_idx < len(df_hist):
                            exit_idx = min(max(0, event_idx + exit_off), len(df_hist)-1)
                            p_exit = df_hist.iloc[exit_idx]['close']
                            t_exit = times[exit_idx]
                            
                            # Metrics
                            net_gain = (p_exit - p_entry) / p_entry if p_entry > 0 else 0
                            duration_bars = exit_off - entry_off
                            duration_time = t_exit - t_entry
                            
                            # Display
                            k1, k2, k3, k4 = st.columns(4)
                            k1.metric("Giriş Fiyatı", f"{p_entry:.4f}")
                            k2.metric("Çıkış Fiyatı", f"{p_exit:.4f}")
                            
                            # Add warning if using default exit
                            gain_label = "Net Kazanç"
                            if current_ann.exit_bar_offset is None:
                                 gain_label += " (Varsayılan Tepe)"
                                 
                            k3.metric(gain_label, f"%{net_gain*100:.2f}", delta=f"{net_gain*100:.2f}%")
                            k4.metric("Süre", f"{duration_bars} Bar", help=f"{duration_time}")
                            
                            st.caption(f"📅 **Aralık:** {t_entry} ➡️ {t_exit}")
                        else:
                            st.warning("Veri aralığı sınırları dışında.")
                            
                    except Exception as e_idx:
                         st.warning(f"Hesaplama hatası (Index): {e_idx}")
            else:
                st.warning("Veri yüklenemedi.")

        except Exception as e_pool:
            st.error(f"Künye hatası: {e_pool}")
