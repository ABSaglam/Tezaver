import streamlit as st
import time
import os
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from tezaver.core.config import DEFAULT_COINS, DEFAULT_HISTORY_TIMEFRAMES
from tezaver.core import coin_cell_paths

def get_file_last_modified(path: Path):
    """Returns the last modification time of a file as a datetime object, or None."""
    if path.exists():
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime)
    return None

def format_age(diff_seconds):
    if diff_seconds < 60:
        return "Şimdi"
    elif diff_seconds < 3600:
        return f"{int(diff_seconds // 60)}dk"
    elif diff_seconds < 86400:
        return f"{int(diff_seconds // 3600)}sa"
    else:
        return f"{int(diff_seconds // 86400)}gn"

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def get_coin_history_days(symbol: str) -> str:
    """Calculates how many days of data we have for a coin (using 1d or 4h)."""
    # Preferred timeframes to check for duration
    for tf in ["1d", "4h", "1h"]:
        file_path = coin_cell_paths.get_history_file(symbol, tf)
        if file_path.exists():
            try:
                # Read only timestamp column to be faster
                df = pd.read_parquet(file_path, columns=["timestamp"])
                if not df.empty:
                    min_ts = df["timestamp"].min()
                    max_ts = df["timestamp"].max()
                    if min_ts and max_ts:
                        days = (max_ts - min_ts) / (1000 * 60 * 60 * 24)
                        return f"{int(days)} gün"
            except:
                continue
    return "-"

def get_data_health_matrix():
    """Scans all history files and returns a pivoted DataFrame."""
    now = datetime.now()
    rows = []
    
    # Define timeframes to show in columns
    target_timeframes = ["15m", "1h", "4h", "1d", "1w"]
    
    for symbol in DEFAULT_COINS:
        row = {"Sembol": symbol}
        total_size = 0
        
        for tf in target_timeframes:
            # Skip if timeframe is not in our default tracked list just in case
            if tf not in DEFAULT_HISTORY_TIMEFRAMES:
                row[tf] = "⚪ N/A"
                continue
                
            file_path = coin_cell_paths.get_history_file(symbol, tf)
            last_mod = get_file_last_modified(file_path)
            
            if not last_mod:
                row[tf] = "⚫ Yok"
            else:
                # Get Size
                try:
                    size = file_path.stat().st_size
                    total_size += size
                except:
                    pass

                diff = now - last_mod
                sec = diff.total_seconds()
                age_str = format_age(sec)
                
                # Status Logic
                is_fresh = False
                if tf == "15m" and sec < 1800: is_fresh = True
                elif tf == "1h" and sec < 7200: is_fresh = True
                elif tf == "4h" and sec < 28800: is_fresh = True
                elif tf == "1d" and sec < 100000: is_fresh = True
                elif tf == "1w" and sec < 700000: is_fresh = True
                
                if is_fresh:
                    emoji = "🟢"
                elif sec < 86400: # Less than a day old data
                    emoji = "🟡"
                else:
                    emoji = "🔴"
                
                # Format: "🟢 5dk"
                row[tf] = f"{emoji} {age_str}"
        
        row["Boyut"] = format_size(total_size)
        
        # Calculate Duration
        row["Veri Süresi"] = get_coin_history_days(symbol)
        
        rows.append(row)
            
    return pd.DataFrame(rows)

import json
import signal
import os

LOG_DIR = Path("logs")
UPDATE_LOG_PATH = LOG_DIR / "data_update.log"
PID_FILE = LOG_DIR / "update_process.pid"

def is_process_running(pid):
    """Check if a process with the given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def get_update_progress():
    """Parses the log file to estimate progress."""
    if not UPDATE_LOG_PATH.exists():
        return 0, "Henüz başlamadı..."
    
    try:
        with open(UPDATE_LOG_PATH, "r") as f:
            lines = f.readlines()
            
        total_coins = len(DEFAULT_COINS)
        processed_count = 0
        last_line = ""
        
        for line in lines:
            if "Updating history for" in line or "Fetching fresh history" in line:
                processed_count += 1
            if line.strip():
                last_line = line.strip()
                
        # Each coin has X timeframes, so exact progress is hard, but we can count lines
        # Let's just return the line count or last action
        return len(lines), last_line
    except:
        return 0, "Log okunamadı."



def render_data_health_page():
    st.header("💾 Veri Merkezi")
    st.caption("Veri güncelliği, boyutu ve geçmişi. Hedef: **Son 2 Yıl** (veya coin'in yaşı kadar).")
    
    # Check running state first to determine expander state
    is_running = False
    pid_data = None
    if PID_FILE.exists():
        try:
            with open(PID_FILE, "r") as f:
                pid_data = json.load(f)
            if is_process_running(pid_data["pid"]):
                is_running = True
        except: 
            pass

    # Update Controls
    # Keeping it expanded by default for better visibility
    with st.expander("🛠️ Veri Güncelleme", expanded=True):
        
        # If running, show monitor HERE
        if PID_FILE.exists(): 
            # Inline Monitor Logic
            try:
                if not pid_data: # Reload if needed
                    with open(PID_FILE, "r") as f:
                        pid_data = json.load(f)
                
                start_str = pid_data.get("start_time")
                pid = pid_data.get("pid")
                
                # Calculate Elapsed
                try:
                    now = datetime.now()
                    start_dt = datetime.combine(now.date(), datetime.strptime(start_str, "%H:%M:%S").time())
                    if start_dt > now: start_dt = start_dt - timedelta(days=1)
                    diff = now - start_dt
                    elapsed_str = str(diff).split('.')[0]
                except:
                    elapsed_str = "..."

                # Fetch progress FIRST to use in condition
                line_count, last_msg = get_update_progress()

                if is_process_running(pid) and "Update completed" not in last_msg:
                    
                    st.info(f"""
                    **🔄 Güncelleme Sürüyor...**
                    *   **⏱️ Süre:** {elapsed_str} | **🔢 Adım:** {line_count}
                    *   **📜 Durum:** `{last_msg[-60:] if last_msg else "..."}`
                    """)
                    
                    
                    # Manual Refresh Button
                    if st.button("🔄 Yenile (Durumu Kontrol Et)"):
                        st.rerun()
                    
                else:
                    st.success("✅ Tamamlandı!")
                    if st.button("Kapat"):
                        PID_FILE.unlink()
                        st.rerun()
            except Exception as e:
                st.error(f"Monitör Hatası: {e}")
                if st.button("Sıfırla"):
                    if PID_FILE.exists(): PID_FILE.unlink()
                    st.rerun()
        
        else:
            # Not running, show start controls
            st.info("Bu işlem, mevcut verilerin üzerine sadece **yeni eklenen** mumları (eksik verileri) indirir.")
            
            if st.button("🚀 Verileri Güncelle (Hızlı)", use_container_width=True):
                import subprocess
                import sys
                import os
                
                cmd = [sys.executable, "src/tezaver/data/run_history_update.py"]
                env = os.environ.copy()
                env["PYTHONPATH"] = "src"
                
                if not LOG_DIR.exists(): LOG_DIR.mkdir()
                log_file = open(UPDATE_LOG_PATH, "w")
                
                try:
                    proc = subprocess.Popen(cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT)
                    with open(PID_FILE, "w") as f:
                        json.dump({
                            "pid": proc.pid,
                            "start_time": datetime.now().strftime("%H:%M:%S")
                        }, f)
                    st.toast("Başlatıldı!", icon="🚀")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Hata: {e}")

    st.markdown("---")
    
    tab_status, tab_docs = st.tabs(["📊 Veri Matrisi", "📚 Veri Sözlüğü"])
    
    with tab_status:
        st.info("Hücreler güncelliği (🟢/🟡/🔴) gösterir. 'Boyut' sütunu, o coine ait tüm verilerin (15m-1w) toplam disk alanıdır.")
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🔄 Durumu Yenile"):
                st.rerun()
            
        df = get_data_health_matrix()
        
        # Display Pivot Table
        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "Sembol": st.column_config.TextColumn("Coin"),
                "15m": st.column_config.TextColumn("15 dk"),
                "1h": st.column_config.TextColumn("1 Saat"),
                "4h": st.column_config.TextColumn("4 Saat"),
                "1d": st.column_config.TextColumn("1 Gün"),
                "1w": st.column_config.TextColumn("1 Hafta"),
                "Boyut": st.column_config.TextColumn("Top. Boyut"),
                "Veri Süresi": st.column_config.TextColumn("Geçmiş", help="Bu coin için elimizde kaç günlük veri var?"),
            },
            hide_index=True
        )
        
    with tab_docs:
        st.markdown("""
        ### Veri Kaynağı ve Yapısı
        
        **Kaynak:** Binance Spot Piyasası (USDT Pariteleri)
        **Format:** OHLCV (Open, High, Low, Close, Volume)
        **Depolama:** Apache Parquet formatında sıkıştırılmış dosyalar.
        
        ### İşaretler
        
        *   🟢 **Yeşil:** Veri taze ve güncel.
        *   🟡 **Sarı:** Veri var ama son 24 saat içinde güncellenmemiş (veya periyoda göre gecikmiş).
        *   🔴 **Kırmızı:** Veri çok eski (>1 gün) veya eksik.
        *   ⚫ **Siyah:** Dosya bulunamadı.
        *   **Süre:** (Örn: 5dk, 2sa) Dosyanın en son ne zaman değiştirildiğini gösterir.
        """)


