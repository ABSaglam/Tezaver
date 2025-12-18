#!/usr/bin/env python3
"""
Add category check before each expander (safest approach).
"""

from pathlib import Path

TARGET = Path("src/tezaver/ui/matrix_operator_tab.py")

# Mapping: expander title -> category
CATEGORY_MAP = {
    "🔁 Live Loop Control | Canlı Döngü Kontrolü": "🎯 Kokpit",
    "🩺 System Health Summary | Sistem Sağlık Özeti": "🎯 Kokpit",
    "🎮 Live Gate Status | Canlı Kapı Durumu": "🎯 Kokpit",
    "🟢 Live Freshness / Lag | Canlı Veri Tazeliği": "🎯 Kokpit",
    "🎬 Trade Replay | İşlem Tekrarı": "🎯 Kokpit",
    
    "📊 Cycles Report | Döngü Raporu": "⚙️ Operasyon",
    "🧭 Live Ops Console | Canlı Operasyon Konsolu": "⚙️ Operasyon",
    "🧾 Last Orders (per cell) | Son Emirler (hücre bazında)": "⚙️ Operasyon",
    
    "⚙️ Exchange & Arm Controls | Borsa & Yetkilendirme Kontrolleri": "🔐 Güvenlik",
    "🔐 Secrets Vault | Gizli Anahtar Kasası": "🔐 Güvenlik",
    "🧹 Dust & Position Hygiene | Bakiye & Pozisyon Temizliği": "🔐 Güvenlik",
    
    "📋 Strategy Board | Strateji Panosu": "📋 Strateji",
    
    "📦 Incident Bundles | Olay Paketi Arşivi": "🔍 Forensics",
    "📊 Events Explorer | Olay Gezgini": "🔍 Forensics",
    "📜 NDJSON Tail Viewer | NDJSON Log Görüntüleyici": "🔍 Forensics",
    
    "✅ Closed Bar Proof | Kapalı Bar Kanıtı": "✅ Test/Kanıt",
    "🔀 Closed-bar Router | Kapalı Bar Yönlendiricisi": "✅ Test/Kanıt",
    "🧾 Proof+Router (E2E) | Kanıt+Yönlendirici (Uçtan Uca)": "✅ Test/Kanıt",
    "🧾 Proof+Router+Cluster (E2E) | Kanıt+Yönlendirici+Küme (Uçtan Uca)": "✅ Test/Kanıt",
}

lines = TARGET.read_text().splitlines(keepends=True)
output = []

i = 0
added_count = 0

while i < len(lines):
    line = lines[i]
    
    # Check if this line is an expander we want to gate
    matched_title = None
    for title in CATEGORY_MAP.keys():
        if f'with st.expander("{title}"' in line:
            matched_title = title
            break
    
    if matched_title:
        # Check if already gated (skip blank lines before)
        prev_idx = i - 1
        while prev_idx >= 0 and not lines[prev_idx].strip():
            prev_idx -= 1
        
        if prev_idx >= 0 and 'if category ==' in lines[prev_idx]:
            # Already gated
            output.append(line)
            i += 1
            continue
        
        # Get indent of with statement
        indent_level = len(line) - len(line.lstrip())
        indent_str = ' ' * indent_level
        
        # Add category check
        cat = CATEGORY_MAP[matched_title]
        output.append(f'{indent_str}if category == "{cat}":\n')
        
        # Add with line with +4 indent
        output.append('    ' + line)
        i += 1
        
        # Indent block content until we hit same or less indent
        while i < len(lines):
            next_line = lines[i]
            
            if not next_line.strip():
                output.append(next_line)
                i += 1
                continue
            
            next_indent = len(next_line) - len(next_line.lstrip())
            
            if next_indent <= indent_level:
                break
            
            output.append('    ' + next_line)
            i += 1
        
        added_count += 1
        print(f"✅ {added_count}: {matched_title[:50]}...")
    else:
        output.append(line)
        i += 1

TARGET.write_text(''.join(output))
print(f"\n🎯 Added category checks to {added_count} expanders")
