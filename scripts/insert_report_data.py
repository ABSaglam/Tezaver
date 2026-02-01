
import os

def insert_data():
    report_path = '/Users/alisaglam/TezaverMac/refined_global_report_v16.md'
    new_data_path = '/Users/alisaglam/TezaverMac/formatted_audit_results.md'
    
    with open(report_path, 'r') as f:
        report_lines = f.readlines()
        
    with open(new_data_path, 'r') as f:
        new_lines = f.readlines()
        
    # Find start index
    start_idx = -1
    for i, line in enumerate(report_lines):
        if "## 📅 21 Ocak 2026" in line:
            start_idx = i
            break
            
    if start_idx == -1:
        print("Could not find start marker '## 📅 21 Ocak 2026'")
        return

    # Find end index
    end_idx = -1
    for i in range(start_idx, len(report_lines)):
        # Correctly check the line at index i
        if "## 📅 28 Ocak 2026" in report_lines[i]:
            end_idx = i
            break
                
    if end_idx == -1:
        print("Could not find end marker '## 📅 28 Ocak 2026'")
        # Fallback: if end descriptor not found, maybe just print the last few lines to debug
        # But we know it exists from view_file.
        return
        
    print(f"Replacing lines {start_idx} to {end_idx} (non-inclusive of end)")
    
    # Ensure new_lines ends with a blank line if needed
    if new_lines and not new_lines[-1].strip() == "":
        new_lines.append("\n")
        
    final_lines = report_lines[:start_idx] + new_lines + report_lines[end_idx:]
    
    with open(report_path, 'w') as f:
        f.writelines(final_lines)
        
    print("Successfully updated report.")

if __name__ == '__main__':
    insert_data()
