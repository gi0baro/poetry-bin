from __future__ import absolute_import, unicode_literals

import sys

from pathlib import Path

__path_pack__ = Path(__path__[0])
if getattr(sys, "oxidized", False):
    parents = 1 if sys.platform.startswith("win") else 2
    __path_assets__ = __path_pack__.parents[parents] / "assets" / "virtualenv"
else:
    __path_assets__ = None

from . import __patches__

from .run import cli_run, session_via_cli
from .version import __version__

__all__ = (
    "__version__",
    "cli_run",
    "session_via_cli",
)
