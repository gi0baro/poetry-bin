import sys

from pathlib import Path


__version__ = "1.1.0a5"

if getattr(sys, "oxidized", False):
    parents = 2 if sys.platform.startswith("win") else 3
    __path_assets__ = Path(__path__[0]).parents[parents] / "assets" / "core"
else:
    __path_assets__ = None
