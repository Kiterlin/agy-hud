#!/usr/bin/env python3
"""Zero-dependency launcher for agy-hud (works directly from a cloned or installed plugin directory)."""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_hud.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
