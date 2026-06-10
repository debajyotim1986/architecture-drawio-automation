"""Inject `src/` onto sys.path so pytest can find the package even when
the editable install's `.pth` file is being ignored by site.py (a known
issue with hatchling-style editable installs on Python 3.13, which
skips `.pth` files whose name starts with an underscore).

Keeps the test suite working on any Python ≥ 3.10."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).parent / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
