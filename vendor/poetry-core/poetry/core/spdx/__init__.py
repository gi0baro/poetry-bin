from pathlib import Path

from .. import __path_assets__

_ASSETS_PATH = (
    __path_assets__ / "spdx" if __path_assets__ else
    Path(__path__[0]) / "data"
)
