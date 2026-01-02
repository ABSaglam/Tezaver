import streamlit as st
import sys
import os
import time
import json
import subprocess
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tezaver.core.settings_manager import settings_manager
from tezaver.core import system_state, coin_cell_paths
from tezaver.core.config import get_turkey_now, to_turkey_time
from tezaver.core.seal_manager import seal_manager
from tezaver.ui.data_health_tab import render_data_health_page

# --- HELPERS ---

def _format_time_diff(dt_iso):
    """Returns a tuple (friendly_str, status_color) for a given ISO timestamp."""
    if not dt_iso:
        return "Hiç çalıştırılmadı", "🔴"
    
    try:
        dt = datetime.fromisoformat(dt_iso.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff = now - dt
        
        if diff.days == 0:
            if diff.seconds < 60: return "Az önce", "🟢"
            elif diff.seconds < 3600: return f"{diff.seconds // 60} dk önce", "🟢"
            else: return f"{diff.seconds // 3600} sa önce", "🟢"
        elif diff.days == 1:
            return "Dün", "🟡"
        else:
            return f"{diff.days} gün önce", "🔴"
    except:
        return "-", "🔴"

def _run_process_with_spinner(label, cmd_list, success_msg="Tamamlandı"):
    """Runs a process with a simple spinner and feedback."""
    with st.spinner(f"{label} çalışıyor..."):
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = "src"
            res = subprocess.run(cmd_list, capture_output=True, text=True, env=env)
            
            if res.returncode == 0:
                system_state.record_task_run(label)
                st.success(f"{label}: {success_msg}")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"❌ {label} hatası!")
                with st.expander("Hata Detayı"):
                    st.code(res.stderr)
        except Exception as e:
            st.error(f"Kritik Hata: {e}")

def _run_complex_sequence(sequence_name, tasks):
    """Runs a multi-step sequence with `st.status`."""
    st.toast(f"{sequence_name} başlatılıyor...", icon="🚀")
    with st.status(f"🔄 {sequence_name} İşleniyor...", expanded=True) as status:
        total = len(tasks)
        for i, (label, script_path) in enumerate(tasks):
            status.write(f"⏳ **{label}** ({i+1}/{total})...")
            try:
                cmd = [sys.executable] + shlex.split(script_path)
                env = os.environ.copy()
                env["PYTHONPATH"] = "src"
                res = subprocess.run(cmd, capture_output=True, text=True, env=env)
                
                if res.returncode != 0:
                    status.update(label="❌ İşlem Sırasında Hata Oluştu!", state="error")
                    st.error(f"Hata: {label}")
                    st.code(res.stderr)
                    return
                
                system_state.record_task_run(label)
                status.write(f"✅ **{label}** tamamlandı.")
            except Exception as e:
                status.update(label="❌ Kritik Hata!", state="error")
                st.error(str(e))
                return
        status.update(label=f"🎉 {sequence_name} Başarıyla Tamamlandı!", state="complete", expanded=False)
    
    st.success("Tüm sistem güncel!")
    time.sleep(1.5)
    st.rerun()

# --- MAIN RENDER ---

def render_system_dashboard():
    st.title("🎛️ Sistem Yönetim Paneli")
    st.markdown("---")

    # Load State
    state = system_state.load_state()

    # Tabs
    tab_ops, tab_scans, tab_data, tab_settings, tab_seals = st.tabs([
        "🎮 Komuta Merkezi", 
        "📡 Sinyal Taramaları", 
        "💾 Veri Merkezi",
        "⚙️ Ayarlar", 
        "🔐 Mühürler & Log"
    ])

    # ================= TAB 1: OPERASYON (KOMUTA) =================
    with tab_ops:
        # 1. System Vitality Header
        last_run_str, last_run_color = _format_time_diff(state.last_full_pipeline_run_at)
        
        c1, c2, c3 = st.columns([2, 5, 2])
        with c1:
            st.metric("Sistem Durumu", "Aktif", delta="Online", delta_color="normal")
        with c2:
            st.metric("Son Tam Tur Analiz", last_run_str, delta=None)
        with c3:
            st.metric("Sistem Sağlığı", "Stabil", delta="OK")

        st.divider()

        # 2. Main Action Buttons (The "Genius" simplified controls)
        c_main, c_maint, c_backup = st.columns([3, 2, 2], gap="medium")

        with c_main:
            st.subheader("🚀 Analiz Başlat")
            st.caption("Verileri günceller, ralli arar ve sonuçları derler.")
            
            if st.button("🔄 Tam Tur Güncelleme", type="primary", use_container_width=True, help="Binance'den son verileri alıp, tüm analiz motorunu (features, snapshots, labeler) çalıştırır."):
                tasks = [
                    ("Veri İndirme (Update)", "src/tezaver/data/run_history_update.py"),
                    ("Özellik İnşası (Features)", "src/tezaver/features/run_feature_build.py"),
                    ("Fotoğraf Çekimi (Snapshots)", "src/tezaver/snapshots/run_snapshot_build.py"),
                    ("Çoklu Zaman Dilimi (Multi-TF)", "src/tezaver/snapshots/run_multi_tf_snapshot_build.py"),
                    ("Ralli Etiketleme (Labeler)", "src/tezaver/outcomes/run_rally_labeler.py"),
                    ("Ralli Aileleri (Families)", "src/tezaver/rally/run_rally_families.py"),
                    ("Seviye Tespiti (Levels)", "src/tezaver/levels/run_trend_levels_build.py"),
                    ("Beyin Senkronizasyonu (Sync)", "src/tezaver/core/run_brain_sync.py")
                ]
                _run_complex_sequence("Tam Sistem Güncellemesi", tasks)

        with c_maint:
            st.subheader("🛠️ Bakım")
            st.caption("Veritabanı temizliği ve onarımı.")
            if st.button("🧹 Temizlik Yap", use_container_width=True):
                 _run_process_with_spinner("Bakım Modu", [sys.executable, "src/tezaver/offline/run_offline_maintenance.py", "--mode", "full", "--all-symbols"], "Temizlik Bitti")

        with c_backup:
            st.subheader("📦 Yedek")
            st.caption("Sistemin anlık kopyası.")
            if st.button("💾 Hızlı Yedek Al", use_container_width=True):
                 _run_process_with_spinner("Hızlı Yedek", [sys.executable, "src/tezaver/backup/run_backup.py"], "Yedek Alındı")

        st.markdown("---")
        
        # 3. Advanced / Manual Control (Collapsed)
        with st.expander("🛡️ Manuel Kontrol (Geliştirici)"):
            st.warning("Bu işlemler manuel müdahale gerektirdiğinde kullanılır. Normal akışta 'Tam Tur Güncelleme' yeterlidir.")
            
            c_m1, c_m2 = st.columns(2)
            with c_m1:
                st.markdown("**Bireysel Modüller**")
                if st.button("Sadece Veri İndir (History)"): _run_process_with_spinner("History Update", [sys.executable, "src/tezaver/data/run_history_update.py"])
                if st.button("Sadece Feature Build"): _run_process_with_spinner("Feature Build", [sys.executable, "src/tezaver/features/run_feature_build.py"])
                if st.button("Sadece Labeler"): _run_process_with_spinner("Labeler", [sys.executable, "src/tezaver/outcomes/run_rally_labeler.py"])
            with c_m2:
                st.markdown("**Testler & Tam Yedek**")
                if st.button("Birim Testleri Çalıştır"): _run_process_with_spinner("Tests", [sys.executable, "-m", "pytest", "tests", "-q"])
                st.markdown("")
                if st.button("FULL Backup (Uzun Sürer)"): _run_process_with_spinner("Full Backup", [sys.executable, "src/tezaver/backup/run_backup.py", "full"])

    # ================= TAB 2: TARAMALAR =================
    with tab_scans:
        st.info("💡 Buradaki taramalar, piyasa verileri üzerinden anlık fırsatlar yakalar.")

        # Helper to get local path timestamp
        def _get_ts(p):
            if p.exists(): return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
            return None

        # 1. UNIFIED TIME-LABS (15m, 1h, 4h)
        st.subheader("⏳ Zaman Analizleri (Time-Labs)")
        
        c1, c2, c3 = st.columns(3)
        
        # 15M
        with c1:
            ts_str, ts_col = _format_time_diff(_get_ts(coin_cell_paths.get_fast15_rallies_summary_path("BTCUSDT")))
            st.markdown(f"**⚡ 15 Dakika** ({ts_col} {ts_str})")
            if st.button("▶️ 15dk Başlat", key="scan_15", use_container_width=True):
                 _run_process_with_spinner("15dk Analizi", [sys.executable, "src/tezaver/rally/run_fast15_rally_scan.py", "--all-symbols"])

        # 1H
        with c2:
             ts_str, ts_col = _format_time_diff(_get_ts(coin_cell_paths.get_time_labs_rallies_summary_path("BTCUSDT", "1h")))
             st.markdown(f"**🕐 1 Saat** ({ts_col} {ts_str})")
             if st.button("▶️ 1H Başlat", key="scan_1h", use_container_width=True):
                 _run_process_with_spinner("1H Analizi", [sys.executable, "src/tezaver/rally/run_time_labs_scan.py", "--tf", "1h", "--all-symbols"])

        # 4H
        with c3:
             ts_str, ts_col = _format_time_diff(_get_ts(coin_cell_paths.get_time_labs_rallies_summary_path("BTCUSDT", "4h")))
             st.markdown(f"**🕓 4 Saat** ({ts_col} {ts_str})")
             if st.button("▶️ 4H Başlat", key="scan_4h", use_container_width=True):
                 _run_process_with_spinner("4H Analizi", [sys.executable, "src/tezaver/rally/run_time_labs_scan.py", "--tf", "4h", "--all-symbols"])

        st.divider()

        # 2. MARKETS TOOLS
        st.subheader("📡 Piyasa Araçları")
        c_radar, _ = st.columns([1, 2])
        
        with c_radar:
            ts_str, ts_col = _format_time_diff(_get_ts(coin_cell_paths.get_coin_profile_dir("BTCUSDT") / "rally_radar.json"))
            st.markdown(f"**🌍 Rally Radar** ({ts_col} {ts_str})")
            st.caption("Tüm piyasanın genel sıcaklık haritası.")
            if st.button("📡 Radarı Güncelle", key="scan_radar"):
                 _run_process_with_spinner("Radar Güncelleme", [sys.executable, "src/tezaver/rally/run_rally_radar_export.py"])
        
        st.divider()
        st.caption("Not: Taramalar sistem kaynağı tüketebilir. Piyasa hareketli değilse sık sık çalıştırmanıza gerek yoktur.")

    # ================= TAB 3: VERİ MERKEZİ (Embedded) =================
    with tab_data:
        render_data_health_page()

    # ================= TAB 4: AYARLAR =================
    with tab_settings:
        if 'user_settings' not in st.session_state:
            st.session_state.user_settings = settings_manager.load_settings()
        
        settings = st.session_state.user_settings
        indicators = settings.get('indicators', {})

        st.subheader("⚙️ Grafik & Analiz Ayarları")
        
        # Save Button Top Right
        if st.button("💾 Kaydet ve Uygula", type="primary", key="set_save_main"):
            settings_manager.save_settings(settings)
            st.success("Ayarlar başarıyla kaydedildi!")
        
        t1, t2, t3 = st.tabs(["📊 Görünüm", "📈 Ortalamalar", "🌊 Osilatörler"])
        
        with t1: # Appearance
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Mum Renkleri**")
                candles = indicators.get('candles', {})
                candles['up_color'] = st.color_picker("Yükseliş", value=candles.get('up_color', '#089981'))
                candles['down_color'] = st.color_picker("Düşüş", value=candles.get('down_color', '#F23645'))
                indicators['candles'] = candles
            with c2:
                st.markdown("**Hacim**")
                vol = indicators.get('volume', {})
                vol['enabled'] = st.toggle("Hacim Barları", value=vol.get('enabled', True))
                indicators['volume'] = vol

        with t2: # MAs
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**EMA Hızlı**")
                ef = indicators.get('ema_fast', {})
                ef['enabled'] = st.toggle("Aktif", value=ef.get('enabled', True), key="ema_f_en")
                ef['period'] = st.number_input("Periyot", 1, value=ef.get('period', 20), key="ema_f_per")
                ef['color'] = st.color_picker("Renk", value=ef.get('color', '#2962FF'), key="ema_f_col")
                indicators['ema_fast'] = ef
            with c2:
                st.markdown("**EMA Yavaş**")
                es = indicators.get('ema_slow', {})
                es['enabled'] = st.toggle("Aktif", value=es.get('enabled', True), key="ema_s_en")
                es['period'] = st.number_input("Periyot", 1, value=es.get('period', 50), key="ema_s_per")
                es['color'] = st.color_picker("Renk", value=es.get('color', '#FF9800'), key="ema_s_col")
                indicators['ema_slow'] = es

        with t3: # Oscillators
            st.markdown("**RSI**")
            rsi = indicators.get('rsi', {})
            rsi['enabled'] = st.toggle("RSI Göster", value=rsi.get('enabled', True))
            rsi['period'] = st.number_input("Periyot", 1, value=rsi.get('period', 14))
            indicators['rsi'] = rsi
            
            st.divider()
            
            st.markdown("**MACD**")
            macd = indicators.get('macd', {})
            macd['enabled'] = st.toggle("MACD Göster", value=macd.get('enabled', True))
            indicators['macd'] = macd

        settings['indicators'] = indicators
        st.session_state.user_settings = settings

    # ================= TAB 5: MÜHÜRLER & LOG =================
    with tab_seals:
        c_seal, c_log = st.columns([1, 1])
        
        with c_seal:
            st.subheader("🔐 Mühür Yönetimi")
            # Simple Seal Viewer
            seals = seal_manager.get_all_seals()
            if not seals:
                st.info("Aktif mühür bulunmuyor.")
            else:
                for k, v in seals.items():
                    with st.expander(f"🔒 {k}"):
                        st.caption(f"Reason: {v.get('reason')}")
                        if st.button("Mührü Kır", key=f"break_{k}"):
                            seal_manager.unseal_item(k)
                            st.rerun()
            
            with st.expander("➕ Mühür Ekle"):
                nk = st.text_input("Mühür Adı")
                nr = st.text_input("Gerekçe")
                if st.button("Ekle"):
                    if nk: seal_manager.seal_item(nk, nr); st.rerun()

        with c_log:
            st.subheader("📜 Sistem Logları")
            lc = st.slider("Satır Sayısı", 100, 1000, 200)
            if st.button("Logları Yenile"): st.rerun()
            lines = system_state.get_log_tail(lc)
            st.code("".join(lines), language="text")
