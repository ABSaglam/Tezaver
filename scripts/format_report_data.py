import re

def format_value(val, type_):
    if not val: return val
    val_str = str(val).strip()
    
    if type_ == 'MAX':
        if '+' in val_str: return f"<font color='green'>{val_str}</font>"
        return val_str
    
    if type_ == 'CLOSE' or type_ == 'P' or type_ == 'P-21' or type_ == 'V-Ch':
        if '+' in val_str: 
            # Check for high values to bold/orange? Report has +83.8% green.
            # Some refer to orange for very high.
            # Simple logic: Green for positive, Red for negative.
            return f"<font color='green'>{val_str}</font>"
        if '-' in val_str: 
            return f"<font color='red'>{val_str}</font>"
        return val_str

    if type_ == 'ANG':
        try:
            v = float(val_str)
            if v > 0: return f"<font color='green'>**+{val_str}**</font>" # Report uses bold + val
            return f"<font color='red'>{val_str}</font>"
        except: return val_str

    if type_ == 'Vrsi':
        # Report: <font color='#00FF00'>**11.1**</font>
        return f"<font color='#00FF00'>**{val_str}**</font>"

    if type_ == 'V100' or type_ == 'V21' or type_ == 'V-Mom':
        # Report: <font color='green'>**8.3**</font> or bold
        return f"<font color='green'>**{val_str}**</font>"
    
    return val_str

def process_file():
    with open('temp_audit_results.md', 'r') as f:
        lines = f.readlines()
        
    formatted_lines = []
    headers = []
    
    for line in lines:
        if line.startswith('| NO'):
            headers = [h.strip() for h in line.split('|')[1:-1]]
            formatted_lines.append(line)
            continue
        if line.startswith('|---'):
            formatted_lines.append(line)
            continue
        if not line.startswith('|'):
            formatted_lines.append(line)
            continue
            
        parts = [p.strip() for p in line.split('|')[1:-1]]
        if len(parts) < len(headers):
            formatted_lines.append(line)
            continue
            
        new_parts = []
        for i, part in enumerate(parts):
            header = headers[i]
            # Apply basic formatting logic
            if header in ['MAX', 'CLOSE', 'P', 'P-21', 'V-Ch']:
                new_parts.append(format_value(part, 'CLOSE')) # Reuse CLOSE logic
            elif header == 'ANG':
                new_parts.append(format_value(part, 'ANG'))
            elif header == 'Vrsi':
                new_parts.append(format_value(part, 'Vrsi'))
            elif header in ['V100', 'V21', 'V-Mom']:
                new_parts.append(format_value(part, 'V100'))
            else:
                new_parts.append(part)
                
        formatted_lines.append('| ' + ' | '.join(new_parts) + ' |\n')
        
    with open('formatted_audit_results.md', 'w') as f:
        f.writelines(formatted_lines)

if __name__ == '__main__':
    process_file()
