from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, Optional
from tezaver.bulut.core.context import get_context

router = APIRouter()

def check_write_permission(ctx):
    """Check if rules editing is allowed."""
    if not ctx.config.rules_edit_enabled:
        raise HTTPException(status_code=403, detail="Rules editing disabled by config")
        
    # Mainnet Arm Block
    if ctx.config.mode == "REAL_MAINNET" and ctx.config.rules_edit_block_on_mainnet_armed:
        # Check armed status
        if hasattr(ctx, "execution_service") and ctx.execution_service.is_armed():
             raise HTTPException(status_code=409, detail="Editing BLOCKED: System is ARMED on MAINNET. Disarm to edit rules.")

@router.get("/list")
async def list_rules():
    ctx = get_context()
    return ctx.rules_registry.list_rules()

@router.get("/get")
async def get_rule(key: str):
    ctx = get_context()
    try:
        content = ctx.rules_registry.read_text(key)
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/validate")
async def validate_rule(key: str, body: Dict[str, Any] = Body(...)):
    ctx = get_context()
    validator = ctx.rules_registry.validator
    
    content = body.get("content") # String or dict depending on key
    if content is None:
        raise HTTPException(status_code=400, detail="Missing content")
        
    # Manual validation call based on key to reuse validator logic without writing
    res = {"ok": True}
    if key.endswith("allowlist"):
        res = validator.validate_allowlist(str(content))
    elif key == "symbol_groups":
        if isinstance(content, str):
            import json
            try: content = json.loads(content)
            except: return {"ok": False, "errors": ["Invalid JSON"]}
        res = validator.validate_symbol_groups(content)
    elif key == "group_caps":
        if isinstance(content, str):
            import json
            try: content = json.loads(content)
            except: return {"ok": False, "errors": ["Invalid JSON"]}
        res = validator.validate_group_caps(content)
        
    return res

@router.post("/apply")
async def apply_rule(key: str, body: Dict[str, Any] = Body(...)):
    ctx = get_context()
    check_write_permission(ctx)
    
    content = body.get("content")
    if content is None: raise HTTPException(status_code=400, detail="Missing content")
    
    try:
        if key in ["symbol_groups", "group_caps"]:
             if isinstance(content, str):
                import json
                content = json.loads(content)
             ctx.rules_registry.write_json(key, content)
        else:
             ctx.rules_registry.write_text(key, str(content))
             
        # Hot Reload Triggers
        if key == "group_caps" and hasattr(ctx, "group_caps_loader"):
             ctx.group_caps_loader.reload()
             
        ctx.telemetry.emit_system_event("RULES_APPLIED", {"key": key})
        return {"status": "ok", "message": f"Rule {key} applied."}
        
    except Exception as e:
        ctx.telemetry.emit_system_event("RULES_APPLY_ERROR", {"key": key, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/exit_profiles")
async def list_exit_profiles():
    ctx = get_context()
    return ctx.rules_registry.list_exit_profiles()

@router.get("/exit_profiles/get")
async def get_exit_profile(name: str):
    ctx = get_context()
    try:
        data = ctx.rules_registry.read_exit_profile(name)
        return data
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/exit_profiles/apply")
async def apply_exit_profile(name: str, body: Dict[str, Any] = Body(...)):
    ctx = get_context()
    check_write_permission(ctx)
    
    content = body.get("content")
    if content is None: raise HTTPException(status_code=400, detail="Missing content")
    
    if isinstance(content, str):
        import json
        try: content = json.loads(content)
        except: raise HTTPException(400, "Invalid JSON")
            
    try:
        ctx.rules_registry.write_exit_profile(name, content)
        
        # Reload profiles
        if hasattr(ctx, "exit_profile_loader"):
            ctx.exit_profile_loader.reload()
            
        ctx.telemetry.emit_system_event("RULES_PROFILE_APPLIED", {"name": name})
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
