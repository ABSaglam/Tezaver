import sys
from pathlib import Path

# Add src to sys.path
project_root = Path(__file__).resolve().parent.parent.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from tezaver.wisdom.global_wisdom import build_global_pattern_wisdom
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main():
    logger.info("Building global wisdom from coin_profiles...")
    build_global_pattern_wisdom()
    logger.info("Global wisdom build completed.")

if __name__ == "__main__":
    main()
