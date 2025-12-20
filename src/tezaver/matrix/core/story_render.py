from typing import Dict, List

def render_timeline(phases: List[Dict], entry: int, invalidation: int, width: int = 60) -> str:
    """Generates an ASCII timeline."""
    if not phases:
        return "[Empty Timeline]"
    
    # Calculate bounds
    min_bar = min(p['start_bar'] for p in phases)
    max_bar = max(max(p['end_bar'] for p in phases), entry, invalidation)
    span = max_bar - min_bar + 1
    if span <= 0: span = 1
    
    # Normalize to width
    ratio = width / span
    
    lines = []
    
    # Header scale
    lines.append(f"Range: {min_bar} -> {max_bar} (Span: {span} bars)")
    
    # Phases
    for p in phases:
        start = p['start_bar']
        end = p['end_bar']
        
        col_start = int((start - min_bar) * ratio)
        col_end = int((end - min_bar) * ratio)
        length = max(1, col_end - col_start)
        
        bar_char = "#"
        if "impulse" in p['name'].lower():
            bar_char = "="
        elif "correction" in p['name'].lower():
            bar_char = "-"
            
        graphic = bar_char * length
        padding = " " * col_start
        
        lines.append(f"{p['name']:<15} |{padding}{graphic:<{width}}| ({start}-{end})")
        
    # Anchors
    anchor_line = [" "] * width
    def mark(bar, char):
        idx = int((bar - min_bar) * ratio)
        if 0 <= idx < width:
            anchor_line[idx] = char
            
    mark(entry, "E")
    mark(invalidation, "X")
    
    lines.append(f"{'Anchors':<15} |{''.join(anchor_line)}| (E={entry}, X={invalidation})")
    
    return "\n".join(lines)

def render_story_html(bundle: Dict) -> str:
    """Renders the full story HTML view."""
    
    story = bundle.get("story", {})
    phases = story.get("phases", [])
    anchors = story.get("anchors", {})
    tags = story.get("tags", [])
    signatures = story.get("signatures", {})
    
    entry = anchors.get("entry_bar", 0)
    inv = anchors.get("invalidation_bar", 0)
    
    timeline_ascii = render_timeline(phases, entry, inv)
    
    # Signature Check
    sig_html = ""
    if signatures:
        from tezaver.matrix.core.story_signatures import check_signatures
        errors = check_signatures(signatures)
        status = "<span style='color:red'>FAIL</span>" if errors else "<span style='color:green'>PASS</span>"
        
        details = ""
        if errors:
            details = "<ul>" + "".join([f"<li>{e}</li>" for e in errors]) + "</ul>"
        else:
            details = "All metrics within bounds."
            
        sig_html = f"""
        <div style="border:1px solid #ccc; padding:10px; margin-top:10px;">
            <h3>Signatures: {status}</h3>
            {details}
            <pre>{str(signatures)}</pre>
        </div>
        """
    
    html = f"""
    <div class="story-container">
        <h2>Story: {bundle.get('symbol')} ({bundle.get('timeframe')})</h2>
        <div class="meta">
            Build: {bundle.get('build_ts')} | Version: {bundle.get('bundle_version')}
        </div>
        
        <div class="tags">
            Tags: {', '.join(tags)}
        </div>
        
        <div class="timeline-box" style="background:#f0f0f0; padding:10px; font-family:monospace; white-space:pre;">
{timeline_ascii}
        </div>
        
        {sig_html}
    </div>
    """
    return html
