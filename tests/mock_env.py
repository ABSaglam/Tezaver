
import sys
from unittest.mock import MagicMock

# Mock dotenv
sys.modules["dotenv"] = MagicMock()

# Also mock other potential nuisances if needed
