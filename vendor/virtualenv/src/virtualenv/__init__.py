from __future__ import annotations

import sys

from pathlib import Path

__path_pack__ = Path(__path__[0])
if getattr(sys, "oxidized", False):
    __path_assets__ = __path_pack__.parents[1] / "assets" / "virtualenv"
else:
    __path_assets__ = None

from . import __patches__

from .run import cli_run, session_via_cli
from .version import __version__

__all__ = [
    "__version__",
    "cli_run",
    "session_via_cli",
]
