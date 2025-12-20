import argparse
import sys
import os
import json
from tezaver.matrix.core.story_compiler import compile_story
from tezaver.matrix.ports.candidate_bundle import bundle_from_dict, bundle_to_dict, candidate_id, validate_bundle_dict

def main():
    parser = argparse.ArgumentParser(description="Matrix Story Compiler (MX-6003)")
    parser.add_argument("--candidate-id", help="Candidate ID to compile")
    parser.add_argument("--path", help="Direct path to candidate json")
    parser.add_argument("--target", required=True, choices=["1h", "4h", "both"], help="Target Timeframe")
    parser.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"), help="Matrix Home")
    
    args = parser.parse_args()
    
    # Locate file
    path = args.path
    if not path and args.candidate_id:
        path = os.path.join(args.home, "candidates", f"{args.candidate_id}.json")
        
    if not path or not os.path.exists(path):
        print(f"Error: Candidate file not found: {path}")
        sys.exit(2)
        
    try:
        with open(path, "r") as f:
            source = json.load(f)
            
        targets = []
        if args.target == "both":
            targets = ["1h", "4h"]
        else:
            targets = [args.target]
            
        compiled_ids = []
        
        for tf in targets:
            compiled = compile_story(source, tf)
            
            # Validate
            errs = validate_bundle_dict(compiled)
            if errs:
                print(f"Validation failed for {tf}: {errs}")
                sys.exit(2)
                
            # Compute ID
            # Convert to obj to use candidate_id helper
            bun_obj = bundle_from_dict(compiled)
            new_id = candidate_id(bun_obj)
            
            # Save
            out_path = os.path.join(args.home, "candidates", f"{new_id}.json")
            with open(out_path, "w") as f:
                json.dump(compiled, f, indent=2)
                
            compiled_ids.append(new_id)
            print(f"Compiled {tf}: {new_id}")
            
    except Exception as e:
        print(f"Error compiling: {e}")
        sys.exit(2)
        
if __name__ == "__main__":
    main()
