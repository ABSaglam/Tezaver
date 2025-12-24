import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from tezaver.ony.auto_approver import OnyAutoApprover

if __name__ == "__main__":
    print("🚀 Starting ONY Auto-Approver...")
    approver = OnyAutoApprover(base_dir=Path("."))
    approver.scan_all_coins()
    print("✅ Done.")
