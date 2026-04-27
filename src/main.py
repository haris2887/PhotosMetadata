from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from gui.app import main

if __name__ == "__main__":
    sys.exit(main())
