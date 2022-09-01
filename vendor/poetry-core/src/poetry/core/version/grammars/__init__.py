from __future__ import annotations

import sys

from pathlib import Path


if getattr(sys, "oxidized", False):
    GRAMMAR_DIR = (
        Path(__path__[0]).parents[4] / "assets" / "core" / "version" / "grammars"
    )
else:
    GRAMMAR_DIR = Path(__path__[0])

GRAMMAR_PEP_508_CONSTRAINTS = GRAMMAR_DIR / "pep508.lark"

GRAMMAR_PEP_508_MARKERS = GRAMMAR_DIR / "markers.lark"
