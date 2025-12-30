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

from tezaver.core.annotations import SniperAnnotation, SniperStatus, SniperLabel
from tezaver.core.molds import Archetype, ARCHETYPE_LABELS, ARCHETYPE_DESCRIPTIONS
from tezaver.ui.chart_area import render_sniper_studio_chart, load_history_data
from tezaver.foundry.archetype_service import ArchetypeService
from tezaver.foundry.rally_assembler import RallyAssembler
from tezaver.core.rally_store import RallyStore

# Reuse helpers from Ony Tab to maintain consistency
from tezaver.ui.ony_tab import (
    _get_available_symbols, 
)

from tezaver.core.tier_utils import (
    normalize_tier, 
    compute_tier_from_gain,
    TIERS
)

def render_molder_page():
    """Render the Kalıpçı page."""
    st.caption("Onaylanmış (Approved) rallilere Arketip (Kalıp) etiketi basar.")
    
    # Handle return from Revize
    if 'molder_target_id' in st.session_state:
        target_id = st.session_state.pop('molder_target_id')
        if target_id:
            # Parse symbol and TF from event ID
            parts = target_id.split('_')
            if len(parts) >= 2:
                st.session_state['molder_sym'] = parts[0]
                st.session_state['molder_tf'] = parts[1]
            st.session_state['molder_prefill_event_id'] = target_id
            st.toast("📐 Revize'den döndünüz! Kalıp seçebilirsiniz.")
    
    # Initialize repository & Assembler
    store = RallyStore()
    assembler = RallyAssembler()

    # --- TOP FILTERS (Coin, TF, Tier) ---
    c_sym, c_tf, c_tier = st.columns([1, 1, 3])
    
    with c_sym:
        symbols = _get_available_symbols()
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
    
    # --- DATA LOADING (Via RallyAssembler) ---
    moldable_rallies = assembler.get_moldable_rallies(sel_sym, sel_tf)
    
    if not moldable_rallies:
         st.info("Bu coin/zaman için onaylanmış (Approved) ralli yok.")
         return

    # Group by Tier
    tier_groups = {t: [] for t in TIERS}
    tier_groups["OTHER"] = [] 
    
    # Sort by Time (Newest First)
    moldable_rallies.sort(key=lambda x: x.event_time, reverse=True)
    
    for rally in moldable_rallies:
        t = rally.tier
        if t not in tier_groups: t = "OTHER"
        tier_groups[t].append(rally)
        
    # --- Handle Return from Revize: Find Target Rally's Tier ---
    prefill_id = st.session_state.get('molder_prefill_event_id')
    if prefill_id:
        for tier, items in tier_groups.items():
            for r in items:
                if r.event_id == prefill_id:
                    st.session_state['molder_selected_tier'] = tier
                    break

    # --- TIER SELECTOR ---
    tier_options = []
    for t in TIERS:
        count = len(tier_groups[t])
        tier_options.append(f"{t} ({count})")
    
    with c_tier:
        if 'molder_selected_tier' not in st.session_state:
            st.session_state['molder_selected_tier'] = "DIAMOND"
            
        def get_clean_tier(opt): return opt.split(" (")[0]
        
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
    
    if not current_list_items:
        st.info(f"🔍 {selected_tier} katmanında etiketlenecek ralli yok.")
        return

    # Helper for Icons
    def get_arch_icon(arch_code):
        if not arch_code: return "❓"
        try:
            lbl = ARCHETYPE_LABELS.get(Archetype(arch_code), "")
            return lbl.split(" ")[-1] if " " in lbl else "🏷️"
        except:
            return "🏷️"

    list_options = []
    list_map = {}
    
    for rally in current_list_items:
        list_options.append(rally.display_label)
        list_map[rally.display_label] = rally

    # Calculate default index
    default_idx = 0
    prefill_id = st.session_state.pop('molder_prefill_event_id', None)
    if prefill_id:
        for i, lbl in enumerate(list_options):
            r = list_map.get(lbl)
            if r and r.event_id == prefill_id:
                default_idx = i
                break

    selected_label_str = st.selectbox("Ralli Seçiniz", list_options, index=default_idx, key="molder_list_select", label_visibility="collapsed")
    
    if not selected_label_str:
        return
        
    current_rally = list_map[selected_label_str] # AssembledRally object
    
    # ==========================
    # 1. AI PREDICTIONS (System Analysis)
    # ==========================
    df_hist_curr = load_history_data(sel_sym, sel_tf)
    scores = []
    
    if df_hist_curr is not None:
         curr_ts = current_rally.event_time
         if curr_ts:
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
             if pos < len(df_hist_curr):
                 eff_idx = min(pos + (current_rally.entry_offset or 0), len(df_hist_curr)-1)
                 idx_start = max(0, eff_idx - 59)
                 window_slice = df_hist_curr.iloc[idx_start:eff_idx+1]
                 w_rsi = window_slice['rsi'].tolist()
                 w_vol = window_slice['volume_rel'].tolist()
                 
                 # PREDICT SCORES
                 scores = ArchetypeService.analyze_trend_scores(w_rsi, w_vol)
                 
                 if scores:
                      best = scores[0]
                      p_arch = best['arch']
                      p_conf = best['conf']
                      p_reason = best['reason']
                      
                      c1, c2 = st.columns([1, 6])
                      with c1:
                          st.metric("Sistem Önerisi", p_arch, f"%{p_conf}")
                      with c2:
                          p_desc = ARCHETYPE_DESCRIPTIONS.get(p_arch, "")
                          st.success(f"**{p_arch}** ({p_desc})\n\n👉 **Gerekçe:** {p_reason}")
                          
                      if len(scores) > 1 and scores[1]['conf'] > 50:
                          sec = scores[1]
                          with st.expander(f"Alternatif: {sec['arch']} (%{sec['conf']})"):
                               s_desc = ARCHETYPE_DESCRIPTIONS.get(sec['arch'], "")
                               st.write(f"**Tanım:** {s_desc}")
                               st.write(f"**Gerekçe:** {sec['reason']}")
                 else:
                      st.warning("Hiçbir kalıp tespit edilemedi.")

    st.markdown("---")

    # ==========================
    # 2. LABELING PANEL + CHART
    # ==========================
    st.markdown("### 🏷️ Kalıp Seçimi (Archetype)")
    
    # Header Info + Revise Button
    hb1, hb2 = st.columns([3, 1])
    with hb1:
         st.info(f"ID: `{current_rally.event_id}` | Mevcut: **{current_rally.archetype or 'YOK'}**")
    with hb2:
         if st.button("🛠️ Revize Et", help="Bu ralliyi Revize Stüdyo'da düzenle", type="primary"):
             st.session_state['nav_selection'] = "🎯 Revize"
             st.session_state['ony_target_id'] = current_rally.event_id
             st.session_state['ony_prefill_symbol'] = sel_sym
             st.session_state['ony_prefill_tf'] = sel_tf
             st.session_state['came_from_molder'] = True
             st.session_state['molder_return_target'] = current_rally.event_id
             st.rerun()

    # Buttons
    cols = st.columns(7)
    mold_list = [
        Archetype.GRIND, Archetype.GUILLOTINE, Archetype.SUPERNOVA, Archetype.PHOENIX,
        Archetype.NINJA, Archetype.SURFER, Archetype.OTHER
    ]
    
    for i, mold in enumerate(mold_list):
        col = cols[i]
        label = ARCHETYPE_LABELS[mold]
        desc = ARCHETYPE_DESCRIPTIONS.get(mold, "")
        is_active = (current_rally.archetype == mold.value)
        
        with col:
            if st.button(
                label, 
                key=f"btn_{mold.value}", 
                use_container_width=True, 
                type="primary" if is_active else "secondary",
                help=desc
            ):
                # SAVE to Store
                doc = store.get_rally(current_rally.event_id)
                rev_data = doc.get('rev_data', {}) or {}
                molder_data = doc.get('molder_data', {}) or {}
                
                # Update Archetype in Rev Data (Labeling)
                rev_data.update({
                    'archetype': mold.value, # Use mold.value for arch_key
                    'updated_at': pd.Timestamp.now()
                })
                
                # Update Molder Metadata
                molder_data.update({
                    'archetype': mold.value, # Use mold.value for arch_key
                    'confidence': scores[0]['conf'] if (scores and scores[0]['arch'] == mold.value) else 0.5, # Simple logic
                    'labeled_at': pd.Timestamp.now()
                })
                
                store.upsert_rally(current_rally.event_id, rev_data, layer='rev')
                store.upsert_rally(current_rally.event_id, molder_data, layer='molder')
                
                st.success(f"✅ Kaydedildi! ({mold.value})")
                st.toast(f"✅ Etiketlendi: {label}")
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

    # Chart
    st.markdown("---")
    event_time = current_rally.event_time
    try:
        render_sniper_studio_chart(
            symbol=sel_sym,
            timeframe=sel_tf,
            event_time=event_time,
            bars_to_peak=current_rally.bars_to_peak,
            entry_offset=current_rally.entry_offset,
            exit_offset=current_rally.exit_offset
        )
    except Exception as e:
        st.error(f"Grafik hatası: {e}")

    # ==========================
    # 3. MASTERY SCORE & INFO POOL
    # ==========================
    st.markdown("---")
    st.caption("📊 Sistem Karnesi (Son 40 İşlem Başarısı)")
    
    all_rallies = store.list_rallies(symbol=sel_sym, timeframe=sel_tf)
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
             if hasattr(times_ai, 'tz') and times_ai.tz is not None: times_ai = times_ai.tz_localize(None)
             
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

    # Info Pool (Trade Künyesi)
    st.markdown("---")
    st.markdown("### 📊 Trade Künyesi")
    
    if df_hist_curr is not None:
         # Reuse df_hist_curr
         if not pd.isna(event_time):
             et_naive = event_time
             if et_naive.tzinfo: et_naive = et_naive.tz_localize(None)
             
             times = df_hist_curr.index if df_hist_curr.index.dtype.kind == 'M' else pd.to_datetime(df_hist_curr['open_time'])
             if hasattr(times, 'tz') and times.tz is not None: times = times.tz_localize(None)
             
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

    # Guide (Static)
    st.markdown("---")
    with st.expander("📚 Kalıp Rehberi (Arketip Tanımları)", expanded=False):
        st.markdown("**GRIND:** Yavaş birikim, düşük volatilite. (RSI ~50)")
        st.markdown("**GUILLOTINE:** Sert düşüş sonrası dip dönüşü. (RSI <30)")
        st.markdown("**SUPERNOVA:** Ani patlama, parabolik yükseliş. (RSI >70)")
        st.markdown("**PHOENIX:** Derin düşüşten V dönüşü.")
        st.markdown("**NINJA:** Gizli birikim, hacimsiz yükseliş.")
        st.markdown("**SURFER:** Güçlü trend takibi. (RSI >60)")
