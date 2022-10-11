from __future__ import annotations

import sys

from pathlib import Path


# this cannot presently be replaced with importlib.metadata.version as when building
# itself, poetry-core is not available as an installed distribution.
__version__ = "1.3.2"
