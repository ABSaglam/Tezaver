
import os

MAIN_REPORT = "refined_global_report_v16.md"
AYAS_REPORT = "jan28_ayas_report.md"
AYSENTI_REPORT = "jan28_aysenti_report.md"

def finalize_report():
    with open(MAIN_REPORT, "r") as f:
        content = f.read()

    # Read new sections
    with open(AYAS_REPORT, "r") as f:
        ayas_content = f.read()
    
    with open(AYSENTI_REPORT, "r") as f:
        aysenti_content = f.read()
    
    # Prepare the replacement block
    # We want to replace everything for Jan 28
    
    # Clean up headers from sub-reports if needed (they have ## Date header)
    # We want a main header for Jan 28, then two sub-sections
    
    # Parse date from ayas report header
    date_line = ayas_content.split('\n')[0] # e.g. ## 📅 28 Ocak 2026...
    
    # Modify headers to distinguish sections
    # Ayaş table
    ayas_lines = ayas_content.split('\n')
    ayas_table = "\n".join(ayas_lines[1:]) # Skip date header
    
    # Aysenti table
    aysenti_lines = aysenti_content.split('\n')
    aysenti_table = "\n".join(aysenti_lines[1:]) # Skip date header
    
    new_section = f"""
{date_line}

### 🚇 AYAŞ TÜNELİ (00:00 Gatekeeper)
> **Kural:** Sadece gece 00:00 itibarıyla "Golden" olan coinler.

{ayas_table}

### 🌉 AYSENTİ GEÇİDİ (Gün İçi Katılanlar)
> **Kural:** Gün içinde "Golden" formuna kavuşanlar.

{aysenti_table}
"""

    # Find where to insert/replace
    # Look for existing Jan 28 header or insert at end if finding logic fails
    start_marker = "## 📅 28 Ocak 2026"
    
    if start_marker in content:
        # Replace existing section
        pre = content.split(start_marker)[0]
        # Find next section or end
        post_parts = content.split(start_marker)[1]
        
        # Check if there is another date after
        pattern = "\n## 📅"
        if pattern in post_parts:
             # Split at next date
             next_date_idx = post_parts.find("\n## 📅")
             post = post_parts[next_date_idx:]
        else:
             post = "" # End of file
        
        final_content = pre + new_section.strip() + "\n" + post
    else:
        # Append
        final_content = content + "\n" + new_section

    with open(MAIN_REPORT, "w") as f:
        f.write(final_content)
    
    print("✅ Rapor Güncellendi: refined_global_report_v16.md")

if __name__ == "__main__":
    finalize_report()
