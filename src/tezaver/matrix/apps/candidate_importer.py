import argparse
import sys
import os
import json
from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore

def main():
    parser = argparse.ArgumentParser(description="Matrix Candidate Importer")
    parser.add_argument("--path", required=True, help="File or Directory to import")
    parser.add_argument("--home", help="Override TEZAVER_MATRIX_HOME")
    
    args = parser.parse_args()
    
    store = FileCandidateStore(home=args.home)
    
    imported_count = 0
    failures = []
    
    files_to_process = []
    
    if os.path.isfile(args.path):
        files_to_process.append(args.path)
    elif os.path.isdir(args.path):
        for root, _, files in os.walk(args.path):
            for f in files:
                if f.endswith(".json"):
                    files_to_process.append(os.path.join(root, f))
    else:
        print(f"Error: Path not found: {args.path}")
        sys.exit(2)
        
    print(f"Processing {len(files_to_process)} files...")
    
    for fpath in files_to_process:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            cid = store.save(data)
            imported_count += 1
            print(f"[OK] {os.path.basename(fpath)} -> {cid}")
        except Exception as e:
            failures.append(f"{os.path.basename(fpath)}: {str(e)}")
            print(f"[FAIL] {os.path.basename(fpath)}: {str(e)}")
            
    print("-" * 40)
    print(f"Imported: {imported_count}")
    print(f"Failed: {len(failures)}")
    
    if failures:
        sys.exit(2)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
