"""Puts the scripts of scripts/ on the import path, for the tests of this folder: `import _paths` comes first."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for folder in (ROOT / "scripts", ROOT / "scripts" / "screenshots"):
    sys.path.insert(0, str(folder))
