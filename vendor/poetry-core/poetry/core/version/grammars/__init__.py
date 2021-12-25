import sys

from pathlib import Path


if getattr(sys, "oxidized", False):
    parents = 4 if sys.platform.startswith("win") else 5
    __path_assets__ = (
        Path(__path__[0]).parents[parents] / "assets" / "core" / "version" / "grammars"
    )
else:
    __path_assets__ = Path(__path__[0])
