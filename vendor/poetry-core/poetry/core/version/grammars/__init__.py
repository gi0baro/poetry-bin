from pathlib import Path

from ... import __path_assets__

GRAMMAR_DIR = (
    __path_assets__ / "version" / "grammars" if __path_assets__ else
    Path(__path__[0])
)

GRAMMAR_PEP_508_CONSTRAINTS = GRAMMAR_DIR / "pep508.lark"

GRAMMAR_PEP_508_MARKERS = GRAMMAR_DIR / "markers.lark"
