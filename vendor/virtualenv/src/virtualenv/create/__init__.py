from pathlib import Path

from virtualenv import __path_assets__

_PATH_ASSETS = (
    __path_assets__ / "create" if __path_assets__ else
    Path(__path__[0])
)
