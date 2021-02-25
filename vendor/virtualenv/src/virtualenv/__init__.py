from __future__ import absolute_import, unicode_literals

from pathlib import Path

__path_pack__ = Path(__path__[0])
__path_assets__ = __path_pack__.parents[2] / "assets" / "virtualenv"

from .run import cli_run, session_via_cli
from .version import __version__

__all__ = (
    "__version__",
    "cli_run",
    "session_via_cli",
)
