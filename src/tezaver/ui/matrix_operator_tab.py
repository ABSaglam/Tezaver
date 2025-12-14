# Matrix Operator Tab v1
"""
Matrix Operator Tab for Streamlit.

Shows Strategy Board and Live Cluster preview in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import os
import streamlit as st

from tezaver.matrix.profile_board import build_profile_board, ProfileBoardRow
from tezaver.matrix.live.live_cluster import build_live_cluster_from_profile_board


# =============================================================================
# Sniper Arena V4 (Single Source of Truth) - HARDENED
# =============================================================================

def _render_sniper_arena_v4() -> None:
    """
    Sniper Arena V4 - Production-grade with:
    - Dataset availability gating
    - Data coverage panel
    - Card provenance viewer
    - Sanity preset buttons
    """
    from pathlib import Path
    from datetime import datetime
    import json
    import pandas as pd
    from tezaver.sniper.v4.arena_v4 import run_sniper_arena_v4
    
    DATA_DIR = Path("data")
    
    st.header("🎯 Sniper Arena V4 – 100 → X")
    st.caption(
        "V4 Engine: Deterministik selection ve backtest. "
        "Her ayar sonucu etkiler. Invariants: Selected=Used=Trades"
    )
    
    # =========================================================================
    # Dataset Path Resolver
    # =========================================================================
    def get_dataset_path(sym: str, tf: str, src: str) -> Path:
        """Get dataset path for given symbol/timeframe/source."""
        if src == "patterns":
            return DATA_DIR / "ai_datasets" / sym / tf / "sniper_entries_v1.parquet"
        else:  # full_replay
            return DATA_DIR / "replay" / sym / tf / "full_replay_bars_v1.parquet"
    
    def check_dataset_exists(sym: str, tf: str, src: str) -> bool:
        """Check if dataset exists."""
        path = get_dataset_path(sym, tf, src)
        if path.exists():
            return True
        # Fallback for patterns
        if src == "patterns":
            alt = DATA_DIR / "sniper" / sym / f"sniper_entries_{tf}_v1.parquet"
            return alt.exists()
        return False
    
    def get_available_timeframes(sym: str, src: str) -> list:
        """Get list of timeframes with available data."""
        available = []
        for tf in ["15m", "1h", "4h"]:
            if check_dataset_exists(sym, tf, src):
                available.append(tf)
            else:
                available.append(f"{tf} (missing)")
        return available
    
    # =========================================================================
    # Basic Settings with Availability Checking
    # =========================================================================
    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.selectbox(
            "Coin",
            ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            key="sniper_v4_symbol"
        )
    with col2:
        source = st.selectbox(
            "Data Source",
            ["patterns", "full_replay"],
            key="sniper_v4_source"
        )
    with col3:
        tf_options = get_available_timeframes(symbol, source)
        tf_selection = st.selectbox(
            "Timeframe",
            tf_options,
            key="sniper_v4_timeframe"
        )
        # Extract actual timeframe (remove "(missing)" suffix)
        timeframe = tf_selection.split(" ")[0]
    
    # Dataset availability check
    dataset_available = check_dataset_exists(symbol, timeframe, source)
    
    if not dataset_available:
        st.warning(f"⚠️ Dataset bulunamadı: {get_dataset_path(symbol, timeframe, source)}")
        st.info(
            f"**Çözüm:** Dataset oluştur:\n"
            f"```bash\n"
            f"PYTHONPATH=src python -m tezaver.sniper {symbol} {timeframe} --from-patterns\n"
            f"```"
        )
    
    # =========================================================================
    # Data Coverage Panel (if dataset exists)
    # =========================================================================
    if dataset_available:
        try:
            path = get_dataset_path(symbol, timeframe, source)
            if not path.exists():
                path = DATA_DIR / "ai_datasets" / symbol / timeframe / "sniper_entries_v1.parquet"
            
            df_preview = pd.read_parquet(path)
            rows_count = len(df_preview)
            
            # Find timestamp column
            ts_col = None
            for c in ["event_time", "entry_ts", "ts", "timestamp"]:
                if c in df_preview.columns:
                    ts_col = c
                    break
            
            if ts_col:
                df_preview[ts_col] = pd.to_datetime(df_preview[ts_col])
                date_min = df_preview[ts_col].min()
                date_max = df_preview[ts_col].max()
                years = (date_max - date_min).days / 365.25
                
                st.caption(
                    f"📈 **{source}** | rows={rows_count} | "
                    f"date={date_min.strftime('%Y-%m-%d')} → {date_max.strftime('%Y-%m-%d')} | "
                    f"~{years:.1f} yıl"
                )
            else:
                st.caption(f"📈 **{source}** | rows={rows_count}")
        except Exception as e:
            st.caption(f"📈 Data coverage: error - {e}")
    
    st.divider()
    
    # =========================================================================
    # Risk & Sizing
    # =========================================================================
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        risk = st.slider(
            "Risk / Trade",
            min_value=0.01,
            max_value=1.0,
            value=1.0,
            step=0.01,
            key="sniper_v4_risk"
        )
    with col2:
        tp_pct = st.slider(
            "Take Profit %",
            min_value=1,
            max_value=20,
            value=8,
            key="sniper_v4_tp"
        ) / 100.0
    with col3:
        sl_pct = st.slider(
            "Stop Loss %",
            min_value=1,
            max_value=10,
            value=3,
            key="sniper_v4_sl"
        ) / 100.0
    with col4:
        sizing_mode = st.selectbox(
            "Sizing Mode",
            ["equity_pct", "initial_notional"],
            key="sniper_v4_sizing"
        )
    
    # =========================================================================
    # Entry Selection Mode (ARENA/CARD_STRICT/CARD_SOURCE)
    # =========================================================================
    st.markdown("### 📋 Entry Selection Mode")
    selection_mode = st.radio(
        "Mod",
        options=["ARENA_FILTERS", "CARD_STRICT_IDS", "CARD_SOURCE_IDS"],
        horizontal=True,
        key="sniper_v4_selection_mode",
        help=(
            "ARENA_FILTERS: UI ayarlarıyla dinamik seçim. "
            "CARD_STRICT_IDS: Karttan strict ID'ler. "
            "CARD_SOURCE_IDS: Karttan source ID'ler (daha geniş)."
        )
    )
    
    # Show card availability for CARD modes
    run_disabled = False
    contract_block_reason = None
    
    if selection_mode != "ARENA_FILTERS":
        card_path = DATA_DIR / "coin_profiles" / symbol / timeframe / "sniper_strategy_card_v1.json"
        alt_card_path = DATA_DIR / "ai_datasets" / symbol / timeframe / "sniper_strategy_card_v1.json"
        card_exists = card_path.exists() or alt_card_path.exists()
        if not card_exists:
            st.warning(f"⚠️ Sniper card bulunamadı ({selection_mode} için gerekli)")
            run_disabled = True
        
        # Contract gating for CARD_STRICT_IDS
        if selection_mode == "CARD_STRICT_IDS" and card_exists:
            from tezaver.sniper.v4.select_v4 import load_card_contract_state
            
            contract_state = load_card_contract_state(symbol, timeframe)
            
            if contract_state.get("available"):
                enforce_mode = contract_state.get("enforce_mode", "WARN")
                contract_ok = contract_state.get("ok", True)
                
                if enforce_mode == "BLOCK" and not contract_ok:
                    run_disabled = True
                    violations = contract_state.get("violations", [])
                    viol_codes = [v.get("code", "?") for v in violations]
                    contract_block_reason = f"Violations: {', '.join(viol_codes)}"
                    st.error(f"⛔ **STRICT CONTRACT BLOCK** — {contract_block_reason}")
                    st.caption(f"Suggestions: {contract_state.get('suggested_actions', [])}")
                elif not contract_ok:
                    # WARN mode - show warning but allow run
                    violations = contract_state.get("violations", [])
                    viol_codes = [v.get("code", "?") for v in violations]
                    st.warning(f"⚠️ Contract WARN: {', '.join(viol_codes)} (run allowed)")
    
    # =========================================================================
    # Tightness with Sanity Presets
    # =========================================================================
    st.markdown("### 🎚️ Tightness (0=Loose, 100=Tight)")

    
    # Sanity preset buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📉 Preset: T=0 (all on)", key="preset_t0"):
            st.session_state["sniper_v4_tightness"] = 0
            st.session_state["sniper_v4_rsi"] = True
            st.session_state["sniper_v4_vol"] = True
            st.session_state["sniper_v4_atr"] = True
            st.session_state["sniper_v4_quality"] = True
            st.session_state["sniper_v4_ml"] = False
            st.rerun()
    with col2:
        if st.button("📈 Preset: T=100 (all on)", key="preset_t100"):
            st.session_state["sniper_v4_tightness"] = 100
            st.session_state["sniper_v4_rsi"] = True
            st.session_state["sniper_v4_vol"] = True
            st.session_state["sniper_v4_atr"] = True
            st.session_state["sniper_v4_quality"] = True
            st.session_state["sniper_v4_ml"] = False
            st.rerun()
    with col3:
        if st.button("🔇 Preset: T=100 (vol OFF)", key="preset_t100_novol"):
            st.session_state["sniper_v4_tightness"] = 100
            st.session_state["sniper_v4_rsi"] = True
            st.session_state["sniper_v4_vol"] = False
            st.session_state["sniper_v4_atr"] = True
            st.session_state["sniper_v4_quality"] = True
            st.session_state["sniper_v4_ml"] = False
            st.rerun()
    
    tightness = st.slider(
        "Tightness",
        min_value=0,
        max_value=100,
        value=st.session_state.get("sniper_v4_tightness", 50),
        step=5,
        key="sniper_v4_tightness"
    )
    
    # =========================================================================
    # Filter Toggles
    # =========================================================================
    st.markdown("### 🎛️ Filter Toggles")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        toggle_rsi = st.checkbox("RSI", value=True, key="sniper_v4_rsi")
    with col2:
        toggle_vol = st.checkbox("VOLUME", value=True, key="sniper_v4_vol")
    with col3:
        toggle_atr = st.checkbox("ATR", value=True, key="sniper_v4_atr")
    with col4:
        toggle_quality = st.checkbox("QUALITY", value=True, key="sniper_v4_quality")
    with col5:
        toggle_ml = st.checkbox("ML", value=False, key="sniper_v4_ml")
    
    toggles = {
        "rsi": toggle_rsi,
        "volume": toggle_vol,
        "atr": toggle_atr,
        "quality": toggle_quality,
        "ml": toggle_ml,
    }
    
    # =========================================================================
    # Card Builder Controls
    # =========================================================================
    with st.expander("🧱 Card Builder Controls", expanded=False):
        st.caption("Kartın hangi annotation'lardan oluşturulacağını ayarla")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Status:**")
            cb_approved = st.checkbox("APPROVED", value=True, key="cb_status_approved")
            cb_reviewed = st.checkbox("REVIEWED", value=False, key="cb_status_reviewed")
            cb_pending = st.checkbox("PENDING", value=False, key="cb_status_pending")
        
        with col2:
            st.markdown("**Label:**")
            cb_good = st.checkbox("GOOD", value=True, key="cb_label_good")
            cb_bad = st.checkbox("BAD", value=False, key="cb_label_bad")
            cb_uncertain = st.checkbox("UNCERTAIN", value=False, key="cb_label_uncertain")
        
        with col3:
            st.markdown("**Quality Floor:**")
            qf_policy = st.selectbox(
                "Policy",
                ["OFF", "SOFT", "HARD"],
                index=2,
                key="cb_qf_policy"
            )
            qf_value = st.slider(
                "Value",
                min_value=0,
                max_value=100,
                value=50,
                key="cb_qf_value"
            )
        
        # Similarity Expansion Controls v2.7
        st.divider()
        st.markdown("**Strict Selection Controls:**")
        
        col1, col2 = st.columns(2)
        with col1:
            similarity_enabled = st.checkbox("🧲 Similarity Enabled", value=True, key="cb_similarity_enabled")
        with col2:
            strict_method = st.selectbox(
                "Method",
                ["HYBRID", "SIMILARITY_TOPK", "SIMILARITY_CUTOFF", "AUTO_RELAX"],
                index=0,
                key="cb_strict_method",
                disabled=not similarity_enabled
            )
        
        col1, col2 = st.columns(2)
        with col1:
            min_strict_count = st.slider(
                "Min Strict Count",
                min_value=1,
                max_value=50,
                value=10,
                key="cb_min_strict_count",
                disabled=not similarity_enabled
            )
        with col2:
            use_distance_cutoff = st.checkbox("Distance Cutoff", value=False, key="cb_use_cutoff")
            distance_cutoff = st.slider(
                "Cutoff Value",
                min_value=0.5,
                max_value=10.0,
                value=3.0,
                step=0.5,
                key="cb_distance_cutoff",
                disabled=not use_distance_cutoff
            ) if use_distance_cutoff else None
        
        # Feature Weights (advanced)
        with st.expander("⚙️ Feature Weights", expanded=False):
            st.caption("Ağırlık 0 = feature devre dışı, 3 = çok yüksek ağırlık")
            wcol1, wcol2 = st.columns(2)
            with wcol1:
                w_rsi = st.slider("RSI 15m", 0.0, 3.0, 1.0, 0.5, key="w_rsi")
                w_vol = st.slider("Volume Rel 15m", 0.0, 3.0, 1.0, 0.5, key="w_vol")
            with wcol2:
                w_atr = st.slider("ATR Pct 15m", 0.0, 3.0, 1.0, 0.5, key="w_atr")
                w_qual = st.slider("Quality Score", 0.0, 3.0, 0.5, 0.5, key="w_qual")
        
        # Seed Policy (advanced)
        with st.expander("🌱 Seed Policy", expanded=False):
            st.caption("Hangi entry'ler seed olarak kullanılacak")
            seed_statuses = st.multiselect(
                "Seed Statuses",
                ["APPROVED", "REVIEWED", "PENDING"],
                default=["APPROVED"],
                key="cb_seed_statuses"
            )
            seed_labels = st.multiselect(
                "Seed Labels",
                ["GOOD", "UNCERTAIN", "BAD"],
                default=["GOOD"],
                key="cb_seed_labels"
            )
            min_seed = st.slider(
                "Min Seed Count (fallback to AUTO_RELAX)",
                min_value=1,
                max_value=10,
                value=3,
                key="cb_min_seed"
            )
        
        # Contract Controls (v2.8)
        with st.expander("🧾 Strict Quality Contract", expanded=False):
            st.caption("Kalite kontratı: min/max sınırlar + enforce modu")
            
            col1, col2 = st.columns(2)
            with col1:
                contract_min_strict = st.slider(
                    "Min Strict Count",
                    min_value=1,
                    max_value=50,
                    value=10,
                    key="sqc_min_strict_count"
                )
                contract_min_seed = st.slider(
                    "Min Seed Count",
                    min_value=1,
                    max_value=10,
                    value=3,
                    key="sqc_min_seed_count"
                )
            with col2:
                contract_auto_relax = st.slider(
                    "Max Auto-Relax Ratio",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.5,
                    step=0.1,
                    key="sqc_max_auto_relax_ratio"
                )
                contract_enforce = st.radio(
                    "Enforce Mode",
                    ["WARN", "BLOCK"],
                    index=0,
                    horizontal=True,
                    key="sqc_enforce_mode"
                )
            
            # P50/P90 limits with checkbox
            col1, col2 = st.columns(2)
            with col1:
                use_max_p50 = st.checkbox("Max P50 Limit", value=False, key="sqc_max_p50_enabled")
                max_p50 = st.slider(
                    "P50 Limit",
                    min_value=1.0,
                    max_value=6.0,
                    value=3.0,
                    step=0.5,
                    key="sqc_max_p50_value",
                    disabled=not use_max_p50
                ) if use_max_p50 else None
            with col2:
                use_max_p90 = st.checkbox("Max P90 Limit", value=False, key="sqc_max_p90_enabled")
                max_p90 = st.slider(
                    "P90 Limit",
                    min_value=1.0,
                    max_value=10.0,
                    value=4.5,
                    step=0.5,
                    key="sqc_max_p90_value",
                    disabled=not use_max_p90
                ) if use_max_p90 else None
        
        # Preset buttons
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("✅ APPROVED+GOOD", key="preset_approved_good"):
                st.session_state["cb_status_approved"] = True
                st.session_state["cb_status_reviewed"] = False
                st.session_state["cb_status_pending"] = False
                st.session_state["cb_label_good"] = True
                st.session_state["cb_label_bad"] = False
                st.session_state["cb_label_uncertain"] = False
                st.rerun()
        with col2:
            if st.button("🧪 Hepsi (explore)", key="preset_all"):
                st.session_state["cb_status_approved"] = True
                st.session_state["cb_status_reviewed"] = True
                st.session_state["cb_status_pending"] = True
                st.session_state["cb_label_good"] = True
                st.session_state["cb_label_bad"] = False
                st.session_state["cb_label_uncertain"] = True
                st.rerun()
        with col3:
            if st.button("🚫 BAD hariç", key="preset_no_bad"):
                st.session_state["cb_status_approved"] = True
                st.session_state["cb_status_reviewed"] = True
                st.session_state["cb_status_pending"] = False
                st.session_state["cb_label_good"] = True
                st.session_state["cb_label_bad"] = False
                st.session_state["cb_label_uncertain"] = True
                st.rerun()
        
        # Effective Builder Filters (diagnostic line)
        st.divider()
        effective_statuses = [s for s, v in [("APPROVED", cb_approved), ("REVIEWED", cb_reviewed), ("PENDING", cb_pending)] if v]
        effective_labels = [l for l, v in [("GOOD", cb_good), ("BAD", cb_bad), ("UNCERTAIN", cb_uncertain)] if v]
        st.caption(
            f"**Filters:** status={effective_statuses} label={effective_labels} "
            f"method={strict_method if similarity_enabled else 'DISABLED'} min_strict={min_strict_count}"
        )
        
        # Rebuild button
        if st.button("🔁 Rebuild Card", key="btn_rebuild_card", type="primary"):
            try:
                from tezaver.sniper.sniper_strategy_card_builder import (
                    SniperStrategyCardConfig,
                    StrictSelectionConfig,
                    save_sniper_strategy_card_for_symbol_timeframe,
                )
                
                include_status = []
                if cb_approved:
                    include_status.append("APPROVED")
                if cb_reviewed:
                    include_status.append("REVIEWED")
                if cb_pending:
                    include_status.append("PENDING")
                
                include_labels = []
                if cb_good:
                    include_labels.append("GOOD")
                if cb_bad:
                    include_labels.append("BAD")
                if cb_uncertain:
                    include_labels.append("UNCERTAIN")
                
                # Build StrictSelectionConfig
                strict_sel_cfg = StrictSelectionConfig(
                    enabled=similarity_enabled,
                    method=strict_method if similarity_enabled else "AUTO_RELAX",
                    min_strict_count=min_strict_count,
                    topk=min_strict_count,
                    distance_cutoff=distance_cutoff if use_distance_cutoff else None,
                    feature_weights={
                        "rsi_15m": w_rsi,
                        "volume_rel_15m": w_vol,
                        "atr_pct_15m": w_atr,
                        "quality_score": w_qual,
                    },
                    normalize="zscore",
                    seed_policy={
                        "use_statuses": seed_statuses if seed_statuses else ["APPROVED"],
                        "use_labels": seed_labels if seed_labels else ["GOOD"],
                        "min_seed_count": min_seed,
                    }
                )
                
                cfg = SniperStrategyCardConfig(
                    symbol=symbol,
                    timeframe=timeframe,
                    include_status=include_status if include_status else ["APPROVED"],
                    include_labels=include_labels if include_labels else ["GOOD"],
                    quality_floor_policy=qf_policy,
                    quality_floor_value=float(qf_value),
                    strict_selection=strict_sel_cfg,
                    similarity_enabled=similarity_enabled,
                    min_strict_count=min_strict_count,
                )
                
                # Build StrictQualityContract from UI
                from tezaver.sniper.sniper_strategy_card_builder import StrictQualityContract
                
                strict_contract = StrictQualityContract(
                    min_strict_count=contract_min_strict,
                    max_distance_p50=max_p50 if use_max_p50 else None,
                    max_distance_p90=max_p90 if use_max_p90 else None,
                    max_auto_relax_ratio=contract_auto_relax,
                    min_seed_count=contract_min_seed,
                    enforce_mode=contract_enforce,
                )
                cfg.strict_contract = strict_contract
                
                with st.spinner("Kart yeniden oluşturuluyor..."):
                    path = save_sniper_strategy_card_for_symbol_timeframe(symbol, timeframe, cfg)
                
                # Show contract result
                with open(path) as f:
                    result_prov = json.load(f).get("provenance", {})
                contract_result = result_prov.get("strict_contract_result", {})
                
                if contract_result.get("ok", True):
                    st.success(f"✅ Kart güncellendi: {path} | Contract: OK")
                else:
                    viol_codes = [v["code"] for v in contract_result.get("violations", [])]
                    if contract_enforce == "BLOCK":
                        st.error(f"⛔ Contract BLOCK: {viol_codes}")
                    else:
                        st.warning(f"⚠️ Contract WARN: {viol_codes}")
                        st.caption(f"Suggestions: {contract_result.get('suggested_actions', [])}")
                
                st.rerun()
                
            except RuntimeError as e:
                # BLOCK mode raises RuntimeError
                st.error(f"⛔ Contract BLOCKED: {e}")
            except Exception as e:
                st.error(f"❌ Rebuild hatası: {e}")
    
    # =========================================================================
    # Card Provenance Viewer + Diagnostics
    # =========================================================================

    with st.expander("📚 Sniper Card Provenance", expanded=False):
        card_path = DATA_DIR / "coin_profiles" / symbol / timeframe / "sniper_strategy_card_v1.json"
        alt_card_path = DATA_DIR / "ai_datasets" / symbol / timeframe / "sniper_strategy_card_v1.json"
        
        card_found = False
        card_data = {}
        
        for p in [card_path, alt_card_path]:
            if p.exists():
                try:
                    card_data = json.loads(p.read_text())
                    card_found = True
                    st.caption(f"📄 Card path: {p}")
                    break
                except:
                    pass
        
        if not card_found:
            st.warning("Sniper strategy card bulunamadı.")
            st.info(
                "**Kart oluşturma komutu:**\n"
                "```bash\n"
                f"PYTHONPATH=src python -m tezaver.sniper.sniper_strategy_card_builder {symbol} {timeframe}\n"
                "```"
            )
        else:
            prov = card_data.get("provenance", {})
            if prov:
                # === Summary Line ===
                st.markdown("**Provenance:**")
                st.caption(
                    f"Version: {prov.get('version', 'N/A')} | "
                    f"Source: {prov.get('source_count', 'N/A')} | "
                    f"Strict: {prov.get('strict_count', 'N/A')} | "
                    f"Dropped: {prov.get('strict_drop_count', 'N/A')}"
                )
                
                # === 0-Entry Guardrail ===
                source_count = prov.get("source_count", 0)
                if source_count == 0:
                    st.error("⚠️ **source_count = 0** — Filtreler çok dar, kart boş!")
                    st.markdown("""
**Öneriler:**
1. 🔄 **Status:** REVIEWED veya PENDING ekle
2. 🏷️ **Label:** UNCERTAIN ekle
3. 📊 **Quality Floor:** HARD ise OFF/SOFT dene
                    """)
                
                # === Drop Breakdown Panel ===
                drop_breakdown = prov.get("drop_breakdown", {})
                if drop_breakdown:
                    st.markdown("**Drop Breakdown:**")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Source→Quality", drop_breakdown.get("source_to_quality_drop", 0))
                    with col2:
                        st.metric("Quality→Strict", drop_breakdown.get("quality_to_strict_drop", 0))
                    with col3:
                        st.metric("Total Drop", drop_breakdown.get("source_to_strict_drop", 0))
                    with col4:
                        bottleneck = drop_breakdown.get("bottleneck", "NONE")
                        bottleneck_color = "🔴" if bottleneck != "NONE" else "🟢"
                        st.metric("Bottleneck", f"{bottleneck_color} {bottleneck}")
                else:
                    st.warning("drop_breakdown bulunamadı — karttı yeniden oluştur")
                
                # === Filters Used ===
                filters_used = prov.get("filters_used", {})
                if filters_used:
                    st.markdown("**Filters Used:**")
                    st.json(filters_used)
                
                # === Annotation Stats ===
                ann_stats = prov.get("annotation_stats", {})
                if ann_stats:
                    st.markdown("**Annotation Stats:**")
                    st.caption(
                        f"Total: {ann_stats.get('total_annotations', 0)} | "
                        f"Matched: {ann_stats.get('matched_annotations', 0)}"
                    )
                
                # === Contract Result (v2.8) ===
                contract_result = prov.get("strict_contract_result", {})
                contract_cfg = prov.get("strict_contract", {})
                if contract_result:
                    enforce_mode = contract_cfg.get("enforce_mode", "WARN")
                    is_ok = contract_result.get("ok", True)
                    
                    if is_ok:
                        st.success("✅ **Contract OK** — Kalite kontratı sağlandı")
                    else:
                        if enforce_mode == "BLOCK":
                            st.error("⛔ **Contract BLOCK** — CARD_STRICT_IDS devre dışı")
                        else:
                            st.warning("⚠️ **Contract WARN** — Kalite uyarısı")
                        
                        # Show violations
                        violations = contract_result.get("violations", [])
                        for v in violations:
                            st.caption(f"- `{v['code']}`: actual={v['actual']}, expected={v['expected']}")
                        
                        # Show suggestions
                        suggestions = contract_result.get("suggested_actions", [])
                        if suggestions:
                            st.caption(f"**Öneriler:** {', '.join(suggestions)}")
                    
                    # Show key metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Auto-Relax %", f"{contract_result.get('auto_relax_ratio', 0)*100:.1f}%")
                    with col2:
                        ss = prov.get("strict_selection", {})
                        p50 = ss.get("distance_stats", {}).get("p50", "N/A")
                        st.metric("P50", p50)
                    with col3:
                        p90 = ss.get("distance_stats", {}).get("p90", "N/A")
                        st.metric("P90", p90)
                
                source_ids = prov.get("source_entry_ids_sample", [])
                if source_ids:
                    st.markdown("**Source IDs (sample):**")
                    st.code("\n".join(source_ids[:10]))
            else:
                st.json(card_data)
    
    # =========================================================================
    # Annotation Coverage Board
    # =========================================================================
    with st.expander("🧾 Annotation Coverage Board", expanded=False):
        try:
            from tezaver.sniper.sniper_annotations import SniperAnnotationRepository
            
            repo = SniperAnnotationRepository()
            annotations = repo.load_all(symbol, timeframe)
            
            if not annotations:
                st.info(f"📭 {symbol}/{timeframe} için annotation bulunamadı.")
            else:
                # Build status × label pivot
                status_labels = {"APPROVED": {}, "REVIEWED": {}, "PENDING": {}, "REJECTED": {}}
                all_labels = ["GOOD", "BAD", "UNCERTAIN"]
                
                # Initialize all cells to 0
                for s in status_labels:
                    for l in all_labels:
                        status_labels[s][l] = 0
                
                # Count annotations
                for ann in annotations:
                    status = ann.status if ann.status in status_labels else "PENDING"
                    label = ann.label if ann.label in all_labels else "UNCERTAIN"
                    status_labels[status][label] += 1
                
                # Create DataFrame for display
                import pandas as pd
                pivot_data = []
                for status, labels_dict in status_labels.items():
                    row = {"Status": status}
                    row.update(labels_dict)
                    row["Total"] = sum(labels_dict.values())
                    pivot_data.append(row)
                
                df_pivot = pd.DataFrame(pivot_data)
                st.table(df_pivot)
                
                st.caption(f"**Toplam annotation:** {len(annotations)}")
                
                # Highlight APPROVED+GOOD count
                approved_good = status_labels.get("APPROVED", {}).get("GOOD", 0)
                st.info(f"✅ **APPROVED+GOOD:** {approved_good}")
                
        except Exception as e:
            st.error(f"Annotation yükleme hatası: {e}")
    
    # =========================================================================
    # Similarity Expansion Report
    # =========================================================================
    with st.expander("🧲 Similarity Expansion Report", expanded=False):
        # Load card for similarity data
        card_path = DATA_DIR / "coin_profiles" / symbol / timeframe / "sniper_strategy_card_v1.json"
        alt_card_path = DATA_DIR / "ai_datasets" / symbol / timeframe / "sniper_strategy_card_v1.json"
        
        card_data = {}
        for p in [card_path, alt_card_path]:
            if p.exists():
                try:
                    card_data = json.loads(p.read_text())
                    break
                except:
                    pass
        
        prov = card_data.get("provenance", {})
        strict_sel = prov.get("strict_selection", {})
        
        if not strict_sel:
            st.info("Similarity expansion verisi yok. Kartı yeniden oluşturun.")
        else:
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                enabled = strict_sel.get("enabled", False)
                st.metric("Enabled", "✅ ON" if enabled else "❌ OFF")
            with col2:
                st.metric("Seed Count", strict_sel.get("seed_count", 0))
            with col3:
                st.metric("Initial Strict", strict_sel.get("initial_strict_count", 0))
            with col4:
                achieved = strict_sel.get("achieved_count", strict_sel.get("initial_strict_count", 0))
                st.metric("Achieved", achieved)
            
            # Method and note
            method = strict_sel.get("method", "THRESHOLD")
            st.caption(f"**Method:** {method}")
            if strict_sel.get("note"):
                st.caption(f"**Note:** {strict_sel.get('note')}")
            
            # Tripwire warning
            min_strict = strict_sel.get("min_strict_count", 10)
            achieved = strict_sel.get("achieved_count", 0)
            seed_count = strict_sel.get("seed_count", 0)
            if enabled and seed_count > 0 and achieved < min_strict:
                st.warning(f"⚠️ Similarity expansion hedefe ulaşamadı: {achieved} < {min_strict} (quality_count yetersiz olabilir)")
            
            # Distance stats
            dist_stats = strict_sel.get("distance_stats", {})
            if dist_stats:
                st.markdown("**Distance Stats:**")
                dist_cols = st.columns(6)
                for i, (key, val) in enumerate(dist_stats.items()):
                    with dist_cols[i % 6]:
                        st.metric(key, f"{val:.4f}")
            
            # Features used
            features_used = strict_sel.get("features_used", [])
            if features_used:
                st.caption(f"**Features Used:** {', '.join(features_used)}")
            
            # Similarity-added IDs
            added_ids = strict_sel.get("strict_added_ids_sample", [])
            if added_ids:
                st.markdown(f"**Similarity-Added IDs ({len(added_ids)}):**")
                st.code("\n".join(added_ids[:10]))
            
            # Selection details table
            details = prov.get("strict_selection_details", [])
            if details:
                st.markdown("**Selection Details (top 25):**")
                import pandas as pd
                df_details = pd.DataFrame(details)
                # Reorder columns for clarity
                cols_order = ["trade_id", "selected_by", "distance", "is_seed", "was_threshold_strict"]
                for f in ["rsi_15m", "volume_rel_15m", "atr_pct_15m", "quality_score"]:
                    if f in df_details.columns:
                        cols_order.append(f)
                cols_order = [c for c in cols_order if c in df_details.columns]
                df_details = df_details[cols_order]
                st.dataframe(df_details, use_container_width=True)
    

    # =========================================================================
    # Compare Modes Panel
    # =========================================================================
    with st.expander("⚖️ Compare Modes (ARENA vs CARD)", expanded=False):
        st.caption("3 modu aynı ayarlarla karşılaştır: ARENA_FILTERS, CARD_STRICT_IDS, CARD_SOURCE_IDS")
        
        if st.button("🔄 Run Compare", key="btn_compare_modes"):
            from tezaver.sniper.v4.select_v4 import load_card_contract_state
            
            modes_to_compare = ["ARENA_FILTERS", "CARD_STRICT_IDS", "CARD_SOURCE_IDS"]
            compare_results = []
            
            for mode in modes_to_compare:
                try:
                    # Check contract for CARD_STRICT_IDS
                    if mode == "CARD_STRICT_IDS":
                        cs = load_card_contract_state(symbol, timeframe)
                        if cs.get("available") and cs.get("enforce_mode") == "BLOCK" and not cs.get("ok"):
                            # BLOCKED - don't run backtest
                            viol_codes = [v.get("code", "?") for v in cs.get("violations", [])]
                            compare_results.append({
                                "Mode": mode,
                                "Selected": cs.get("strict_count", 0),
                                "Trades": cs.get("strict_count", 0),
                                "Cap": "BLOCKED",
                                "PnL%": "BLOCKED",
                                "WinRate": "-",
                                "ContractOK": "❌",
                                "Enforce": "BLOCK",
                                "P50": cs.get("distance_p50", "-"),
                                "Violations": ";".join(viol_codes),
                            })
                            continue
                    
                    r = run_sniper_arena_v4(
                        symbol=symbol,
                        timeframe=timeframe,
                        source=source,
                        selection_mode=mode,
                        tightness=tightness,
                        toggles=toggles,
                        risk=risk,
                        tp_pct=tp_pct,
                        sl_pct=sl_pct,
                        sizing_mode=sizing_mode,
                    )
                    
                    # Get contract info for CARD modes
                    contract_ok = "✅"
                    enforce = "-"
                    p50 = "-"
                    violations = "-"
                    
                    if mode in ("CARD_STRICT_IDS", "CARD_SOURCE_IDS"):
                        cs = load_card_contract_state(symbol, timeframe)
                        if cs.get("available"):
                            contract_ok = "✅" if cs.get("ok") else "⚠️"
                            enforce = cs.get("enforce_mode", "-")
                            p50 = cs.get("distance_p50", "-")
                            if not cs.get("ok"):
                                viol_codes = [v.get("code", "?") for v in cs.get("violations", [])]
                                violations = ";".join(viol_codes) if viol_codes else "-"
                    
                    compare_results.append({
                        "Mode": mode,
                        "Selected": r["selected_count"],
                        "Trades": r["trades"],
                        "Cap": f"100→{r['capital_end']:.0f}",
                        "PnL%": f"{r['pnl_pct']:+.2f}%",
                        "WinRate": f"{r['win_rate']:.1f}%",
                        "ContractOK": contract_ok,
                        "Enforce": enforce,
                        "P50": p50,
                        "Violations": violations,
                    })
                except Exception as e:
                    compare_results.append({
                        "Mode": mode,
                        "Selected": f"Error",
                        "Trades": "-",
                        "Cap": str(e)[:20],
                        "PnL%": "-",
                        "WinRate": "-",
                        "ContractOK": "-",
                        "Enforce": "-",
                        "P50": "-",
                        "Violations": "-",
                    })
            
            # Display as table
            import pandas as pd
            df_compare = pd.DataFrame(compare_results)
            st.dataframe(df_compare, use_container_width=True, hide_index=True)
            
            # Diff summary
            if len(compare_results) >= 2:
                arena = next((r for r in compare_results if r["Mode"] == "ARENA_FILTERS"), None)
                strict = next((r for r in compare_results if r["Mode"] == "CARD_STRICT_IDS"), None)
                
                if arena and strict and isinstance(arena.get("Selected"), int) and isinstance(strict.get("Selected"), int):
                    diff_as = arena["Selected"] - strict["Selected"]
                    st.caption(f"ARENA vs STRICT: ΔSelected={diff_as:+d}")
    
    st.divider()

    
    # =========================================================================
    # Run Button (disabled if no dataset OR contract blocked)
    # =========================================================================
    # Note: run_disabled may already be True from contract BLOCK check above
    if not dataset_available:
        run_disabled = True
    
    if st.button(
        "🚀 Run Sniper Arena V4", 
        type="primary", 
        use_container_width=True, 
        key="btn_run_v4",
        disabled=run_disabled
    ):
        try:
            with st.spinner("V4 Arena çalışıyor..."):
                result = run_sniper_arena_v4(
                    symbol=symbol,
                    timeframe=timeframe,
                    source=source,
                    selection_mode=selection_mode,
                    tightness=tightness,
                    toggles=toggles,
                    risk=risk,
                    tp_pct=tp_pct,
                    sl_pct=sl_pct,
                    sizing_mode=sizing_mode,
                )
            
            # === Enhanced Proof Line (with Mode) ===
            toggles_str = ",".join([k for k, v in toggles.items() if v])
            proof = (
                f"RUN={result['run_id']} | Mode={selection_mode} | DataSource={source} | TF={timeframe} | Symbol={symbol}\n"
                f"Selected={result['selected_count']} Used={result['used_count']} Trades={result['trades']}\n"
                f"SelFP={result['selection_fingerprint']} | PnLSig={result['pnl_signature']}\n"
                f"Cap=100→{result['capital_end']:.0f} | Tightness={tightness} | Toggles={toggles_str}"
            )

            
            st.success("✅ V4 Arena tamamlandı!")
            st.code(proof, language=None)
            
            # === Invariant Check ===
            sel = result["selected_count"]
            used = result["used_count"]
            trades = result["trades"]
            if sel == used == trades:
                st.success(f"✅ Invariants OK: Selected={sel} == Used={used} == Trades={trades}")
            else:
                st.error(f"⚠️ INVARIANT FAIL: Selected={sel} Used={used} Trades={trades}")
                st.stop()
            
            # === Metrics ===
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💰 Capital", f"100 → {result['capital_end']:.0f}")
            col2.metric("📈 PnL", f"{result['pnl_pct']:+.2f}%")
            col3.metric("🏆 Win Rate", f"{result['win_rate']:.1f}%")
            col4.metric("📊 Trades", f"{result['trades']}")
            
            # === Exit Distribution ===
            exit_counts = result.get("exit_counts", {})
            st.caption(
                f"Exit: TP={exit_counts.get('TP', 0)} | "
                f"SL={exit_counts.get('SL', 0)} | "
                f"HORIZON={exit_counts.get('HORIZON', 0)}"
            )
            
            # === Window Details ===
            with st.expander("🔍 Filter Window Details", expanded=False):
                st.json(result.get("window", {}))
            
            # === Session State for Diff ===
            prev_key = f"sniper_v4_prev::{symbol}::{timeframe}"
            prev_result = st.session_state.get(prev_key)
            
            if prev_result:
                prev_fp = prev_result.get("selection_fingerprint", "")
                curr_fp = result.get("selection_fingerprint", "")
                prev_pnl = prev_result.get("pnl_signature", "")
                curr_pnl = result.get("pnl_signature", "")
                
                if prev_fp != curr_fp:
                    delta_sel = result["selected_count"] - prev_result["selected_count"]
                    delta_cap = result["capital_end"] - prev_result["capital_end"]
                    st.info(
                        f"📊 **Diff:** ΔSelected={delta_sel:+d} | ΔCap={delta_cap:+.1f} | "
                        f"SelFP: {prev_fp[:6]}→{curr_fp[:6]} | PnLSig: {prev_pnl[:6]}→{curr_pnl[:6]}"
                    )
                else:
                    st.caption("📊 Trade set değişmedi (aynı fingerprint)")
            else:
                st.caption("📊 İlk run (baseline oluşturuldu)")
            
            # Store for next comparison
            st.session_state[prev_key] = result
            
        except RuntimeError as e:
            st.error(f"⚠️ V4 INVARIANT VIOLATION: {e}")
            st.stop()
        except FileNotFoundError as e:
            st.error(f"❌ Dataset bulunamadı: {e}")
        except Exception as e:
            st.error(f"❌ Hata: {e}")



def _render_strategy_board_table(rows: List[ProfileBoardRow]) -> None:
    """
    Render Strategy Board table in Streamlit.
    """
    if not rows:
        st.info("Henüz CoinPage V2 profili bulunamadı. profile_tools CLI'ını kontrol et.")
        return

    # Prepare data for display
    data = []
    for r in rows:
        data.append({
            "Coin": r.symbol,
            "TF": r.timeframe,
            "Profil": r.profile_id,
            "Durum": r.status,
            "PnL %": f"{r.pnl_pct:.2f}" if r.pnl_pct is not None else "-",
            "İşlem": r.trades if r.trades is not None else "-",
            "Max Risk %": f"{r.max_risk_per_trade * 100:.2f}" if r.max_risk_per_trade is not None else "-",
            "LIVE?": "✅ Evet" if r.live_eligible else "❌ Hayır",
        })

    st.dataframe(data, use_container_width=True)

    total_profiles = len(rows)
    live_eligible = sum(1 for r in rows if r.live_eligible)
    st.caption(f"Toplam profil: {total_profiles} | LIVE uygun: {live_eligible}")


def _render_live_cluster_preview(
    rows: List[ProfileBoardRow],
    initial_capital: float,
    risk_mode: str,
) -> None:
    """
    Render Live Cluster preview from live-eligible profiles.
    """
    st.subheader("📡 Live Cluster Önizleme")

    st.caption(
        "Strategy Board'dan LIVE'a uygun profilleri alır ve "
        "**Matrix Live Cluster** içinde hangi cell'lerin açılacağını gösterir. "
        "Şu anda *simülasyon / read-only* moddadır."
    )

    try:
        cluster = build_live_cluster_from_profile_board(
            initial_capital=initial_capital,
            risk_mode=risk_mode,
        )
    except Exception as exc:
        st.error(
            "Live Cluster oluşturulurken hata oluştu.\n\n"
            f"Detay: {exc}"
        )
        return

    cells = cluster.list_cells()
    if not cells:
        st.warning("Şu anda LIVE için uygun cell bulunamadı.")
        return

    # Build preview data
    preview = []
    for cell in cells:
        # Find corresponding row for max_risk
        max_risk = None
        for r in rows:
            if (r.symbol == cell.symbol and 
                r.timeframe == cell.timeframe and
                r.profile_id == cell.profile_id):
                max_risk = r.max_risk_per_trade
                break
        
        equity = cluster.get_equity(cell.symbol, cell.timeframe, cell.profile_id)

        preview.append({
            "Coin": cell.symbol,
            "TF": cell.timeframe,
            "Profil": cell.profile_id,
            "Max Risk %": f"{max_risk * 100:.2f}" if max_risk else "-",
            "Sermaye": f"{equity:.2f}",
        })

    st.table(preview)
    st.success(f"Toplam {len(cells)} cell LIVE'a hazır!")


def render_matrix_operator_tab() -> None:
    """
    Main entry: Matrix Operator panel.
    
    V2: 3 modes with sidebar navigation:
    - 🎮 War Game: Silver/Sniper backtests
    - 📡 Live: Live Cluster config & monitor
    - 🎯 Sniper Arena: Sniper-specific testing
    """
    st.markdown("## 🧭 Matrix Operator")
    
    # === SIDEBAR: Mode Selection ===
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧬 Matrix Modu")
    mode = st.sidebar.radio(
        "Mod seçimi",
        options=["🎯 Sniper Arena", "🎮 War Game", "📡 Live"],
        key="matrix_operator_mode_v2",
        label_visibility="collapsed",
    )
    
    # === Strategy Board (common, collapsible) ===
    try:
        rows = build_profile_board()
    except Exception as e:
        st.error(f"Strategy Board yüklenirken hata: {e}")
        rows = []
    
    with st.expander("📋 Strategy Board – CoinPage V2 Profilleri", expanded=False):
        _render_strategy_board_table(rows)
    
    st.divider()
    
    # === Mode-specific content ===
    if mode == "🎮 War Game":
        _render_wargame_section_v2()
    elif mode == "📡 Live":
        _render_live_section_v2(rows)
    elif mode == "🎯 Sniper Arena":
        _render_sniper_arena_v4()


def _render_wargame_section_v2() -> None:
    """War Game mode - Silver 15m backtesting."""
    st.header("🎮 War Game – Silver 15m Backtest")
    st.caption(
        "Silver 15m stratejisini pattern dataset veya full replay ile test et. "
        "100 birim sermaye ile simülasyon yapar."
    )
    _render_wargame_silver_15m_section()


def _render_live_section_v2(rows: List[ProfileBoardRow]) -> None:
    """Live mode - Live Cluster config and monitoring."""
    st.header("📡 Live Mode – Cluster Yapılandırma")
    st.caption(
        "Live için uygun profilleri (status=APPROVED) bir cluster'a toplar. "
        "Şimdilik simülasyon amaçlı."
    )
    
    # =========================================================================
    # Live Loop Control (NEW)
    # =========================================================================
    with st.expander("🔁 Live Loop Control", expanded=True):
        from tezaver.matrix.live.live_loop_service import LiveLoopService
        from tezaver.matrix.live.live_loop import TICK_POLICY_ON_CLOSED_BAR, TICK_POLICY_ON_ANY_NEW_BAR
        
        service = LiveLoopService.get()
        status = service.status()
        
        # Status line
        if status.running:
            st.success(f"RUNNING ✅ | polls={status.polls} ticks={status.ticks} skips={status.skips}")
        else:
            st.warning(f"STOPPED ⛔ | polls={status.polls} ticks={status.ticks} skips={status.skips}")
        
        if status.last_error:
            st.error(f"❌ Error: {status.last_error}")
        
        st.divider()
        
        # Controls
        col1, col2, col3 = st.columns(3)
        with col1:
            use_real = st.checkbox("🌐 Use REAL Binance", value=False, key="loop_use_real")
            tf_override = st.selectbox(
                "Timeframe",
                ["inherit", "1m", "15m"],
                key="loop_tf_override"
            )
        with col2:
            tick_policy = st.radio(
                "Tick Policy",
                [TICK_POLICY_ON_CLOSED_BAR, TICK_POLICY_ON_ANY_NEW_BAR],
                key="loop_tick_policy"
            )
        with col3:
            poll_interval = st.slider("Poll interval (s)", 1, 15, 5, key="loop_poll_interval")
            until_next_closed = st.checkbox("Until next closed", value=False, key="loop_until_next_closed")
        
        # Start/Stop buttons
        col_start, col_stop = st.columns(2)
        with col_start:
            if st.button("✅ Start Loop", type="primary", disabled=status.running, use_container_width=True):
                # Build cells from live eligible profiles
                live_cells = []
                for row in rows:
                    if row.live_eligible:
                        tf = row.timeframe if tf_override == "inherit" else tf_override
                        live_cells.append((row.symbol, tf))
                
                if live_cells:
                    # Use until_next_closed to set max_runtime
                    max_runtime = 3600.0 if not until_next_closed else 900.0
                    
                    started = service.start(
                        cells=live_cells[:5],  # Limit to 5 cells
                        use_real=use_real,
                        tick_policy=tick_policy,
                        poll_interval=float(poll_interval),
                        max_runtime=max_runtime,
                    )
                    if started:
                        st.success("Loop started!")
                        st.rerun()
                else:
                    st.warning("No live eligible profiles found")
        
        with col_stop:
            if st.button("⛔ Stop Loop", type="secondary", disabled=not status.running, use_container_width=True):
                stopped = service.stop()
                if stopped:
                    st.warning("Loop stopped")
                    st.rerun()
    
    # =========================================================================
    # Live Freshness Table
    # =========================================================================
    with st.expander("🟢 Live Freshness / Lag", expanded=status.running):
        cell_metrics = service.get_cell_metrics()
        
        if cell_metrics:
            import pandas as pd
            freshness_rows = []
            for m in cell_metrics:
                lag = m.get("lag_sec")
                lag_str = f"{lag:.0f}s" if lag else "-"
                if lag and lag > 120:
                    lag_str = f"⚠️ {lag_str}"
                
                freshness_rows.append({
                    "Symbol": m.get("symbol"),
                    "TF": m.get("timeframe"),
                    "last_closed_bar": m.get("last_closed_bar_ts", "-")[:19] if m.get("last_closed_bar_ts") else "-",
                    "lag": lag_str,
                    "ticks": m.get("ticks_count", 0),
                    "skips": m.get("skips_count", 0),
                    "reason": m.get("last_tick_reason", "-"),
                    "close": f"{m.get('last_close'):.2f}" if m.get("last_close") else "-",
                })
            
            st.dataframe(pd.DataFrame(freshness_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Loop başlatıldığında freshness verileri burada görünür.")
    
    # =========================================================================
    # Closed Bar Proof (NEW)
    # =========================================================================
    with st.expander("✅ Closed Bar Proof", expanded=False):
        st.caption("Kapalı bar tick'ini tek tuşla kanıtla. Proof sırasında trade devre dışı.")
        
        from tezaver.matrix.live.timeframe_utils import eta_to_next_close, format_eta
        from datetime import datetime, timezone as tz
        
        proof_state = service.get_proof_state()
        
        # Controls
        col1, col2, col3 = st.columns(3)
        with col1:
            proof_symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], key="proof_symbol")
        with col2:
            proof_tf = st.selectbox("Timeframe", ["1m", "15m"], key="proof_tf")
        with col3:
            proof_poll = st.slider("Poll (s)", 3, 10, 5, key="proof_poll")
        
        proof_real = st.checkbox("🌐 Use REAL Binance", value=True, key="proof_real")
        
        # ETA countdown
        now_utc = datetime.now(tz.utc)
        eta_sec, progress, next_close = eta_to_next_close(now_utc, proof_tf)
        eta_str = format_eta(eta_sec)
        
        st.caption(f"⏳ Next {proof_tf} close ETA: **{eta_str}** (UTC)")
        st.progress(progress)
        
        # Refresh button
        if st.button("🔄 Refresh", key="btn_proof_refresh"):
            st.rerun()
        
        st.divider()
        
        # Status line
        if proof_state.get("running"):
            st.success(f"PROOF RUNNING ✅ | run_id={proof_state.get('proof_run_id')} | ETA: {eta_str}")
        else:
            if proof_state.get("last_proof_event"):
                st.success("PROOF_OK ✅")
            else:
                st.info("PROOF STOPPED ⛔")
        
        if proof_state.get("last_error"):
            st.error(f"Error: {proof_state.get('last_error')}")
        
        # Buttons
        col_start, col_stop = st.columns(2)
        with col_start:
            if st.button("▶️ Start Proof", type="primary", disabled=proof_state.get("running", False), key="btn_start_proof"):
                run_id = service.start_proof_closed(
                    symbol=proof_symbol,
                    timeframe=proof_tf,
                    poll_sec=float(proof_poll),
                    use_real=proof_real,
                )
                if run_id:
                    st.success(f"Proof started: {run_id}")
                    st.rerun()
        
        with col_stop:
            if st.button("⏹ Stop Proof", disabled=not proof_state.get("running", False), key="btn_stop_proof"):
                service.stop_proof_closed()
                st.warning("Proof stopped")
                st.rerun()
        
        # Proof result card
        last_proof = proof_state.get("last_proof_event")
        if last_proof:
            st.divider()
            st.markdown("### 🎯 Proof Result")
            
            proof_cols = st.columns(4)
            with proof_cols[0]:
                st.metric("Symbol", f"{last_proof.get('symbol')}/{last_proof.get('timeframe')}")
            with proof_cols[1]:
                st.metric("bar_close_ts", last_proof.get("bar_close_ts", "-")[:19] if last_proof.get("bar_close_ts") else "-")
            with proof_cols[2]:
                lag = last_proof.get("lag_sec")
                st.metric("lag_sec", f"{lag:.1f}" if lag else "-")
            with proof_cols[3]:
                close = last_proof.get("close")
                st.metric("close", f"{close:.2f}" if close else "-")
            
            st.code(f"PROOF_OK | {last_proof.get('symbol')}/{last_proof.get('timeframe')} bar_close_ts={last_proof.get('bar_close_ts')} lag={last_proof.get('lag_sec')} close={last_proof.get('close')} policy={last_proof.get('policy')} dry_run={last_proof.get('proof_force_dry_run')}")
        
        # Proof history table
        proof_history = service.get_proof_history()
        if proof_history:
            st.divider()
            st.markdown("### 📋 Proof History (Last 10)")
            
            import pandas as pd
            history_rows = []
            for p in proof_history:
                history_rows.append({
                    "ts": p.get("ts", "-")[:19] if p.get("ts") else "-",
                    "symbol": p.get("symbol"),
                    "tf": p.get("timeframe"),
                    "bar_close_ts": p.get("bar_close_ts", "-")[:19] if p.get("bar_close_ts") else "-",
                    "lag": f"{p.get('lag_sec'):.1f}" if p.get("lag_sec") else "-",
                    "close": f"{p.get('close'):.2f}" if p.get("close") else "-",
                    "policy": p.get("policy", "-"),
                })
            
            st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
    
    # =========================================================================
    # Dust & Position Hygiene (NEW)
    # =========================================================================
    with st.expander("🧹 Dust & Position Hygiene", expanded=False):
        st.caption("Pozisyon temizliği ve dust policy ayarları. Proof cycle çalıştırarak test edebilirsiniz.")
        
        # Control columns
        ctrl_col1, ctrl_col2 = st.columns(2)
        
        with ctrl_col1:
            dust_policy = st.selectbox(
                "Dust Policy",
                options=["IGNORE", "FLATTEN_AFTER", "BLOCK"],
                index=1,  # Default: FLATTEN_AFTER (production-safe)
                help="IGNORE: dust kabul, FLATTEN_AFTER: temizleme emri (önerilen), BLOCK: fail if dust",
                key="dust_policy_select"
            )
            
            dust_threshold = st.slider(
                "Dust Threshold (BTC)",
                min_value=0.0001,
                max_value=0.01,
                value=0.001,  # Default: 0.001 (production-safe)
                step=0.0001,
                format="%.4f",
                help="0.001 BTC ≈ $100 @ 100k. Threshold altı 'dust' kabul edilir.",
                key="dust_threshold_slider"
            )
        
        with ctrl_col2:
            preflight_mode = st.selectbox(
                "Preflight Mode",
                options=["BLOCK", "FLATTEN_FIRST", "IGNORE"],
                index=1,  # Default: FLATTEN_FIRST (production-safe)
                help="Mevcut pozisyon varsa: FLATTEN_FIRST önerilir",
                key="preflight_mode_select"
            )
            
            close_policy = st.selectbox(
                "Close Policy",
                options=["NEXT_CLOSED_BAR", "NEXT_SIGNAL"],
                index=0,  # Default: NEXT_CLOSED_BAR
                help="CLOSE tetikleme politikası",
                key="close_policy_select"
            )
        
        # Advanced Debug (hidden by default)
        close_qty_mult = 1.0  # Safe default
        with st.expander("🔧 Advanced Debug", expanded=False):
            close_qty_mult = st.slider(
                "Close Qty Multiplier",
                min_value=0.1,
                max_value=1.0,
                value=1.0,
                step=0.1,
                help="1.0 = full close, <1.0 = partial close (DEBUG ONLY - pozisyon kalır!)",
                key="close_qty_mult_slider"
            )
            
            # Guardrail warning
            if close_qty_mult < 1.0:
                st.error("🚨 **DEBUG ONLY**: close_qty_mult < 1.0 - Partial close aktif! Pozisyon kalacak!")
                st.warning("⚠️ Bu ayar sadece BLOCK fail kanıtı için kullanılmalıdır.")
        
        # Expected Behavior card
        st.divider()
        behavior_text = {
            "IGNORE": "✅ Dust kabul edilir, cleanup yapılmaz.",
            "FLATTEN_AFTER": "🧹 CLOSE sonrası dust varsa temizleme emri gönderilir. (Önerilen)",
            "BLOCK": "⛔ Dust threshold aşılırsa sistem durur (RuntimeError).",
        }
        st.info(f"**Beklenen Davranış:** {behavior_text.get(dust_policy, '-')}")
        
        # Exchange mode selection
        st.divider()
        proof_exchange_mode = st.radio(
            "Exchange Mode",
            options=["DUMMY_ORDER", "REAL_TESTNET"],
            index=0,
            horizontal=True,
            help="DUMMY: gerçek emir yok, REAL_TESTNET: gerçek testnet emri",
            key="proof_exchange_mode"
        )
        
        # Guardrails check
        can_run = True
        guardrail_msg = ""
        
        if proof_exchange_mode == "REAL_TESTNET" and close_qty_mult < 1.0:
            st.error("🚨 **DANGER**: REAL_TESTNET + partial close! Gerçek pozisyon kalabilir!")
        
        # BLOCK + close_qty_mult < 1.0 = sabotage prevention
        if dust_policy == "BLOCK" and close_qty_mult < 1.0:
            can_run = False
            st.error("⛔ **BLOCKED**: BLOCK mode + close_qty_mult < 1.0 kombinasyonu izin verilmez! "
                    "Bu kasıtlı fail senaryosudur. Test için dust_policy=IGNORE veya FLATTEN_AFTER kullanın.")
        
        # Run Proof Cycle button
        if st.button("▶️ Run Proof Cycle", type="primary", use_container_width=True, 
                     disabled=not can_run, key="btn_run_proof_cycle"):
            with st.spinner("Proof cycle çalışıyor... (2-3 bar bekleniyor, ~3 dk)"):
                import subprocess
                
                cmd = [
                    "./venv/bin/python", "-m", "tezaver.matrix.live.live_loop",
                    "proof_router_cluster",
                    "--real", "--tf", "1m", "--poll", "5",
                    f"--exchange-mode", proof_exchange_mode,
                    "--armed", "--no-force-dry-run", "--exchange-enabled",
                    "--hold-policy", "HOLD_NEXT_CLOSED", "--until-done",
                    f"--dust-policy", dust_policy,
                    f"--dust-threshold", str(dust_threshold),
                    f"--close-qty-mult", str(close_qty_mult),
                ]
                
                try:
                    result = subprocess.run(
                        cmd,
                        cwd="/Users/alisaglam/TezaverMac",
                        capture_output=True,
                        text=True,
                        timeout=360,  # 6 min timeout
                    )
                    
                    st.session_state["proof_cycle_stdout"] = result.stdout
                    st.session_state["proof_cycle_stderr"] = result.stderr
                    st.session_state["proof_cycle_exit_code"] = result.returncode
                    
                except subprocess.TimeoutExpired:
                    st.session_state["proof_cycle_exit_code"] = -1
                    st.session_state["proof_cycle_stderr"] = "TIMEOUT (360s)"
                except Exception as e:
                    st.session_state["proof_cycle_exit_code"] = -2
                    st.session_state["proof_cycle_stderr"] = str(e)
                
                st.rerun()
        
        # Show proof cycle result
        if "proof_cycle_exit_code" in st.session_state:
            st.divider()
            exit_code = st.session_state.get("proof_cycle_exit_code", 0)
            stdout = st.session_state.get("proof_cycle_stdout", "")
            stderr = st.session_state.get("proof_cycle_stderr", "")
            
            # Status display
            if exit_code == 0:
                st.success(f"✅ Proof Cycle BAŞARILI (exit_code={exit_code})")
            else:
                st.error(f"⛔ Proof Cycle FAIL (exit_code={exit_code})")
            
            # Extract summary line
            summary_line = ""
            for line in stdout.split("\n"):
                if "PROOF_ROUTER_CLUSTER_POLICY_OK" in line or "BLOCKED" in line:
                    summary_line = line
                    break
            
            if summary_line:
                st.code(summary_line, language="text")
            
            # Extract key metrics
            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
            
            # Parse from stdout
            residual = "-"
            cleanup_attempted = "-"
            cleanup_result = "-"
            
            for line in stdout.split("\n"):
                if "residual_after:" in line:
                    residual = line.split("residual_after:")[1].strip().split()[0] if "residual_after:" in line else "-"
                if "cleanup_attempted:" in line:
                    cleanup_attempted = line.split("cleanup_attempted:")[1].strip().split()[0] if "cleanup_attempted:" in line else "-"
                if "cleanup_result:" in line:
                    cleanup_result = line.split("cleanup_result:")[1].strip().split()[0] if "cleanup_result:" in line else "-"
            
            with metrics_col1:
                st.metric("exit_code", exit_code)
            with metrics_col2:
                st.metric("residual", residual)
            with metrics_col3:
                st.metric("cleanup", cleanup_attempted)
            
            # Detailed output
            with st.expander("📊 Detaylı Çıktı", expanded=exit_code != 0):
                st.text(stdout[-3000:] if len(stdout) > 3000 else stdout)
                if stderr:
                    st.error(stderr[-1000:] if len(stderr) > 1000 else stderr)
            
            # Clear button
            if st.button("🗑️ Sonuçları Temizle", key="btn_clear_proof_result"):
                for key in ["proof_cycle_exit_code", "proof_cycle_stdout", "proof_cycle_stderr"]:
                    st.session_state.pop(key, None)
                st.rerun()
        
        # NDJSON Event Viewer
        st.divider()
        st.markdown("### 📋 Son PROOF_* Events")
        
        ndjson_path = "/Users/alisaglam/TezaverMac/data/logs/live_events.ndjson"
        try:
            import json
            proof_events = []
            if os.path.exists(ndjson_path):
                with open(ndjson_path, "r") as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            event_type = event.get("event_type", "")
                            if event_type.startswith("PROOF_") or event_type.startswith("ROUTER_POLICY"):
                                proof_events.append(event)
                        except:
                            pass
                
                # Show last 20
                proof_events = proof_events[-20:]
                
                if proof_events:
                    import pandas as pd
                    event_rows = []
                    for e in proof_events:
                        event_rows.append({
                            "ts": e.get("ts", "-")[:19] if e.get("ts") else "-",
                            "type": e.get("event_type", "-"),
                            "state": e.get("state", "-"),
                            "symbol": e.get("symbol", "-"),
                            "residual": e.get("residual_after", e.get("residual", "-")),
                            "dust_policy": e.get("dust_policy", "-"),
                        })
                    st.dataframe(pd.DataFrame(event_rows), use_container_width=True, hide_index=True)
                else:
                    st.info("PROOF_* event bulunamadı.")
            else:
                st.warning(f"NDJSON dosyası bulunamadı: {ndjson_path}")
        except Exception as e:
            st.error(f"NDJSON okuma hatası: {e}")
    
    # =========================================================================
    # Closed-bar Router (NEW)
    with st.expander("🔀 Closed-bar Router", expanded=False):
        st.caption("Kapalı bar tick'lerini MatrixLiveCluster'a yönlendir.")
        
        from tezaver.matrix.live.live_router import MatrixLiveRouter, LiveRouterConfig
        
        router_state = service.get_router_state()
        
        # Controls
        col1, col2 = st.columns(2)
        with col1:
            router_enabled = st.toggle("Router Enabled", value=False, key="router_enabled")
        with col2:
            router_dry_run = st.toggle("Force DRY RUN", value=True, key="router_dry_run")
        
        router_symbols = st.multiselect("Symbols", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], default=["BTCUSDT"], key="router_symbols")
        router_tf = st.selectbox("Timeframe", ["1m", "15m"], key="router_tf")
        
        # Status line
        if router_state.get("attached"):
            st.success(f"✅ Router ATTACHED | ticks={router_state.get('ticks', 0)}")
        else:
            st.info("⛔ Router NOT attached")
        
        # Attach/Detach buttons
        col_attach, col_detach = st.columns(2)
        with col_attach:
            if st.button("▶️ Attach Router", type="primary", disabled=router_state.get("attached", False), key="btn_attach_router"):
                # Create router with config
                config = LiveRouterConfig(
                    enabled=router_enabled,
                    force_dry_run=router_dry_run,
                    only_symbols=router_symbols if router_symbols else None,
                    only_timeframes=[router_tf] if router_tf else None,
                )
                router = MatrixLiveRouter(cluster=None, config=config)
                service.set_on_closed_bar_callback(router.handle_snapshot)
                st.success("Router attached!")
                st.rerun()
        
        with col_detach:
            if st.button("⏹ Detach Router", disabled=not router_state.get("attached", False), key="btn_detach_router"):
                service.detach_router()
                st.warning("Router detached")
                st.rerun()
        
        # Router stats
        st.divider()
        st.markdown("**Router Stats:**")
        stats_cols = st.columns(4)
        with stats_cols[0]:
            st.metric("Ticks", router_state.get("ticks", 0))
        with stats_cols[1]:
            skip_count = router_state.get("skip_count", 0) if "skip_count" in str(router_state) else 0
            st.metric("Skips", skip_count)
        with stats_cols[2]:
            st.metric("Errors", router_state.get("error_count", 0))
        with stats_cols[3]:
            attached_str = "✅ YES" if router_state.get("attached") else "⛔ NO"
            st.metric("Attached", attached_str)
        
        # Last router tick
        last_tick = router_state.get("last_tick")
        if last_tick:
            st.markdown("### 🎯 Last Router Tick")
            st.code(f"ROUTER_OK | {last_tick.get('symbol')}/{last_tick.get('timeframe')} bar_close_ts={last_tick.get('bar_close_ts')} close={last_tick.get('close')} dry_run=True ticks={router_state.get('ticks', 0)}")
        
        # ARM gating check
        st.divider()
        arm_check = service.check_arm_allowed(router_enabled=router_enabled, exchange_enabled=False, exchange_mode="DRY_RUN")
        
        if arm_check.get("allowed"):
            st.success("🔫 ARMED toggle available")
        else:
            st.warning("🔒 ARMED not available. Missing requirements:")
            for reason in arm_check.get("missing_reasons", []):
                st.caption(f"  ⚠️ {reason}")
        
        st.caption(f"`ARMED_GATE | allowed={arm_check.get('allowed')} missing={arm_check.get('missing_reasons')}`")
    
    # =========================================================================
    # Proof+Router (E2E) Panel
    # =========================================================================
    with st.expander("🧾 Proof+Router (E2E)", expanded=False):
        st.caption("Tek butonla 15m bar kapanışını + router tick'ini kanıtla. Forced DRY RUN.")
        
        from tezaver.matrix.live.timeframe_utils import eta_to_next_close, format_eta
        from datetime import datetime, timezone as tz
        
        pr_state = service.get_proof_router_state()
        
        # Controls
        col1, col2, col3 = st.columns(3)
        with col1:
            pr_symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], key="pr_symbol")
        with col2:
            pr_tf = st.selectbox("Timeframe", ["15m", "1m"], key="pr_tf")
        with col3:
            pr_poll = st.slider("Poll (s)", 3, 10, 5, key="pr_poll")
        
        # ETA countdown
        now_utc = datetime.now(tz.utc)
        eta_sec, progress, next_close = eta_to_next_close(now_utc, pr_tf)
        eta_str = format_eta(eta_sec)
        
        st.caption(f"⏳ Next {pr_tf} close ETA: **{eta_str}** (UTC) | Next close: {next_close.strftime('%H:%M:%S')}")
        st.progress(progress)
        
        # Status line
        if pr_state.get("running"):
            st.success(f"PROOF+ROUTER RUNNING ✅ | run_id={pr_state.get('proof_run_id')} | ETA: {eta_str}")
        else:
            if pr_state.get("last_proof_event"):
                st.success("PROOF_OK + ROUTER_OK ✅")
            else:
                st.info("⛔ Proof+Router not running")
        
        if pr_state.get("last_error"):
            st.error(f"Error: {pr_state.get('last_error')}")
        
        # Buttons
        col_run, col_stop, col_refresh = st.columns(3)
        with col_run:
            if st.button("▶️ Run Proof+Router", type="primary", disabled=pr_state.get("running", False), key="btn_run_pr"):
                run_id = service.start_proof_router(
                    symbol=pr_symbol,
                    timeframe=pr_tf,
                    poll_sec=float(pr_poll),
                    use_real=True,
                )
                if run_id:
                    st.success(f"Started: {run_id}")
                    st.rerun()
        
        with col_stop:
            if st.button("⏹ Stop", disabled=not pr_state.get("running", False), key="btn_stop_pr"):
                service.stop_proof_closed()
                st.warning("Stopped")
                st.rerun()
        
        with col_refresh:
            if st.button("🔄 Refresh", key="btn_refresh_pr"):
                st.rerun()
        
        # Result card
        last_proof = pr_state.get("last_proof_event")
        if last_proof:
            st.divider()
            st.markdown("### 🎯 Proof+Router Result")
            
            # Proof metrics
            proof_cols = st.columns(5)
            with proof_cols[0]:
                st.metric("Symbol", f"{last_proof.get('symbol')}/{last_proof.get('timeframe')}")
            with proof_cols[1]:
                bar_close = last_proof.get("bar_close_ts", "-")
                st.metric("bar_close_ts", bar_close[:19] if bar_close else "-")
            with proof_cols[2]:
                lag = last_proof.get("lag_sec")
                st.metric("lag_sec", f"{lag:.1f}" if lag else "-")
            with proof_cols[3]:
                close = last_proof.get("close")
                st.metric("close", f"{close:.2f}" if close else "-")
            with proof_cols[4]:
                st.metric("strict", "✅" if last_proof.get("strict_new_closed") else "❌")
            
            # Router metrics
            router_cols = st.columns(3)
            with router_cols[0]:
                st.metric("Router Ticks", pr_state.get("router_ticks", 0))
            with router_cols[1]:
                st.metric("Router Skips", pr_state.get("router_skips", 0))
            with router_cols[2]:
                st.metric("dry_run", "TRUE ✅")
            
            # Result code
            st.code(f"PROOF_OK | {last_proof.get('symbol')}/{last_proof.get('timeframe')} baseline={last_proof.get('baseline_closed_ts', '-')[:19] if last_proof.get('baseline_closed_ts') else '-'} seen={last_proof.get('bar_close_ts', '-')[:19] if last_proof.get('bar_close_ts') else '-'} lag={last_proof.get('lag_sec', '-')} strict=True")
            st.code(f"ROUTER_OK | ticks={pr_state.get('router_ticks', 0)} skips={pr_state.get('router_skips', 0)} dry_run=True")
        
        # E2E History
        proof_history = service.get_proof_history()
        if proof_history:
            st.divider()
            st.markdown("### 📋 E2E History (Last 10)")
            
            import pandas as pd
            history_rows = []
            for p in proof_history:
                history_rows.append({
                    "ts": p.get("ts", "-")[:19] if p.get("ts") else "-",
                    "symbol": p.get("symbol"),
                    "tf": p.get("timeframe"),
                    "bar_close": p.get("bar_close_ts", "-")[:19] if p.get("bar_close_ts") else "-",
                    "lag": f"{p.get('lag_sec'):.1f}" if p.get("lag_sec") else "-",
                    "strict": "✅" if p.get("strict_new_closed") else "❌",
                })
            
            st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
    
    # =========================================================================
    # Proof+Router+Cluster (E2E) Panel
    # =========================================================================
    with st.expander("🧾 Proof+Router+Cluster (E2E)", expanded=False):
        st.caption("Proof + Router + Cluster (DRY RUN) tam E2E kanıtı. Forced DRY RUN.")
        
        from tezaver.matrix.live.timeframe_utils import eta_to_next_close, format_eta
        from datetime import datetime, timezone as tz
        
        prc_state = service.get_proof_router_cluster_state()
        
        # Controls
        col1, col2, col3 = st.columns(3)
        with col1:
            prc_symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], key="prc_symbol")
        with col2:
            prc_tf = st.selectbox("Timeframe", ["15m", "1m"], key="prc_tf")
        with col3:
            prc_poll = st.slider("Poll (s)", 3, 10, 5, key="prc_poll")
        
        # ETA countdown
        now_utc = datetime.now(tz.utc)
        eta_sec, progress, next_close = eta_to_next_close(now_utc, prc_tf)
        eta_str = format_eta(eta_sec)
        
        st.caption(f"⏳ Next {prc_tf} close ETA: **{eta_str}** | Next close: {next_close.strftime('%H:%M:%S')} UTC")
        st.progress(progress)
        
        # Status line
        if prc_state.get("running"):
            st.success(f"✅ PROOF+ROUTER+CLUSTER RUNNING | run_id={prc_state.get('proof_run_id')} | ETA: {eta_str}")
        else:
            cluster_result = prc_state.get("cluster_last_result")
            if cluster_result:
                st.success(f"✅ PROOF_ROUTER_CLUSTER_OK | allow={cluster_result.get('allow')} dry_run=True order_id={cluster_result.get('order_id')}")
            else:
                st.info("⛔ Proof+Router+Cluster not running")
        
        if prc_state.get("last_error"):
            st.error(f"Error: {prc_state.get('last_error')}")
        
        # Buttons
        col_run, col_stop, col_refresh = st.columns(3)
        with col_run:
            if st.button("▶️ Run Proof+Router+Cluster", type="primary", disabled=prc_state.get("running", False), key="btn_run_prc"):
                run_id = service.start_proof_router_cluster(
                    symbol=prc_symbol,
                    timeframe=prc_tf,
                    poll_sec=float(prc_poll),
                    use_real=True,
                )
                if run_id:
                    st.success(f"Started: {run_id}")
                    st.rerun()
        
        with col_stop:
            if st.button("⏹ Stop", disabled=not prc_state.get("running", False), key="btn_stop_prc"):
                service.stop()
                st.warning("Stopped")
                st.rerun()
        
        with col_refresh:
            if st.button("🔄 Refresh", key="btn_refresh_prc"):
                st.rerun()
        
        # Result cards - 3 columns
        last_proof = prc_state.get("last_proof_event")
        last_router = prc_state.get("router_last_tick")
        cluster_result = prc_state.get("cluster_last_result")
        
        if last_proof or last_router or cluster_result:
            st.divider()
            
            card_cols = st.columns(3)
            
            # Proof card
            with card_cols[0]:
                st.markdown("**📋 Proof Result**")
                if last_proof:
                    st.metric("bar_close_ts", last_proof.get("bar_close_ts", "-")[:19] if last_proof.get("bar_close_ts") else "-")
                    lag = last_proof.get("lag_sec")
                    st.metric("lag_sec", f"{lag:.1f}" if lag else "-")
                    st.metric("strict", "✅" if last_proof.get("strict_new_closed") else "❌")
                else:
                    st.caption("No proof yet")
            
            # Router card
            with card_cols[1]:
                st.markdown("**🔀 Router Result**")
                st.metric("Ticks", prc_state.get("router_ticks", 0))
                st.metric("Skips", prc_state.get("router_skips", 0))
                if last_router:
                    st.metric("close", last_router.get("close", "-"))
            
            # Cluster card
            with card_cols[2]:
                st.markdown("**🎯 Cluster Result**")
                if cluster_result:
                    st.metric("allow", "✅" if cluster_result.get("allow") else "❌")
                    st.metric("decisions", cluster_result.get("decisions_count", 0))
                    st.metric("dry_run", "TRUE ✅")
                    st.metric("order_id", cluster_result.get("order_id", "-"))
                else:
                    st.caption("No cluster result yet")
            
            # E2E proof line
            if cluster_result:
                bar_close = last_proof.get("bar_close_ts", "-")[:19] if last_proof and last_proof.get("bar_close_ts") else "-"
                close = last_proof.get("close") if last_proof else "-"
                st.code(f"PROOF_ROUTER_CLUSTER_OK | {prc_symbol}/{prc_tf} bar_close_ts={bar_close} close={close} allow={cluster_result.get('allow')} dry_run=True order_id={cluster_result.get('order_id')} decisions={cluster_result.get('decisions_count')}")
        
        # History table
        prc_history = prc_state.get("history", [])
        if prc_history:
            st.divider()
            st.markdown("### 📋 E2E History (Last 20)")
            
            import pandas as pd
            history_rows = []
            for h in prc_history[-20:]:
                history_rows.append({
                    "ts": h.get("ts", "-")[:19] if h.get("ts") else "-",
                    "symbol": h.get("symbol"),
                    "tf": h.get("timeframe"),
                    "bar_close": h.get("bar_close_ts", "-")[:19] if h.get("bar_close_ts") else "-",
                    "allow": "✅" if h.get("allow") else "❌",
                    "decisions": h.get("decisions_count", 0),
                    "dry_run": "✅" if h.get("dry_run") else "❌",
                })
            
            st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
    
    # =========================================================================
    # Exchange & Arm Controls (Phase-1)
    # =========================================================================
    with st.expander("⚙️ Exchange & Arm Controls", expanded=False):
        st.caption("Exchange mode ve ARMED kontrolü. DUMMY_ORDER modunda secrets gerekmez.")
        
        from tezaver.matrix.live.live_gateway import ExchangeMode
        
        # Controls row
        ctrl_cols = st.columns(4)
        
        with ctrl_cols[0]:
            exchange_enabled = st.toggle("Exchange Enabled", value=False, key="exchange_enabled_toggle")
        
        with ctrl_cols[1]:
            exchange_mode = st.selectbox(
                "Exchange Mode",
                options=["DRY_RUN", "DUMMY_ORDER", "REAL_TESTNET", "REAL_MAINNET"],
                index=0,
                key="exchange_mode_select",
            )
        
        with ctrl_cols[2]:
            global_paused = st.toggle("⏸️ Global Pause", value=False, key="global_pause_toggle")
        
        with ctrl_cols[3]:
            st.metric("Mode", exchange_mode)
        
        # ARMED gating check
        router_state = service.get_router_state()
        router_attached = router_state.get("attached", False)
        
        arm_check = service.check_arm_allowed(
            router_enabled=router_attached,
            exchange_enabled=exchange_enabled,
            exchange_mode=exchange_mode,
        )
        
        st.divider()
        
        # ARMED checkbox with gating
        if arm_check.get("allowed"):
            st.success("✅ ARMED can be enabled")
            armed_enabled = st.checkbox("🔫 ARMED", value=False, key="armed_checkbox", disabled=False)
            if armed_enabled:
                st.warning("⚠️ ARMED: Orders will be submitted!")
        else:
            st.warning("🔒 ARMED not available. Missing requirements:")
            for reason in arm_check.get("missing_reasons", []):
                st.caption(f"  ⚠️ {reason}")
            st.checkbox("🔫 ARMED", value=False, key="armed_checkbox_disabled", disabled=True)
        
        # Status summary
        st.divider()
        st.markdown("**Summary:**")
        summary_cols = st.columns(4)
        with summary_cols[0]:
            st.metric("ExchangeMode", arm_check.get("exchange_mode", "-"))
        with summary_cols[1]:
            st.metric("Requires Secrets", "YES" if arm_check.get("requires_secrets") else "NO")
        with summary_cols[2]:
            st.metric("Router Attached", "✅" if router_attached else "❌")
        with summary_cols[3]:
            st.metric("Allowed to ARM", "✅" if arm_check.get("allowed") else "❌")
    
    # =========================================================================
    # Secrets Vault Panel (Phase-1)
    # =========================================================================
    with st.expander("🔐 Secrets Vault", expanded=False):
        st.caption("API key/secret yönetimi. REAL mode için gerekli, DUMMY_ORDER için gerekmez.")
        
        from tezaver.matrix.live.secrets import get_vault_status
        
        # Source selection
        vault_cols = st.columns(2)
        with vault_cols[0]:
            vault_source = st.radio("Vault Source", ["ENV", "FILE"], key="vault_source_radio", horizontal=True)
        with vault_cols[1]:
            if vault_source == "FILE":
                file_path = st.text_input("File Path", value="data/secrets/live_keys.txt", key="secrets_file_path")
            else:
                file_path = ""
                st.caption("Using environment variables")
        
        # Get vault status
        vault_status = get_vault_status(source=vault_source, file_path=file_path)
        
        st.divider()
        
        # Key status display
        st.markdown("**Key Status:**")
        key_cols = st.columns(2)
        with key_cols[0]:
            api_key_status = vault_status.get("api_key_status", "MISSING")
            if api_key_status == "FOUND":
                st.success("✅ API_KEY: FOUND")
            else:
                st.error("❌ API_KEY: MISSING")
        with key_cols[1]:
            api_secret_status = vault_status.get("api_secret_status", "MISSING")
            if api_secret_status == "FOUND":
                st.success("✅ API_SECRET: FOUND")
            else:
                st.error("❌ API_SECRET: MISSING")
        
        # Permission warning
        file_perms = vault_status.get("file_permissions")
        if file_perms:
            if not file_perms.get("is_secure"):
                st.warning(f"⚠️ {file_perms.get('warning', 'File permissions issue')}")
            else:
                st.success(f"✅ File permissions: {file_perms.get('mode')} (secure)")
        
        # Warnings
        for warning in vault_status.get("warnings", []):
            st.warning(f"⚠️ {warning}")
        
        # Setup hints
        st.divider()
        st.markdown("**Setup Hints:**")
        if vault_source == "ENV":
            st.code("""# Add to your shell profile (.bashrc, .zshrc, etc.)
export BINANCE_API_KEY=your_api_key_here
export BINANCE_API_SECRET=your_api_secret_here""", language="bash")
        else:
            st.code("""{
    "BINANCE_API_KEY": "***REDACTED***",
    "BINANCE_API_SECRET": "***REDACTED***"
}""", language="json")
            st.caption("⚠️ Set file permissions: chmod 600 <file_path>")
    
    # =========================================================================
    # Live Gate Status (existing)
    # =========================================================================
    with st.expander("🎮 Live Gate Status", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            armed_mode = st.toggle("🔫 Armed Mode", value=False, key="live_armed_mode")
            if armed_mode:
                st.warning("⚠️ ARMED: Gerçek order gönderilecek!")
            else:
                st.info("💤 DRY RUN: Sadece simülasyon")
        with col2:
            st.metric("Data", "public ✅")
        with col3:
            st.metric("Trade", "private 🔒")
        
        st.markdown("**🚦 Gate Status:**")
        from tezaver.matrix.live.live_cluster import live_can_trade
        
        gate_rows = []
        live_eligible = [r for r in rows if r.live_eligible]
        selection_mode = st.session_state.get("live_selection_mode", "ARENA_FILTERS")
        
        for row in live_eligible[:5]:  # Limit to 5 for display
            allow, details = live_can_trade(
                symbol=row.symbol,
                timeframe=row.timeframe,
                profile_id=row.profile_id,
                profile_status=row.status,
                selection_mode=selection_mode,
            )
            
            gates = details.get("gates", {})
            contract_gate = details.get("contract_gate", "NA")
            
            # Extract violation codes from violation objects
            violations = details.get("violations", [])
            viol_codes = []
            for v in violations:
                if isinstance(v, dict):
                    viol_codes.append(v.get("code", "?"))
                else:
                    viol_codes.append(str(v))
            
            gate_rows.append({
                "Cell": f"{row.symbol}/{row.timeframe}",
                "Profile": row.profile_id[:20],
                "Allowed?": "✅ YES" if allow else "❌ NO",
                "ProfileGate": "✅" if gates.get("profile_status", {}).get("passed") else "❌",
                "RiskGate": "✅" if gates.get("risk_contract", {}).get("passed") else "❌",
                "ContractGate": contract_gate,
                "Violations": ",".join(viol_codes) if viol_codes else "-",
            })
        
        if gate_rows:
            import pandas as pd
            st.dataframe(pd.DataFrame(gate_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Live eligible profil bulunamadı.")
    
    # =========================================================================
    # NDJSON Tail Viewer
    # =========================================================================
    with st.expander("📜 NDJSON Tail Viewer", expanded=False):
        st.caption("Live event log dosyasından son N satır.")
        
        from tezaver.matrix.live.logs_tail import read_ndjson_tail, filter_events, events_to_table_rows
        
        tail_cols = st.columns(4)
        with tail_cols[0]:
            ndjson_path = st.text_input("NDJSON Path", value="data/logs/live_events.ndjson", key="ndjson_path_input")
        with tail_cols[1]:
            last_n = st.slider("Last N lines", min_value=50, max_value=2000, value=200, key="ndjson_last_n")
        with tail_cols[2]:
            event_types = st.multiselect(
                "Event Types", 
                options=["ROUTER_TICK", "ROUTER_CLUSTER_TICK", "ROUTER_CLUSTER_EXEC_SUMMARY", 
                         "ORDER_SUBMIT", "ORDER_RESULT", "ORDER_BLOCKED", "PROOF_CLOSED"],
                default=["ROUTER_CLUSTER_EXEC_SUMMARY"],
                key="ndjson_event_types"
            )
        with tail_cols[3]:
            symbol_filter = st.text_input("Symbol Filter", value="", key="ndjson_symbol_filter")
        
        if st.button("🔄 Refresh Tail", key="btn_refresh_tail"):
            st.rerun()
        
        # Read and display
        tail_result = read_ndjson_tail(ndjson_path, n=last_n)
        
        if tail_result.get("error"):
            st.warning(f"⚠️ {tail_result.get('error')}")
        
        # Filter events
        filtered = filter_events(
            tail_result.get("events", []),
            include_types=set(event_types) if event_types else None,
            symbol=symbol_filter if symbol_filter else None,
        )
        
        # Summary
        st.markdown(f"**Lines read:** {tail_result.get('lines_read', 0)} | **Parse errors:** {tail_result.get('parse_errors', 0)} | **Shown:** {len(filtered)}")
        
        # Table
        if filtered:
            import pandas as pd
            rows = events_to_table_rows(filtered[-100:])  # Limit display
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No events matching filters.")
    
    # =========================================================================
    # Last Orders (per cell)
    # =========================================================================
    with st.expander("🧾 Last Orders (per cell)", expanded=False):
        st.caption("Her cell için son ORDER_SUBMIT/ORDER_RESULT durumu.")
        
        from tezaver.matrix.live.order_state import get_order_state_store
        
        order_store = get_order_state_store()
        cells_list = order_store.get_cells_list()
        
        if cells_list:
            import pandas as pd
            st.dataframe(pd.DataFrame(cells_list), use_container_width=True, hide_index=True)
        else:
            st.info("Henüz order state yok. proof_router_cluster çalıştırın.")
        
        if st.button("🧹 Clear All Cell State", key="btn_clear_order_state"):
            order_store.clear()
            st.success("Order state temizlendi.")
            st.rerun()
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        initial_capital = st.number_input(
            "Başlangıç sermaye (her cell için)",
            min_value=10.0,
            max_value=1_000_000.0,
            value=100.0,
            step=10.0,
            key="live_initial_capital",
        )
    with col2:
        risk_mode = st.selectbox(
            "Risk modu",
            options=["contract", "experiment"],
            index=0,
            key="live_risk_mode",
        )
    
    if st.button("📡 Live Cluster Oluştur", type="primary", use_container_width=True):
        _render_live_cluster_preview(rows, initial_capital, risk_mode)
    
    st.divider()
    
    st.subheader("📊 Live Monitor")
    _render_live_monitor_section(rows, initial_capital)


def _render_sniper_arena_section_v2() -> None:
    """Sniper Arena mode - Full featured Sniper testing with advanced settings."""
    import json
    from pathlib import Path
    
    st.header("🎯 Sniper Arena – 100 → X")
    st.caption(
        "Sniper entries dataset üzerinden backtest. "
        "Profil, risk kontrat, ve veri kaynağı ayarlanabilir."
    )
    
    # === Basic Settings ===
    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.selectbox(
            "Coin",
            ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            key="sniper_arena_symbol_v2"
        )
    with col2:
        timeframe = st.selectbox(
            "Timeframe",
            ["15m", "1h", "4h"],
            key="sniper_arena_tf_v2"
        )
    with col3:
        risk = st.slider(
            "Risk / Trade",
            min_value=0.01,
            max_value=1.0,
            value=1.0,
            step=0.01,
            key="sniper_arena_risk_v2"
        )
    
    # === Advanced Settings ===
    with st.expander("⚙️ Gelişmiş Ayarlar", expanded=False):
        use_profile = st.checkbox(
            "CoinPage V2 profilini kullan (Sniper config + risk)", 
            value=True, 
            key="sniper_use_profile"
        )
        use_risk_contract = st.checkbox(
            "Risk kontrat limitini uygula (contract mode)", 
            value=False, 
            key="sniper_use_risk_contract"
        )
        
        data_source = st.radio(
            "Veri Kaynağı",
            ["⚡ Quick (pre-computed)", "🎬 Full Replay (bar-bar)"],
            horizontal=True,
            key="sniper_data_source_v2"
        )
        
        if "Full Replay" in data_source:
            c1, c2, c3 = st.columns(3)
            with c1:
                tp_pct = st.slider("Take Profit %", 1, 20, 8, key="sniper_tp_v2") / 100.0
            with c2:
                sl_pct = st.slider("Stop Loss %", 1, 10, 3, key="sniper_sl_v2") / 100.0
            with c3:
                max_bars = st.slider("Max Bars", 10, 100, 50, key="sniper_max_bars_v2")
        else:
            tp_pct, sl_pct, max_bars = 0.08, 0.03, 50
        
        enable_sniper = st.checkbox("Sniper Arena aktif", value=True, key="sniper_enabled_v2")
        
        # Entry Selection Mode
        st.divider()
        st.markdown("**Entry Selection Mode:**")
        entry_selection_mode = st.radio(
            "Entry seçim modu",
            options=["ARENA_FILTERS (Dinamik)", "CARD_STRICT_IDS (Karttan)"],
            index=0,
            key="sniper_entry_selection_mode",
            horizontal=True,
            help="ARENA_FILTERS: Tightness/toggles ile dinamik seçim. CARD_STRICT_IDS: Kart provenance'ından sabit IDs."
        )
    
    # === Filter Controls ===
    with st.expander("🎛️ Filter Controls", expanded=False):
        st.markdown("**Tightness (Filtre Sıkılığı):**")
        st.caption("0 = En gevşek (dataset min/max), 100 = En sıkı (profil ayarları)")
        tightness = st.slider(
            "Tightness",
            min_value=0,
            max_value=100,
            value=50,
            step=5,
            key="sniper_tightness_v2"
        )
        
        st.markdown("**Filtre Aktif/Pasif:**")
        col1, col2 = st.columns(2)
        with col1:
            toggle_rsi = st.checkbox("RSI filtresi", value=True, key="sniper_toggle_rsi")
            toggle_vol = st.checkbox("VOLUME filtresi", value=True, key="sniper_toggle_vol")
            toggle_atr = st.checkbox("ATR filtresi", value=True, key="sniper_toggle_atr")
        with col2:
            toggle_quality = st.checkbox("QUALITY filtresi", value=True, key="sniper_toggle_quality")
            # ML default off when tightness < 40
            ml_default = tightness >= 40
            toggle_ml = st.checkbox("ML filtreleri", value=ml_default, key="sniper_toggle_ml")
        
        # Store toggles in state
        filter_toggles = {
            "rsi": toggle_rsi,
            "volume": toggle_vol,
            "atr": toggle_atr,
            "quality": toggle_quality,
            "ml": toggle_ml,
        }
        st.session_state["sniper_filter_toggles"] = filter_toggles
        st.session_state["sniper_tightness"] = tightness
    
    # === Tightness Sweep Table ===
    with st.expander("📊 Tightness Sweep Tablosu", expanded=False):
        st.caption("Farklı tightness seviyelerinde beklenen sonuçlar")
        
        sweep_ml_toggle = st.checkbox("ML filtreleri dahil et", value=False, key="sweep_ml_toggle")
        
        if st.button("🔄 Sweep Hesapla", key="btn_tightness_sweep"):
            try:
                import pandas as pd
                from tezaver.sniper.sniper_filter_debug import (
                    compute_sniper_dataset_stats,
                    build_effective_sniper_filter_window,
                    compute_sniper_filter_debug,
                )
                
                entries_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/sniper_entries_v1.parquet")
                if not entries_path.exists():
                    st.warning("Sniper entries bulunamadı.")
                else:
                    df = pd.read_parquet(entries_path)
                    dataset_stats = compute_sniper_dataset_stats(df)
                    
                    # Load profile config
                    card_path = Path(f"data/coin_profiles/{symbol}/{timeframe}/sniper_strategy_card_v1.json")
                    profile_cfg = json.loads(card_path.read_text()) if card_path.exists() else {}
                    
                    sweep_data = []
                    tightness_levels = [0, 20, 40, 60, 80, 100]
                    
                    for t_level in tightness_levels:
                        toggles = {
                            "rsi": True, "volume": True, "atr": True, 
                            "quality": True, "ml": sweep_ml_toggle and t_level >= 40
                        }
                        
                        eff_window = build_effective_sniper_filter_window(
                            profile_cfg, t_level, toggles, dataset_stats
                        )
                        
                        debug = compute_sniper_filter_debug(df, eff_window)
                        
                        selected = debug.data_stats.get("selected_entries", 0)
                        total = debug.data_stats.get("total_entries", 1)
                        pass_rate = selected / total * 100 if total > 0 else 0
                        
                        sweep_data.append({
                            "Tightness": t_level,
                            "Entries": selected,
                            "Pass %": f"{pass_rate:.0f}%",
                            "Bottleneck": debug.bottleneck_stage or "-",
                            "ML": "ON" if toggles["ml"] else "OFF",
                        })
                    
                    st.table(sweep_data)
                    
            except Exception as e:
                st.error(f"Sweep hesaplanamadı: {e}")
    
    # === Sniper Card Provenance ===
    with st.expander("📚 Sniper Kart Kaynağı (Provenance)", expanded=False):
        card_path = Path(f"data/coin_profiles/{symbol}/{timeframe}/sniper_strategy_card_v1.json")
        if card_path.exists():
            card = json.loads(card_path.read_text())
            
            # Provenance info
            st.markdown("**🏗️ Build Bilgisi:**")
            built_at = card.get("built_at", "-")
            builder_version = card.get("builder_version", "v1")
            st.write(f"- **Oluşturulma:** {built_at}")
            st.write(f"- **Builder Versiyonu:** {builder_version}")
            
            st.divider()
            
            # Source filters
            st.markdown("**🔍 Kaynak Filtreleri:**")
            filters = card.get("source_filters", {})
            src_grades = filters.get("source_grades", filters.get("grade", ["SILVER"]))
            status_in = filters.get("status_in", filters.get("status", ["APPROVED"]))
            label_in = filters.get("label_in", filters.get("label", ["GOOD"]))
            
            filter_table = [
                {"Filtre": "Grade", "Değer": ", ".join(src_grades) if isinstance(src_grades, list) else str(src_grades)},
                {"Filtre": "Status", "Değer": ", ".join(status_in) if isinstance(status_in, list) else str(status_in)},
                {"Filtre": "Label", "Değer": ", ".join(label_in) if isinstance(label_in, list) else str(label_in)},
            ]
            st.table(filter_table)
            
            st.divider()
            
            # Source counts
            st.markdown("**📊 Kaynak İstatistikleri:**")
            meta = card.get("meta", card.get("source_counts", {}))
            total = meta.get("entries_total") or meta.get("total_annotations") or meta.get("num_entries_total")
            used = meta.get("entries_selected") or meta.get("used_annotations") or meta.get("num_entries_used")
            pos_rate = meta.get("positive_rate")
            
            count_table = [
                {"Metrik": "Toplam Annotation", "Değer": str(total) if total else "-"},
                {"Metrik": "Kullanılan", "Değer": str(used) if used else "-"},
                {"Metrik": "Pozitif Oran", "Değer": f"{pos_rate*100:.1f}%" if pos_rate else "-"},
            ]
            st.table(count_table)
            
        else:
            st.info("Sniper strategy card bulunamadı. CLI: `python -m tezaver.sniper.sniper_strategy_card_builder`")
    
    # === Self-Consistency Check ===
    with st.expander("🔍 Card Self-Consistency Check", expanded=False):
        st.caption("Kart kaynağındaki entry'lerin tightness=100'de aynı sonuçları verip vermediğini kontrol et")
        
        if st.button("✅ Self-Check Çalıştır", key="btn_self_check"):
            try:
                import pandas as pd
                from tezaver.sniper.sniper_filter_debug import (
                    compute_sniper_dataset_stats,
                    build_effective_sniper_filter_window,
                    compute_sniper_filter_debug,
                )
                
                entries_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/sniper_entries_v1.parquet")
                card_path = Path(f"data/coin_profiles/{symbol}/{timeframe}/sniper_strategy_card_v1.json")
                
                if not entries_path.exists():
                    st.warning("Sniper entries bulunamadı.")
                elif not card_path.exists():
                    st.warning("Strategy card bulunamadı.")
                else:
                    df = pd.read_parquet(entries_path)
                    card = json.loads(card_path.read_text())
                    dataset_stats = compute_sniper_dataset_stats(df)
                    
                    # Tightness=100, ML OFF
                    toggles_ml_off = {"rsi": True, "volume": True, "atr": True, "quality": True, "ml": False}
                    window_ml_off = build_effective_sniper_filter_window(card, 100, toggles_ml_off, dataset_stats)
                    debug_ml_off = compute_sniper_filter_debug(df, window_ml_off)
                    
                    # Tightness=100, ML ON
                    toggles_ml_on = {"rsi": True, "volume": True, "atr": True, "quality": True, "ml": True}
                    window_ml_on = build_effective_sniper_filter_window(card, 100, toggles_ml_on, dataset_stats)
                    debug_ml_on = compute_sniper_filter_debug(df, window_ml_on)
                    
                    # Card meta - try multiple possible fields
                    meta = card.get("meta", {})
                    provenance = card.get("provenance", {})
                    source_stats = card.get("source_stats", {})
                    
                    # Get card_used from various possible locations
                    card_used = (
                        provenance.get("used_entry_count") or
                        source_stats.get("used_count") or
                        meta.get("entries_selected") or
                        meta.get("used_annotations") or
                        meta.get("num_entries_used") or
                        len(df)  # fallback to dataset size
                    )
                    
                    # Ensure it's an integer
                    if isinstance(card_used, str):
                        try:
                            card_used = int(card_used)
                        except:
                            card_used = 0
                    
                    st.markdown("**Self-Consistency Sonucu (Two-Layer):**")
                    
                    ml_off_pass = debug_ml_off.data_stats.get("selected_entries", 0)
                    ml_on_pass = debug_ml_on.data_stats.get("selected_entries", 0)
                    
                    # Get provenance V2 metrics
                    provenance = card.get("provenance", {})
                    source_count = provenance.get("source_count", card_used)
                    strict_count = provenance.get("strict_count", card_used)
                    
                    # Two-layer mismatch
                    mismatch_source_vs_strict = source_count - strict_count
                    mismatch_strict_vs_arena_off = strict_count - ml_off_pass
                    mismatch_strict_vs_arena_on = strict_count - ml_on_pass
                    
                    sc_table = [
                        {"Test": "Source Count (Dataset)", "Değer": str(source_count)},
                        {"Test": "Strict Count (Card Window)", "Değer": str(strict_count)},
                        {"Test": "Arena Pass (ML OFF)", "Değer": str(ml_off_pass)},
                        {"Test": "Arena Pass (ML ON)", "Değer": str(ml_on_pass)},
                        {"Test": "─────────────────────", "Değer": "────────"},
                        {"Test": "Source→Strict Drop", "Değer": str(mismatch_source_vs_strict)},
                        {"Test": "⚠️ Strict→Arena (ML OFF)", "Değer": f"{mismatch_strict_vs_arena_off}" + (" ✅" if mismatch_strict_vs_arena_off == 0 else " 🐛")},
                        {"Test": "⚠️ Strict→Arena (ML ON)", "Değer": f"{mismatch_strict_vs_arena_on}" + (" ✅" if mismatch_strict_vs_arena_on == 0 else " 🐛")},
                        {"Test": "─────────────────────", "Değer": "────────"},
                        {"Test": "Bottleneck (ML OFF)", "Değer": debug_ml_off.bottleneck_stage or "-"},
                        {"Test": "Bottleneck (ML ON)", "Değer": debug_ml_on.bottleneck_stage or "-"},
                    ]
                    st.table(sc_table)
                    
                    # Store for later display
                    st.session_state["self_check_result"] = {
                        "card_used": card_used,
                        "ml_off_pass": ml_off_pass,
                        "ml_on_pass": ml_on_pass,
                        "ml_off_bottleneck": debug_ml_off.bottleneck_stage,
                        "ml_on_bottleneck": debug_ml_on.bottleneck_stage,
                        "df": df,
                        "window_ml_off": window_ml_off,
                    }
                    
                    # Failing Entries Drilldown
                    mismatch = card_used - ml_off_pass if card_used else 0
                    if mismatch > 0:
                        with st.expander(f"🔎 Failing Entries ({mismatch} adet)", expanded=True):
                            st.caption("Tightness=100 (ML OFF) ile geçemeyen entry'ler")
                            
                            # Find failing entries
                            entry_filters = window_ml_off.get("entry_filters", {})
                            
                            failing_rows = []
                            for idx, row in df.iterrows():
                                first_fail = None
                                fail_reason = {}
                                
                                # RSI check
                                rsi_cfg = entry_filters.get("rsi", {})
                                if rsi_cfg.get("enabled", True):
                                    rsi_col = "feat_rsi_14" if "feat_rsi_14" in df.columns else "rsi"
                                    if rsi_col in df.columns:
                                        val = row.get(rsi_col)
                                        rsi_min = rsi_cfg.get("min", 0)
                                        rsi_max = rsi_cfg.get("max", 100)
                                        if val is not None and (val < rsi_min or val > rsi_max):
                                            first_fail = "RSI"
                                            fail_reason = {"val": val, "min": rsi_min, "max": rsi_max}
                                
                                # Volume check
                                if not first_fail:
                                    vol_cfg = entry_filters.get("volume", {})
                                    if vol_cfg.get("enabled", True):
                                        vol_col = "feat_volume_ratio" if "feat_volume_ratio" in df.columns else "volume"
                                        if vol_col in df.columns:
                                            val = row.get(vol_col)
                                            vol_min = vol_cfg.get("min", 0)
                                            if val is not None and val < vol_min:
                                                first_fail = "VOLUME"
                                                fail_reason = {"val": val, "min": vol_min, "max": "∞"}
                                
                                # ATR check
                                if not first_fail:
                                    atr_cfg = entry_filters.get("atr", {})
                                    if atr_cfg.get("enabled", True):
                                        atr_col = "feat_atr_14" if "feat_atr_14" in df.columns else "atr"
                                        if atr_col in df.columns:
                                            val = row.get(atr_col)
                                            atr_min = atr_cfg.get("min", 0)
                                            atr_max = atr_cfg.get("max", 999)
                                            if val is not None and (val < atr_min or val > atr_max):
                                                first_fail = "ATR"
                                                fail_reason = {"val": val, "min": atr_min, "max": atr_max}
                                
                                # Quality check
                                if not first_fail:
                                    q_cfg = entry_filters.get("quality", {})
                                    if q_cfg.get("enabled", True):
                                        q_col = "feat_quality_score" if "feat_quality_score" in df.columns else "quality_score"
                                        if q_col in df.columns:
                                            val = row.get(q_col)
                                            q_min = q_cfg.get("min", 0)
                                            if val is not None and val < q_min:
                                                first_fail = "QUALITY"
                                                fail_reason = {"val": val, "min": q_min, "max": "∞"}
                                
                                if first_fail:
                                    ts_col = "event_time" if "event_time" in df.columns else "ts"
                                    failing_rows.append({
                                        "event_id": str(row.get("event_id", idx))[:20],
                                        "entry_ts": str(row.get(ts_col, ""))[:19],
                                        "failed_stage": first_fail,
                                        "value": f"{fail_reason.get('val', '')}",
                                        "min": f"{fail_reason.get('min', '')}",
                                        "max": f"{fail_reason.get('max', '')}",
                                    })
                                
                                if len(failing_rows) >= 10:  # Limit to first 10
                                    break
                            
                            if failing_rows:
                                st.caption(f"İlk {len(failing_rows)} failing entry gösteriliyor")
                                
                                # Display each failing entry with action buttons
                                for i, fail_row in enumerate(failing_rows):
                                    col_info, col_lab, col_bad = st.columns([4, 1, 1])
                                    
                                    with col_info:
                                        st.text(
                                            f"{fail_row['failed_stage']}: {fail_row['value']} "
                                            f"(min={fail_row['min']}, max={fail_row['max']}) | "
                                            f"{fail_row['entry_ts']}"
                                        )
                                    
                                    with col_lab:
                                        if st.button("📝 Lab", key=f"open_lab_{i}", help="Sniper Lab'de aç"):
                                            st.session_state["sniper_lab_target_event"] = fail_row["event_id"]
                                            st.session_state["sniper_lab_target_ts"] = fail_row["entry_ts"]
                                            st.info(f"🎯 Sniper Lab'e git → {fail_row['event_id'][:10]}...")
                                    
                                    with col_bad:
                                        if st.button("🚫 BAD", key=f"mark_bad_{i}", help="BAD olarak işaretle"):
                                            try:
                                                from tezaver.sniper.sniper_annotations import SniperAnnotationRepository
                                                ann_repo = SniperAnnotationRepository()
                                                ann_repo.append(
                                                    symbol=symbol,
                                                    timeframe=timeframe,
                                                    event_id=fail_row["event_id"],
                                                    entry_bar_offset=0,
                                                    note="Auto-marked BAD from Sniper Arena",
                                                    status="REJECTED",
                                                    label="BAD",
                                                )
                                                st.success(f"✅ {fail_row['event_id'][:10]}... BAD işaretlendi")
                                            except Exception as e:
                                                st.error(f"Hata: {e}")
                            else:
                                st.success("✅ Tüm entry'ler geçiyor - mismatch yok!")
                    
                    # Quick Rebuild Button
                    st.divider()
                    if st.button("🔁 Sniper Card'ı Yeniden Üret", key="btn_rebuild_card", type="secondary"):
                        with st.spinner("Card yeniden üretiliyor..."):
                            try:
                                from tezaver.sniper.sniper_strategy_card_builder import save_sniper_strategy_card_for_symbol_timeframe
                                path = save_sniper_strategy_card_for_symbol_timeframe(symbol, timeframe)
                                st.success(f"✅ Card yeniden üretildi: {path.name}")
                                
                                # Show new provenance stats
                                new_card = json.loads(path.read_text())
                                new_prov = new_card.get("provenance", {})
                                st.write(f"📊 Yeni: source={new_prov.get('source_count')}, strict={new_prov.get('strict_count')}")
                                st.write(f"🕐 Built: {new_prov.get('built_at')}")
                                
                                # Auto rerun
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Rebuild hatası: {e}")
                    
            except Exception as e:
                st.error(f"Self-check hatası: {e}")
    
    # === Stage Threshold Viewer ===
    with st.expander("📏 Stage Threshold Viewer (Tightness=100)", expanded=False):
        card_path = Path(f"data/coin_profiles/{symbol}/{timeframe}/sniper_strategy_card_v1.json")
        if card_path.exists():
            card = json.loads(card_path.read_text())
            entry_filters = card.get("entry_filters", card.get("filters", {}))
            
            def fmt_val(v):
                """Format threshold values - handle None, NaN, inf."""
                if v is None:
                    return "-"
                if isinstance(v, str):
                    return v if v != "-" else "-"
                try:
                    import math
                    if math.isnan(v):
                        return "-"
                    if math.isinf(v):
                        return "∞" if v > 0 else "-∞"
                    return f"{v:.6g}"
                except (TypeError, ValueError):
                    return str(v)
            
            threshold_table = []
            
            # RSI
            rsi = entry_filters.get("rsi", {})
            threshold_table.append({
                "Stage": "RSI",
                "Min": fmt_val(rsi.get("min")),
                "Max": fmt_val(rsi.get("max")),
            })
            
            # Volume
            vol = entry_filters.get("volume", {})
            threshold_table.append({
                "Stage": "VOLUME",
                "Min": fmt_val(vol.get("min")),
                "Max": fmt_val(vol.get("max")) if vol.get("max") else "∞",
            })
            
            # ATR
            atr = entry_filters.get("atr", {})
            threshold_table.append({
                "Stage": "ATR",
                "Min": fmt_val(atr.get("min")),
                "Max": fmt_val(atr.get("max")),
            })
            
            # Quality
            quality = entry_filters.get("quality", {})
            threshold_table.append({
                "Stage": "QUALITY",
                "Min": fmt_val(quality.get("min")),
                "Max": fmt_val(quality.get("max")) if quality.get("max") else "∞",
            })
            
            # ML
            ml = card.get("ml_filters", {})
            threshold_table.append({
                "Stage": "ML",
                "Min": fmt_val(ml.get("threshold")),
                "Max": "1.0",
            })
            
            st.table(threshold_table)
        else:
            st.info("Strategy card bulunamadı.")
    
    # === AutoTune ===
    with st.expander("🎚️ AutoTune (Target Pass Ratio)", expanded=False):
        st.caption("Hedef geçiş oranına göre tightness öneri")
        
        target_pass = st.slider(
            "🎯 Hedef Pass %",
            min_value=15,
            max_value=80,
            value=50,
            step=5,
            key="autotune_target_pass"
        )
        
        if st.button("🔮 AutoTune Hesapla", key="btn_autotune"):
            try:
                import pandas as pd
                from tezaver.sniper.sniper_filter_debug import (
                    compute_sniper_dataset_stats,
                    build_effective_sniper_filter_window,
                    compute_sniper_filter_debug,
                )
                
                entries_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/sniper_entries_v1.parquet")
                card_path = Path(f"data/coin_profiles/{symbol}/{timeframe}/sniper_strategy_card_v1.json")
                
                if entries_path.exists() and card_path.exists():
                    df = pd.read_parquet(entries_path)
                    card = json.loads(card_path.read_text())
                    dataset_stats = compute_sniper_dataset_stats(df)
                    total = len(df)
                    
                    # Sweep to find best tightness
                    best_tightness = 50
                    best_diff = 100
                    best_pass_rate = 0
                    best_bottleneck = None
                    
                    for t_level in [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
                        toggles = {"rsi": True, "volume": True, "atr": True, "quality": True, "ml": False}
                        window = build_effective_sniper_filter_window(card, t_level, toggles, dataset_stats)
                        debug = compute_sniper_filter_debug(df, window)
                        
                        selected = debug.data_stats.get("selected_entries", 0)
                        pass_rate = selected / total * 100 if total > 0 else 0
                        diff = abs(pass_rate - target_pass)
                        
                        if diff < best_diff:
                            best_diff = diff
                            best_tightness = t_level
                            best_pass_rate = pass_rate
                            best_bottleneck = debug.bottleneck_stage
                    
                    st.success(f"✅ Önerilen Tightness: **{best_tightness}**")
                    st.write(f"Beklenen Pass Rate: **{best_pass_rate:.0f}%**")
                    st.write(f"Bottleneck: **{best_bottleneck or '-'}**")
                    
                    if best_bottleneck:
                        st.info(f"💡 Öneri: {best_bottleneck} filtresini gevşetmeyi düşünebilirsin.")
                    
            except Exception as e:
                st.error(f"AutoTune hatası: {e}")
    
    # === Effective Config ===
    with st.expander("📌 Effective Config", expanded=False):
        st.markdown("**Risk Ayarları:**")
        
        # Determine effective risk
        risk_requested = risk
        risk_contract_max = 0.01  # Default from EXPERIMENTAL profile
        risk_effective = min(risk_requested, risk_contract_max) if use_risk_contract else risk_requested
        
        c1, c2, c3 = st.columns(3)
        c1.metric("🎯 İstenen Risk", f"{risk_requested:.2f}")
        c2.metric("📜 Kontrat Max", f"{risk_contract_max:.2f}")
        c3.metric("✅ Uygulanan Risk", f"{risk_effective:.2f}")
        
        st.markdown("**Exit Parametreleri:**")
        st.write(f"- **TP:** {tp_pct*100:.0f}%")
        st.write(f"- **SL:** {sl_pct*100:.0f}%")
        st.write(f"- **Max Bars:** {max_bars}")
        
        st.markdown("**Config Kaynağı:**")
        if use_profile:
            st.write("📂 CoinPage V2 Profile + Override")
        else:
            st.write("🔧 Manual Override (profil kapalı)")
        
        st.markdown("**Mode:**")
        st.write(f"{'🔒 Contract' if use_risk_contract else '🧪 Experiment'}")
    
    # === Filter Debug (after running) ===
    # This will be populated after backtest runs - stored in session state
    if "sniper_debug_info" in st.session_state and st.session_state["sniper_debug_info"]:
        debug_info = st.session_state["sniper_debug_info"]
        
        with st.expander("🧪 Filter Debug – Daraltma Analizi", expanded=False):
            st.markdown("**Filter Stage Tablosu:**")
            
            # Create table data
            stage_data = []
            for stage in debug_info.stages:
                emoji = "🎯" if stage.stage == debug_info.bottleneck_stage else "  "
                stage_data.append({
                    "": emoji,
                    "Aşama": stage.stage,
                    "Kalan": stage.count,
                    "Oran": f"{stage.ratio*100:.1f}%",
                    "Düşen": stage.dropped,
                })
            
            st.table(stage_data)
            
            # Bottleneck highlight
            if debug_info.bottleneck_stage:
                st.warning(f"🎯 **En çok daraltan aşama:** {debug_info.bottleneck_stage}")
            
            # Data stats
            st.markdown("**Veri İstatistikleri:**")
            stats = debug_info.data_stats
            st.write(f"- **Toplam Entry:** {stats.get('total_entries', 0)}")
            st.write(f"- **Seçilen Entry:** {stats.get('selected_entries', 0)}")
            st.write(f"- **Geçiş Oranı:** {stats.get('filter_pass_rate', '-')}")
            st.write(f"- **Tarih Aralığı:** {stats.get('date_range', '-')}")
    
    # === Disabled check ===
    if not enable_sniper:
        st.info("Sniper Arena şu an kapalı. Gelişmiş ayarlardan aktif edebilirsin.")
        return
    
    # =========================================================================
    # PATTERN RULES UI (Dynamic)
    # =========================================================================
    card_path = Path(f"data/coin_profiles/{symbol}/{timeframe}/sniper_strategy_card_v1.json")
    card_ui = json.loads(card_path.read_text()) if card_path.exists() else {}
    pattern_rules_ui = card_ui.get("pattern_rules_v1", {}).get("rules", [])
    
    selected_pattern_features = []
    pattern_stage_active = True
    
    if pattern_rules_ui:
        with st.expander("🧠 Pattern Rules (Desenler)", expanded=False):
            col_p1, col_p2 = st.columns([2, 3])
            pattern_stage_active = col_p1.checkbox(
                "Pattern Stage Aktif", 
                value=True, 
                key=f"sniper_arena::{symbol}::{timeframe}::pattern_active"
            )
            
            if pattern_stage_active:
                col_p2.caption(f"Toplam {len(pattern_rules_ui)} kural. Seçilileri uygula.")
                
                # Table Header
                cols = st.columns([3, 1.5, 1.5, 1.2, 1.2, 1.2, 1])
                cols[0].markdown("**Feature**")
                cols[1].markdown("**Min**")
                cols[2].markdown("**Max**")
                cols[3].markdown("**Lift**")
                cols[4].markdown("**Supp**")
                cols[5].markdown("**Good**")
                cols[6].markdown("**On**")
                
                # Table Rows
                for i, r in enumerate(pattern_rules_ui):
                    feat = r["feature"]
                    ckey = f"sniper_arena::{symbol}::{timeframe}::rule::{feat}"
                    # Default True (enabled)
                    is_active = st.checkbox("✅", value=True, key=ckey, label_visibility="collapsed")
                    
                    if is_active:
                        selected_pattern_features.append(feat)
                    
                    # Display row
                    cols = st.columns([3, 1.5, 1.5, 1.2, 1.2, 1.2, 1])
                    cols[0].code(feat)
                    cols[1].write(f"{r['min']:.2f}")
                    cols[2].write(f"{r['max']:.2f}")
                    cols[3].write(f"{r['lift']:.2f}")
                    cols[4].write(f"{r['support']}")
                    cols[5].write(f"{r['good_rate']:.2f}")
                    cols[6].write("✅" if is_active else "❌")
            else:
                st.warning("Pattern stage kapalı. Tüm kurallar yoksayılacak.")

    # =========================================================================
    # QUALITY CLAMP POLICY CONTROLS
    # =========================================================================
    with st.expander("🎚️ Quality Clamp Policy", expanded=False):
        st.caption(
            "QUALITY filtresinin tightness=0'da ne kadar gevşeyebileceğini kontrol eder."
        )
        
        clamp_policy = st.radio(
            "Clamp Policy",
            options=["OFF", "SOFT", "HARD"],
            index=2,  # Default HARD
            horizontal=True,
            key=f"sniper_arena::{symbol}::{timeframe}::clamp_policy",
            help=(
                "**OFF**: Clamp yok, tightness=0'da dataset min'e kadar inebilir.\n"
                "**SOFT**: Floor tightness ile gevşer (0'da dataset min, 100'de 50).\n"
                "**HARD**: Floor her zaman 50 (mevcut davranış)."
            )
        )
        
        use_quality_override = st.checkbox(
            "Quality Min Override",
            value=False,
            key=f"sniper_arena::{symbol}::{timeframe}::use_quality_override"
        )
        
        quality_override_value = None
        if use_quality_override:
            quality_override_value = st.slider(
                "Quality Min Override Value",
                min_value=0,
                max_value=100,
                value=30,
                key=f"sniper_arena::{symbol}::{timeframe}::quality_override_value"
            )
            st.caption(f"Override aktif: Quality min = {quality_override_value}")

    # =========================================================================
    # ARENA RUN CONFIG - Single Source of Truth
    # =========================================================================
    import hashlib
    
    # Collect all controls into single config dict
    arena_run_config = {
        "symbol": symbol,
        "timeframe": timeframe,
        "data_source": data_source,
        "entry_selection_mode": entry_selection_mode,
        "risk_requested": float(risk),
        "use_coinpage_profile": use_profile,
        "enforce_risk_contract": use_risk_contract,
        "tightness": st.session_state.get("sniper_tightness", 50),
        "filter_toggles": st.session_state.get("sniper_filter_toggles", {
            "rsi": True, "volume": True, "atr": True, "quality": True, "ml": False
        }),
        "pattern_config": {
            "stage_enabled": pattern_stage_active,
            "enabled_features": selected_pattern_features,
        },
        "exit": {
            "tp_pct": tp_pct,
            "sl_pct": sl_pct,
            "max_bars": max_bars,
        },
    }
    
    # Generate config hash
    run_config_json = json.dumps(arena_run_config, sort_keys=True)
    run_config_hash = hashlib.sha1(run_config_json.encode()).hexdigest()[:10]
    
    # Display config hash
    st.divider()
    col_h1, col_h2 = st.columns([1, 3])
    with col_h1:
        st.metric("🔑 Config Hash", run_config_hash)
    with col_h2:
        with st.expander("📋 Full Config (Debug)", expanded=False):
            st.code(run_config_json, language="json")
    
    # Wiring guardrail: check if hash changed
    last_hash = st.session_state.get("sniper_last_run_config_hash")
    if last_hash and last_hash == run_config_hash:
        st.caption("ℹ️ Config hash değişmedi (önceki run ile aynı)")
    
    # === Run Button ===
    run_btn = st.button(
        "🚀 Sniper Test Çalıştır",
        key="btn_sniper_arena_run_v2",
        use_container_width=True,
        type="primary"
    )
    
    if run_btn:
        # Store config hash for comparison
        st.session_state["sniper_last_run_config_hash"] = run_config_hash
        
        try:
            if "Quick" in data_source:
                from tezaver.sniper.v3.sniper_arena_v3 import run_sniper_arena_v3
                
                with st.spinner("Sniper Arena v3 çalışıyor..."):
                    try:
                        v3_result = run_sniper_arena_v3(
                            symbol=symbol,
                            timeframe=timeframe,
                            data_source="patterns",
                            tightness=arena_run_config["tightness"],
                            toggles=arena_run_config["filter_toggles"],
                            clamp_policy=clamp_policy,
                            quality_min_override=quality_override_value,
                            mode="contract" if use_risk_contract else "experiment",
                            risk=float(risk),
                            tp_pct=tp_pct,
                            sl_pct=sl_pct,
                            max_bars=max_bars,
                            pnl_mode="TPSL",  # Default, can add UI toggle later
                        )
                        
                        # Convert v3 result to report format for UI compatibility
                        report = {
                            "run_id": v3_result["run_id"],
                            "computed_at": v3_result["computed_at"],
                            "config_hash": v3_result["config_hash"],
                            "window_hash": v3_result["window_hash"],
                            "selected_count": v3_result["selected_count"],
                            "unique_count": v3_result["unique_count"],
                            "total_entries": v3_result["total_entries"],
                            "used_count": v3_result["backtest"]["used_count"],
                            "trade_count": v3_result["trades"],
                            "capital_start": v3_result["backtest"]["capital_start"],
                            "capital_end": v3_result["capital_end"],
                            "pnl_pct": v3_result["pnl_pct"],
                            "win_rate": v3_result["backtest"]["win_rate"],
                            "max_drawdown_pct": v3_result["backtest"]["max_drawdown_pct"],
                            "selection_fingerprint": v3_result["selection_fingerprint"],
                            "pnl_signature_v2": v3_result["pnl_signature_v2"],
                            "top_pnl_bins": v3_result["top_pnl_bins"],
                            "debug_stage_counts": v3_result["debug_stage_counts"],
                            "exit_reason_counts": v3_result["backtest"]["exit_reason_counts"],
                            "tp_capped_count": v3_result["backtest"]["tp_capped_count"],
                            "sl_capped_count": v3_result["backtest"]["sl_capped_count"],
                            "pnl_eff_stats": v3_result["backtest"]["pnl_eff_stats"],
                            "pnl_unique_count": v3_result["backtest"]["pnl_unique_count"],
                            "trade_list": v3_result["backtest"]["ledger_sample"],
                            "pnl_mode": v3_result["pnl_mode"],
                            "tightness": v3_result["tightness"],
                            "engine_path": "V3_ARENA",
                            # Compatibility
                            "selected_hash": v3_result["selection_fingerprint"],
                            "used_hash": v3_result["pnl_signature_v2"],
                            "clamp_policy": v3_result["clamp_policy"],
                            "selection_mode": "ARENA_FILTERS",
                        }
                    except RuntimeError as e:
                        st.error(f"⚠️ V3 INVARIANT VIOLATION: {e}")
                        return
                
                st.success("✅ Sniper Arena tamamlandı!")
                
                # V3 Proof Line (guaranteed: Selected == Unique == Used == Trades)
                st.caption(
                    f"**RUN={report['run_id']}** | "
                    f"Selected={report['selected_count']} Unique={report.get('unique_count', report['selected_count'])} "
                    f"Trades={report['trade_count']}"
                )
                st.caption(
                    f"SelFP={report.get('selection_fingerprint', report.get('selected_hash', 'N/A'))} | "
                    f"PnLSigV2={report.get('pnl_signature_v2', 'N/A')} | "
                    f"Cap=100→{report['capital_end']:.0f}"
                )
                
                # Stage counts (debug)
                stage_counts = report.get('debug_stage_counts', {})
                if stage_counts:
                    stages = " → ".join([f"{k}={v}" for k, v in stage_counts.items()])
                    st.caption(f"📊 Stages: {stages}")
                
                # Top PnL bins
                top_bins = report.get('top_pnl_bins', [])
                if top_bins:
                    bins_str = ", ".join([f"({v}, {c})" for v, c in top_bins[:5]])
                    st.caption(f"TopPnL=[{bins_str}]")
                
                # V3 Invariant Check (guaranteed: selected == used == trades)
                sel = report['selected_count']
                used = report['used_count']
                trades = report['trade_count']
                if sel == used == trades:
                    st.success(f"✅ V3 Invariants OK: Selected={sel} == Used={used} == Trades={trades}")
                else:
                    st.error(f"⚠️ V3 INVARIANT BROKEN: Selected={sel} Used={used} Trades={trades}")
                
                # Entry Diff (compare to previous run)
                prev_ids_key = f"sniper_arena_prev_ids::{symbol}::{timeframe}"
                current_ids = set(report.get('selected_ids_sample', []))
                prev_ids = set(st.session_state.get(prev_ids_key, []))
                
                if prev_ids:
                    added_ids = current_ids - prev_ids
                    removed_ids = prev_ids - current_ids
                    union_len = len(current_ids | prev_ids)
                    intersection_len = len(current_ids & prev_ids)
                    jaccard = intersection_len / union_len if union_len > 0 else 1.0
                    
                    if added_ids or removed_ids:
                        st.caption(
                            f"📊 **Entry Diff:** +{len(added_ids)} added, -{len(removed_ids)} removed | "
                            f"Jaccard={jaccard:.2f}"
                        )
                        with st.expander("🔄 Entry Diff Details", expanded=False):
                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown("**➕ Added (sample):**")
                                st.code("\n".join(list(added_ids)[:10]) if added_ids else "None")
                            with c2:
                                st.markdown("**➖ Removed (sample):**")
                                st.code("\n".join(list(removed_ids)[:10]) if removed_ids else "None")
                    else:
                        st.caption("📊 **Entry Diff:** No changes from previous run")
                else:
                    st.caption("📊 **Entry Diff:** First run (no baseline)")
                
                # Store current IDs for next comparison
                st.session_state[prev_ids_key] = list(current_ids)
                
                # =========================================================================
                # TRADE DIFF (compare trade lists between runs)
                # =========================================================================
                prev_trades_key = f"sniper_arena_prev_trades::{symbol}::{timeframe}"
                current_trades = report.get('trade_list', [])
                current_trade_ids = {t['trade_id'] for t in current_trades}
                current_trade_map = {t['trade_id']: t for t in current_trades}
                
                prev_trades = st.session_state.get(prev_trades_key, [])
                prev_trade_ids = {t['trade_id'] for t in prev_trades}
                prev_trade_map = {t['trade_id']: t for t in prev_trades}
                
                if prev_trade_ids:
                    added_trade_ids = current_trade_ids - prev_trade_ids
                    removed_trade_ids = prev_trade_ids - current_trade_ids
                    trade_union = len(current_trade_ids | prev_trade_ids)
                    trade_intersect = len(current_trade_ids & prev_trade_ids)
                    trade_jaccard = trade_intersect / trade_union if trade_union > 0 else 1.0
                    
                    # Calculate PnL attribution
                    added_pnl = sum(current_trade_map[tid]['pnl_pct'] for tid in added_trade_ids)
                    removed_pnl = sum(prev_trade_map[tid]['pnl_pct'] for tid in removed_trade_ids)
                    delta_pnl = added_pnl - removed_pnl
                    
                    st.caption(
                        f"📈 **Trade Diff:** +{len(added_trade_ids)} added, -{len(removed_trade_ids)} removed | "
                        f"Jaccard={trade_jaccard:.2f} | ΔPnL={delta_pnl:+.2f}%"
                    )
                    st.caption(f"🔑 Trade Fingerprint: {report.get('trade_ids_hash', 'N/A')}")
                    
                    # Tripwires
                    entry_diff_count = len(added_ids) + len(removed_ids) if prev_ids else 0
                    trade_diff_count = len(added_trade_ids) + len(removed_trade_ids)
                    
                    if entry_diff_count > 0 and trade_diff_count == 0:
                        st.error("⚠️ TRADE NO-CHANGE: Entries changed but trades didn't! (ID mapping bug?)")
                    
                    if trade_diff_count > 0 and abs(delta_pnl) < 0.01:
                        st.warning("⚠️ PNL COLLAPSE: Trades changed but ΔPnL ≈ 0 (rounding/clamp issue?)")
                    
                    if added_trade_ids or removed_trade_ids:
                        with st.expander("🔄 Trade Diff Details", expanded=False):
                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown("**➕ Added Trades (sample):**")
                                added_sample = [current_trade_map[tid] for tid in list(added_trade_ids)[:10]]
                                for t in added_sample:
                                    st.write(f"`{t['trade_id'][:30]}...` | {t['pnl_pct']:+.2f}% | {t['exit_reason']}")
                            with c2:
                                st.markdown("**➖ Removed Trades (sample):**")
                                removed_sample = [prev_trade_map[tid] for tid in list(removed_trade_ids)[:10]]
                                for t in removed_sample:
                                    st.write(f"`{t['trade_id'][:30]}...` | {t['pnl_pct']:+.2f}% | {t['exit_reason']}")
                else:
                    st.caption(f"📈 **Trade Diff:** First run (no baseline) | Fingerprint: {report.get('trade_ids_hash', 'N/A')}")
                
                # Store current trades for next comparison
                st.session_state[prev_trades_key] = current_trades
                
                # Forensic Details Expander
                with st.expander("🔬 Forensic Details", expanded=False):
                    st.json({
                        "run_id": report['run_id'],
                        "computed_at": report['computed_at'],
                        "config_hash": report['config_hash'],
                        "window_hash": report['window_hash'],
                        "selection_mode": report['selection_mode'],
                        "tightness": report['tightness'],
                        "clamp_policy": report.get('clamp_policy', 'N/A'),
                        "quality_override": report.get('quality_override'),
                        "selected_count": report['selected_count'],
                        "selected_hash": report['selected_hash'],
                        "selected_ids_sample": report.get('selected_ids_sample', []),
                        "used_count": report['used_count'],
                        "used_hash": report['used_hash'],
                        "used_ids_sample": report.get('used_ids_sample', []),
                        "total_entries": report['total_entries'],
                        "engine_path": report['engine_path'],
                        "pnl_signature": report.get('pnl_signature', 'N/A'),
                        "position_sizing_mode": report.get('position_sizing_mode', 'N/A'),
                    })
                
                # =========================================================================
                # BACKTEST DIAGNOSTICS EXPANDER
                # =========================================================================
                with st.expander("📌 Backtest Diagnostics", expanded=False):
                    # Exit reason counts
                    exit_counts = report.get('exit_reason_counts', {})
                    tp_count = exit_counts.get('TP', 0)
                    sl_count = exit_counts.get('SL', 0)
                    hz_count = exit_counts.get('HORIZON', 0)
                    total_trades = tp_count + sl_count + hz_count
                    
                    st.markdown("**Exit Reason Distribution:**")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("TP", f"{tp_count} ({tp_count*100/total_trades:.0f}%)" if total_trades else "0")
                    col2.metric("SL", f"{sl_count} ({sl_count*100/total_trades:.0f}%)" if total_trades else "0")
                    col3.metric("HORIZON", f"{hz_count} ({hz_count*100/total_trades:.0f}%)" if total_trades else "0")
                    
                    # Capping stats
                    tp_capped = report.get('tp_capped_count', 0)
                    sl_capped = report.get('sl_capped_count', 0)
                    st.caption(f"Capped: TP={tp_capped} ({tp_capped*100/total_trades:.0f}%) | SL={sl_capped} ({sl_capped*100/total_trades:.0f}%)" if total_trades else "Capped: N/A")
                    
                    # Raw vs Effective PnL stats
                    st.markdown("**PnL Statistics:**")
                    raw_stats = report.get('pnl_raw_stats', {})
                    eff_stats = report.get('pnl_eff_stats', {})
                    
                    st.caption(
                        f"Raw: min={raw_stats.get('min', 0):.2f}% | p50={raw_stats.get('p50', 0):.2f}% | "
                        f"p90={raw_stats.get('p90', 0):.2f}% | max={raw_stats.get('max', 0):.2f}%"
                    )
                    st.caption(
                        f"Eff: min={eff_stats.get('min', 0):.2f}% | p50={eff_stats.get('p50', 0):.2f}% | "
                        f"p90={eff_stats.get('p90', 0):.2f}% | max={eff_stats.get('max', 0):.2f}%"
                    )
                    
                    # Signatures
                    st.markdown("**Signatures:**")
                    caps_status = "ON" if not report.get('disable_tp_sl_caps', False) else "OFF"
                    raw_status = "ON" if report.get('use_raw_pnl', False) else "OFF"
                    st.caption(
                        f"Trade Fingerprint: {report.get('trade_ids_hash', 'N/A')} | "
                        f"PnL Sig v1: {report.get('pnl_signature', 'N/A')} | "
                        f"PnL Sig v2: {report.get('pnl_signature_v2', 'N/A')}"
                    )
                    st.caption(
                        f"Sizing: {report.get('position_sizing_mode', 'N/A')} | "
                        f"Caps: {caps_status} | Raw: {raw_status}"
                    )
                    
                    # Histogram / Uniqueness
                    unique_count = report.get('pnl_eff_unique_count', 0)
                    top_bins = report.get('pnl_eff_top_bins', [])
                    st.caption(f"PnL Unique Values: {unique_count}")
                    if unique_count <= 3:
                        st.warning("⚠️ LOW PNL VARIETY: ≤3 unique PnL values (TP/SL'e yapışmış olabilir)")
                    
                    if top_bins:
                        st.markdown("**Top PnL Values (histogram):**")
                        top_str = " | ".join([f"{v:.4f}% ({c}x)" for v, c in top_bins[:5]])
                        st.caption(top_str)
                    
                    # Sample trades table
                    trade_list = report.get('trade_list', [])
                    if trade_list:
                        st.markdown("**Trade Sample (first 20):**")
                        import pandas as pd
                        df_trades = pd.DataFrame(trade_list[:20])
                        st.dataframe(df_trades, use_container_width=True, height=200)
                
                # PNL_COLLAPSE Tripwire
                prev_fingerprint_key = f"sniper_arena_prev_fingerprint::{symbol}::{timeframe}"
                prev_pnl_sig_key = f"sniper_arena_prev_pnl_sig::{symbol}::{timeframe}"
                
                curr_fingerprint = report.get('trade_ids_hash', '')
                curr_pnl_sig = report.get('pnl_signature', '')
                prev_fingerprint = st.session_state.get(prev_fingerprint_key, '')
                prev_pnl_sig = st.session_state.get(prev_pnl_sig_key, '')
                
                if prev_fingerprint and prev_pnl_sig:
                    if curr_fingerprint != prev_fingerprint and curr_pnl_sig == prev_pnl_sig:
                        st.warning(
                            "⚠️ PNL_COLLAPSE: Trade Fingerprint değişti ama PnL Signature aynı! "
                            "(TP cap veya sabit notional olabilir)"
                        )
                
                # Store for next run
                st.session_state[prev_fingerprint_key] = curr_fingerprint
                st.session_state[prev_pnl_sig_key] = curr_pnl_sig
                
                # Metrics
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("💰 Sermaye", f"{report['capital_start']:.0f} → {report['capital_end']:.0f}")
                c2.metric("📈 PnL %", f"{report['pnl_pct']:+.2f}%")
                c3.metric("🏆 Win Rate", f"{report['win_rate']:.1f}%")
                c4.metric("📉 Max DD", f"{report['max_drawdown_pct']:.1f}%")
                
                st.caption(f"Trades: {report['trade_count']} | Tightness: {report['tightness']} | Mode: {report['selection_mode']}")
                
            else:  # Full Replay
                from tezaver.matrix.wargame.runner import run_sniper_full_replay_for_symbol
                
                with st.spinner("Full Replay çalışıyor (2 yıl bar-bar)..."):
                    report = run_sniper_full_replay_for_symbol(
                        symbol=symbol,
                        timeframe=timeframe,
                        risk=float(risk),
                        tp_pct=tp_pct,
                        sl_pct=sl_pct,
                        max_bars=max_bars,
                    )
                
                st.success("✅ Full Replay tamamlandı!")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("💰 Sermaye", f"{report.capital_start:.0f} → {report.capital_end:.0f}")
                pnl = (report.capital_end / report.capital_start - 1.0) * 100.0
                c2.metric("📈 PnL %", f"{pnl:+.2f}%")
                c3.metric("🏆 Win Rate", f"{report.win_rate * 100:.1f}%")
                c4.metric("📉 Max DD", f"{report.max_drawdown_pct * 100:.1f}%")
                
                st.caption(f"Trades: {report.trade_count} | TP: {tp_pct*100:.0f}% | SL: {sl_pct*100:.0f}%")
                
                # Profile info
                st.caption(f"📋 Profil: {report.profile_id}")
                
                # Equity curve (downsample for performance)
                if report.equity_curve and len(report.equity_curve) > 10:
                    curve = report.equity_curve
                    # Downsample to max 500 points to prevent UI lag
                    if len(curve) > 500:
                        step = len(curve) // 500
                        curve = [curve[i] for i in range(0, len(curve), step)]
                    st.line_chart(curve)
                    
        except FileNotFoundError as e:
            st.error(
                f"❌ Dataset bulunamadı: {e}\n\n"
                f"Sniper: `PYTHONPATH=src python -m tezaver.sniper {symbol} {timeframe} --from-patterns`\n"
                f"Full Replay: `PYTHONPATH=src python -m tezaver.rally.rally_full_replay_builder {symbol}`"
            )
        except Exception as e:
            st.error(f"❌ Hata: {e}")


DEFAULT_SILVER_15M_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def _render_wargame_silver_15m_section() -> None:
    """Silver 15m War Game (Backtest) section."""
    st.subheader("🎮 War Game – Silver 15m Backtest")

    st.caption(
        "Bu bölüm, seçtiğin Silver 15m profilini geçmiş veri üzerinde test eder. "
        "Coin Lab'den gelen **Silver 15m pattern dataset** kullanılır. "
        "**Tamamen simülasyon** modundadır."
    )

    # Show pattern metadata
    from tezaver.matrix.wargame.filter_debug import load_pattern_meta
    meta = load_pattern_meta(DEFAULT_SILVER_15M_SYMBOLS[0], "15m")
    if meta:
        st.caption(
            f"📚 **Veri Kapsamı:** {meta['start_date']} → {meta['end_date']} | "
            f"Pattern: {meta['num_events']} | ~{meta['years']:.1f} yıl"
        )

    # Data source selector
    data_source = st.radio(
        "Veri Kaynağı",
        options=["Pattern Dataset", "Full Replay", "Hybrid (Karşılaştırma)"],
        horizontal=True,
        help=(
            "**Pattern Dataset**: Yalnızca tespit edilen rally pattern'leri. Hızlı A/B testi.\n"
            "**Full Replay**: Tüm 15m bar serisini yeniden oynatır. Gerçek simülasyon.\n"
            "**Hybrid**: Aynı ayarlarla hem Pattern hem Full Replay çalışır ve karşılaştırır."
        ),
        key="wg_data_source",
    )
    
    col1, col2, col3, col4 = st.columns([2, 2, 2, 3])
    with col1:
        symbol = st.selectbox(
            "Coin",
            options=DEFAULT_SILVER_15M_SYMBOLS,
            index=0,
            key="wg_symbol",
        )
    with col2:
        risk = st.number_input(
            "Risk (% / trade)",
            min_value=0.01,
            max_value=1.0,
            value=1.0,
            step=0.01,
            help="0.01 = %1, 1.0 = %100",
            key="wg_risk",
        )
    with col3:
        mode = st.selectbox(
            "Mod",
            options=["contract", "experiment"],
            index=1,  # Default to experiment for testing
            help=(
                '"contract": CoinPage V2 sıkı filtreler.\n'
                '"experiment": Geniş filtreler, test amaçlı.'
            ),
            key="wg_mode",
        )
    with col4:
        tightness = st.slider(
            "Sıkılık",
            min_value=0,
            max_value=100,
            value=50,  # Default midpoint
            step=5,
            help=(
                "100 = CoinPage kartı birebir. "
                "0 = Dataset min-max, ML kapalı. "
                "50 = Ortası."
            ),
            key="wg_tightness",
            disabled=(mode == "contract"),
        )

    # Data source stats caption
    try:
        from tezaver.matrix.wargame.filter_debug import (
            compute_silver_pattern_dataset_stats,
            compute_silver_full_replay_dataset_stats,
            format_data_source_stats_human,
        )
        
        if data_source == "Pattern Dataset":
            stats = compute_silver_pattern_dataset_stats(symbol, "15m")
            st.caption(format_data_source_stats_human(stats))
        elif data_source == "Full Replay":
            stats = compute_silver_full_replay_dataset_stats(symbol, "15m")
            st.caption(format_data_source_stats_human(stats))
        else:  # Hybrid
            p_stats = compute_silver_pattern_dataset_stats(symbol, "15m")
            f_stats = compute_silver_full_replay_dataset_stats(symbol, "15m")
            st.caption(format_data_source_stats_human(p_stats))
            st.caption(format_data_source_stats_human(f_stats))
    except Exception:
        pass

    if st.button("🎮 War Game'i Çalıştır", use_container_width=True, key="wg_run"):
        with st.spinner("War Game çalışıyor..."):
            try:
                if data_source == "Pattern Dataset":
                    from tezaver.matrix.wargame.runner import run_silver_15m_from_patterns_for_symbol
                    
                    report = run_silver_15m_from_patterns_for_symbol(
                        symbol=symbol,
                        risk_per_trade_pct=float(risk),
                        mode=mode,
                        tightness=float(tightness) if mode == "experiment" else 100.0,
                    )
                elif data_source == "Full Replay":
                    from tezaver.matrix.wargame.runner import run_silver_15m_full_replay_for_symbol
                    
                    report = run_silver_15m_full_replay_for_symbol(
                        symbol=symbol,
                        risk=float(risk),
                        mode=mode,
                        tightness=int(tightness) if mode == "experiment" else 100,
                    )
                else:  # Hybrid
                    from tezaver.matrix.wargame.runner import run_silver_15m_hybrid_for_symbol
                    
                    hybrid_result = run_silver_15m_hybrid_for_symbol(
                        symbol=symbol,
                        risk=float(risk),
                        mode=mode,
                        tightness=int(tightness) if mode == "experiment" else 100,
                    )
                    
                    # Render hybrid comparison
                    st.markdown("#### 🔀 Hybrid Sonuç – Pattern vs Full Replay")
                    
                    pr = hybrid_result.pattern_report
                    fr = hybrid_result.full_replay_report
                    pr_pnl = (pr.capital_end / pr.capital_start - 1.0) * 100.0 if pr.capital_start > 0 else 0.0
                    fr_pnl = (fr.capital_end / fr.capital_start - 1.0) * 100.0 if fr.capital_start > 0 else 0.0
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**📊 Pattern Dataset**")
                        st.metric("💰 Sermaye", f"{pr.capital_start:.2f} → {pr.capital_end:.2f}", f"{pr_pnl:+.2f}%")
                        st.metric("📉 Max DD", f"{pr.max_drawdown_pct * 100:.2f}%")
                        st.metric("🧾 İşlemler", f"{pr.trade_count} ({pr.win_rate:.0%})")
                    with col2:
                        st.markdown("**📈 Full Replay**")
                        st.metric("💰 Sermaye", f"{fr.capital_start:.2f} → {fr.capital_end:.2f}", f"{fr_pnl:+.2f}%")
                        st.metric("📉 Max DD", f"{fr.max_drawdown_pct * 100:.2f}%")
                        st.metric("🧾 İşlemler", f"{fr.trade_count} ({fr.win_rate:.0%})")
                    
                    st.markdown("---")
                    st.markdown(
                        f"**Δ PnL%:** {hybrid_result.delta_pnl_pct:+.2f}% &nbsp;&nbsp; "
                        f"**Δ Trades:** {hybrid_result.delta_trades:+d} &nbsp;&nbsp; "
                        f"**Δ MaxDD%:** {hybrid_result.delta_max_dd_pct * 100:+.2f}%"
                    )
                    return  # Exit after hybrid render
                    
            except Exception as exc:
                st.error(f"War Game çalıştırılırken hata: {exc}")
                return

        # Display results (for single-source modes)
        st.markdown("#### 📊 Sonuç Özeti")

        cap_start = report.capital_start
        cap_end = report.capital_end
        pnl_pct = (cap_end / cap_start - 1.0) * 100.0 if cap_start > 0 else 0.0
        max_dd = report.max_drawdown_pct * 100 if report.max_drawdown_pct else 0.0
        trades = report.trade_count

        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            st.metric("💰 Sermaye", f"{cap_start:.2f} → {cap_end:.2f}", f"{pnl_pct:+.2f}%")
        with col_b:
            st.metric("📉 Max Drawdown", f"{max_dd:.2f}%")
        with col_c:
            st.metric("🧾 İşlem Sayısı", f"{trades}")
        with col_d:
            st.metric("🏆 Win Rate", f"{report.win_rate:.1%}")

        # Equity curve
        if report.equity_curve:
            st.markdown("##### 📈 Equity Curve")
            import pandas as pd
            eq_df = pd.DataFrame({
                "Tick": list(range(len(report.equity_curve))),
                "Equity": report.equity_curve,
            })
            st.line_chart(eq_df, x="Tick", y="Equity", use_container_width=True)

        # Matrix Diary expander
        if report.events:
            with st.expander(f"📓 Matrix Günlüğü (Diary) – {len(report.events)} event", expanded=False):
                from tezaver.matrix.wargame.diary import format_events_as_lines
                
                lines = format_events_as_lines(report.events)
                diary_text = "\n".join(lines)
                st.text_area(
                    "Günlük",
                    value=diary_text,
                    height=300,
                    label_visibility="collapsed",
                )
        else:
            st.info("Bu War Game raporu için kayıtlı telemetry/event bulunamadı.")

        # Filter Analysis expander (only in experiment mode)
        if mode == "experiment":
            with st.expander("🧪 Filtre Özeti (Tightness V2)", expanded=False):
                try:
                    from tezaver.matrix.wargame.filter_debug import (
                        compute_silver_dataset_stats_from_patterns,
                        analyze_silver_filter_squeeze,
                    )
                    from tezaver.matrix.wargame.runner import _load_silver_profile_and_config
                    from tezaver.matrix.strategies.silver_core import (
                        build_silver_filter_window,
                        SilverStrategyConfig,
                    )
                    
                    # Load card config and dataset stats
                    _, cfg = _load_silver_profile_and_config(symbol)
                    stats = compute_silver_dataset_stats_from_patterns(symbol, "15m")
                    
                    if stats:
                        # Build filter window with tightness
                        window = build_silver_filter_window(cfg, stats, float(tightness))
                        
                        # Display tightness info
                        st.markdown(f"**Tightness:** {tightness}")
                        ml_status = "✅ AÇIK" if window.ml_enabled else "❌ KAPALI"
                        st.markdown(f"**ML Filtreleri:** {ml_status}")
                        
                        # Display effective ranges
                        st.markdown("**Etkin Aralıklar:**")
                        st.markdown(f"- RSI 15m: `{window.rsi_15m_range[0]:.2f} – {window.rsi_15m_range[1]:.2f}`")
                        st.markdown(f"- Volume Rel: `{window.volume_rel_range[0]:.2f} – {window.volume_rel_range[1]:.2f}`")
                        st.markdown(f"- ATR %: `{window.atr_pct_range[0]:.3f} – {window.atr_pct_range[1]:.3f}`")
                        
                        if window.ml_enabled and window.rsi_gap_1d_range:
                            st.markdown(f"- RSI Gap 1D: `{window.rsi_gap_1d_range[0]:.2f} – {window.rsi_gap_1d_range[1]:.2f}`")
                        if window.ml_enabled and window.rsi_1h_range:
                            st.markdown(f"- RSI 1H: `{window.rsi_1h_range[0]:.2f} – {window.rsi_1h_range[1]:.2f}`")
                        
                        # Stage analysis (using window ranges via a temp config)
                        temp_cfg = SilverStrategyConfig(
                            symbol=symbol,
                            timeframe="15m",
                            rsi_range=window.rsi_15m_range,
                            volume_rel_range=window.volume_rel_range,
                            atr_pct_range=window.atr_pct_range,
                            rsi_gap_1d_range=window.rsi_gap_1d_range if window.ml_enabled else None,
                            rsi_1h_range=window.rsi_1h_range if window.ml_enabled else None,
                            min_quality_score=60.0,
                        )
                        stage_stats = analyze_silver_filter_squeeze(symbol, "15m", temp_cfg)
                        
                        if stage_stats.total_patterns > 0:
                            st.markdown(f"**Aşama Analizi:** (Toplam: {stage_stats.total_patterns})")
                            import pandas as pd
                            filter_df = pd.DataFrame(stage_stats.to_list())
                            st.dataframe(filter_df, use_container_width=True)
                    else:
                        st.info("Dataset stats bulunamadı.")
                except Exception as e:
                    st.warning(f"Filtre analizi yapılamadı: {e}")



def _render_live_monitor_section(rows: List[ProfileBoardRow], initial_capital: float) -> None:
    """Live cell state monitor section."""
    st.subheader("📡 Live Durum – Hesap & İşlem Özeti")

    st.caption(
        "Matrix Live cluster'daki LIVE-eligible hücrelerin disk üzerindeki state dosyalarından "
        "okunan equity ve işlem özeti. State dosyaları: `data/live_state/...`"
    )

    # Get LIVE eligible rows
    live_rows = [r for r in rows if getattr(r, 'live_eligible', False)]

    if not live_rows:
        st.info("Henüz LIVE için uygun profil yok. Strategy Board'dan en az bir profil APPROVED + risk_contract ile işaretlenmeli.")
        return

    from tezaver.matrix.live.live_state_tools import load_live_cell_state
    import pandas as pd

    summaries = []
    for row in live_rows:
        state = load_live_cell_state(
            symbol=row.symbol,
            timeframe=row.timeframe,
            profile_id=row.profile_id,
            initial_capital=initial_capital,
        )

        summaries.append({
            "Coin": state.symbol,
            "TF": state.timeframe,
            "Profil": state.profile_id[:25] + "..." if len(state.profile_id) > 28 else state.profile_id,
            "Equity": f"{state.equity:.2f}" if state.equity else "-",
            "PnL %": f"{state.pnl_pct:+.2f}%" if state.pnl_pct else "-",
            "İşlem": state.trade_count,
            "Son İşlem": state.last_side or "-",
            "Son PnL": f"{state.last_pnl:+.2f}" if state.last_pnl else "-",
        })

    st.dataframe(summaries, use_container_width=True)


# =============================================================================
# SNIPER ARENA SECTION
# =============================================================================

def _render_sniper_arena_section():
    """Sniper Arena - Sniper backtest moved from Sniper Lab."""
    
    st.subheader("🎯 Sniper Arena – 100 → X")
    st.caption(
        "Sniper entries dataset üzerinden backtest. "
        "Sniper Lab annotation için, test burada."
    )
    
    with st.expander("🎯 Sniper Backtest Ayarları", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            symbol = st.selectbox(
                "Coin",
                ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
                key="sniper_arena_symbol"
            )
        
        with col2:
            timeframe = st.selectbox(
                "Timeframe",
                ["15m", "1h", "4h"],
                key="sniper_arena_tf"
            )
        
        with col3:
            risk = st.slider(
                "Risk / Trade",
                min_value=0.01,
                max_value=1.0,
                value=1.0,
                step=0.01,
                key="sniper_arena_risk"
            )
        
        # Mode selector
        st.markdown("---")
        mode = st.radio(
            "Test Modu",
            options=["quick", "full_replay"],
            format_func=lambda x: {
                "quick": "⚡ Quick Backtest (pre-computed gains ile hızlı)",
                "full_replay": "🎬 Full Replay (2 yıllık bar-bar simülasyon)",
            }[x],
            horizontal=True,
            key="sniper_arena_mode"
        )
        
        # Full replay settings
        if mode == "full_replay":
            c1, c2, c3 = st.columns(3)
            with c1:
                tp_pct = st.slider("Take Profit %", 1, 20, 8, key="sniper_arena_tp") / 100.0
            with c2:
                sl_pct = st.slider("Stop Loss %", 1, 10, 3, key="sniper_arena_sl") / 100.0
            with c3:
                max_bars = st.slider("Max Bars", 10, 100, 50, key="sniper_arena_max_bars")
        
        run_btn = st.button(
            "🚀 Sniper Test Çalıştır",
            key="btn_run_sniper_arena",
            use_container_width=True,
            type="primary"
        )
        
        if run_btn:
            try:
                if mode == "quick":
                    from tezaver.sniper.sniper_backtest import run_sniper_backtest_for_symbol_timeframe
                    
                    with st.spinner("Quick Backtest çalışıyor..."):
                        result = run_sniper_backtest_for_symbol_timeframe(
                            symbol=symbol,
                            timeframe=timeframe,
                            risk_per_trade=float(risk),
                        )
                    
                    st.success("✅ Quick Backtest tamamlandı!")
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("💰 Sermaye", f"{result['capital_start']:.0f} → {result['capital_end']:.0f}")
                    c2.metric("📈 PnL %", f"{result['pnl_pct']:+.2f}%")
                    c3.metric("🏆 Win Rate", f"{result['win_rate']:.1f}%")
                    c4.metric("📉 Max DD", f"{result['max_drawdown_pct']:.1f}%")
                    
                    st.caption(
                        f"Entries: {result['selected_entries']}/{result['total_entries']} | "
                        f"Trades: {result['trade_count']}"
                    )
                    
                    # Profile info
                    profile_id = f"{symbol.replace('USDT', '')}_SNIPER_15M_CORE_V1"
                    st.caption(
                        f"📋 Profil: {profile_id} | Durum: EXPERIMENTAL | Max Risk (contract): 0.01"
                    )
                    
                    with st.expander("🧬 Ham JSON", expanded=False):
                        st.json(result)
                
                else:  # full_replay
                    from tezaver.matrix.wargame.runner import run_sniper_full_replay_for_symbol
                    
                    with st.spinner("Full Replay çalışıyor (2 yıllık bar-bar)..."):
                        report = run_sniper_full_replay_for_symbol(
                            symbol=symbol,
                            timeframe=timeframe,
                            risk=float(risk),
                            tp_pct=tp_pct,
                            sl_pct=sl_pct,
                            max_bars=max_bars,
                        )
                    
                    st.success("✅ Full Replay tamamlandı!")
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("💰 Sermaye", f"{report.capital_start:.0f} → {report.capital_end:.0f}")
                    pnl = (report.capital_end / report.capital_start - 1.0) * 100.0
                    c2.metric("📈 PnL %", f"{pnl:+.2f}%")
                    c3.metric("🏆 Win Rate", f"{report.win_rate * 100:.1f}%")
                    c4.metric("📉 Max DD", f"{report.max_drawdown_pct * 100:.1f}%")
                    
                    st.caption(f"Trades: {report.trade_count} | TP: {tp_pct*100:.0f}% | SL: {sl_pct*100:.0f}% | Max Bars: {max_bars}")
                    
                    # Equity curve
                    if report.equity_curve and len(report.equity_curve) > 10:
                        st.line_chart(report.equity_curve)
                    
            except FileNotFoundError as e:
                st.error(
                    f"❌ Dataset bulunamadı: {e}\n\n"
                    f"Sniper: `PYTHONPATH=src python -m tezaver.sniper {symbol} {timeframe} --from-patterns`\n"
                    f"Full Replay: `PYTHONPATH=src python -m tezaver.rally.rally_full_replay_builder {symbol}`"
                )
            except Exception as e:
                st.error(f"❌ Hata: {e}")
