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

# Helper for standard button rendering (migrated from main_panel)
def _render_scan_button(label: str, path: Optional[Path], key: str, help_text: str, run_func):
    """Renders a standardized scan button with status indicator."""
    status_emoji = "🔴"
    time_str = "Hiç çalıştırılmadı"
    
    if path and path.exists():
        mtime_utc = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        mtime_tr = to_turkey_time(mtime_utc)
        now_tr = get_turkey_now()
        diff = now_tr - mtime_tr
        
        if diff.days == 0:
            if diff.seconds < 60: time_str = "Az önce"
            elif diff.seconds < 3600: time_str = f"{diff.seconds // 60} dk önce"
            else: time_str = f"{diff.seconds // 3600} sa önce"
            status_emoji = "🟢"
        elif diff.days == 1:
            time_str = "Dün"
            status_emoji = "🟡"
        else:
            time_str = f"{diff.days} gn önce"
            status_emoji = "🔴"

    # Button Row
    col_btn, col_info = st.columns([3, 1])
    with col_btn:
        if st.button(f"{status_emoji} {label}", key=key, help=help_text, use_container_width=True):
            run_func()
    with col_info:
        st.caption(time_str)

def _run_script(script_path: str, success_msg: str):
    """Generalized script runner."""
    st.toast(f"{success_msg} başlatılıyor...", icon="🚀")
    with st.spinner(f"{success_msg} çalışıyor..."):
        try:
            # Prepare environment
            env = os.environ.copy()
            env["PYTHONPATH"] = "src"
            
            # Prepare command
            cmd = [sys.executable] + shlex.split(script_path)
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            
            if result.returncode == 0:
                # Record timestamp
                try:
                    system_state.record_task_run(success_msg)
                except Exception as e:
                    print(f"Error recording state: {e}")
                    
                st.success(f"{success_msg} Tamamlandı!")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Hata Kodu: {result.returncode}")
                with st.expander("Hata Detayı"):
                    st.code(result.stdout + "\n" + result.stderr)
                    
        except Exception as e:
            st.error(f"Kritik Hata: {e}")

def _run_command_with_feedback(label: str, cmd: list, on_success, on_fail):
    """Runs a command with feedback (progress spinner)."""
    with st.spinner(f"{label} çalışıyor..."):
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = "src"
            start_time = time.time()
            
            res = subprocess.run(cmd, capture_output=True, text=True, env=env)
            duration = time.time() - start_time
            
            if res.returncode == 0:
                on_success(duration, res.stdout, res.stderr)
            else:
                on_fail(duration, res.stdout, res.stderr)
        except Exception as e:
            st.error(f"Komut çalıştırma hatası: {e}")

def _format_relative_time_local(iso_str):
    """Local version of time formatter."""
    if not iso_str:
        return "-", "K", "🔴"
    
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff = now - dt
        
        if diff.days == 0:
            status = "Y"
            dot = "🟢"
            if diff.seconds < 60: s = "Az önce"
            elif diff.seconds < 3600: s = f"{diff.seconds // 60} dk önce"
            else: s = f"{diff.seconds // 3600} sa önce"
        elif diff.days == 1:
            status = "S"
            dot = "🟡"
            s = "Dün"
        else:
            status = "K"
            dot = "🔴"
            s = f"{diff.days} gün önce"
            
        return s, status, dot
    except:
        return "-", "K", "🔴"

def render_system_dashboard():
    """Renders the unified System & Settings Dashboard."""
    
    st.title("🖥️ Sistem Yönetim Merkezi")
    st.markdown("---")
    
    # Navigation Tabs
    tab_status, tab_scans, tab_settings, tab_dev = st.tabs([
        "📡 Durum & Kontrol", 
        "🛠️ Taramalar", 
        "⚙️ Ayarlar", 
        "👨‍💻 Geliştirici"
    ])
    
    # ================= TAB 1: SÜREÇLER & KONTROL =================
    with tab_status:
        state = system_state.load_state()

        # 1. Helpers
        def _run_sequence(sequence_name, tasks):
            """Runs a list of tasks sequentially."""
            st.toast(f"{sequence_name} başlatılıyor...", icon="🚀")
            with st.status(f"{sequence_name} Çalışıyor...", expanded=True) as status:
                total = len(tasks)
                for i, (label, script_path) in enumerate(tasks):
                    status.write(f"⏳ **{label}** çalıştırılıyor ({i+1}/{total})...")
                    try:
                        cmd = [sys.executable] + shlex.split(script_path)
                        env = os.environ.copy()
                        env["PYTHONPATH"] = "src"
                        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
                        if res.returncode != 0:
                            status.update(label="Hata!", state="error", expanded=True)
                            st.error(f"❌ {label} başarısız oldu!")
                            st.error(res.stderr)
                            return
                        
                        # Update state for this task
                        system_state.record_task_run(label)
                        status.write(f"✅ **{label}** tamamlandı.")
                    except Exception as e:
                        status.update(label="Hata!", state="error", expanded=True)
                        st.error(f"Kritik Hata ({label}): {e}")
                        return
                status.update(label=f"🎉 {sequence_name} Başarıyla Tamamlandı!", state="complete", expanded=False)
            st.success("Tüm işlemler bitti!")
            time.sleep(1)
            st.rerun()

        # 2. Definitions
        tasks_data = [
            ("📥 History Update", "src/tezaver/data/run_history_update.py"),
            ("🧮 Feature Build", "src/tezaver/features/run_feature_build.py"),
            ("📸 Snapshot Build", "src/tezaver/snapshots/run_snapshot_build.py"),
            ("⏱️ Multi-TF Snap", "src/tezaver/snapshots/run_multi_tf_snapshot_build.py")
        ]
        tasks_analysis = [
            ("🏷️ Rally Labeler", "src/tezaver/outcomes/run_rally_labeler.py"),
            ("🧬 Rally Families", "src/tezaver/rally/run_rally_families.py"),
            ("🧱 Levels Build", "src/tezaver/levels/run_trend_levels_build.py")
        ]
        tasks_wisdom = [
            ("📜 Pattern Wisdom", "src/tezaver/wisdom/run_pattern_stats.py"),
            ("⚡ Regime Shock", "src/tezaver/brains/run_regime_shock_build.py"),
            ("🌍 Global Wisdom", "src/tezaver/wisdom/run_global_wisdom.py")
        ]
        tasks_sync = [
             ("🧠 Brain Sync", "src/tezaver/core/run_brain_sync.py"),
             ("☁️ Bulut Export", "src/tezaver/export/run_bulut_export.py")
        ]
        
        # Group 5: Maintenance & Health (Special commands handled via string for shlex)
        # Group 5: Maintenance
        tasks_maint = [
             ("🛠️ Offline Lab Bakımı", "src/tezaver/offline/run_offline_maintenance.py --mode full --all-symbols"),
             ("🧪 Birim Testleri", "-m pytest tests -q")
        ]
        
        # Group 6: Backup Center
        tasks_backup = [
             ("🧠 Sadece Durum (State)", "src/tezaver/backup/run_backup.py state"),
             ("🗂️ Sadece Profiller", "src/tezaver/backup/run_backup.py profiles"),
             ("📦 Mini Backup (Paket)", "src/tezaver/backup/run_backup.py"),
             ("👨‍💻 Kod Yedekle (src)", "src/tezaver/backup/run_backup.py src"),
             ("📊 Veri Yedekle (data)", "src/tezaver/backup/run_backup.py data"),
             ("📚 Kütüphane Yedekle (lib)", "src/tezaver/backup/run_backup.py library"),
             ("🗄️ Tam Sistem Yedeği (Full)", "src/tezaver/backup/run_backup.py full")
        ]
        
        all_tasks_sequence = tasks_data + tasks_analysis + tasks_wisdom + tasks_sync + tasks_maint + tasks_backup

        TASK_DESCRIPTIONS = {
            "📥 History Update": "**Ne Yapar?**\nBinance API'sine bağlanarak seçili coinlerin en son mum (fiyat) verilerini çeker.\n\n**Nasıl Çalışır?**\n- Son güncelleme tarihini kontrol eder.\n- Eksik olan mumları (1m, 15m, 1h, 4h) parça parça indirir.\n- Veritabanına (Parquet dosyaları) ekler.",
            "🧮 Feature Build": "**Ne Yapar?**\nHam fiyat verilerini işleyerek teknik analiz indikatörlerini hesaplar.\n\n**Neleri Hesaplar?**\n- RSI (Relative Strength Index)\n- MACD (Moving Average Convergence Divergence)\n- ATR (Average True Range)\n- Bollinger Bantları\n- Hacim osilatörleri",
            "📸 Snapshot Build": "**Ne Yapar?**\nVerileri yapay zeka ve analiz motorlarının okuyabileceği 'Snapshot' (Anlık Görüntü) formatına dönüştürür.\n\n**Detay:**\nHer bir zaman dilimi için fiyat, hacim ve indikatör verilerini birleştirip standart bir yapıya sokar.",
            "⏱️ Multi-TF Snap": "**Ne Yapar?**\nFarklı zaman dilimlerini (15dk, 1S, 4S, Günlük) birbiriyle senkronize eder.\n\n**Neden Gerekli?**\nBir coini analiz ederken sadece tek bir grafiğe değil, büyük resme (Multi-Timeframe) bakabilmek için verileri eşleştirir.",
            "🏷️ Rally Labeler": "**Ne Yapar?**\nGeçmişteki fiyat hareketlerini tarar ve hangilerinin 'Ralli' (Büyük Yükseliş) olduğunu tespit eder.\n\n**Kriterler:**\n- Belirli bir süre içinde %X yükseliş.\n- Hacim artışı.\n- Trendin devamlılığı.",
            "🧬 Rally Families": "**Ne Yapar?**\nTespit edilen rallileri karakterlerine göre ailelere ayırır.\n\n**Aile Örnekleri:**\n- 🚀 **Ani Patlama:** Çok kısa sürede sert yükseliş.\n- 🧗 **İstikrarlı Tırmanış:** Yavaş ama kararlı yükseliş.\n- 🎢 **Volatil:** İnişli çıkışlı yükseliş.",
            "🧱 Levels Build": "**Ne Yapar?**\nFiyatın geçmişte tepki verdiği Destek ve Direnç seviyelerini hesaplar.\n\n**Nasıl?**\n- Pivot noktalarını bulur.\n- Hacim yoğunlaşma bölgelerini analiz eder.\n- Trend çizgilerini belirler.",
            "📜 Pattern Wisdom": "**Ne Yapar?**\nGrafik formasyonlarının (Bayrak, Flama, OBO, vb.) başarı oranlarını istatistiksel olarak çıkarır.\n\n**Örnek:**\n'BTC'de Bayrak formasyonu oluştuğunda %70 ihtimalle yukarı kırıyor.' bilgisini üretir.",
            "⚡ Regime Shock": "**Ne Yapar?**\nPiyasanın o anki ruh halini (Rejim) analiz eder.\n\n**Rejimler:**\n- 🐂 **Boğa:** Yükseliş trendi.\n- 🐻 **Ayı:** Düşüş trendi.\n- 🦀 **Yatay:** Kararsız piyasa.\n- ⚡ **Şok:** Ani ve beklenmedik volatilite.",
            "🌍 Global Wisdom": "**Ne Yapar?**\nTekil coinlere değil, tüm piyasaya bakarak genel dersler çıkarır.\n\n**Faydası:**\nBitcoin'in hareketi altcoinleri nasıl etkiliyor? Piyasa genelinde para girişi var mı?",
            "🧠 Brain Sync": "**Ne Yapar?**\nTüm modüllerden (Data, Features, Wisdom, Levels) gelen analizleri tek bir `CoinState` dosyasında birleştirir.\n\n**Önemi:**\nUygulamanın arayüzünde gördüğünüz tüm veriler bu işlem sonucunda bir araya gelir.",
            "☁️ Bulut Export": "**Ne Yapar?**\nAnaliz sonuçlarını web arayüzünde hızlıca gösterilebilecek hafif JSON formatına dönüştürür.",
            "🛠️ Offline Lab Bakımı": "**Ne Yapar?**\nSistemin 'Sağlık Kontrolü'nü yapar.\n\n**İşlemler:**\n- Bozuk veri dosyalarını tespit eder ve siler.\n- Geçici (Temp) dosyaları temizler.\n- Eksik klasörleri oluşturur.",
            "🧪 Birim Testleri": "**Ne Yapar?**\nYazılımın kodlarında hata olup olmadığını kontrol eder.\n\n**Nasıl?**\nÖnceden yazılmış test senaryolarını çalıştırarak 'Beklenen' ve 'Gerçekleşen' sonuçları karşılaştırır.",
            "📦 Mini Backup": "**Ne Yapar?**\nSistemin sadece 'State' (Durum) dosyalarını yedekler. Hızlıdır ve az yer kaplar.",
            "🗄️ Full Backup": "**Ne Yapar?**\nTüm verileri (Fiyatlar, Analizler, Ayarlar) yedekler. Güvenlidir ama uzun sürer ve çok yer kaplar.",
             # Scans
            "Ani Yükseliş (15 Dakika)": "**Ne Yapar?**\nSon 15 dakika içinde anormal hacim ve fiyat artışı gösteren coinleri yakalar.\n\n**Kullanım:**\nGün içi trade (Scalping) fırsatlarını bulmak için kullanılır.",
            "Rally Radar (Isı Haritası)": "**Ne Yapar?**\nTüm piyasadaki ralli sinyallerini tek bir haritada birleştirir.\n\n**Görünüm:**\nSıcak bölgeler (Kırmızı/Turuncu) yükselişin yoğun olduğu zaman dilimlerini gösterir.",
            "Rally Analizi (1 Saat)": "**Ne Yapar?**\n1 Saatlik mum (periyot) verilerini kullanarak analiz yapar.\n\n**Detay:**\nGrafiğe 1 saatlik periyotla bakar ve bu zaman dilimindeki önemli rallileri tespit eder.",
            "Rally Analizi (4 Saat)": "**Ne Yapar?**\n4 Saatlik mum (periyot) verilerini kullanarak analiz yapar.\n\n**Detay:**\nGrafiğe 4 saatlik periyotla bakar ve daha büyük trendleri/rallileri tespit eder.",
            "Sim Affinity (Uyum)": "**Ne Yapar?**\nHangi coinin hangi stratejiye (RSI, MACD, Trend Takibi vb.) daha uygun olduğunu test eder.",
            "Global Wisdom": "**Ne Yapar?**\nTekil coinlere değil, tüm piyasaya bakarak genel dersler çıkarır.\n\n**Faydası:**\nBitcoin'in hareketi altcoinleri nasıl etkiliyor? Piyasa genelinde para girişi var mı?",
            "Pattern İstatistikleri": "**Ne Yapar?**\nGrafik formasyonlarının (Bayrak, Flama, OBO, vb.) başarı oranlarını istatistiksel olarak çıkarır.\n\n**Örnek:**\n'BTC'de Bayrak formasyonu oluştuğunda %70 ihtimalle yukarı kırıyor.' bilgisini üretir.",
            "Bulut Paketle (Json Export)": "**Ne Yapar?**\nAnaliz sonuçlarını web arayüzünde hızlıca gösterilebilecek hafif JSON formatına dönüştürür.",
        }

        # Helper for task row with status
        def _task_row(label, desc, script_path, timestamp_iso=None, help_txt="", cmd_override=None):
            # Prefer granular timestamp if available
            granular_ts = state.task_timestamps.get(label) if state.task_timestamps else None
            # Fallback to provided timestamp (usually pipeline run) if granular not found
            effective_ts = granular_ts if granular_ts else timestamp_iso
            
            date_str, status, dot = _format_relative_time_local(effective_ts)
            c1, c2, c3, c4 = st.columns([3, 5, 2, 2])
            with c1: st.markdown(f"**{label}**")
            with c2:
                info_text = TASK_DESCRIPTIONS.get(label, f"**{label}** hakkında detaylı bilgi bulunamadı.")
                st.caption(desc, help=info_text)
            with c3: st.caption(f"🕒 {date_str}")
            with c4: 
                btn_label = f"{dot} Çalıştır"
                safe_key = label.lower().replace(' ','_').replace('&','').replace('.','').replace('(','').replace(')','').encode('ascii', 'ignore').decode('ascii')
                if st.button(btn_label, key=f"btn_task_{safe_key}", use_container_width=True, help=help_txt):
                     if cmd_override:
                         # For override commands (like tests), we update status manually on success
                         _run_command_with_feedback(label, cmd_override, lambda d,o,e: [system_state.record_task_run(label), st.success("Tamamlandı"), st.rerun()], lambda d,o,e: st.error("Hata"))
                     else:
                         _run_script(script_path, label)
                         # Note: _run_script reloads the page on success, but it doesn't currently cal record_task_run.
                         # We should update _run_script or do it here.
                         # Since _run_script is generic (defined outside tab_status), we can't easily inject the specific label recording unless we modify it.
                         # But wait, _run_script is defined at module level.
                         # Better to wrap it here or modify the global definition.
                         # Let's modify the global definition to accept an optional callback or handle it.
                         # OR, simpler: do the recording here if possible. But st.button callback is tricky.
                         # Actually _run_script does subprocess.run. 
                         # Let's modify _run_script in the next step to support recording state.
                         pass

        # 3. Header & Master Button
        c_head, c_btn = st.columns([2, 1])
        with c_head:
            st.subheader("Süreç Yönetimi")
        with c_btn:
             if st.button("🚀 Hepsini Sırayla Çalıştır", type="primary", use_container_width=True):
                 _run_sequence("Tüm Sistem Pipeline", all_tasks_sequence)
        
        st.divider()

        # Define all tasks for the master runner and groups
        # Format: (Label, Script, Description)
        # Note: We duplicate descriptions here slightly or just use the label lookup. 
        # Ideally we'd use a single source of truth but for now we list scripts here.
        


        # Group 1: Data & Prep
        with st.expander("1. Veri ve Hazırlık", expanded=True):
            ts = state.last_full_pipeline_run_at
            for lbl, script in tasks_data:
                # Retrieve desc from key map to avoid duplication if possible, or pass empty since _task_row looks it up?
                # _task_row looks it up from TASK_DESCRIPTIONS using label.
                # But _task_row signature is (label, desc, script, ...)
                # We need to pass a dummy desc or fix _task_row to default it. 
                # Let's pass a placeholder since _task_row prioritizes the popover lookup but typically displays 'desc' as caption.
                # Actually, the 'desc' argument in _task_row IS the caption.
                # So we should probably define captions here or fetch them.
                # For simplicity/revert, I will hardcode them back as they were or fetch from a dict.
                
                # Fast lookup for captions (reconstituted from previous code)
                captions = {
                    "📥 History Update": "Binance'den son mum verilerini çeker.",
                    "🧮 Feature Build": "Teknik indikatörleri hesaplar.",
                    "📸 Snapshot Build": "Verileri analiz edilebilir parçalara böler.",
                    "⏱️ Multi-TF Snap": "Farklı zaman dilimlerini senkronize eder.",
                    "🏷️ Rally Labeler": "Geçmiş yükselişleri (Rallileri) tespit eder.",
                    "🧬 Rally Families": "Rallileri karakterlerine göre gruplar.",
                    "🧱 Levels Build": "Destek ve direnç seviyelerini hesaplar.",
                    "📜 Pattern Wisdom": "Pattern'lerin başarı oranlarını öğrenir.",
                    "⚡ Regime Shock": "Piyasa rejimini ve şokları analiz eder.",
                    "🌍 Global Wisdom": "Tüm coinlerden ortak dersler çıkarır.",
                    "🧠 Brain Sync": "Tüm analizleri CoinState objesinde birleştirir.",
                    "☁️ Bulut Export": "Web arayüzü için JSON paketleri oluşturur."
                }
                _task_row(lbl, captions.get(lbl, ""), script, ts)

        # Group 2: Analysis
        with st.expander("2. Analiz ve Etiketleme", expanded=True):
            ts = state.last_full_pipeline_run_at
            for lbl, script in tasks_analysis:
                _task_row(lbl, captions.get(lbl, ""), script, ts)

        # Group 3: Wisdom
        with st.expander("3. Bilgelik (Wisdom)", expanded=True):
            ts = state.last_full_pipeline_run_at
            for lbl, script in tasks_wisdom:
                _task_row(lbl, captions.get(lbl, ""), script, ts)

        # Group 4: Sync & Export
        with st.expander("4. Senkronizasyon ve Çıktı", expanded=True):
             last_run = state.last_fast_pipeline_run_at
             for lbl, script in tasks_sync:
                 _task_row(lbl, captions.get(lbl, ""), script, last_run)

        # Group 5: Maintenance & Health
        # Group 5: Maintenance & Health
        with st.expander("5. Sistem Sağlığı & Bakım", expanded=True):
             # Try to get maintenance status - assuming it exists or None
             maint_ts = getattr(state, "last_offline_maintenance_run_at", None)
             _task_row("🛠️ Offline Lab Bakımı", "Veritabanı temizliği ve onarımı yapar.", "src/tezaver/offline/run_offline_maintenance.py", maint_ts, cmd_override=[sys.executable, "src/tezaver/offline/run_offline_maintenance.py", "--mode", "full", "--all-symbols"])
             
             _task_row("🧪 Birim Testleri", "Sistemin doğruluğunu test eder (Pytest).", "", state.last_tests_run_at, cmd_override=[sys.executable, "-m", "pytest", "tests", "-q"])

        # Group 6: Backup Center
        with st.expander("6. Yedekleme Merkezi", expanded=True):
             st.caption("🧩 Mini Yedekleme (Hızlı)")
             _task_row("🧠 Sadece Durum (State)", "Sadece 'coin_state.json' dosyasını yedekler. Sistemin hafızasıdır.", "src/tezaver/backup/run_backup.py", None, cmd_override=[sys.executable, "src/tezaver/backup/run_backup.py", "state"])
             _task_row("🗂️ Sadece Profiller", "Tüm coinlerin analiz klasörlerini (coin_profiles) yedekler.", "src/tezaver/backup/run_backup.py", None, cmd_override=[sys.executable, "src/tezaver/backup/run_backup.py", "profiles"])
             _task_row("📦 Mini Backup (Paket)", "State + Profiller + Global Wisdom hepsini içerir.", "src/tezaver/backup/run_backup.py", state.last_mini_backup_at)
             
             st.markdown("---")
             st.caption("📂 Ana Klasör Yedekleme")
             _task_row("👨‍💻 Kod Yedekle (src)", "Sadece kaynak kodları (src klasörü) zipler.", "src/tezaver/backup/run_backup.py", None, cmd_override=[sys.executable, "src/tezaver/backup/run_backup.py", "src"])
             _task_row("📊 Veri Yedekle (data)", "Sadece veri klasörünü (data) zipler. Analizler buradadır.", "src/tezaver/backup/run_backup.py", None, cmd_override=[sys.executable, "src/tezaver/backup/run_backup.py", "data"])
             _task_row("📚 Kütüphane Yedekle (lib)", "Sadece kütüphane klasörünü (library) zipler. Snapshotlar buradadır.", "src/tezaver/backup/run_backup.py", None, cmd_override=[sys.executable, "src/tezaver/backup/run_backup.py", "library"])
             
             st.markdown("---")
             st.caption("🗄️ Tam Yedekleme")
             _task_row("🗄️ Tam Sistem Yedeği (Full)", "Tüm sistemin (Kod + Veri + Lib) snapshot'ını alır.", "src/tezaver/backup/run_backup.py", state.last_full_backup_at, cmd_override=[sys.executable, "src/tezaver/backup/run_backup.py", "full"])

        st.divider()
        if st.button("Logları İncele", key="goto_logs"):
             st.session_state['show_logs'] = True
             st.rerun()

    # ================= TAB 2: TARAMALAR =================
    with tab_scans:
        st.subheader("Piyasa Taramaları")

        st.divider()
        
        # Last run times are file-based, so we read them here or inside _task_row (but _task_row takes ISO string)
        # We need to bridge file mtime to ISO string for _task_row compatibility
        def _get_file_ts(path: Path):
            if path and path.exists():
                return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
            return None

        # Group 1: Instant & Short Term
        with st.expander("🚨 Anlık & Kısa Vade", expanded=True):
            _task_row(
                "Ani Yükseliş (15 Dakika)",
                "15 dakikalık sert yükselişleri yakalar.",
                "src/tezaver/rally/run_fast15_rally_scan.py --all-symbols",
                _get_file_ts(coin_cell_paths.get_fast15_rallies_summary_path("BTCUSDT")),
                "15 Dakika Scan"
            )
            _task_row(
                "Rally Radar (Isı Haritası)",
                "Tüm piyasanın yükseliş haritasını çıkarır.",
                "src/tezaver/rally/run_rally_radar_export.py",
                _get_file_ts(coin_cell_paths.get_coin_profile_dir("BTCUSDT") / "rally_radar.json"),
                "Radar Export"
            )

        # Group 2: Time-Labs (Deep Analysis)
        with st.expander("⏳ Zaman Analizleri (Time-Labs)", expanded=True):
            _task_row(
                "Rally Analizi (1 Saat)",
                "Son 1 saatlik ralli performanslarını inceler.",
                "src/tezaver/rally/run_time_labs_scan.py --tf 1h --all-symbols",
                 _get_file_ts(coin_cell_paths.get_time_labs_rallies_summary_path("BTCUSDT", "1h")),
                "1H Analysis"
            )
            _task_row(
                "Rally Analizi (4 Saat)",
                "Son 4 saatlik ralli performanslarını inceler.",
                "src/tezaver/rally/run_time_labs_scan.py --tf 4h --all-symbols",
                 _get_file_ts(coin_cell_paths.get_time_labs_rallies_summary_path("BTCUSDT", "4h")),
                "4H Analysis"
            )

        # Group 3: Wisdom & Simulation
        with st.expander("🧠 Bilgelik & Simülasyon", expanded=True):
             # These are duplicates of Tab 1, but user asked for cleanup.
             # Only keeping unique scans if any.
             # Actually, Sim Affinity is unique to Scans tab in previous context? No, it was in Tab 1 too.
             # Let's check what is NOT in Tab 1.
             # Tab 1 had: Global Wisdom, Pattern Stats, Sim Affinity(NO), Export(YES).
             # Wait, Sim Affinity was NOT in Tab 1. I should check Tab 1 content again.
             
             # Tab 1 Group 3: Patter Wisdom, Regime Shock, Global Wisdom.
             # Tab 1 Group 4: Brain Sync, Bulut Export.
             
             # So Sim Affinity IS unique to Tab 2.
             _task_row(
                "Sim Affinity (Uyum)",
                "Hangi coine hangi stratejinin uyduğunu test eder.",
                "src/tezaver/sim/run_sim_affinity_export.py",
                 _get_file_ts(coin_cell_paths.get_coin_profile_dir("BTCUSDT") / "sim_affinity.json"),
                "Sim Affinity"
             )




    # ================= TAB 3: AYARLAR (SETTINGS) =================
    with tab_settings:
        # Load current settings from session state or file
        if 'user_settings' not in st.session_state:
            st.session_state.user_settings = settings_manager.load_settings()
        
        settings = st.session_state.user_settings
        indicators = settings.get('indicators', {})
        
        col_save, _ = st.columns([1, 4])
        with col_save:
             if st.button("💾 Ayarları Kaydet", type="primary", use_container_width=True, key="sys_settings_save"):
                settings_manager.save_settings(settings)
                st.success("Ayarlar kaydedildi!")
        
        st.markdown("")
        
        sub_tab_graph, sub_tab_ma, sub_tab_mom, sub_tab_vol = st.tabs([
            "📊 Grafik & Görünüm", 
            "📈 Hareketli Ortalamalar", 
            "🌊 Momentum (MACD/RSI)", 
            "⚡ Volatilite (ATR)"
        ])
        
        # 1. GRAFİK
        with sub_tab_graph:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**🕯️ Mum Renkleri**")
                candles = indicators.get('candles', {})
                candles['up_color'] = st.color_picker("Yükseliş (Yeşil)", value=candles.get('up_color', '#089981'), key="s_candles_up")
                candles['down_color'] = st.color_picker("Düşüş (Kırmızı)", value=candles.get('down_color', '#F23645'), key="s_candles_down")
                indicators['candles'] = candles
            with c2:
                st.markdown("**📊 Hacim**")
                vol = indicators.get('volume', {})
                vol['enabled'] = st.toggle("Hacim Göster", value=vol.get('enabled', True), key="s_vol_en")
                vol['up_color'] = st.color_picker("Yükseliş Hacmi", value=vol.get('up_color', '#089981'), key="s_vol_up")
                vol['down_color'] = st.color_picker("Düşüş Hacmi", value=vol.get('down_color', '#F23645'), key="s_vol_down")
                indicators['volume'] = vol

        # 2. MA
        with sub_tab_ma:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**EMA Hızlı (Fast)**")
                ef = indicators.get('ema_fast', {})
                ef['enabled'] = st.toggle("Aktif", value=ef.get('enabled', True), key="s_ef_en")
                ef['period'] = st.number_input("Periyot", 1, value=ef.get('period', 20), key="s_ef_per")
                ef['color'] = st.color_picker("Renk", value=ef.get('color', '#2962FF'), key="s_ef_col")
                indicators['ema_fast'] = ef
            with c2:
                st.markdown("**EMA Yavaş (Slow)**")
                es = indicators.get('ema_slow', {})
                es['enabled'] = st.toggle("Aktif", value=es.get('enabled', True), key="s_es_en")
                es['period'] = st.number_input("Periyot", 1, value=es.get('period', 50), key="s_es_per")
                es['color'] = st.color_picker("Renk", value=es.get('color', '#FF9800'), key="s_es_col")
                indicators['ema_slow'] = es

        # 3. MOMENTUM
        with sub_tab_mom:
            # RSI
            st.markdown("#### RSI")
            rsi = indicators.get('rsi', {})
            rc1, rc2 = st.columns(2)
            with rc1:
                rsi['enabled'] = st.toggle("RSI Aktif", value=rsi.get('enabled', True), key="s_rsi_en")
                rsi['period'] = st.number_input("RSI Periyot", 1, value=rsi.get('period', 11), key="s_rsi_per")
                rsi['color'] = st.color_picker("RSI Renk", value=rsi.get('color', '#7E57C2'), key="s_rsi_col")
            with rc2:
                rsi['ema_period'] = st.number_input("RSI Sinyal (EMA)", 1, value=rsi.get('ema_period', 11), key="s_rsi_sper")
                rsi['ema_color'] = st.color_picker("Sinyal Renk", value=rsi.get('ema_color', '#FFC107'), key="s_rsi_scol")
            indicators['rsi'] = rsi
            
            st.divider()
            
            # MACD
            st.markdown("#### MACD")
            macd = indicators.get('macd', {})
            mc1, mc2 = st.columns(2)
            with mc1:
                macd['enabled'] = st.toggle("MACD Aktif", value=macd.get('enabled', True), key="s_macd_en")
                macd['fast'] = st.number_input("Hızlı (12)", 1, value=macd.get('fast', 12), key="s_m_fast")
                macd['slow'] = st.number_input("Yavaş (26)", 1, value=macd.get('slow', 26), key="s_m_slow")
                macd['signal'] = st.number_input("Sinyal (9)", 1, value=macd.get('signal', 9), key="s_m_sig")
                macd['color_tolerance'] = st.slider("Tolerans (%)", 0.0, 100.0, value=float(macd.get('color_tolerance', 0.0)), key="s_m_tol")
            with mc2:
                st.markdown("**Renkler (Histogram)**")
                macd['hist_pos_inc_color'] = st.color_picker("Yeşil (Güçlü Al)", value=macd.get('hist_pos_inc_color', '#00E676'), key="s_m_pi")
                macd['hist_pos_dec_color'] = st.color_picker("Mor (Zayıf Al)", value=macd.get('hist_pos_dec_color', '#D500F9'), key="s_m_pd")
                macd['hist_neg_inc_color'] = st.color_picker("Kırmızı (Güçlü Sat)", value=macd.get('hist_neg_inc_color', '#FF1744'), key="s_m_ni")
                macd['hist_neg_dec_color'] = st.color_picker("Sarı (Zayıf Sat)", value=macd.get('hist_neg_dec_color', '#FFEA00'), key="s_m_nd")
            indicators['macd'] = macd

        # 4. VOLATILITE
        with sub_tab_vol:
            st.markdown("**ATR Bantları**")
            atr = indicators.get('atr', {})
            ac1, ac2 = st.columns(2)
            with ac1:
                atr['enabled'] = st.toggle("ATR Aktif", value=atr.get('enabled', False), key="s_atr_en")
                atr['period'] = st.number_input("Periyot", 1, value=atr.get('period', 14), key="s_atr_per")
            with ac2:
                atr['multiplier'] = st.number_input("Çarpan (Bant)", 0.1, value=atr.get('multiplier', 2.0), key="s_atr_mul")
                atr['color'] = st.color_picker("Renk", value=atr.get('color', '#00BCD4'), key="s_atr_col")
            indicators['atr'] = atr
            
        # Update session
        settings['indicators'] = indicators
        st.session_state.user_settings = settings

    # ================= TAB 4: DEVELOPER =================
    with tab_dev:
        st.subheader("Sistem Logları & JSON")
        
        ld_cnt = st.selectbox("Log Satır Sayısı", [100, 500, 1000], index=0, key="sys_log_cnt")
        if st.button("Logları Yenile", key="sys_log_refresh"):
            st.rerun()
            
        lines = system_state.get_log_tail(ld_cnt)
        st.code("".join(lines), language="text")
        
        st.markdown("---")
        with st.expander("JSON State Dump"):
            st.json(system_state.load_state().__dict__)
