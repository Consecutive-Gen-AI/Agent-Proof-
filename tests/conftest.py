"""Global test configuration and fixtures."""

import sys
from pathlib import Path

# Add src to sys.path
src_dir = Path(__file__).parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
