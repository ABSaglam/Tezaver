from dataclasses import dataclass, field
from typing import List

@dataclass
class QualityReport:
    ok: bool
    issues: List[str] = field(default_factory=list)

def validate_bar_sequence(timestamps: List[int]) -> QualityReport:
    """Checks for empty sequence, duplicates, and out-of-order timestamps."""
    if not timestamps:
        return QualityReport(ok=False, issues=["Sequence is empty"])
    
    issues = []
    
    # check order & duplicates
    for i in range(1, len(timestamps)):
        prev = timestamps[i-1]
        curr = timestamps[i]
        
        if curr == prev:
            issues.append(f"Duplicate timestamp found: {curr}")
        if curr < prev:
            issues.append(f"Out-of-order timestamp: {curr} after {prev}")
            
    if issues:
        return QualityReport(ok=False, issues=issues)
        
    return QualityReport(ok=True)
