from dataclasses import dataclass, field
from typing import List, Dict
from tezaver.matrix.core.bars import Bar

@dataclass
class QualityReport:
    ok: bool
    issues: List[str] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

def validate_bars(bars: List[Bar], tf_seconds: int) -> QualityReport:
    if not bars:
        return QualityReport(ok=False, issues=["Sequence is empty"])
        
    issues = []
    stats = {
        "count": len(bars),
        "duplicates": 0,
        "out_of_order": 0,
        "misaligned": 0, 
        "missing": 0,
        "irregular": 0
    }
    
    tf_ms = tf_seconds * 1000
    
    for i in range(len(bars)):
        curr = bars[i]
        
        # Misalignment check
        if curr.ts % tf_ms != 0:
            stats["misaligned"] += 1
            if stats["misaligned"] <= 5: # limit noise
                issues.append(f"Misaligned timestamp: {curr.ts}")

        if i > 0:
            prev = bars[i-1]
            diff = curr.ts - prev.ts
            
            if curr.ts == prev.ts:
                stats["duplicates"] += 1
                issues.append(f"Duplicate timestamp: {curr.ts}")
                
            elif curr.ts < prev.ts:
                stats["out_of_order"] += 1
                issues.append(f"Out-of-order: {curr.ts} after {prev.ts}")
                
            else:
                # Gap analysis
                if diff > tf_ms:
                    if diff % tf_ms == 0:
                        missing_count = (diff // tf_ms) - 1
                        stats["missing"] += missing_count
                        if stats["missing"] < 100: # only log first few gaps explicitly? or generic message
                             pass 
                    else:
                        stats["irregular"] += 1
                        issues.append(f"Irregular gap: {diff}ms at {curr.ts}")
                elif diff < tf_ms:
                     stats["irregular"] += 1
                     issues.append(f"Irregular step < timeframe: {diff}ms at {curr.ts}")

    # Summary logic
    ok = (
        stats["duplicates"] == 0 and 
        stats["out_of_order"] == 0 and 
        stats["misaligned"] == 0 and
        stats["irregular"] == 0
        # missing bars might be 'ok' depending on strictness, but let's assume ok=True if structure is sound
    )
    
    if not ok:
        issues.insert(0, f"Quality check failed. Stats: {stats}")
        
    return QualityReport(ok=ok, issues=issues, stats=stats)
