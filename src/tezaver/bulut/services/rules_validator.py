import re
import json

class RulesValidator:
    """Validator for Bulut rules and configuration files."""
    
    @staticmethod
    def validate_allowlist(text: str) -> dict:
        errors = []
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
        
        if not lines:
            # Mainnet often requires at least one, but generic validator might just warn
            # Let's say if empty result = valid but empty.
            pass
            
        symbol_pattern = re.compile(r"^[A-Z0-9]{2,25}$")
        
        for i, line in enumerate(lines):
            # Format: SYMBOL or SYMBOL # comment
            parts = line.split("#")
            sym = parts[0].strip()
            if not sym: continue
            
            if not symbol_pattern.match(sym):
                errors.append(f"Invalid symbol format: '{sym}'")
                
        return {"ok": len(errors) == 0, "errors": errors}

    @staticmethod
    def validate_symbol_groups(data: dict) -> dict:
        errors = []
        if not isinstance(data, dict):
            return {"ok": False, "errors": ["Must be a JSON object"]}
            
        for k, v in data.items():
            if not isinstance(k, str) or not k:
                errors.append(f"Invalid key: {k}")
            if not isinstance(v, str) or not v:
                errors.append(f"Invalid group for {k}: {v}")
                
        return {"ok": len(errors) == 0, "errors": errors}

    @staticmethod
    def validate_group_caps(data: dict) -> dict:
        errors = []
        if not isinstance(data, dict):
             return {"ok": False, "errors": ["Must be a JSON object"]}
             
        for k, v in data.items():
            if not isinstance(v, int) or v < 0:
                # v could be -1 for unlimited? Assuming >=0 for caps usually.
                errors.append(f"Invalid cap for {k}: {v}")
                
        return {"ok": len(errors) == 0, "errors": errors}

    @staticmethod
    def validate_exit_profile(data: dict) -> dict:
        errors = []
        if not isinstance(data, dict):
             return {"ok": False, "errors": ["Must be a JSON object"]}
             
        if data.get("schema") != "exit_profile_v1":
             errors.append("Invalid or missing schema version (expected exit_profile_v1)")
             
        # Basic structural check
        if "profile_id" not in data: errors.append("Missing profile_id")
        
        rules = data.get("rules", [])
        if not isinstance(rules, list):
            errors.append("Rules must be a list")
            
        return {"ok": len(errors) == 0, "errors": errors}
